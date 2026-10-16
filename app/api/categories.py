"""
Endpoints de gestion des catégories formelles de produits (Section 13.5 du CDC).
"""

import uuid
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import get_current_business_id
from app.db.session import async_session
from app.models import Category, Product

router = APIRouter(prefix="/api/categories", tags=["Categories"])


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


@router.get("")
async def list_categories(business_id: uuid.UUID = Depends(get_current_business_id)):
    """
    Retourne la liste des catégories de la boutique avec le nombre de produits associés.
    """
    async with async_session() as session:
        # Requête avec comptage des produits associés
        stmt = (
            select(
                Category,
                func.count(Product.id).label("product_count"),
            )
            .outerjoin(Product, Product.category_id == Category.id)
            .where(Category.business_id == business_id)
            .group_by(Category.id)
            .order_by(Category.name.asc())
        )
        results = (await session.execute(stmt)).all()

        return [
            {
                "id": str(cat.id),
                "business_id": str(cat.business_id),
                "name": cat.name,
                "description": cat.description,
                "product_count": count,
                "created_at": cat.created_at.isoformat() if cat.created_at else None,
            }
            for cat, count in results
        ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Crée une nouvelle catégorie pour la boutique courante.
    """
    cat_name = payload.name.strip()
    async with async_session() as session:
        # Vérification d'unicité insensible à la casse
        stmt = select(Category).where(
            Category.business_id == business_id,
            func.lower(Category.name) == cat_name.lower(),
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Une catégorie avec le nom '{cat_name}' existe déjà.",
            )

        category = Category(
            business_id=business_id,
            name=cat_name,
            description=payload.description.strip() if payload.description else None,
        )
        session.add(category)
        await session.commit()

        return {
            "id": str(category.id),
            "business_id": str(category.business_id),
            "name": category.name,
            "description": category.description,
            "product_count": 0,
            "message": "Catégorie créée avec succès",
        }


@router.patch("/{category_id}")
@router.put("/{category_id}")
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Modifie le nom ou la description d'une catégorie.
    """
    async with async_session() as session:
        stmt = select(Category).where(
            Category.id == category_id,
            Category.business_id == business_id,
        )
        category = (await session.execute(stmt)).scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=404, detail="Catégorie introuvable")

        if payload.name is not None:
            new_name = payload.name.strip()
            # Vérification de doublon
            stmt_dup = select(Category).where(
                Category.business_id == business_id,
                Category.id != category_id,
                func.lower(Category.name) == new_name.lower(),
            )
            dup = (await session.execute(stmt_dup)).scalar_one_or_none()
            if dup:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Une catégorie avec le nom '{new_name}' existe déjà.",
                )

            category.name = new_name

            # Synchronisation du texte category sur les produits rattachés
            stmt_prods = select(Product).where(Product.category_id == category_id)
            prods = (await session.execute(stmt_prods)).scalars().all()
            for p in prods:
                p.category = new_name

        if payload.description is not None:
            category.description = payload.description.strip() if payload.description else None

        await session.commit()

        # Compte des produits
        stmt_count = select(func.count(Product.id)).where(Product.category_id == category_id)
        count = (await session.execute(stmt_count)).scalar() or 0

        return {
            "id": str(category.id),
            "name": category.name,
            "description": category.description,
            "product_count": count,
            "message": "Catégorie mise à jour avec succès",
        }


@router.delete("/{category_id}")
async def delete_category(
    category_id: uuid.UUID,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Supprime une catégorie. Les produits associés conservent leur historique textuel
    mais leur category_id est dissocié (NULL).
    """
    async with async_session() as session:
        stmt = select(Category).where(
            Category.id == category_id,
            Category.business_id == business_id,
        )
        category = (await session.execute(stmt)).scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=404, detail="Catégorie introuvable")

        # Dissocie les produits
        stmt_prods = select(Product).where(Product.category_id == category_id)
        prods = (await session.execute(stmt_prods)).scalars().all()
        for p in prods:
            p.category_id = None

        await session.delete(category)
        await session.commit()

        return {"message": "Catégorie supprimée avec succès"}
