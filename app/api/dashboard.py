"""
Endpoints pour les statistiques et indicateurs clés (KPIs) du Dashboard.
"""

from datetime import datetime, timezone
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_business_id
from app.db.session import async_session
from app.models import Business, Conversation, ConversationMessage, Customer, Order, OrderItem, OrderStatus, Product

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


class HandoffReplyIn(BaseModel):
    message: str


@router.get("/stats")
async def get_dashboard_stats(business_id: uuid.UUID = Depends(get_current_business_id)):
    async with async_session() as session:
        business = (
            await session.execute(select(Business).where(Business.id == business_id))
        ).scalar_one_or_none()
        if not business:
            raise HTTPException(status_code=404, detail="Commerce introuvable")

        # 1. Total clients
        stmt_cust = select(func.count(Customer.id)).where(Customer.business_id == business.id)
        total_customers = (await session.execute(stmt_cust)).scalar() or 0

        # 2. Commandes du jour & en attente
        start_of_today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        stmt_today_orders = select(func.count(Order.id)).where(
            Order.business_id == business.id,
            Order.created_at >= start_of_today,
        )
        today_orders_count = (await session.execute(stmt_today_orders)).scalar() or 0

        stmt_pending = select(func.count(Order.id)).where(
            Order.business_id == business.id,
            Order.status == OrderStatus.PENDING,
        )
        pending_orders_count = (await session.execute(stmt_pending)).scalar() or 0

        # 3. Chiffre d'affaires total et du jour (hors commandes annulées)
        stmt_items_rev = (
            select(func.coalesce(func.sum(OrderItem.unit_price_snapshot * OrderItem.quantity), 0))
            .select_from(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.business_id == business.id, Order.status != OrderStatus.CANCELLED)
        )
        items_revenue = (await session.execute(stmt_items_rev)).scalar() or 0

        stmt_delivery_rev = (
            select(func.coalesce(func.sum(Order.delivery_fee), 0))
            .where(Order.business_id == business.id, Order.status != OrderStatus.CANCELLED)
        )
        delivery_revenue = (await session.execute(stmt_delivery_rev)).scalar() or 0
        total_revenue = items_revenue + delivery_revenue

        stmt_today_items_rev = (
            select(func.coalesce(func.sum(OrderItem.unit_price_snapshot * OrderItem.quantity), 0))
            .select_from(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.business_id == business.id,
                Order.status != OrderStatus.CANCELLED,
                Order.created_at >= start_of_today,
            )
        )
        today_items_rev = (await session.execute(stmt_today_items_rev)).scalar() or 0

        stmt_today_deliv_rev = (
            select(func.coalesce(func.sum(Order.delivery_fee), 0))
            .where(
                Order.business_id == business.id,
                Order.status != OrderStatus.CANCELLED,
                Order.created_at >= start_of_today,
            )
        )
        today_deliv_rev = (await session.execute(stmt_today_deliv_rev)).scalar() or 0
        today_revenue = today_items_rev + today_deliv_rev

        # 4. Alertes de stock bas
        stmt_low_stock = (
            select(Product)
            .where(Product.business_id == business.id, Product.stock_quantity <= Product.low_stock_threshold)
            .order_by(Product.stock_quantity.asc())
        )
        low_stock_prods = (await session.execute(stmt_low_stock)).scalars().all()
        low_stock_products = [
            {
                "id": str(p.id),
                "name": p.name,
                "category": p.category,
                "price": int(p.price),
                "stock_quantity": p.stock_quantity,
                "low_stock_threshold": p.low_stock_threshold,
            }
            for p in low_stock_prods
        ]

        # 5. Escalades humaines en attente
        stmt_handoffs_cnt = select(func.count(Conversation.id)).where(
            Conversation.business_id == business.id,
            Conversation.status == "needs_human",
        )
        pending_handoffs_count = (await session.execute(stmt_handoffs_cnt)).scalar() or 0

        # 6. Commandes récentes (strictement limitées aux 5 dernières)
        stmt_recent_orders = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.business_id == business.id)
            .order_by(Order.created_at.desc())
            .limit(5)
        )
        recent_orders_db = (await session.execute(stmt_recent_orders)).scalars().all()

        recent_orders = [
            {
                "id": str(o.id),
                "short_id": str(o.id)[:8].upper(),
                "customer_id": str(o.customer_id),
                "status": o.status.value,
                "total_amount": int(o.total_amount),
                "delivery_address": o.delivery_address,
                "delivery_fee": int(o.delivery_fee or 0),
                "items_count": len(o.items),
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in recent_orders_db
        ]

        return {
            "business": {
                "id": str(business.id),
                "name": business.name,
                "currency": business.currency,
                "whatsapp_phone_number": business.whatsapp_phone_number,
            },
            "kpis": {
                "total_revenue": int(total_revenue),
                "today_revenue": int(today_revenue),
                "today_orders_count": today_orders_count,
                "pending_orders_count": pending_orders_count,
                "total_customers": total_customers,
                "low_stock_count": len(low_stock_products),
                "pending_handoffs_count": pending_handoffs_count,
            },
            "low_stock_products": low_stock_products,
            "recent_orders": recent_orders,
        }


@router.get("/handoffs")
async def list_handoff_conversations(business_id: uuid.UUID = Depends(get_current_business_id)):
    async with async_session() as session:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.business_id == business_id,
                Conversation.status == "needs_human",
            )
            .order_by(Conversation.updated_at.desc())
        )
        convs = (await session.execute(stmt)).scalars().all()

        cust_ids = {c.customer_id for c in convs}
        customers_map = {}
        if cust_ids:
            stmt_c = select(Customer).where(Customer.id.in_(cust_ids))
            customers = (await session.execute(stmt_c)).scalars().all()
            customers_map = {c.id: c for c in customers}

        result = []
        for c in convs:
            cust = customers_map.get(c.customer_id)
            msgs = [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in (c.messages[-20:] if c.messages else [])
            ]
            result.append({
                "id": str(c.id),
                "customer_id": str(c.customer_id),
                "customer_phone": cust.whatsapp_phone_number if cust else "Inconnu",
                "customer_name": cust.display_name if cust else None,
                "handoff_reason": c.handoff_reason or "Assistance demandée",
                "status": c.status,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "messages": msgs,
            })

        return {"handoffs": result, "total": len(result)}


