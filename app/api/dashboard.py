"""
Endpoints pour les statistiques et indicateurs clés (KPIs) du Dashboard.
"""

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_business_id
from app.db.session import async_session
from app.models import Business, Conversation, ConversationMessage, Customer, Order, OrderItem, OrderStatus, Product

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def get_dashboard_stats(business_id: uuid.UUID = Depends(get_current_business_id)):
    async with async_session() as session:
        business = (
            await session.execute(select(Business).where(Business.id == business_id))
        ).scalar_one_or_none()
        if not business:
            raise HTTPException(status_code=404, detail="Commerce introuvable")

        stmt_cust = select(func.count(Customer.id)).where(Customer.business_id == business.id)
        total_customers = (await session.execute(stmt_cust)).scalar() or 0

        stmt_orders = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.business_id == business.id)
            .order_by(Order.created_at.desc())
        )
        orders = (await session.execute(stmt_orders)).scalars().all()

        now_date = datetime.now(timezone.utc).date()
        today_orders = [o for o in orders if o.created_at and o.created_at.date() == now_date]

        today_orders_count = len(today_orders)
        pending_orders_count = len([o for o in orders if o.status == OrderStatus.PENDING])

        total_revenue = sum((o.total_amount for o in orders if o.status != OrderStatus.CANCELLED), start=0)
        today_revenue = sum((o.total_amount for o in today_orders if o.status != OrderStatus.CANCELLED), start=0)

        stmt_prods = select(Product).where(Product.business_id == business.id)
        products = (await session.execute(stmt_prods)).scalars().all()

        low_stock_products = [
            {
                "id": str(p.id),
                "name": p.name,
                "category": p.category,
                "price": int(p.price),
                "stock_quantity": p.stock_quantity,
            }
            for p in products
            if p.stock_quantity <= 3
        ]

        stmt_handoffs_cnt = select(func.count(Conversation.id)).where(
            Conversation.business_id == business.id,
            Conversation.status == "needs_human",
        )
        pending_handoffs_count = (await session.execute(stmt_handoffs_cnt)).scalar() or 0

        recent_orders = []
        for o in orders[:5]:
            recent_orders.append({
                "id": str(o.id),
                "short_id": str(o.id)[:8].upper(),
                "customer_id": str(o.customer_id),
                "status": o.status.value,
                "total_amount": int(o.total_amount),
                "delivery_address": o.delivery_address,
                "delivery_fee": int(o.delivery_fee or 0),
                "items_count": len(o.items),
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })

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
                for m in (c.messages[-6:] if c.messages else [])
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


@router.post("/handoffs/{conversation_id}/resolve")
async def resolve_handoff(
    conversation_id: uuid.UUID, business_id: uuid.UUID = Depends(get_current_business_id)
):
    async with async_session() as session:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.business_id == business_id,
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
        return {"status": "success", "message": "Conversation résolue. L'agent IA est réactivé."}
