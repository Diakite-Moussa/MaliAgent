"""
Configuration centralisée du système de logging pour MaliAgent.
Remplace les print() par des logs structurés (DEBUG, INFO, WARNING, ERROR).
"""

import logging
import sys

from app.core.config import settings


def setup_logging():
    """Initialise le formateur et les handlers de logs."""
    log_level = logging.DEBUG if settings.env.lower() in ("dev", "test") else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(log_level)

    root_logger = logging.getLogger("maliagent")
    root_logger.setLevel(log_level)
    # Éviter les handlers en double si appelé plusieurs fois
    if not root_logger.handlers:
        root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Retourne un logger nommé préfixé par maliagent."""
    return logging.getLogger(f"maliagent.{name}")
