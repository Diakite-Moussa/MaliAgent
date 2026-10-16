"""
Routeur FastAPI pour la consultation et le téléchargement des factures PDF.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session
from app.models import Business, Customer, Invoice, Order, OrderStatus, Product
from app.services.invoice_generator import generate_invoice_pdf

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("/{invoice_number}")
async def get_invoice_pdf(invoice_number: str):
    """
    Télécharge ou affiche la facture PDF correspondant au numéro de facture.
    Si la commande associée est livrée ou acquittée, s'assure que le PDF affiche le statut Payée.
    """
    invoice_number = invoice_number.strip().upper()
    pdf_path = Path("storage") / "invoices" / f"{invoice_number}.pdf"

    async with async_session() as session:
        stmt = (
            select(Invoice)
            .options(selectinload(Invoice.order).selectinload(Order.items))
            .where(Invoice.invoice_number == invoice_number)
        )
        invoice = (await session.execute(stmt)).scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=404, detail="Facture introuvable")

        order = invoice.order
        # Synchronisation automatique du statut si la commande est livrée ou payée
        is_order_paid = (
            order is not None and (
                order.status == OrderStatus.DELIVERED
                or getattr(order, "payment_status", "") == "paid"
            )
        )
        if is_order_paid and invoice.status != "paid":
            invoice.status = "paid"
            if order and getattr(order, "payment_status", "") != "paid":
                order.payment_status = "paid"
            await session.commit()
            if pdf_path.exists():
                try:
                    pdf_path.unlink()
                except Exception:
                    pass

        if pdf_path.exists():
            return FileResponse(
                path=str(pdf_path),
                media_type="application/pdf",
                filename=f"Facture_{invoice_number}.pdf",
            )

        # Génération du PDF avec les informations fraîches
        business = (await session.execute(select(Business).where(Business.id == invoice.business_id))).scalar_one()
        customer = (await session.execute(select(Customer).where(Customer.id == order.customer_id))).scalar_one()

        # Charger la table de produits
        prods = (await session.execute(select(Product).where(Product.business_id == business.id))).scalars().all()
        products_map = {p.id: p for p in prods}

        generated_path = generate_invoice_pdf(
            invoice=invoice,
            order=order,
            business=business,
            customer=customer,
            products_map=products_map,
        )

        return FileResponse(
            path=str(generated_path),
            media_type="application/pdf",
            filename=f"Facture_{invoice_number}.pdf",
        )
