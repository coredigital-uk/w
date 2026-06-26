#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
#  start_screens.sh — Porneste toate instantele active in screen
#
#  Apeleaza o singura data pe server. Ruleaza nonstop in fundal.
#  Piete: RO (olx.ro) | UK (gumtree.com) | UK_B2B (companies house)
#  Cehia a fost eliminata complet din sistem.
#
#  Comenzi utile (din Termux sau SSH):
#    screen -r hk_ro      → ataseaza la instanta Romania
#    screen -r hk_uk      → ataseaza la instanta UK (consumer)
#    screen -r hk_uk_b2b  → ataseaza la instanta UK B2B
#    Ctrl+A, D            → detaseaza (lasa sa ruleze)
#    screen -ls           → lista sesiuni active
#    ./stop_screens.sh    → opreste tot
# ══════════════════════════════════════════════════════════════
set -e

PROJ="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJ/venv/bin/activate"

# Verifica ca venv exista
if [ ! -f "$VENV" ]; then
    echo "❌  venv nu exista! Ruleaza mai intai: ./setup.sh"
    exit 1
fi

# Verifica ca .env exista
if [ ! -f "$PROJ/.env" ]; then
    echo "❌  .env nu exista! Copiaza .env.example si completeaza."
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║        HYBRID KING — Pornesc instantele active       ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Opreste sesiuni vechi daca exista (inclusiv numele legacy) ──
for session in hk_cz hk_ro hk_uk hk_uk_b2b; do
    if screen -list | grep -q "$session"; then
        echo "  → Opresc sesiune veche: $session"
        screen -S "$session" -X quit 2>/dev/null || true
        sleep 1
    fi
done

# ── Creeaza directoare ────────────────────────────────────
mkdir -p "$PROJ/logs" "$PROJ/sites"

# ── Porneste instanta ROMANIA (olx.ro) ────────────────────
echo "  → Pornesc hk_ro (Romania — olx.ro)..."
screen -dmS hk_ro bash -c "
    cd '$PROJ'
    source '$VENV'
    echo ''
    echo '  [RO] Hybrid King Romania pornit la: \$(date)'
    echo ''
    python main.py --market ro 2>&1 | tee -a logs/hybridking_ro.log
    echo ''
    echo '  [RO] INSTANTA OPRITA. Apasa Enter pentru a iesi.'
    read
"
sleep 2

# ── Porneste instanta UK consumer (gumtree.com) ───────────
echo "  → Pornesc hk_uk (UK — gumtree.com)..."
screen -dmS hk_uk bash -c "
    cd '$PROJ'
    source '$VENV'
    echo ''
    echo '  [UK] Hybrid King UK pornit la: \$(date)'
    echo ''
    python main.py --market uk 2>&1 | tee -a logs/hybridking_uk.log
    echo ''
    echo '  [UK] INSTANTA OPRITA. Apasa Enter pentru a iesi.'
    read
"
sleep 2

# ── Porneste instanta UK B2B (companies house) ────────────
# NOTA: necesita COMPANIES_HOUSE_API_KEY in .env, altfel se opreste
# imediat cu eroare clara in log (nu crapa silentios).
echo "  → Pornesc hk_uk_b2b (UK B2B — companies house)..."
screen -dmS hk_uk_b2b bash -c "
    cd '$PROJ'
    source '$VENV'
    echo ''
    echo '  [UK_B2B] Hybrid King UK B2B pornit la: \$(date)'
    echo ''
    python main.py --market uk_b2b 2>&1 | tee -a logs/hybridking_uk_b2b.log
    echo ''
    echo '  [UK_B2B] INSTANTA OPRITA. Apasa Enter pentru a iesi.'
    read
"
sleep 2

# ── Verifica ca au pornit ─────────────────────────────────
echo ""
echo "  Sesiuni active:"
screen -ls | grep -E "hk_(ro|uk|uk_b2b)" | sed 's/^/  /' || echo "  (nicio sesiune gasita)"

echo ""
echo "══════════════════════════════════════════════════════"
echo "  Toate instantele ruleaza in fundal."
echo ""
echo "  Ataseaza-te din Termux / SSH:"
echo "    screen -r hk_ro      → Romania (olx.ro)"
echo "    screen -r hk_uk      → UK consumer (gumtree.com)"
echo "    screen -r hk_uk_b2b  → UK B2B (companies house)"
echo "    Ctrl+A, D            → detaseaza"
echo ""
echo "  Verifica lead-urile gata:"
echo "    python status.py"
echo ""
echo "  CSV-uri cu mesajele:"
echo "    $PROJ/outreach_ro.csv"
echo "    $PROJ/outreach_uk.csv"
echo "    $PROJ/outreach_uk_b2b.csv  (drafturi email B2B)"
echo "══════════════════════════════════════════════════════"
echo ""
