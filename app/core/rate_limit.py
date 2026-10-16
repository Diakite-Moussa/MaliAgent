"""
Rate limiter applicatif en mémoire pour l'authentification.
Protège contre les attaques par force brute (brute-force) sur /api/auth/login,
indépendamment de la configuration du reverse-proxy (Nginx).
"""

from collections import defaultdict
import logging
import time
from fastapi import HTTPException, Request

from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthRateLimiter:
    """
    Limiteur de débit basé sur une fenêtre glissante (sliding window) en mémoire.
    Suit les tentatives par adresse IP et/ou combinaison (IP, email).
    """

    def __init__(
        self,
        max_attempts: int | None = None,
        window_seconds: int | None = None,
    ):
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        # Clé -> liste de timestamps float
        self._attempts: dict[str, list[float]] = defaultdict(list)

    @property
    def max_attempts(self) -> int:
        return self._max_attempts or settings.auth_rate_limit_max_attempts

    @property
    def window_seconds(self) -> int:
        return self._window_seconds or settings.auth_rate_limit_window_seconds

    def _get_client_ip(self, request: Request) -> str:
        """
        Extrait l'adresse IP du client de façon sécurisée.
        Prend en compte X-Forwarded-For si disponible.
        """
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Le premier IP de la liste est l'adresse originale du client
            return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    def _build_key(self, request: Request, identifier: str | None = None) -> str:
        ip = self._get_client_ip(request)
        if identifier:
            return f"{ip}:{identifier.strip().lower()}"
        return ip

    def _cleanup_old_attempts(self, key: str, now: float) -> None:
        window_start = now - self.window_seconds
        self._attempts[key] = [t for t in self._attempts[key] if t > window_start]
        if not self._attempts[key]:
            self._attempts.pop(key, None)

    def check(self, request: Request, identifier: str | None = None) -> None:
        """
        Vérifie si la requête dépasse le quota de tentatives autorisées.
        Lève HTTPException 429 si la limite est atteinte.
        """
        now = time.time()
        # On vérifie à la fois au niveau de l'IP et au niveau (IP + email)
        ip_key = self._get_client_ip(request)
        keys_to_check = [ip_key]
        if identifier:
            keys_to_check.append(self._build_key(request, identifier))

        for key in keys_to_check:
            self._cleanup_old_attempts(key, now)
            attempts = self._attempts.get(key, [])
            if len(attempts) >= self.max_attempts:
                oldest_in_window = attempts[0]
                retry_after = max(1, int(oldest_in_window + self.window_seconds - now) + 1)
                logger.warning(
                    "Rate limit dépassé pour la clé %s: %d tentatives enregistrées",
                    key,
                    len(attempts),
                )
                raise HTTPException(
                    status_code=429,
                    detail="Trop de tentatives de connexion. Veuillez réessayer dans quelques instants.",
                    headers={"Retry-After": str(retry_after)},
                )

    def record_failure(self, request: Request, identifier: str | None = None) -> None:
        """Enregistre un échec d'authentification."""
        now = time.time()
        ip_key = self._get_client_ip(request)
        self._cleanup_old_attempts(ip_key, now)
        self._attempts[ip_key].append(now)

        if identifier:
            full_key = self._build_key(request, identifier)
            self._cleanup_old_attempts(full_key, now)
            self._attempts[full_key].append(now)

    def record_success(self, request: Request, identifier: str | None = None) -> None:
        """Réinitialise les échecs pour l'IP / utilisateur après une authentification réussie."""
        ip_key = self._get_client_ip(request)
        self._attempts.pop(ip_key, None)
        if identifier:
            full_key = self._build_key(request, identifier)
            self._attempts.pop(full_key, None)

    def reset(self) -> None:
        """Réinitialise complètement l'état du limiteur (utile pour les tests de non-régression)."""
        self._attempts.clear()


auth_rate_limiter = AuthRateLimiter()
