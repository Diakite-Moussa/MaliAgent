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
        description="Vérifie le stock disponible pour un produit précis, par son nom exact.",
        parameters={
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Nom exact du produit"},
            },
            "required": ["product_name"],
        },
    ),
    ToolDefinition(
        name="calculate_delivery",
        description=(
            "Calcule les frais et délais de livraison pour un quartier, une commune ou "
            "un lieu précis (ex. 'ACI 2000', 'Faladié', 'Kati', 'retrait en magasin'). "
            "Utilise TOUJOURS ce tool quand le client mentionne un lieu de livraison ou "
            "demande combien coûte la livraison."
        ),
        parameters={
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Nom du quartier, commune ou lieu indiqué par le client",
                },
            },
            "required": ["zone"],
        },
    ),
    ToolDefinition(
        name="create_order",
        description=(
            "Enregistre définitivement une commande dans le système après CONFIRMATION EXPLICITE "
            "du client (suite à un récapitulatif détaillé contenant : articles, quantités, total "
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
            "Utilise ce tool dès que le client demande explicitement à parler à un humain ('je veux parler au patron', "
            "'passez-moi un conseiller', 'appelez-moi un responsable'), lors d'une réclamation complexe, "
            "ou d'une demande de négociation de prix / remise impossible à traiter automatiquement."
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
]