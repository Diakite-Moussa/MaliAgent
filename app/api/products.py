"""
Endpoints de gestion du catalogue de produits et des stocks pour le Dashboard.
"""

from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import get_current_business_id
from app.db.session import async_session
from app.models import Product

router = APIRouter(prefix="/api/products", tags=["Products"])


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    price: Decimal | None = Field(None, ge=0)
    stock_quantity: int | None = Field(None, ge=0)


class ProductCreate(BaseModel):
    name: str
    category: str
    price: Decimal = Field(..., ge=0)
    stock_quantity: int = Field(0, ge=0)


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
        )
        session.add(product)
        await session.commit()

        return {
            "id": str(product.id),
            "name": product.name,
            "category": product.category,
            "price": int(product.price),
            "stock_quantity": product.stock_quantity,
            "message": "Produit créé avec succès",
        }


@router.patch("/{product_id}")
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Met à jour le stock ou le prix d'un produit appartenant au commerce courant.
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

        await session.commit()

        return {
            "id": str(product.id),
            "name": product.name,
            "category": product.category,
            "price": int(product.price),
            "stock_quantity": product.stock_quantity,
            "message": "Produit mis à jour avec succès",
        }