@router.post("/handoffs/{conversation_id}/reply")
async def reply_handoff(
    conversation_id: uuid.UUID,
    payload: HandoffReplyIn,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Permet au commerçant d'envoyer un message WhatsApp direct au client depuis le dashboard.
    Enregistre le message dans l'historique de la conversation.
    """
    msg_text = payload.message.strip()
    if not msg_text:
        raise HTTPException(status_code=400, detail="Le message ne peut pas être vide")

    async with async_session() as session:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.customer))
            .where(
                Conversation.id == conversation_id,
                Conversation.business_id == business_id,
            )
        )
        conv = (await session.execute(stmt)).scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation introuvable pour cette boutique")

        # Enregistrer le message de la boutique dans l'historique
        new_msg = ConversationMessage(
            conversation_id=conv.id,
            role="assistant",
            content=msg_text,
        )
        session.add(new_msg)
        await session.commit()
        await session.refresh(new_msg)

        # Envoi en direct sur WhatsApp au client
        phone = conv.customer.whatsapp_phone_number if conv.customer else None
        if phone:
            try:
                from app.whatsapp.client import send_text_message

                await send_text_message(to=phone, body=msg_text)
                logger.info(f"Réponse commerçant WhatsApp envoyée à {phone}")
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le message WhatsApp commerçant : {e}")

        return {
            "status": "sent",
            "message_id": str(new_msg.id),
            "content": new_msg.content,
            "created_at": new_msg.created_at.isoformat() if new_msg.created_at else None,
        }


@router.post("/handoffs/{conversation_id}/resolve")
async def resolve_handoff(
    conversation_id: uuid.UUID,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Résout l'intervention humaine, réactive l'agent commercial IA et confirme la reprise au client sur WhatsApp.
    """
    async with async_session() as session:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.customer))
            .where(
                Conversation.id == conversation_id,
                Conversation.business_id == business_id,
            )
        )
        conv = (await session.execute(stmt)).scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation introuvable")

        conv.status = "active"
        conv.handoff_reason = None
        resolution_msg = ConversationMessage(
            conversation_id=conv.id,
            role="assistant",
            content="[Note interne du système : L'intervention humaine demandée a été traitée et résolue par le commerçant. L'échange commercial normal reprend maintenant sans ré-escalade.]",
        )
        session.add(resolution_msg)
        await session.commit()

        # Notifier courtoisement le client sur WhatsApp
        phone = conv.customer.whatsapp_phone_number if conv.customer else None
        if phone:
            try:
                from app.whatsapp.client import send_text_message

                preferred_lang = getattr(conv.customer, "preferred_language", "fr")
                if preferred_lang == "bm":
                    close_msg = (
                        "🙏 *I ni ce i ka munyuli la !*\n\n"
                        "An ka dɛmɛbaga y'i ka kibaaru ɲɛnabɔ. "
                        "I bɛ se ka to k'i ka yamaruya (commande) kɛ an fɛ yan sisan !"
                    )
                else:
                    close_msg = (
                        "🙏 *Merci pour votre échange avec notre conseiller !*\n\n"
                        "Votre demande a bien été prise en charge. "
                        "Je reste à votre entière disposition pour vos commandes et questions sur notre boutique !"
                    )
                await send_text_message(to=phone, body=close_msg)
            except Exception as e:
                logger.warning(f"Échec notification WhatsApp clôture handoff : {e}")

        return {"status": "success", "message": "Conversation résolue. L'agent IA est réactivé."}
