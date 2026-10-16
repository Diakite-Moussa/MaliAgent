"""
Dépendances FastAPI pour protéger les endpoints du dashboard commerçant.

Le business_id ne doit JAMAIS venir d'un paramètre de requête modifiable
par le client — il doit toujours être extrait du JWT vérifié, pour
garantir l'isolation multi-tenant (section 18.3 du cahier des charges).
"""

import uuid

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.security import decode_access_token, get_permissions_for_role
from app.db.session import async_session
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def _extract_token_from_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    """
    Extrait le token JWT selon l'architecture d'authentification hybride :
    1. Header Authorization: Bearer (prioritaire) :
       - Requis pour l'impersonation Super Admin (token temporaire de boutique sans écraser le cookie admin).
       - Utilisé pour les clients API tiers, scripts d'automatisation, tests d'intégration (pytest),
         et applications mobiles livreurs.
    2. Cookie HttpOnly 'access_token' (défaut navigateur) :
       - Utilisé par le Dashboard SPA Angular pour protéger les sessions web contre les fuites XSS.
    """
    if credentials and credentials.credentials:
        return credentials.credentials
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    return None


async def get_current_business_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> uuid.UUID:
    token = _extract_token_from_request(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="Authentification requise")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expirée, veuillez vous reconnecter")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

    business_id_str = payload.get("business_id")
    if not business_id_str:
        raise HTTPException(status_code=401, detail="Token invalide")

    try:
        return uuid.UUID(business_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token invalide")


async def get_current_super_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """
    Dépendance de sécurité garantissant que l'appelant est bien le
    SUPER_ADMIN (propriétaire de la plateforme SaaS).
    Rejette toute tentative d'accès commerçant avec un code 403.
    """
    token = _extract_token_from_request(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="Authentification requise")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expirée, veuillez vous reconnecter")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Token invalide")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token invalide")

    async with async_session() as session:
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Compte inactif ou introuvable")

        if user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Accès refusé : privilèges Super Administrateur requis",
            )

        return user


def require_permission(permission: str):
    """
    Vérifie qu'un utilisateur possède la permission RBAC requise.
    Exemple : Depends(require_permission("platform:manage_business"))
    """
    async def permission_checker(admin: User = Depends(get_current_super_admin)) -> User:
        role_str = admin.role.value if hasattr(admin.role, "value") else str(admin.role)
        perms = get_permissions_for_role(role_str)
        if permission not in perms:
            raise HTTPException(
                status_code=403,
                detail=f"Action non autorisée : permission '{permission}' manquante",
            )
        return admin

    return permission_checker


async def get_current_driver(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    """
    Dépendance de sécurité garantissant que l'appelant est un LIVREUR authentifié.
    Rejette les accès non autorisés avec HTTP 401 ou 403.
    """
    token = _extract_token_from_request(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="Authentification requise")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expirée, veuillez vous reconnecter")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Token invalide")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token invalide")

    async with async_session() as session:
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Compte livreur inactif ou introuvable")

        if user.role != UserRole.LIVREUR:
            raise HTTPException(
                status_code=403,
                detail="Accès refusé : compte Livreur requis",
            )

        return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    """
    Récupère l'utilisateur actuellement connecté (marchand, admin ou livreur).
    """
    token = _extract_token_from_request(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="Authentification requise")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expirée, veuillez vous reconnecter")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Token invalide")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token invalide")

    async with async_session() as session:
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Compte inactif ou introuvable")

        return user


