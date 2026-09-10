"""
Fix pour psycopg (mode async) sur Windows.

psycopg ne supporte pas le ProactorEventLoop, qui est la boucle
d'événements par défaut d'asyncio sur Windows. Il faut basculer sur un
SelectorEventLoop. À appeler tout en haut de chaque point d'entrée
(scripts, app/main.py) AVANT toute création de event loop — sinon le
changement de policy n'a aucun effet.

Limite connue du SelectorEventLoop sur Windows : pas de support des
sous-processus asyncio. On ne lance aucun sous-processus dans cette
app, donc pas d'impact pour MaliAgent.
"""

import asyncio
import sys


def use_selector_event_loop_on_windows() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
