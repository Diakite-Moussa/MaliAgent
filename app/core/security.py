"""
Utilitaires de sécurité : hachage des mots de passe (bcrypt) et
jetons JWT (section 18.1 du cahier des charges).
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


# Matrice de permissions RBAC (Section 4 du cahier des charges)
PLATFORM_PERMISSIONS: set[str] = {
    "platform:read",
    "platform:manage_business",
    "platform:manage_users",
    "platform:manage_subscriptions",
    "platform:manage_payments",
    "platform:manage_ai",
    "platform:manage_social_channels",
    "platform:impersonate",
    "platform:system",
    "platform:audit",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": PLATFORM_PERMISSIONS,
    "admin": {
        "store:read",
        "store:write",
        "store:manage_users",
        "store:manage_products",
        "store:manage_orders",
        "store:manage_delivery",
    },
    "vendeur": {"store:read", "store:manage_products", "store:manage_orders", "store:manage_delivery"},
    "operateur": {"store:read", "store:manage_orders", "store:chat"},
    "livreur": {"driver:read", "driver:update_status", "driver:location"},
}


def get_permissions_for_role(role: str) -> set[str]:
    """Retourne l'ensemble des permissions associées à un rôle."""
    return set(ROLE_PERMISSIONS.get(role, set()))


def create_access_token(
    user_id: str,
    business_id: str | None = None,
    expires_delta: timedelta | None = None,
    impersonation: bool = False,
    acting_as_business: str | None = None,
    role: str | None = None,
    permissions: list[str] | None = None,
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)

    payload = {
        "sub": str(user_id),
        "exp": expire,
    }
    if business_id:
        payload["business_id"] = str(business_id)
    if role:
        payload["role"] = str(role)
    if impersonation:
        payload["impersonation"] = True
        payload["acting_as_business"] = str(acting_as_business or business_id)
    if permissions:
        payload["permissions"] = list(permissions)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Lève jwt.PyJWTError (ou une sous-classe) si le token est invalide/expiré."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
