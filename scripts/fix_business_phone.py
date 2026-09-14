"""
Corrige les numéros WhatsApp déjà en base pour qu'ils soient stockés sous
forme normalisée (chiffres uniquement), cohérente avec le format envoyé
par Meta dans `display_phone_number` du payload webhook.

Contexte : le Business de démo avait été créé avec
"1 (555) 664-0413" (espaces/parenthèses/tiret), alors que Meta envoie
"15556640413" (chiffres seuls) — le lookup par égalité exacte échouait
donc silencieusement, et aucune réponse n'était jamais renvoyée sur
WhatsApp. Voir app/business/lookup.py::normalize_phone_number.

À lancer une seule fois après avoir mis à jour app/business/lookup.py.

Usage : python scripts/fix_business_phone.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.business.lookup import normalize_phone_number  # noqa: E402
from app.core.asyncio_compat import use_selector_event_loop_on_windows  # noqa: E402
from app.db.session import async_session  # noqa: E402
from app.models import Business  # noqa: E402

use_selector_event_loop_on_windows()


async def main():
    async with async_session() as session:
        result = await session.execute(select(Business))
        businesses = result.scalars().all()

        if not businesses:
            print("Aucun business en base.")
            return

        changed = 0
        for b in businesses:
            normalized = normalize_phone_number(b.whatsapp_phone_number)
            if normalized != b.whatsapp_phone_number:
                print(f"{b.name}: {b.whatsapp_phone_number!r} -> {normalized!r}")
                b.whatsapp_phone_number = normalized
                changed += 1
            else:
                print(f"{b.name}: déjà normalisé ({b.whatsapp_phone_number!r})")

        await session.commit()
        print(f"\n{changed} business(es) corrigé(s) sur {len(businesses)}.")


if __name__ == "__main__":
    asyncio.run(main())
