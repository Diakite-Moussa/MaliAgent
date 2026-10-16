"""
Endpoint de connexion et gestion de session pour les utilisateurs du dashboard.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.rate_limit import auth_rate_limiter
from app.core.security import create_access_token, verify_password
from app.db.session import async_session
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    business_id: str | None = None
    email: str
    role: str


class UserProfileResponse(BaseModel):
    id: str
    email: str
    role: str
    business_id: str | None = None


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, response: Response):
    # Protection anti-brute force applicative
    auth_rate_limiter.check(request, payload.email)

    async with async_session() as session:
        stmt = select(User).where(User.email == payload.email.lower())
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
            # Enregistrement de l'échec pour le rate limiter
            auth_rate_limiter.record_failure(request, payload.email)
            # Message volontairement générique : ne pas révéler si c'est
            # l'email ou le mot de passe qui est incorrect.
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

        # Succès : réinitialiser le compteur d'échecs pour cette IP/utilisateur
        auth_rate_limiter.record_success(request, payload.email)

        biz_id_str = str(user.business_id) if user.business_id else None
        token = create_access_token(user_id=str(user.id), business_id=biz_id_str)

        # Injection du cookie de session sécurisé HttpOnly (protection anti-XSS et HTTPS en prod)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            secure=settings.is_cookie_secure,
            max_age=settings.jwt_expire_minutes * 60,
            path="/",
        )

        return LoginResponse(
            access_token=token,
            business_id=biz_id_str,
            email=user.email,
            role=user.role.value,
        )


@router.post("/logout")
async def logout(response: Response):
    """
    Révoque la session en supprimant le cookie HttpOnly côté client.
    """
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=settings.is_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return {"status": "ok", "message": "Déconnexion réussie"}


@router.get("/me", response_model=UserProfileResponse)
async def me(current_user: User = Depends(get_current_user)):
    """
    Permet au dashboard de vérifier si un cookie de session valide est présent.
    """
    return UserProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        business_id=str(current_user.business_id) if current_user.business_id else None,
    )
