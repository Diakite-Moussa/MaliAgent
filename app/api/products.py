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
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import get_current_business_id, get_current_user
from app.db.session import async_session
from app.models import Category, Product, ProductVariant, StockMovement, StockMovementType, User
from app.services.stock import record_stock_movement

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
    if v:
        v_clean = v.strip()
        is_https = v_clean.startswith("https://")
        is_local_http = v_clean.startswith("http://localhost") or v_clean.startswith("http://127.0.0.1")
        is_relative = v_clean.startswith("/api/products/images/")
        if not (is_https or is_local_http or is_relative):
            raise ValueError("image_url doit être une URL https valide (ou locale en développement)")
        return v_clean
    return v


class VariantInput(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., min_length=1, max_length=100)
    price: Decimal | None = Field(None, ge=0)
    stock_quantity: int = Field(0, ge=0)
    sku: str | None = Field(None, max_length=100)
    image_url: str | None = None


class ProductStockUpdate(BaseModel):
    stock_quantity: int = Field(..., ge=0)


class VariantStockUpdate(BaseModel):
    stock_quantity: int = Field(..., ge=0)


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    category_id: uuid.UUID | None = None
    price: Decimal | None = Field(None, ge=0)
    stock_quantity: int | None = Field(None, ge=0)
    low_stock_threshold: int | None = Field(None, ge=0)
    image_url: str | None = None
    variants: list[VariantInput] | None = None

    @field_validator("image_url")
    @classmethod
    def check_image_url(cls, v):
        return _validate_image_url(v)


class ProductCreate(BaseModel):
    name: str
    category: str | None = None
    category_id: uuid.UUID | None = None
    price: Decimal = Field(..., ge=0)
    stock_quantity: int = Field(0, ge=0)
    low_stock_threshold: int = Field(3, ge=0)
    image_url: str | None = None
    variants: list[VariantInput] | None = None

    @field_validator("image_url")
    @classmethod
    def check_image_url(cls, v):
        return _validate_image_url(v)


