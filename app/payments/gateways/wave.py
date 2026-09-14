"""
WavePaymentGateway : Connecteur officiel Wave Checkout API (Réservé Phase 2 — Production).

Documentation officielle : https://docs.wave.com/checkout
Ce module prépare l'intégration de production avec l'API Wave Mali :
- Session checkout (POST /v1/checkout/sessions)
- Vérification cryptographique des signatures de webhooks (Wave-Signature)
- Gestion des devises XOF (FCFA) et deep-links mobiles

Note : En phase actuelle V2.1 (développement), le mode actif est PAYMENT_PROVIDER=mock.
Toute tentative d'utilisation directe en production sans clés marchandes lève NotImplementedError.
"""

from app.core.config import settings
from app.payments.base import (
    BasePaymentGateway,
    PaymentInitiateRequest,
    PaymentInitiateResult,
    PaymentVerifyResult,
    PaymentWebhookResult,
)


class WavePaymentGateway(BasePaymentGateway):
    """
    Passerelle de paiement Wave Mali pour la Phase 2 (Production).
    Prête pour injection des credentials marchands :
    - WAVE_API_KEY
    - WAVE_API_URL
    - WAVE_WEBHOOK_SECRET
    """

    def __init__(self):
        self.api_key = settings.wave_api_key
        self.api_url = settings.wave_api_url or "https://api.wave.com/v1/checkout/sessions"
        self.webhook_secret = settings.wave_webhook_secret

    async def initiate_payment(self, request: PaymentInitiateRequest) -> PaymentInitiateResult:
        """
        Initie une session de paiement Wave Checkout officielle.
        TODO Phase 2 :
        1. Requête HTTP POST sécurisée vers self.api_url avec header Authorization: Bearer {self.api_key}
        2. Payload : {
               "amount": str(request.amount),
               "currency": "XOF",
               "client_reference": str(request.order_id),
               "success_url": request.return_url,
               "error_url": request.return_url
           }
        3. Retourner checkout_url = response.json()["wave_launch_url"]
        """
        raise NotImplementedError(
            "WavePaymentGateway n'est pas encore actif en production. "
            "Configurez WAVE_API_KEY et passez PAYMENT_MODE=production après signature du contrat marchand Wave."
        )

    async def verify_payment(self, transaction_ref: str) -> PaymentVerifyResult:
        """
        Interroge l'API Wave pour vérifier l'état de la session.
        TODO Phase 2 :
        GET https://api.wave.com/v1/checkout/sessions/{session_id}
        """
        raise NotImplementedError(
            "Vérification d'API Wave réservée à la phase 2 de production."
        )

    async def process_webhook(self, payload: dict, headers: dict) -> PaymentWebhookResult:
        """
        Traite un webhook officiel envoyé par Wave.
        TODO Phase 2 :
        1. Vérifier le header 'Wave-Signature' via HMAC-SHA256 avec self.webhook_secret
        2. Parser l'événement checkout.session.completed
        3. Extraire provider_event_id = payload['id'] pour garantir l'idempotence
        """
        raise NotImplementedError(
            "Traitement des webhooks réels Wave réservé à la phase 2 de production."
        )
