#!/usr/bin/env bash
# stop_screens.sh — Opreste toate instantele screen active
# Piete: RO, UK, UK_B2B (CZ eliminat complet din sistem)

echo ""
echo "Opresc instante Hybrid King..."

for session in hk_cz hk_ro hk_uk hk_uk_b2b; do
    if screen -list 2>/dev/null | grep -q "$session"; then
        screen -S "$session" -X quit
        echo "  ✅  Oprit: $session"
    else
        echo "  –   Nu ruleaza: $session"
    fi
done

echo ""
echo "  Toate sesiunile oprite."
echo "  Lead-urile deja gasite sunt in:"
echo "    outreach_ro.csv"
echo "    outreach_uk.csv"
echo "    outreach_uk_b2b.csv"
echo ""
