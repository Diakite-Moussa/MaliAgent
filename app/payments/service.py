"""
PaymentService : Orchestrateur central des paiements Mobile Money.

Section V2.1 du projet MaliAgent.
Gère :
- Le choix dynamique du gateway (Mock, Wave, Orange Money) selon la configuration et le mode
- L'isolation multi-tenant stricte par business_id
- L'idempotence absolue des webhooks (provider_event_id)
- La réconciliation automatique de bout en bout (Payment -> Order -> Invoice -> Notification WhatsApp)
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.payments.base import BasePaymentGateway, PaymentInitiateRequest
from app.payments.gateways.mock import MockPaymentGateway
from app.payments.gateways.orange_money import OrangeMoneyPaymentGateway
from app.payments.gateways.wave import WavePaymentGateway
from app.whatsapp.client import send_text_message

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self):
        self._mock_gateway = MockPaymentGateway()
        self._wave_gateway = WavePaymentGateway()
        self._orange_gateway = OrangeMoneyPaymentGateway()

    def get_gateway(self, provider_hint: str | None = None) -> BasePaymentGateway:
        """
        Sélectionne la gateway appropriée.
        En phase de développement / simulation (PAYMENT_MODE=simulation ou PAYMENT_PROVIDER=mock),
        MockPaymentGateway est toujours retournée pour tester 100% du flux sans argent réel.
        En production, retourne Wave ou Orange Money selon le provider spécifié.
        """
        if settings.is_payment_simulation:
            return self._mock_gateway

        p = (provider_hint or settings.payment_provider).lower()
        if "wave" in p:
            return self._wave_gateway
        elif "orange" in p:
            return self._orange_gateway
        return self._mock_gateway

    async def initiate_payment(
        self,
        session: AsyncSession,
        business_id: uuid.UUID,
        order_id: uuid.UUID,
        provider: str = "mock",
        customer_phone: str | None = None,
        return_url: str | None = None,
    ) -> Payment:
        """
        Initie une transaction de paiement pour une commande donnée.
        Vérifie l'isolation multi-tenant et crée l'enregistrement en base.
        """
        # 1. Vérifier la commande et l'isolation tenant
        stmt = (
            select(Order)
            .where(Order.id == order_id, Order.business_id == business_id)
            .options(selectinload(Order.customer), selectinload(Order.items), selectinload(Order.payments))
        )
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            raise ValueError(f"Commande introuvable ou non autorisée pour ce business : {order_id}")

        if order.payment_status == "paid":
            raise ValueError(f"La commande {order_id} est déjà réglée.")

        customer = order.customer
        phone = customer_phone or (customer.whatsapp_phone_number if customer else None)
        amount = Decimal(str(order.total_amount))

        # 2. Appel de la Gateway
        gateway = self.get_gateway(provider)
        req = PaymentInitiateRequest(
            order_id=order.id,
            business_id=business_id,
            customer_id=order.customer_id,
            amount=amount,
            currency="XOF",
            customer_phone=phone,
            customer_name=customer.display_name if customer else "Client",
            order_ref=f"#{str(order.id)[:8]}",
            provider_name=provider,
            return_url=return_url or f"{settings.public_base_url}/api/delivery/track/{order.id}",
        )

        init_result = await gateway.initiate_payment(req)
        if not init_result.success:
            raise RuntimeError(f"Échec d'initiation du paiement : {init_result.error_message}")

        # 3. Création du record Payment
        payment = Payment(
            business_id=business_id,
            order_id=order.id,
            customer_id=order.customer_id,
            provider=init_result.provider,
            amount=amount,
            currency="XOF",
            status=init_result.status,
            transaction_reference=init_result.transaction_reference,
            provider_tx_id=init_result.provider_tx_id,
            customer_phone=phone,
            checkout_url=init_result.checkout_url,
            qr_code_url=init_result.qr_code_url,
            raw_metadata=init_result.raw_response,
        )
        session.add(payment)

        # 4. Mise à jour de la commande
        order.payment_status = "pending"
        order.payment_method = init_result.provider

        await session.commit()
        await session.refresh(payment)
        logger.info(
            "Paiement initié avec succès: ref=%s, provider=%s, amount=%s",
            payment.transaction_reference,
            payment.provider,
            payment.amount,
        )
        return payment

    async def handle_webhook(
        self,
        session: AsyncSession,
        provider: str,
        payload: dict,
        headers: dict,
    ) -> dict:
        """
        Traite un webhook opérateur entrant avec réconciliation automatique et IDEMPOTENCE ABSOLUE.
        """
        gateway = self.get_gateway(provider)
        wh_result = await gateway.process_webhook(payload, headers)

        if not wh_result.success or not wh_result.handled:
            logger.warning("Webhook ignoré ou non valide: %s", wh_result.error_message)
            return {"status": "ignored", "error": wh_result.error_message}

        # --- CONTRÔLE D'IDEMPOTENCE STRICT ---
        # 1. Vérifier si cet événement exact a déjà été traité
        if wh_result.provider_event_id:
            dup_stmt = select(Payment).where(Payment.provider_event_id == wh_result.provider_event_id)
            dup_res = await session.execute(dup_stmt)
            if dup_res.scalar_one_or_none():
                logger.info("Webhook déjà traité (idempotence event_id=%s)", wh_result.provider_event_id)
                return {
                    "status": "already_processed",
                    "transaction_reference": wh_result.transaction_reference,
                    "payment_status": wh_result.status.value,
                    "message": "Événement webhook déjà exécuté (idempotent).",
                }

        # 2. Récupérer le paiement correspondant
        stmt = (
            select(Payment)
            .where(Payment.transaction_reference == wh_result.transaction_reference)
            .options(
                selectinload(Payment.order).selectinload(Order.customer),
                selectinload(Payment.order).selectinload(Order.items),
            )
        )
        res = await session.execute(stmt)
        payment = res.scalar_one_or_none()

        if not payment:
            logger.error("Paiement introuvable pour la transaction: %s", wh_result.transaction_reference)
            return {
                "status": "not_found",
                "transaction_reference": wh_result.transaction_reference,
                "error": "Transaction introuvable en base.",
            }

        # 3. Si déjà en statut SUCCESS et que le webhook est SUCCESS, éviter les doubles effets de bord
        if payment.status == PaymentStatus.SUCCESS and wh_result.status == PaymentStatus.SUCCESS:
            logger.info("Paiement déjà marqué SUCCESS: %s", payment.transaction_reference)
            return {
                "status": "already_processed",
                "transaction_reference": payment.transaction_reference,
                "payment_status": payment.status.value,
            }

        # 4. Mise à jour de l'état du paiement
        payment.status = wh_result.status
        payment.provider_event_id = wh_result.provider_event_id
        if wh_result.provider_tx_id:
            payment.provider_tx_id = wh_result.provider_tx_id
        if wh_result.paid_at:
            payment.paid_at = wh_result.paid_at
        payment.raw_metadata = wh_result.raw_event

        # --- RÉCONCILIATION COMMANDE & FACTURE ---
        order = payment.order
        if wh_result.status == PaymentStatus.SUCCESS:
            if order:
                order.payment_status = "paid"
                if order.status == OrderStatus.PENDING:
                    order.status = OrderStatus.CONFIRMED

                # Recherche et mise à jour de la facture
                inv_stmt = select(Invoice).where(Invoice.order_id == order.id)
                inv_res = await session.execute(inv_stmt)
                invoice = inv_res.scalar_one_or_none()
                if invoice:
                    invoice.status = "paid"
                    invoice.payment_method = payment.provider
                    invoice.payment_reference = payment.transaction_reference

                # Notification WhatsApp automatique au client
                customer_phone = payment.customer_phone or (order.customer.whatsapp_phone_number if order.customer else None)
                if customer_phone:
                    try:
                        provider_clean = (
                            "Wave"
                            if "wave" in payment.provider
                            else "Orange Money"
                            if "orange" in payment.provider
                            else "Paiement Mobile"
                        )
                        order_short = f"#{str(order.id)[:8]}"
                        msg_wa = (
                            f"✅ *Paiement reçu avec succès !*\n\n"
                            f"Votre paiement de *{int(payment.amount):,} FCFA* via *{provider_clean}* "
                            f"a bien été validé.\n"
                            f"• Réf transaction : `{payment.transaction_reference}`\n"
                            f"• Commande : `{order_short}` confirmée et en cours de préparation.\n\n"
                            f"Merci pour votre confiance ! 🙏"
                        )
                        await send_text_message(customer_phone, msg_wa)
                        logger.info("Notification WhatsApp paiement envoyée à %s", customer_phone)
                    except Exception as exc:
                        logger.error("Erreur notification WhatsApp paiement: %s", exc)

        elif wh_result.status in (PaymentStatus.FAILED, PaymentStatus.EXPIRED, PaymentStatus.CANCELLED):
            if order and order.payment_status == "pending":
                order.payment_status = "unpaid"

        await session.commit()
        await session.refresh(payment)

        return {
            "status": "processed",
            "transaction_reference": payment.transaction_reference,
            "payment_status": payment.status.value,
            "order_id": order.id if order else None,
        }

    async def simulate_payment(
        self,
        session: AsyncSession,
        transaction_reference: str,
        outcome: str = "success",
        amount: Decimal | None = None,
        event_id: str | None = None,
    ) -> dict:
        """
        Déclenche la simulation d'un webhook opérateur.
        STRICTEMENT RÉSERVÉ au mode simulation / dev.
        """
        if not settings.is_payment_simulation:
            raise PermissionError("La simulation de webhook est formellement interdite en mode production.")

        mock_payload = MockPaymentGateway.build_simulated_webhook(
            transaction_reference=transaction_reference,
            outcome=outcome,
            event_id=event_id,
            amount=amount,
        )
        return await self.handle_webhook(
            session=session,
            provider="mock",
            payload=mock_payload,
            headers={"X-Mock-Simulate": "true"},
        )

    async def get_payment_status(
        self,
        session: AsyncSession,
        business_id: uuid.UUID,
        payment_id_or_ref: str,
    ) -> Payment | None:
        """Récupère un paiement en garantissant l'isolation multi-tenant."""
        try:
            p_uuid = uuid.UUID(payment_id_or_ref)
            stmt = select(Payment).where(Payment.id == p_uuid, Payment.business_id == business_id)
        except ValueError:
            stmt = select(Payment).where(
                Payment.transaction_reference == payment_id_or_ref,
                Payment.business_id == business_id,
            )

        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_payments(
        self,
        session: AsyncSession,
        business_id: uuid.UUID,
        status: str | None = None,
        provider: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Payment]:
        """Liste les paiements pour le dashboard commerçant."""
        query = (
            select(Payment)
            .where(Payment.business_id == business_id)
            .options(selectinload(Payment.order), selectinload(Payment.customer))
            .order_by(desc(Payment.created_at))
            .limit(limit)
            .offset(offset)
        )
        if status:
            query = query.where(Payment.status == status)
        if provider:
            query = query.where(Payment.provider.ilike(f"%{provider}%"))

        res = await session.execute(query)
        return list(res.scalars().all())


payment_service = PaymentService()
