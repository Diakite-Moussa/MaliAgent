"""
Point d'entrée unique pour toute modification de stock_quantity d'un Product.

Règle du projet : ne jamais faire `product.stock_quantity += n` ailleurs
que dans ce module. Toujours passer par record_stock_movement() pour que
le journal StockMovement reste exhaustif.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, StockMovement, StockMovementType
from app.models.product_variant import ProductVariant


async def record_stock_movement(
    session: AsyncSession,
    product: Product,
    quantity_change: int,
    movement_type: StockMovementType,
    reason: str | None = None,
    order_id: uuid.UUID | None = None,
    created_by_user_id: uuid.UUID | None = None,
    variant: ProductVariant | None = None,
) -> StockMovement:
    """
    Applique quantity_change au stock (du produit ou de sa variante si spécifiée)
    et journalise le mouvement. Ne fait PAS de commit — l'appelant garde la
    responsabilité de la transaction, comme partout ailleurs dans le projet.
    """
    if variant is not None:
        before = variant.stock_quantity
        variant.stock_quantity = before + quantity_change
        after = variant.stock_quantity
        # Synchronise le stock global du produit parent
        product.stock_quantity = product.effective_stock
        variant_id = variant.id
    else:
        before = product.stock_quantity
        product.stock_quantity = before + quantity_change
        after = product.stock_quantity
        variant_id = None

    movement = StockMovement(
        business_id=product.business_id,
        product_id=product.id,
        variant_id=variant_id,
        order_id=order_id,
        movement_type=movement_type,
        quantity_change=quantity_change,
        quantity_before=before,
        quantity_after=after,
        reason=reason,
        created_by_user_id=created_by_user_id,
    )
    session.add(movement)
    return movement
