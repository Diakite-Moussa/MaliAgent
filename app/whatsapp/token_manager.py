"""
Gestionnaire et diagnostic du jeton d'accès WhatsApp Meta (Sprint 8).
Permet :
1. De diagnostiquer l'état d'un jeton (validité, expiration, scopes) via /debug_token.
2. D'échanger un jeton court terme (24h) contre un jeton longue durée (60 jours).
3. De fournir des alertes préventives avant expiration pour le monitoring et la santé de l'API.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("maliagent.whatsapp.token")


async def inspect_token(
    input_token: str | None = None,
    auth_token: str | None = None,
) -> dict[str, Any]:
    """
    Interroge l'endpoint Meta /debug_token pour vérifier la validité et la date d'expiration d'un jeton.
    """
    token_to_check = input_token or settings.whatsapp_access_token
    if not token_to_check:
        return {
            "is_valid": False,
            "status": "missing",
            "message": "Aucun jeton WhatsApp configuré (WHATSAPP_ACCESS_TOKEN vide)",
        }

    # Pour interroger debug_token, on utilise le token lui-même ou le token applicatif
    bearer = auth_token or token_to_check
    url = "https://graph.facebook.com/debug_token"
    params = {"input_token": token_to_check}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers={"Authorization": f"Bearer {bearer}"})
            if resp.status_code != 200:
                return {
                    "is_valid": False,
                    "status": "invalid_or_expired",
                    "http_status": resp.status_code,
                    "message": f"Échec de validation Meta ({resp.status_code}): {resp.text}",
                }

            data = resp.json().get("data", {})
            is_valid = bool(data.get("is_valid", False))
            expires_at_ts = data.get("expires_at", 0)

            days_remaining = None
            expires_at_iso = None
            if expires_at_ts and expires_at_ts > 0:
                dt_exp = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc)
                expires_at_iso = dt_exp.isoformat()
                diff = dt_exp - datetime.now(timezone.utc)
                days_remaining = max(0, diff.days)

            status = "valid"
            if not is_valid:
                status = "invalid"
            elif days_remaining is not None and days_remaining <= 7:
                status = "expiring_soon"

            return {
                "is_valid": is_valid,
                "status": status,
                "app_id": data.get("app_id"),
                "type": data.get("type", "UNKNOWN"),
                "scopes": data.get("scopes", []),
                "expires_at": expires_at_iso,
                "days_remaining": days_remaining,
                "is_never_expiring": expires_at_ts == 0,
                "message": "Jeton valide (permanent ou longue durée)" if expires_at_ts == 0 else f"Valide, expire dans {days_remaining} jours",
            }
    except Exception as exc:
        logger.warning(f"Impossible d'inspecter le token WhatsApp: {exc}")
        return {
            "is_valid": False,
            "status": "network_error",
            "message": f"Erreur réseau lors de la vérification du token: {exc}",
        }


async def exchange_for_long_lived_token(
    short_lived_token: str,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    """
    Échange un jeton utilisateur temporaire (24h) contre un jeton longue durée (60 jours).
    """
    url = "https://graph.facebook.com/v21.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "fb_exchange_token": short_lived_token,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data.get("access_token"),
            "token_type": data.get("token_type", "bearer"),
            "expires_in_seconds": data.get("expires_in"),
            "expires_in_days": round(data.get("expires_in", 0) / 86400, 1),
        }


def get_token_quick_status() -> dict[str, Any]:
    """
    Diagnostic rapide sans appel réseau externe (vérification locale de présence et format).
    """
    tok = settings.whatsapp_access_token.strip()
    configured = bool(tok and len(tok) > 15)
    return {
        "configured": configured,
        "phone_number_id_configured": bool(settings.whatsapp_phone_number_id.strip()),
        "token_prefix": tok[:8] + "..." if configured else None,
    }
