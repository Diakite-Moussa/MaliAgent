"""
Endpoint de connexion pour les utilisateurs du dashboard.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

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


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    async with async_session() as session:
        stmt = select(User).where(User.email == payload.email.lower())
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
            # Message volontairement générique : ne pas révéler si c'est
            # l'email ou le mot de passe qui est incorrect.
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

        biz_id_str = str(user.business_id) if user.business_id else None
        token = create_access_token(user_id=str(user.id), business_id=biz_id_str)
        return LoginResponse(
            access_token=token,
            business_id=biz_id_str,
            email=user.email,
            role=user.role.value,
        )