@router.get("")
async def list_products(business_id: uuid.UUID = Depends(get_current_business_id)):
    """
    Retourne la liste de tous les produits du commerce avec leurs prix, stocks et variantes.
    """
    async with async_session() as session:
        stmt = (
            select(Product)
            .options(selectinload(Product.variants))
            .where(Product.business_id == business_id)
            .order_by(Product.name.asc())
        )
        products = (await session.execute(stmt)).scalars().all()

        return [
            {
                "id": str(p.id),
                "business_id": str(p.business_id),
                "name": p.name,
                "category": p.category,
                "category_id": str(p.category_id) if p.category_id else None,
                "price": int(p.price),
                "stock_quantity": p.effective_stock,
                "low_stock_threshold": p.low_stock_threshold,
                "is_low_stock": p.effective_stock <= p.low_stock_threshold,
                "is_out_of_stock": p.effective_stock <= 0,
                "image_url": p.image_url,
                "has_variants": p.has_variants,
                "variants": [
                    {
                        "id": str(v.id),
                        "name": v.name,
                        "value": v.value,
                        "label": v.label,
                        "price": int(v.price) if v.price is not None else None,
                        "stock_quantity": v.stock_quantity,
                        "sku": v.sku,
                        "image_url": v.image_url,
                    }
                    for v in p.variants
                ],
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
        cat_name = (payload.category or "Général").strip()
        cat_id = payload.category_id

        if cat_id:
            stmt_c = select(Category).where(
                Category.id == cat_id, Category.business_id == business_id
            )
            cat = (await session.execute(stmt_c)).scalar_one_or_none()
            if cat:
                cat_name = cat.name
        elif payload.category:
            # Recherche d'une catégorie existante correspondante
            stmt_c = select(Category).where(
                Category.business_id == business_id,
                func.lower(Category.name) == cat_name.lower(),
            )
            cat = (await session.execute(stmt_c)).scalar_one_or_none()
            if cat:
                cat_id = cat.id

        product = Product(
            business_id=business_id,
            name=payload.name.strip(),
            category_id=cat_id,
            category=cat_name,
            price=payload.price,
            stock_quantity=payload.stock_quantity,
            low_stock_threshold=payload.low_stock_threshold,
            image_url=payload.image_url,
        )
        session.add(product)
        await session.flush()

        if payload.variants:
            for v_data in payload.variants:
                var = ProductVariant(
                    business_id=business_id,
                    product_id=product.id,
                    name=v_data.name.strip(),
                    value=v_data.value.strip(),
                    price=v_data.price,
                    stock_quantity=v_data.stock_quantity,
                    sku=v_data.sku.strip() if v_data.sku else None,
                    image_url=v_data.image_url,
                )
                session.add(var)
            await session.flush()
            product.stock_quantity = sum(v.stock_quantity for v in payload.variants)

        await session.commit()

        # Rechargement avec variantes
        stmt_reload = (
            select(Product)
            .options(selectinload(Product.variants))
            .where(Product.id == product.id)
        )
        p_loaded = (await session.execute(stmt_reload)).scalar_one()

        return {
            "id": str(p_loaded.id),
            "name": p_loaded.name,
            "category": p_loaded.category,
            "category_id": str(p_loaded.category_id) if p_loaded.category_id else None,
            "price": int(p_loaded.price),
            "stock_quantity": p_loaded.effective_stock,
            "low_stock_threshold": p_loaded.low_stock_threshold,
            "image_url": p_loaded.image_url,
            "has_variants": p_loaded.has_variants,
            "variants": [
                {
                    "id": str(v.id),
                    "name": v.name,
                    "value": v.value,
                    "label": v.label,
                    "price": int(v.price) if v.price is not None else None,
                    "stock_quantity": v.stock_quantity,
                    "sku": v.sku,
                    "image_url": v.image_url,
                }
                for v in p_loaded.variants
            ],
            "message": "Produit créé avec succès",
        }


@router.patch("/{product_id}")
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Met à jour le stock, le prix, la catégorie ou les variantes d'un produit.
    """
    async with async_session() as session:
        stmt = (
            select(Product)
            .options(selectinload(Product.variants))
            .where(Product.id == product_id, Product.business_id == business_id)
        )
        product = (await session.execute(stmt)).scalar_one_or_none()

        if not product:
            raise HTTPException(status_code=404, detail="Produit introuvable")

        if payload.name is not None:
            product.name = payload.name.strip()

        if payload.category_id is not None:
            stmt_c = select(Category).where(
                Category.id == payload.category_id, Category.business_id == business_id
            )
            cat = (await session.execute(stmt_c)).scalar_one_or_none()
            if cat:
                product.category_id = cat.id
                product.category = cat.name
        elif payload.category is not None:
            product.category = payload.category.strip()

        if payload.price is not None:
            product.price = payload.price
        if payload.stock_quantity is not None:
            product.stock_quantity = payload.stock_quantity
        if payload.low_stock_threshold is not None:
            product.low_stock_threshold = payload.low_stock_threshold
        if payload.image_url is not None:
            product.image_url = payload.image_url

        if payload.variants is not None:
            existing_variants_map = {v.id: v for v in product.variants}
            payload_variant_ids = {v.id for v in payload.variants if v.id is not None}

            # Supprimer les variantes qui ne sont plus dans la liste envoyée
            for v_id, v in list(existing_variants_map.items()):
                if v_id not in payload_variant_ids:
                    await session.delete(v)

            # Mettre à jour ou ajouter
            for v_data in payload.variants:
                if v_data.id and v_data.id in existing_variants_map:
                    var = existing_variants_map[v_data.id]
                    var.name = v_data.name.strip()
                    var.value = v_data.value.strip()
                    var.price = v_data.price
                    var.stock_quantity = v_data.stock_quantity
                    var.sku = v_data.sku.strip() if v_data.sku else None
                    var.image_url = v_data.image_url
                else:
                    var = ProductVariant(
                        business_id=business_id,
                        product_id=product.id,
                        name=v_data.name.strip(),
                        value=v_data.value.strip(),
                        price=v_data.price,
                        stock_quantity=v_data.stock_quantity,
                        sku=v_data.sku.strip() if v_data.sku else None,
                        image_url=v_data.image_url,
                    )
                    session.add(var)

            await session.flush()
            product.stock_quantity = sum(v.stock_quantity for v in payload.variants)

        await session.commit()

        # Rechargement avec variantes fraîches
        stmt_reload = (
            select(Product)
            .options(selectinload(Product.variants))
            .where(Product.id == product.id)
        )
        p_loaded = (await session.execute(stmt_reload)).scalar_one()

        return {
            "id": str(p_loaded.id),
            "name": p_loaded.name,
            "category": p_loaded.category,
            "category_id": str(p_loaded.category_id) if p_loaded.category_id else None,
            "price": int(p_loaded.price),
            "stock_quantity": p_loaded.effective_stock,
            "low_stock_threshold": p_loaded.low_stock_threshold,
            "image_url": p_loaded.image_url,
            "has_variants": p_loaded.has_variants,
            "variants": [
                {
                    "id": str(v.id),
                    "name": v.name,
                    "value": v.value,
                    "label": v.label,
                    "price": int(v.price) if v.price is not None else None,
                    "stock_quantity": v.stock_quantity,
                    "sku": v.sku,
                    "image_url": v.image_url,
                }
                for v in p_loaded.variants
            ],
            "message": "Produit mis à jour avec succès",
        }


@router.patch("/{product_id}/stock")
async def update_product_stock(
    product_id: uuid.UUID,
    payload: ProductStockUpdate,
    business_id: uuid.UUID = Depends(get_current_business_id),
    user: User = Depends(get_current_user),
):
    """
    Ajuste rapidement la quantité en stock d'un produit (boutons +1, -1, +5).
    Chaque ajustement est journalisé dans stock_movements avec l'auteur.
    """
    async with async_session() as session:
        stmt = select(Product).where(Product.id == product_id, Product.business_id == business_id)
        product = (await session.execute(stmt)).scalar_one_or_none()

        if not product:
            raise HTTPException(status_code=404, detail="Produit introuvable")

        delta = payload.stock_quantity - product.stock_quantity
        if delta != 0:
            movement_type = (
                StockMovementType.MANUAL_RESTOCK if delta > 0 else StockMovementType.MANUAL_ADJUSTMENT
            )
            await record_stock_movement(
                session,
                product,
                delta,
                movement_type,
                reason="Ajustement manuel Dashboard",
                created_by_user_id=user.id,
            )

        await session.commit()

        return {
            "id": str(product.id),
            "name": product.name,
            "stock_quantity": product.effective_stock,
            "message": "Stock mis à jour avec succès",
        }


@router.patch("/{product_id}/variants/{variant_id}/stock")
async def update_variant_stock(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    payload: VariantStockUpdate,
    business_id: uuid.UUID = Depends(get_current_business_id),
    user: User = Depends(get_current_user),
):
    """
    Ajuste rapidement la quantité en stock d'une déclinaison spécifique d'un produit.
    Le mouvement est journalisé dans stock_movements avec le variant_id et l'auteur.
    """
    async with async_session() as session:
        stmt = (
            select(Product)
            .options(selectinload(Product.variants))
            .where(Product.id == product_id, Product.business_id == business_id)
        )
        product = (await session.execute(stmt)).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Produit introuvable")

        variant = next((v for v in product.variants if v.id == variant_id), None)
        if not variant:
            raise HTTPException(status_code=404, detail="Variante introuvable")

        delta = payload.stock_quantity - variant.stock_quantity
        if delta != 0:
            movement_type = (
                StockMovementType.MANUAL_RESTOCK if delta > 0 else StockMovementType.MANUAL_ADJUSTMENT
            )
            await record_stock_movement(
                session,
                product,
                delta,
                movement_type,
                reason="Ajustement manuel variante Dashboard",
                created_by_user_id=user.id,
                variant=variant,
            )

        await session.commit()

        return {
            "id": str(variant.id),
            "product_id": str(product.id),
            "name": variant.name,
            "value": variant.value,
            "stock_quantity": variant.stock_quantity,
            "product_effective_stock": product.effective_stock,
            "message": "Stock de la variante mis à jour avec succès",
        }


@router.get("/{product_id}/movements")
async def get_product_stock_movements(
    product_id: uuid.UUID,
    limit: int = 50,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Historique des mouvements de stock d'un produit (ventes, annulations,
    ajustements manuels), du plus récent au plus ancien.
    """
    async with async_session() as session:
        stmt_prod = select(Product).where(Product.id == product_id, Product.business_id == business_id)
        product = (await session.execute(stmt_prod)).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Produit introuvable")

        stmt = (
            select(StockMovement)
            .where(StockMovement.product_id == product_id, StockMovement.business_id == business_id)
            .order_by(StockMovement.created_at.desc())
            .limit(min(limit, 200))
        )
        movements = (await session.execute(stmt)).scalars().all()

        return [
            {
                "id": str(m.id),
                "movement_type": m.movement_type.value,
                "quantity_change": m.quantity_change,
                "quantity_before": m.quantity_before,
                "quantity_after": m.quantity_after,
                "reason": m.reason,
                "order_id": str(m.order_id) if m.order_id else None,
                "created_by_user_id": str(m.created_by_user_id) if m.created_by_user_id else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in movements
        ]


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