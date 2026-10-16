import uuid

from sqlalchemy import select

from app.db.session import async_session
from app.models import Business, Customer, Order, OrderStatus, Product, StockMovement, StockMovementType
from app.services.stock import record_stock_movement


async def test_record_stock_movement_updates_stock_and_creates_journal():
    async with async_session() as session:
        business = Business(
            name="Boutique Test",
            whatsapp_phone_number=f"+223{uuid.uuid4().hex[:8]}",
            currency="XOF",
        )
        session.add(business)
        await session.flush()

        product = Product(
            business_id=business.id,
            name="Téléphone test",
            category="téléphone",
            price=50000,
            stock_quantity=10,
            low_stock_threshold=3,
        )
        session.add(product)
        await session.flush()

        customer = Customer(
            business_id=business.id,
            whatsapp_phone_number=f"+223{uuid.uuid4().hex[:8]}",
            display_name="Client test",
        )
        session.add(customer)
        await session.flush()

        order = Order(
            business_id=business.id,
            customer_id=customer.id,
            status=OrderStatus.PENDING,
            delivery_address="Bamako",
            delivery_fee=0,
        )
        session.add(order)
        await session.flush()

        movement = await record_stock_movement(
            session,
            product,
            -2,
            StockMovementType.SALE,
            reason="ventes whatsapp",
            order_id=order.id,
        )

        assert product.stock_quantity == 8
        assert movement.quantity_before == 10
        assert movement.quantity_after == 8
        assert movement.quantity_change == -2
        assert movement.movement_type == StockMovementType.SALE
        assert movement.order_id == order.id

        await session.commit()

        stored = (
            await session.execute(
                select(StockMovement).where(StockMovement.product_id == product.id)
            )
        ).scalars().one()

        assert stored.quantity_change == -2
        assert stored.quantity_after == 8
