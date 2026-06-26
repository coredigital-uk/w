"""
email_composer.py — Compune email B2B personalizat (NU trimite automat)
==========================================================================
Genereaza email-uri B2B personalizate pentru lead-urile UK Companies House
care au:
  - email gasit (prin email_extractor)
  - site web deja generat si deployed (prin orchestrator)

FILOSOFIA DE BAZA: la fel ca WhatsApp-ul tau RO. Tu trimiti manual,
sistemul iti pregateste drafturile. Nu iei ban de pe domain-ul tau de
email pentru ca tu controlezi volumul si poti customiza fiecare draft
inainte de trimitere.

Output:
  - Fisier CSV: outreach_uk_b2b.csv cu: company | email | subject | body | site_demo
  - Pentru fiecare lead, draft incepe cu un detaliu UNIC (nume firma, 
    locatie, SIC) — NU template identic copy-paste.

Daca configurezi SMTP in .env, comanda `python email_composer.py --send`
trimite efectiv. La inceput RECOMANDAT modul "draft only" (default).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import random
import re
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import aiosmtplib
from sqlalchemy import select

from config import settings
from database import AsyncSessionLocal, Job, JobStatus, init_db

logger = logging.getLogger(__name__)

_DRAFTS_CSV = Path("outreach_uk_b2b.csv")

# Variante de SUBJECT - randomizate per email ca sa nu para mass-template
_SUBJECT_VARIANTS = [
    "Quick website concept for {name}",
    "Made a site preview for {name}",
    "{name} — small idea worth a look",
    "Free website mockup for {name}",
    "Built a demo for {name} this morning",
]


def _industry_label(sic_or_niche: str) -> str:
    """Construction (SIC 41202) -> 'residential construction'"""
    if "41201" in sic_or_niche:
        return "commercial construction"
    if "41202" in sic_or_niche:
        return "residential construction"
    if "41100" in sic_or_niche:
        return "building development"
    if "43210" in sic_or_niche:
        return "electrical installation"
    if "43220" in sic_or_niche:
        return "plumbing and heating"
    if "43320" in sic_or_niche:
        return "joinery"
    return "construction"


def _compose_email(job: Job) -> tuple[str, str]:
    """
    Returneaza (subject, body) personalizat. Adaptat pe limba
    (Romanian -> RO text, English -> UK text) si pe is_b2b
    (B2B foloseste pitch industrie, consumer foloseste pitch direct).
    """
    name = job.business_name
    demo_url = job.vercel_url or "(demo se genereaza dupa contact)"

    # Extrage oras
    city = ""
    desc = job.description or ""
    for c in ["London", "Manchester", "Birmingham", "Glasgow", "Leeds",
              "Liverpool", "Bristol", "Edinburgh", "Cardiff", "Belfast",
              "Bucuresti", "Cluj-Napoca", "Timisoara", "Iasi", "Constanta",
              "Craiova", "Brasov", "Galati", "Ploiesti", "Oradea"]:
        if c in desc:
            city = c
            break

    if job.language == "Romanian":
        subject_variants = [
            f"Site demo pentru {name}",
            f"Am facut o schita de site pentru {name}",
            f"{name} — o idee rapida",
            f"Demo gratuit pentru {name}",
        ]
        subject = random.choice(subject_variants)
        location_part = f" din {city}" if city else ""
        body = f"""Buna,

Am observat anuntul dvs si am pregatit o schita de website pe care cred ca o veti gasi interesanta:

{demo_url}

E un demo gratuit, fara obligatii. Site complet, optimizat pentru mobil, gata de folosit.

Daca va intereseaza, raspundeti la acest email sau scrieti-mi pe WhatsApp.

Cu respect,
{settings.smtp_from_name or 'Agentie Web'}

---
P.S. Daca nu va intereseaza, raspundeti cu "nu, multumesc" si nu va mai contactez.
"""
    else:
        industry = _industry_label(job.niche or "")
        subject_variants = [
            "Quick website concept for {name}",
            "Made a site preview for {name}",
            "{name} — small idea worth a look",
            "Free website mockup for {name}",
        ]
        subject = random.choice(subject_variants).format(name=name)
        location_part = f" based in {city}" if city else ""
        body = f"""Hi,

