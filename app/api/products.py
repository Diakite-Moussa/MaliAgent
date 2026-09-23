"""
Endpoints de gestion du catalogue de produits et des stocks pour le Dashboard.
"""

from decimal import Decimal
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import get_current_business_id
from app.db.session import async_session
from app.models import Product

router = APIRouter(prefix="/api/products", tags=["Products"])

PRODUCTS_IMG_DIR = Path("storage") / "products"
PRODUCTS_IMG_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 Mo


def _validate_image_url(v: str | None) -> str | None:
    if v and not v.startswith(("http://", "https://")):
        raise ValueError("image_url doit être une URL http(s) valide")
    return v


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    price: Decimal | None = Field(None, ge=0)
    stock_quantity: int | None = Field(None, ge=0)
    image_url: str | None = None

    @field_validator("image_url")
    @classmethod
    def check_image_url(cls, v):
        return _validate_image_url(v)


class ProductCreate(BaseModel):
    name: str
    category: str
    price: Decimal = Field(..., ge=0)
    stock_quantity: int = Field(0, ge=0)
    image_url: str | None = None

    @field_validator("image_url")
    @classmethod
    def check_image_url(cls, v):
        return _validate_image_url(v)


@router.get("")
async def list_products(business_id: uuid.UUID = Depends(get_current_business_id)):
    """
    Retourne la liste de tous les produits du commerce avec leurs prix et stocks.
    """
    async with async_session() as session:
        stmt = select(Product).where(Product.business_id == business_id).order_by(Product.name.asc())
        products = (await session.execute(stmt)).scalars().all()

        return [
            {
                "id": str(p.id),
                "business_id": str(p.business_id),
                "name": p.name,
                "category": p.category,
                "price": int(p.price),
                "stock_quantity": p.stock_quantity,
                "is_low_stock": p.stock_quantity <= 3,
                "is_out_of_stock": p.stock_quantity <= 0,
                "image_url": p.image_url,
            }
            for p in products
        ]


@router.post("")
async def create_product(
    payload: ProductCreate, business_id: uuid.UUID = Depends(get_current_business_id)
):
    """
    Ajoute un nouveau produit au catalogue du commerce courant.
    """
    async with async_session() as session:
        product = Product(
            business_id=business_id,
            name=payload.name.strip(),
            category=payload.category.strip().lower(),
            price=payload.price,
            stock_quantity=payload.stock_quantity,
            image_url=payload.image_url,
        )
        session.add(product)
        await session.commit()

        return {
            "id": str(product.id),
            "name": product.name,
            "category": product.category,
            "price": int(product.price),
            "stock_quantity": product.stock_quantity,
            "image_url": product.image_url,
            "message": "Produit créé avec succès",
        }


@router.patch("/{product_id}")
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Met à jour le stock, le prix ou la photo d'un produit appartenant au commerce courant.
    """
    async with async_session() as session:
        stmt = select(Product).where(Product.id == product_id, Product.business_id == business_id)
        product = (await session.execute(stmt)).scalar_one_or_none()

        if not product:
            raise HTTPException(status_code=404, detail="Produit introuvable")

        if payload.name is not None:
            product.name = payload.name.strip()
        if payload.category is not None:
            product.category = payload.category.strip().lower()
        if payload.price is not None:
            product.price = payload.price
        if payload.stock_quantity is not None:
            product.stock_quantity = payload.stock_quantity
        if payload.image_url is not None:
            product.image_url = payload.image_url

        await session.commit()

        return {
            "id": str(product.id),
            "name": product.name,
            "category": product.category,
            "price": int(product.price),
            "stock_quantity": product.stock_quantity,
            "image_url": product.image_url,
            "message": "Produit mis à jour avec succès",
        }


@router.post("/upload-image")
async def upload_product_image(
    file: UploadFile = File(...),
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Upload d'une photo produit depuis le Dashboard. Retourne l'URL publique
    à réutiliser dans image_url lors de la création/mise à jour du produit.
    Authentification requise (business_id extrait du JWT).
    """
    if file.content_type not in ALLOWED_MIME_TO_EXT:
        raise HTTPException(
            status_code=400,
            detail="Format non autorisé. Formats acceptés : JPEG, PNG, WEBP.",
        )

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Image trop volumineuse (5 Mo maximum).")
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")

    ext = ALLOWED_MIME_TO_EXT[file.content_type]
    filename = f"{uuid.uuid4()}.{ext}"
    file_path = PRODUCTS_IMG_DIR / filename

    with open(file_path, "wb") as f:
        f.write(content)

    public_base = settings.public_base_url.rstrip("/")
    public_url = f"{public_base}/api/products/images/{filename}"

    return {"image_url": public_url, "filename": filename}


@router.get("/images/{filename}")
async def get_product_image(filename: str):
    """
    Sert publiquement les photos de produits (sans authentification) afin
    que Meta WhatsApp puisse les télécharger pour l'envoi via send_image_message.
    """
    safe_name = os.path.basename(filename)
    file_path = PRODUCTS_IMG_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image introuvable")

    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    media_type = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )