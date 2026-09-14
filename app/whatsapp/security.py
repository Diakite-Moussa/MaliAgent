
"""
Vérification de signature des requêtes webhook Meta (WhatsApp Cloud API).

Meta signe chaque payload webhook avec l'App Secret et l'envoie dans le
header X-Hub-Signature-256. Sans cette vérification, n'importe qui
connaissant l'URL du webhook peut poster un faux message et déclencher
l'agent (créer des commandes, etc.).

Référence : https://developers.facebook.com/docs/graph-api/webhooks/getting-started#validate-payloads
"""

import hashlib
import hmac


def verify_meta_signature(payload_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    if not app_secret:
        # Pas d'App Secret configuré : on refuse par défaut plutôt que
        # de laisser passer silencieusement en "faux positif ouvert".
        return False

    expected_signature = signature_header.split("sha256=", 1)[1]
    computed_signature = hmac.new(
        app_secret.encode("utf-8"), payload_body, hashlib.sha256
    ).hexdigest()

    # compare_digest évite les attaques par timing sur la comparaison
    return hmac.compare_digest(computed_signature, expected_signature)