I noticed {name}{location_part} working in {industry} and put together a quick website concept that I thought you might find interesting:

{demo_url}

It's a free demo - no obligation. Built to help convert visitors into enquiries.

If it's something you'd like to discuss, just reply to this email.

Best regards,
{settings.smtp_from_name or 'Web Agency'}

---
P.S. If you'd prefer not to hear from me, just reply with "no thanks" and I won't contact you again.
"""
    return subject, body


def _write_draft_csv(jobs: list[Job]) -> None:
    """Salveaza drafturi intr-un CSV pentru tine sa le revizuiesti
    si sa le trimiti manual din clientul tau de email."""
    write_header = not _DRAFTS_CSV.exists()

    with open(_DRAFTS_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "timestamp", "job_id", "company_name", "email",
                "demo_url", "subject", "body",
            ])

        for job in jobs:
            subject, body = _compose_email(job)
            writer.writerow([
                datetime.now().isoformat(),
                job.id,
                job.business_name,
                job.email or "",
                job.vercel_url or "",
                subject,
                body,
            ])


async def _send_email_smtp(to_email: str, subject: str, body: str) -> bool:
    """Trimite email prin SMTP configurat in .env. Returneaza True daca succes."""
    if not settings.smtp_host or not settings.smtp_from_email:
        logger.error("SMTP neconfigurat — nu pot trimite")
        return False

    msg = EmailMessage()
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
            timeout=30,
        )
        return True
    except Exception as exc:
        logger.error("SMTP eroare pentru %s: %s", to_email, exc)
        return False


async def compose_email_drafts(send: bool = False, limit: int = 20, only_b2b: bool = False) -> None:
    """
    Compune drafturi pentru job-uri (RO/UK/B2B) care:
    - au email completat
    - au vercel_url (site demo deja deployed)
    - status DEPLOYED si NU SENT inca

    Daca send=True si SMTP e configurat, trimite efectiv si marcheaza SENT.
    Daca send=False (default), doar salveaza CSV cu drafturi.

    SIGURANTA: max 20/rulare, 60s intre emailuri. La trimitere automata,
    NU ridica limita fara sa testezi mai intai manual 20-30 trimiteri
    cu rata buna de raspuns — un domeniu de email nou care trimite
    brusc 200 emailuri/zi e marcat spam de Gmail/Outlook in cateva ore.
    """
    await init_db()

    query = select(Job).where(
        Job.email.isnot(None),
        Job.vercel_url.isnot(None),
        Job.status == JobStatus.DEPLOYED,
    )
    if only_b2b:
        query = query.where(Job.is_b2b.is_(True))
    query = query.limit(limit)

    async with AsyncSessionLocal() as session:
        result = await session.execute(query)
        jobs = list(result.scalars().all())

    if not jobs:
        logger.info("Niciun job pregatit (cu email + site demo).")
        return

    logger.info("Email drafts: %d job-uri pregatite (only_b2b=%s)", len(jobs), only_b2b)

    if send and settings.smtp_host:
        sent_ok = 0
        for job in jobs:
            subject, body = _compose_email(job)
            ok = await _send_email_smtp(job.email, subject, body)
            if ok:
                sent_ok += 1
                async with AsyncSessionLocal() as session:
                    db_job = await session.get(Job, job.id)
                    if db_job:
                        db_job.status = JobStatus.SENT
                        await session.commit()
                logger.info("EMAIL SENT: %s -> %s", job.business_name[:40], job.email)
            # 60s intre emailuri — siguranta reputatie domeniu
            await asyncio.sleep(60)

        logger.info("DONE. Sent %d/%d", sent_ok, len(jobs))
    else:
        _write_draft_csv(jobs)
        logger.info(
            "DONE. %d drafturi salvate in %s. Trimite manual.",
            len(jobs), _DRAFTS_CSV.resolve(),
        )


# Backward-compat alias
compose_b2b_drafts = compose_email_drafts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true",
                        help="Trimite efectiv via SMTP (default: doar drafturi)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--only-b2b", action="store_true",
                        help="Doar lead-uri B2B Companies House (exclude RO/UK consumer)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    asyncio.run(compose_email_drafts(send=args.send, limit=args.limit, only_b2b=args.only_b2b))


if __name__ == "__main__":
    main()
