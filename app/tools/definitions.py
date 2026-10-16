"""
Définitions des tools exposés au LLM — indépendantes de leur exécution.
"""

from app.llm.base import ToolDefinition

TOOLS = [
    ToolDefinition(
        name="search_products",
        description=(
            "Recherche des produits dans le catalogue par nom OU par catégorie "
            "(ex. 'téléphone', 'alimentation'). Utilise ce tool pour toute "
            "question sur la disponibilité ou le prix d'un produit."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nom ou catégorie recherchée"},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="check_stock",
        description="Vérifie le stock disponible pour un produit précis (et optionnellement pour une déclinaison : taille, couleur, capacité).",
        parameters={
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Nom exact du produit"},
                "variant": {
                    "type": "string",
                    "description": "Déclinaison spécifique si demandée (ex: '128Go', 'XL', 'Noir')",
                },
            },
            "required": ["product_name"],
        },
    ),
    ToolDefinition(
        name="send_product_photo",
        description=(
            "Envoie la photo officielle d'un produit au client directement sur WhatsApp. "
            "Utilise ce tool dès que le client souhaite voir un produit ou en demande une image "
            "(ex: 'envoyez-moi une photo', 'vous avez une image ?', 'montrez-moi le produit')."
        ),
        parameters={
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "Nom ou mot-clé du produit dont le client souhaite voir la photo",
                },
            },
            "required": ["product_name"],
        },
    ),
    ToolDefinition(
        name="calculate_delivery",
        description=(
            "Calcule les frais et délais de livraison pour un quartier, une commune ou "
            "un lieu précis (ex. 'ACI 2000', 'Faladié', 'Kati', 'retrait en magasin') "
            "OU à partir des coordonnées GPS (latitude, longitude) partagées par le client sur WhatsApp. "
            "Utilise TOUJOURS ce tool quand le client mentionne un lieu de livraison, partage sa position GPS, "
            "ou demande combien coûte la livraison."
        ),
        parameters={
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Nom du quartier, commune ou lieu indiqué par le client (optionnel si coordonnées GPS fournies)",
                },
                "latitude": {
                    "type": "number",
                    "description": "Latitude GPS exacte partagée par le client via WhatsApp (ex: 12.63214)",
                },
                "longitude": {
                    "type": "number",
                    "description": "Longitude GPS exacte partagée par le client via WhatsApp (ex: -8.02547)",
                },
            },
        },
    ),
    ToolDefinition(
        name="create_order",
        description=(
            "Enregistre définitivement une commande dans le système après CONFIRMATION EXPLICITE "
            "du client (suite à un récapitulatif détaillé contenant : articles, variantes, quantités, total "
            "et frais de livraison). Ne JAMAIS appeler ce tool sans l'accord clair du client."
        ),
        parameters={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Liste des articles commandés",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_name": {
                                "type": "string",
                                "description": "Nom du produit commandé",
                            },
                            "variant": {
                                "type": "string",
                                "description": "Variante ou déclinaison choisie si le produit en possède (ex: '128Go', 'Noir', 'XL')",
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "Quantité commandée (au moins 1)",
                            },
                        },
                        "required": ["product_name", "quantity"],
                    },
                },
                "delivery_address": {
                    "type": "string",
                    "description": "Adresse, quartier ou lieu de livraison (ou 'Retrait en boutique')",
                },
                "delivery_fee": {
                    "type": "number",
                    "description": "Frais de livraison calculés via calculate_delivery (0 si retrait en boutique)",
                },
                "latitude": {
                    "type": "number",
                    "description": "Latitude GPS de destination si partagée par le client",
                },
                "longitude": {
                    "type": "number",
                    "description": "Longitude GPS de destination si partagée par le client",
                },
                "allow_partial": {
                    "type": "boolean",
                    "description": "Si vrai, valide la commande avec les stocks disponibles maximums en cas de rupture partielle sur un article.",
                },
            },
            "required": ["items", "delivery_address"],
        },
    ),
    ToolDefinition(
        name="get_order_status",
        description=(
            "Consulte l'état et le détail de la commande récente du client "
            "(ex. 'Où en est ma commande ?', 'Statut de ma commande')."
        ),
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    ToolDefinition(
        name="generate_invoice",
        description=(
            "Génère la facture commerciale officielle au format PDF pour la commande récente "
            "du client (ou par référence de commande) et fournit le lien de téléchargement. "
            "Utilise ce tool dès que le client demande sa facture ('Envoyez-moi la facture', "
            "'Je veux ma facture', 'facture pdf', etc.)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "order_ref": {
                    "type": "string",
                    "description": "Référence ou numéro de commande optionnel (ex. '#A8AC3CD7'). Si omis, sélectionne automatiquement la dernière commande du client.",
                },
            },
        },
    ),
    ToolDefinition(
        name="escalate_to_human",
        description=(
            "Transfère immédiatement la conversation à un responsable ou conseiller humain de la boutique. "
            "Utilise ce tool dès que le client demande explicitement à parler à un humain en français ou bambara ('je veux parler au patron', "
            "'passez-moi un conseiller', 'appelez-moi un responsable', 'mɔgɔ bɛ yen wa', 'n'b'a fɛ ka kuma mɔgɔ yɛrɛ fɛ', 'kuma kuntigi fɛ'), "
            "lors d'une réclamation complexe, d'un problème de SAV, ou d'une demande de négociation de prix / remise impossible à traiter automatiquement."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Motif explicite du transfert vers l'humain (ex: 'demande de remise spéciale', 'réclamation livraison', 'demande de contact humain direct').",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["normal", "high", "critical"],
                    "description": "Niveau d'urgence du transfert.",
                },
            },
            "required": ["reason"],
        },
    ),
    ToolDefinition(
        name="update_order_address",
        description=(
            "Met à jour l'adresse ou le quartier de livraison d'une commande existante du client "
            "et recalcule automatiquement les frais de livraison. "
            "Utilise ce tool dès que le client indique qu'il se trouve dans un autre quartier "
            "ou souhaite modifier son lieu de livraison (ex. 'je suis à ACI 2000 pas à Faladié', "
            "'changez l'adresse pour ACI 2000', etc.)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "new_zone": {
                    "type": "string",
                    "description": "Nouveau quartier ou commune de livraison (ex: 'ACI 2000', 'Badalabougou')",
                },
                "order_ref": {
                    "type": "string",
                    "description": "Référence de la commande (ex: '#9783C39B'). Optionnel, cible la dernière commande si omis.",
                },
            },
            "required": ["new_zone"],
        },
    ),
    ToolDefinition(
        name="cancel_order",
        description=(
            "Annule une commande client non encore expédiée ou livrée, et remet automatiquement les produits en stock. "
            "Utilise ce tool si le client demande expressément à annuler sa commande."
        ),
        parameters={
            "type": "object",
            "properties": {
                "order_ref": {
                    "type": "string",
                    "description": "Référence ou numéro de commande (ex: '#B956F8AB' ou 'B956F8AB'). Si omis, cible la dernière commande en attente.",
                },
                "reason": {
                    "type": "string",
                    "description": "Motif de l'annulation exprimé par le client.",
                },
            },
        },
    ),
    ToolDefinition(
        name="initiate_payment",
        description=(
            "Initie une demande de règlement par Mobile Money (Wave, Orange Money, Moov Money) ou enregistre un paiement en espèces pour une commande. "
            "Utilise ce tool dès que le client indique comment il souhaite régler (ex: 'je veux payer par Wave', 'envoyez-moi le lien Wave', 'je paie par Orange Money', 'je veux payer par Moov Money', 'wari sara ni Wave ye', 'je préfère payer cash / wari kɛlɛn')."
        ),
        parameters={
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": "Opérateur de paiement choisi : 'wave' pour Wave, 'orange_money' pour Orange Money, 'moov_money' (ou 'moov') pour Moov Africa / Malitel, 'cash' pour paiement en espèces à la livraison.",
                },
                "customer_phone": {
                    "type": "string",
                    "description": "Numéro de téléphone du compte Mobile Money (ex: '76123456' ou '+22376123456'). Optionnel.",
                },
                "order_ref": {
                    "type": "string",
                    "description": "Référence de la commande (#...). Si omis, cible automatiquement la dernière commande en attente.",
                },
            },
            "required": ["provider"],
        },
    ),
    ToolDefinition(
        name="check_payment_status",
        description=(
            "Vérifie si le paiement d'une commande a été reçu et validé. "
            "Utilise ce tool si le client demande si son virement ou son paiement Mobile Money a été pris en compte."
        ),
        parameters={
            "type": "object",
            "properties": {
                "order_ref": {
                    "type": "string",
                    "description": "Référence de la commande (#...). Optionnel.",
                },
            },
        },
    ),
    ToolDefinition(
        name="search_knowledge_base",
        description=(
            "Recherche dans la base de connaissances de la boutique (FAQ, politique de retour, "
            "garanties, horaires, conditions spécifiques) pour répondre à une question du client "
            "qui n'est pas couverte par les autres tools (produits, commandes, livraison). "
            "Utilise ce tool avant de dire que tu ne sais pas répondre à une question générale sur la boutique."
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question du client, reformulée si besoin"},
                "query": {"type": "string", "description": "Sujet ou terme de recherche (synonyme de question)"},
            },
            "required": ["question"],
        },
    ),
]