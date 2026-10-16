"""
Endpoints REST pour les paiements Mobile Money (Section V2.1).

Routes :
- POST /api/payments/initiate : Initialiser une session de paiement
- GET /api/payments/{payment_id}/status : Consulter le statut d'un paiement
- GET /api/payments : Lister les paiements du business (Dashboard)
- POST /api/payments/webhook/{provider} : Réception des webhooks opérateurs
- POST /api/payments/simulate-webhook : Simulation de callback (mode DEV uniquement)
- GET /api/payments/mock-checkout/{tx_ref} : Page HTML de test simulant l'écran mobile
"""

from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import get_current_business_id
from app.db.session import async_session
from app.models.payment import Payment
from app.payments.schemas import (
    PaymentInitiateIn,
    PaymentInitiateOut,
    PaymentStatusOut,
    PaymentWebhookOut,
    SimulateWebhookIn,
)
from app.payments.service import payment_service

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/initiate", response_model=PaymentInitiateOut)
async def initiate_payment(
    body: PaymentInitiateIn,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """Initie une transaction de paiement pour une commande du business connecté."""
    async with async_session() as db:
        try:
            payment = await payment_service.initiate_payment(
                session=db,
                business_id=business_id,
                order_id=body.order_id,
                provider=body.provider,
                customer_phone=body.customer_phone,
                return_url=body.return_url,
                force_new=body.force_new,
            )
            return PaymentInitiateOut(
                payment_id=payment.id,
                order_id=payment.order_id,
                transaction_reference=payment.transaction_reference,
                provider=payment.provider,
                status=payment.status.value,
                amount=payment.amount,
                currency=payment.currency,
                checkout_url=payment.checkout_url,
                qr_code_url=payment.qr_code_url,
                instructions=(
                    f"Lien de paiement généré pour {payment.amount} {payment.currency} ({payment.provider})."
                ),
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=list[PaymentStatusOut])
async def list_payments(
    status_filter: str | None = Query(None, alias="status"),
    provider_filter: str | None = Query(None, alias="provider"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """Liste tous les paiements du business pour le Dashboard commerçant."""
    async with async_session() as db:
        payments = await payment_service.list_payments(
            session=db,
            business_id=business_id,
            status=status_filter,
            provider=provider_filter,
            limit=limit,
            offset=offset,
        )
        return [
            PaymentStatusOut(
                id=p.id,
                order_id=p.order_id,
                transaction_reference=p.transaction_reference,
                provider=p.provider,
                status=p.status.value,
                amount=p.amount,
                currency=p.currency,
                customer_phone=p.customer_phone,
                checkout_url=p.checkout_url,
                paid_at=p.paid_at,
                created_at=p.created_at,
            )
            for p in payments
        ]


@router.get("/{payment_id_or_ref}/status", response_model=PaymentStatusOut)
async def get_payment_status(
    payment_id_or_ref: str,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """Consulte le statut d'une transaction."""
    async with async_session() as db:
        payment = await payment_service.get_payment_status(
            session=db,
            business_id=business_id,
            payment_id_or_ref=payment_id_or_ref,
        )
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction introuvable.")

        return PaymentStatusOut(
            id=payment.id,
            order_id=payment.order_id,
            transaction_reference=payment.transaction_reference,
            provider=payment.provider,
            status=payment.status.value,
            amount=payment.amount,
            currency=payment.currency,
            customer_phone=payment.customer_phone,
            checkout_url=payment.checkout_url,
            paid_at=payment.paid_at,
            created_at=payment.created_at,
        )


@router.post("/webhook/{provider}", response_model=PaymentWebhookOut)
async def payment_webhook(
    provider: str,
    request: Request,
):
    """
    Endpoint public de callback recevant les webhooks de notification des opérateurs.
    Gère Wave, Orange Money et Mock.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    headers = dict(request.headers)
    async with async_session() as db:
        result = await payment_service.handle_webhook(
            session=db,
            provider=provider,
            payload=payload,
            headers=headers,
        )

        if result.get("status") in ("not_found", "error"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "Erreur webhook"))

        return PaymentWebhookOut(
            status=result.get("status", "processed"),
            transaction_reference=result.get("transaction_reference", ""),
            payment_status=result.get("payment_status", ""),
            order_id=result.get("order_id"),
            message=result.get("message"),
        )


@router.post("/simulate-webhook", response_model=PaymentWebhookOut)
async def simulate_webhook(
    body: SimulateWebhookIn,
):
    """
    Simule la validation ou l'échec d'un paiement en 1 clic.
    STRICTEMENT PROTÉGÉ : Bloqué si PAYMENT_MODE != 'simulation'.
    """
    if not settings.is_payment_simulation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La simulation de webhook est formellement interdite en mode production.",
        )

    async with async_session() as db:
        try:
            result = await payment_service.simulate_payment(
                session=db,
                transaction_reference=body.transaction_reference,
                outcome=body.outcome,
                amount=body.amount,
                event_id=body.event_id,
            )
            return PaymentWebhookOut(
                status=result.get("status", "processed"),
                transaction_reference=result.get("transaction_reference", body.transaction_reference),
                payment_status=result.get("payment_status", ""),
                order_id=result.get("order_id"),
                message=result.get("message", f"Simulation exécutée avec statut {body.outcome}"),
            )
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/mock-checkout/{tx_ref}", response_class=HTMLResponse)
async def mock_checkout_page(
    tx_ref: str,
):
    """
    Page Web de simulation simulant l'écran mobile de Wave ou Orange Money.
    Permet au développeur ou au testeur de cliquer sur 'Confirmer le paiement'
    pour déclencher le webhook automatiquement.
    """
    if not settings.is_payment_simulation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Non disponible en production")

    async with async_session() as db:
        stmt = select(Payment).where(Payment.transaction_reference == tx_ref)
        res = await db.execute(stmt)
        payment = res.scalar_one_or_none()

    if not payment:
        return HTMLResponse("<h2>Transaction introuvable</h2>", status_code=404)

    p_lower = payment.provider.lower()
    if "wave" in p_lower:
        provider_title = "Wave Mali 🌊"
        provider_color = "#1DA1F2"
        provider_hint = "Validation instantanée via votre application Wave"
    elif "orange" in p_lower:
        provider_title = "Orange Money Mali 🍊"
        provider_color = "#FF7900"
        provider_hint = "Validation par code secret #144# ou invite Push USSD"
    elif "moov" in p_lower or "malitel" in p_lower:
        provider_title = "Moov Money Mali 🔵"
        provider_color = "#005BAA"
        provider_hint = "Validation par code secret *166# ou invite Push USSD"
    else:
        provider_title = "Mobile Money Mali 💳"
        provider_color = "#10B981"
        provider_hint = "Validation de transaction sécurisée"

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{provider_title} — Simulation de Paiement</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 16px;
        }}
        .card {{
            background: #1e293b;
            border-radius: 16px;
            padding: 24px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            text-align: center;
            border-top: 6px solid {provider_color};
        }}
        .badge {{
            display: inline-block;
            background: rgba(255,255,255,0.1);
            color: {provider_color};
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 12px;
        }}
        .amount {{
            font-size: 32px;
            font-weight: 800;
            margin: 12px 0;
            color: #ffffff;
        }}
        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #334155;
            font-size: 14px;
            color: #94a3b8;
        }}
        .info-value {{
            font-weight: 600;
            color: #f8fafc;
        }}
        .btn {{
            width: 100%;
            padding: 14px;
            border-radius: 10px;
            border: none;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            margin-top: 16px;
            transition: all 0.2s;
        }}
        .btn-pay {{
            background: {provider_color};
            color: white;
        }}
        .btn-pay:hover {{
            opacity: 0.9;
            transform: translateY(-1px);
        }}
        .btn-fail {{
            background: #ef4444;
            color: white;
            margin-top: 8px;
        }}
        .alert {{
            margin-top: 16px;
            padding: 12px;
            border-radius: 8px;
            display: none;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">SIMULATION V2.1 — MALIAGENT</span>
        <h2>{provider_title}</h2>
        <p style="color: #94a3b8; font-size: 13px;">Validation sécurisée de votre commande</p>

        <div class="amount">{int(payment.amount):,} {payment.currency}</div>

        <div class="info-row">
            <span>Référence :</span>
            <span class="info-value">{payment.transaction_reference}</span>
        </div>
        <div class="info-row">
            <span>Téléphone :</span>
            <span class="info-value">{payment.customer_phone or "Non renseigné"}</span>
        </div>
        <div class="info-row">
            <span>Statut actuel :</span>
            <span class="info-value" id="status-label">{payment.status.value.upper()}</span>
        </div>

        <button class="btn btn-pay" id="btn-success" onclick="triggerSimulation('success')">
            ✅ Valider le paiement (Succès)
        </button>
        <button class="btn btn-fail" id="btn-fail" onclick="triggerSimulation('failed')">
            ❌ Simuler un rejet (Solde insuffisant)
        </button>

        <div id="result-box" class="alert"></div>
    </div>

    <script>
        async function triggerSimulation(outcome) {{
            const btnSuccess = document.getElementById('btn-success');
            const btnFail = document.getElementById('btn-fail');
            const box = document.getElementById('result-box');
            btnSuccess.disabled = true;
            btnFail.disabled = true;

            try {{
                const res = await fetch('/api/payments/simulate-webhook', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        transaction_reference: '{payment.transaction_reference}',
                        outcome: outcome
                    }})
                }});
                const data = await res.json();
                box.style.display = 'block';
                if (res.ok) {{
                    box.style.background = outcome === 'success' ? '#065f46' : '#7f1d1d';
                    box.style.color = '#ffffff';
                    box.innerText = outcome === 'success'
                        ? '🎉 Paiement confirmé ! Commande validée et notification WhatsApp émise.'
                        : '⚠️ Transaction rejetée.';
                    document.getElementById('status-label').innerText = data.payment_status.toUpperCase();
                }} else {{
                    box.style.background = '#7f1d1d';
                    box.innerText = 'Erreur : ' + (data.detail || 'Échec');
                }}
            }} catch (err) {{
                box.style.display = 'block';
                box.style.background = '#7f1d1d';
                box.innerText = 'Erreur réseau : ' + err.message;
            }}
        }}
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
