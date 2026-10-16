"""
Endpoints de gestion des commandes pour le Dashboard commerçant.
"""

import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_business_id
from app.db.session import async_session
from app.models import Customer, Invoice, Order, OrderItem, OrderStatus, Product

router = APIRouter(prefix="/api/orders", tags=["Orders"])


class OrderStatusUpdate(BaseModel):
    status: Literal["pending", "confirmed", "delivered", "cancelled"]


@router.get("")
async def list_orders(
    business_id: uuid.UUID = Depends(get_current_business_id),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Retourne la liste des commandes avec les détails des articles et du client.
    """
    async with async_session() as session:
        stmt = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.business_id == business_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(Order.status == status)

        orders = (await session.execute(stmt)).scalars().all()

        # Charger la table des clients et des produits pour enrichir les résultats
        cust_ids = {o.customer_id for o in orders}
        customers_map = {}
        if cust_ids:
            stmt_c = select(Customer).where(Customer.id.in_(cust_ids))
            customers = (await session.execute(stmt_c)).scalars().all()
            customers_map = {c.id: c for c in customers}

        prod_ids = {item.product_id for o in orders for item in o.items}
        products_map = {}
        if prod_ids:
            stmt_p = select(Product).where(Product.id.in_(prod_ids))
            prods = (await session.execute(stmt_p)).scalars().all()
            products_map = {p.id: p for p in prods}

        # Récupérer les factures associées
        order_ids = {o.id for o in orders}
        invoices_map = {}
        if order_ids:
            stmt_inv = select(Invoice).where(Invoice.order_id.in_(order_ids))
            invoices = (await session.execute(stmt_inv)).scalars().all()
            invoices_map = {inv.order_id: inv for inv in invoices}

        result = []
        for o in orders:
            cust = customers_map.get(o.customer_id)
            inv = invoices_map.get(o.id)

            items_data = [
                {
                    "id": str(it.id),
                    "product_id": str(it.product_id),
                    "product_name": products_map[it.product_id].name if it.product_id in products_map else "Article",
                    "quantity": it.quantity,
                    "unit_price": int(it.unit_price_snapshot),
                    "total_price": int(it.unit_price_snapshot * it.quantity),
                }
                for it in o.items
            ]

            result.append({
                "id": str(o.id),
                "short_id": str(o.id)[:8].upper(),
                "status": o.status.value,
                "delivery_address": o.delivery_address,
                "delivery_fee": int(o.delivery_fee or 0),
                "total_amount": int(o.total_amount),
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "customer": {
                    "id": str(cust.id) if cust else str(o.customer_id),
                    "phone": cust.whatsapp_phone_number if cust else "Inconnu",
                    "name": cust.display_name if cust else None,
                },
                "items": items_data,
                "invoice": {
                    "number": inv.invoice_number if inv else None,
                    "status": inv.status if inv else None,
                    "download_url": f"/invoices/{inv.invoice_number}" if inv else None,
                },
            })

        return {"orders": result, "total": len(result)}


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: uuid.UUID,
    update: OrderStatusUpdate,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Met à jour le statut d'une commande (pending, confirmed, delivered, cancelled).
    Si le statut devient 'delivered', la facture associée est marquée comme 'paid'.
    """
    async with async_session() as session:
        stmt = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id, Order.business_id == business_id)
        )
        order = (await session.execute(stmt)).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Commande introuvable")

        order.status = OrderStatus(update.status)
        if update.status == "delivered":
            order.payment_status = "paid"

        # Mise à jour éventuelle de la facture
        stmt_inv = select(Invoice).where(Invoice.order_id == order.id)
        inv = (await session.execute(stmt_inv)).scalar_one_or_none()
        if inv and update.status == "delivered":
            inv.status = "paid"
            try:
                old_pdf = Path("storage") / "invoices" / f"{inv.invoice_number}.pdf"
                if old_pdf.exists():
                    old_pdf.unlink()
            except Exception:
                pass
        elif inv and update.status == "cancelled":
            inv.status = "cancelled"

        await session.commit()

        return {
            "id": str(order.id),
            "short_id": str(order.id)[:8].upper(),
            "status": order.status.value,
            "invoice_status": inv.status if inv else None,
            "message": f"Statut mis à jour : {order.status.value}",
        }


@router.get("/export-csv")
async def export_orders_csv(business_id: uuid.UUID = Depends(get_current_business_id)):
    """
    Exporte l'ensemble des commandes au format CSV compatible Excel (encodage UTF-8 BOM).
    """
    from fastapi.responses import Response
    import io
    import csv

    async with async_session() as session:
        stmt = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.business_id == business_id)
            .order_by(Order.created_at.desc())
        )

        orders = (await session.execute(stmt)).scalars().all()

        cust_ids = {o.customer_id for o in orders}
        customers_map = {}
        if cust_ids:
            stmt_c = select(Customer).where(Customer.id.in_(cust_ids))
            customers = (await session.execute(stmt_c)).scalars().all()
            customers_map = {c.id: c for c in customers}

        prod_ids = {item.product_id for o in orders for item in o.items}
        products_map = {}
        if prod_ids:
            stmt_p = select(Product).where(Product.id.in_(prod_ids))
            prods = (await session.execute(stmt_p)).scalars().all()
            products_map = {p.id: p for p in prods}

        output = io.StringIO()
        # Écriture du BOM UTF-8 pour ouverture directe sous Excel sans problème d'accents
        output.write("\ufeff")
        writer = csv.writer(output, delimiter=";")
        writer.writerow([
            "Reference",
            "Date",
            "Telephone Client",
            "Articles",
            "Frais Livraison (FCFA)",
            "Total (FCFA)",
            "Statut",
            "Adresse Livraison",
        ])

        for o in orders:
            cust = customers_map.get(o.customer_id)
            phone = cust.whatsapp_phone_number if cust else "Inconnu"
            items_str = ", ".join(
                f"{it.quantity}x {products_map.get(it.product_id).name if it.product_id in products_map else 'Article'}"
                for it in o.items
            )
            date_str = o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else ""
            writer.writerow([
                str(o.id)[:8].upper(),
                date_str,
                phone,
                items_str,
                int(o.delivery_fee or 0),
                int(o.total_amount),
                o.status.value,
                o.delivery_address or "",
            ])

        csv_data = output.getvalue()
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=commandes_maliagent.csv",
                "Content-Type": "text/csv; charset=utf-8",
            },
        )
