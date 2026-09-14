"""
Schémas Pydantic pour l'API de paiement (Section V2.1).
"""

from datetime import datetime
from decimal import Decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PaymentInitiateIn(BaseModel):
    order_id: uuid.UUID
    provider: str = Field(default="mock", description="'mock', 'wave', 'orange_money', 'cash'")
    customer_phone: str | None = None
    return_url: str | None = None


class PaymentInitiateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: uuid.UUID
    order_id: uuid.UUID
    transaction_reference: str
    provider: str
    status: str
    amount: Decimal
    currency: str
    checkout_url: str | None = None
    qr_code_url: str | None = None
    instructions: str | None = None


class PaymentStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    transaction_reference: str
    provider: str
    status: str
    amount: Decimal
    currency: str
    customer_phone: str | None = None
    checkout_url: str | None = None
    paid_at: datetime | None = None
    created_at: datetime


class SimulateWebhookIn(BaseModel):
    transaction_reference: str
    outcome: str = Field(default="success", description="'success', 'failed', 'expired'")
    amount: Decimal | None = None
    event_id: str | None = None


class PaymentWebhookOut(BaseModel):
    status: str
    transaction_reference: str
    payment_status: str
    order_id: uuid.UUID | None = None
    message: str | None = None
