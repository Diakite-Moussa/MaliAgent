"""
Exécution des tools contre la vraie base de données.

Règle de sécurité du projet : business_id et customer_id viennent
TOUJOURS du contexte de la conversation (jamais des arguments fournis
par le LLM). Chaque requête est filtrée par business_id — c'est
l'isolation multi-tenant en pratique, pas seulement dans le schéma.
"""

import unicodedata
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    Business,
    Conversation,
    Customer,
    DeliveryZone,
    Invoice,
    Order,
    OrderItem,
    OrderStatus,
    Product,
)
from app.payments.service import payment_service
from app.services.invoice_generator import generate_invoice_pdf


def _normalize(s: str) -> str:
    """
    Normalise une chaîne pour un matching robuste aux variantes de
    formatage introduites par le LLM (tirets typographiques ‑/–/—
    copiés depuis ses propres réponses en Markdown, espaces multiples,
    casse, accents typographiques). Sans ça, un nom de produit ré-injecté
    depuis une réponse formatée peut ne plus matcher le nom en base.
    """
    s = unicodedata.normalize("NFKC", s or "")
    for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        s = s.replace(dash, "-")
    s = " ".join(s.split())
    return s.strip().lower()



async def execute_tool(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    tool_name: str,
    arguments: dict,
) -> str:
    if tool_name == "search_products":
        return await _search_products(session, business_id, arguments.get("query", ""))
    if tool_name == "check_stock":
        return await _check_stock(session, business_id, arguments.get("product_name", ""))
    if tool_name == "calculate_delivery":
        return await _calculate_delivery(session, business_id, arguments.get("zone", ""))
    if tool_name == "create_order":
        return await _create_order(
            session,
            business_id,
            customer_id,
            arguments.get("items", []),
            arguments.get("delivery_address", ""),
            arguments.get("delivery_fee", 0),
        )
    if tool_name == "get_order_status":
        return await _get_order_status(session, business_id, customer_id)
    if tool_name == "generate_invoice":
        return await _generate_invoice(
            session, business_id, customer_id, arguments.get("order_ref")
        )
    if tool_name == "escalate_to_human":
        return await _escalate_to_human(
            session,
            business_id,
            customer_id,
            arguments.get("reason", "Demande client"),
            arguments.get("urgency", "normal"),
        )
    if tool_name == "cancel_order":
        return await _cancel_order(
            session,
            business_id,
            customer_id,
            arguments.get("order_ref"),
            arguments.get("reason", "Demande client"),
        )
    if tool_name == "update_order_address":
        return await _update_order_address(
            session,
            business_id,
            customer_id,
            arguments.get("new_zone", ""),
            arguments.get("order_ref"),
        )
    if tool_name == "initiate_payment":
        return await _initiate_payment(
            session,
            business_id,
            customer_id,
            arguments.get("provider", "mock"),
            arguments.get("customer_phone"),
            arguments.get("order_ref"),
        )
    if tool_name == "check_payment_status":
        return await _check_payment_status(
            session,
            business_id,
            customer_id,
            arguments.get("order_ref"),
        )
    return f"Tool inconnu : {tool_name}"



async def _search_products(session: AsyncSession, business_id: uuid.UUID, query: str) -> str:
    query = _normalize(query)
    query_words = [w for w in query.split() if len(w) > 1]
    stmt = select(Product).where(Product.business_id == business_id)
    result = await session.execute(stmt)
    products = result.scalars().all()

    matches = [
        p
        for p in products
        if query in _normalize(p.name)
        or _normalize(p.name) in query
        or query in _normalize(p.category)
        or _normalize(p.category) in query
        or (query_words and all(w in _normalize(p.name) for w in query_words))
    ]

    if not matches:
        return "Aucun produit trouvé pour cette recherche."

    return "\n".join(
        f"- {p.name} : {int(p.price)} FCFA {p.stock_quantity and 'en stock (' + str(p.stock_quantity) + ' unités)' or 'RUPTURE DE STOCK'}"
        for p in matches
    )


async def _check_stock(session: AsyncSession, business_id: uuid.UUID, product_name: str) -> str:
    stmt = select(Product).where(
        Product.business_id == business_id,
        Product.name.ilike(product_name.strip()),
    )
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()

    if not product:
        # Recherche souple si pas de match exact
        normalized_name = _normalize(product_name)
        norm_words = [w for w in normalized_name.split() if len(w) > 1]
        stmt_all = select(Product).where(Product.business_id == business_id)
        all_prods = (await session.execute(stmt_all)).scalars().all()
        for p in all_prods:
            p_norm = _normalize(p.name)
            if (
                normalized_name in p_norm
                or p_norm in normalized_name
                or normalized_name.replace(" ", "") == p_norm.replace(" ", "")
                or (norm_words and all(w in p_norm for w in norm_words))
            ):
                product = p
                break

    if not product:
        return "Produit introuvable avec ce nom."
    return f"Stock de {product.name} : {product.stock_quantity} unité(s) au prix de {int(product.price)} FCFA."


async def _calculate_delivery(session: AsyncSession, business_id: uuid.UUID, zone: str) -> str:
    zone_clean = (zone or "").strip().lower()

    if any(k in zone_clean for k in ["retrait", "magasin", "boutique", "sur place", "passer chercher"]):
        return "Retrait gratuit en boutique (Frais : 0 FCFA, Délai : Immédiat aux heures d'ouverture)."

    stmt = select(DeliveryZone).where(
        DeliveryZone.business_id == business_id,
        DeliveryZone.active.is_(True),
    )
    result = await session.execute(stmt)
    zones = result.scalars().all()

    if not zones:
        return "Aucune zone de livraison configurée pour ce commerce. Proposez le retrait en boutique."

    matched: DeliveryZone | None = None
    for z in zones:
        if zone_clean in z.name.lower() or z.name.lower() in zone_clean:
            matched = z
            break
        if z.keywords:
            clean_kw_str = z.keywords.replace("{", "").replace("}", "").replace('"', '')
            keywords_list = [kw.strip().lower() for kw in clean_kw_str.split(",") if kw.strip()]
            if any(kw == zone_clean or kw in zone_clean or zone_clean in kw for kw in keywords_list):
                matched = z
                break

    if matched:
        fee_int = int(matched.fee)
        time_str = f" (Délai estimé : {matched.estimated_time})" if matched.estimated_time else ""
        return f"Oui, nous livrons à '{zone}'. Frais de livraison : {fee_int} FCFA{time_str} (Zone : {matched.name})."

    zones_list = "\n".join(
        f"- {z.name} : {int(z.fee)} FCFA ({z.estimated_time or 'délai standard'})" for z in zones
    )
    return (
        f"La zone '{zone}' n'est pas répertoriée directement dans nos tarifs. "
        f"Voici les zones habituellement desservies :\n{zones_list}\n"
        f"Précisez votre quartier parmi cette liste ou choisissez le retrait en boutique."
    )


def _find_alternative_product(
    all_products: list[Product], out_of_stock: Product, needed_qty: int
) -> Product | None:
    """
    Cherche un produit équivalent (même catégorie, en stock suffisant)
    pour proposer une alternative en cas de rupture.
    """
    candidates = [
        p
        for p in all_products
        if p.id != out_of_stock.id
        and p.category == out_of_stock.category
        and p.stock_quantity >= needed_qty
    ]
    if not candidates:
        return None
    # On priorise le produit dont le prix est le plus proche de l'original
    candidates.sort(key=lambda p: abs(p.price - out_of_stock.price))
    return candidates[0]


async def _create_order(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    items: list[dict],
    delivery_address: str,
    delivery_fee: float | int | str = 0,
) -> str:
    if not items:
        return "Erreur : aucun article spécifié pour la commande."

    try:
        fee = Decimal(str(delivery_fee or 0))
    except Exception:
        fee = Decimal("0")

    stmt = select(Product).where(Product.business_id == business_id)
    result = await session.execute(stmt)
    all_products = result.scalars().all()

    order_lines: list[tuple[Product, int]] = []

    for item in items:
        product_name = _normalize(str(item.get("product_name", "")))
        try:
            qty = int(item.get("quantity", 1))
        except (ValueError, TypeError):
            qty = 1
        if qty <= 0:
            qty = 1

        found_prod = None
        item_words = [w for w in product_name.split() if len(w) > 1]
        for p in all_products:
            p_name_norm = _normalize(p.name)
            if (
                product_name == p_name_norm
                or product_name in p_name_norm
                or p_name_norm in product_name
                or product_name.replace(" ", "") == p_name_norm.replace(" ", "")
                or (item_words and all(w in p_name_norm for w in item_words))
            ):
                found_prod = p
                break

        if not found_prod:
            return f"Erreur de commande : le produit '{item.get('product_name')}' est introuvable au catalogue."

        if found_prod.stock_quantity < qty:
            alternative = _find_alternative_product(all_products, found_prod, qty)
            if alternative:
                return (
                    f"Stock insuffisant pour '{found_prod.name}' "
                    f"(demandé : {qty}, disponible : {found_prod.stock_quantity}).\n"
                    f"En alternative, je peux vous proposer : {alternative.name} "
                    f"({int(alternative.price)} FCFA, {alternative.stock_quantity} en stock). "
                    f"Souhaitez-vous cet article à la place ?"
                )
            return (
                f"Impossible de valider la commande : stock insuffisant pour '{found_prod.name}'. "
                f"Demandé : {qty}, Disponible en stock : {found_prod.stock_quantity}."
            )

        order_lines.append((found_prod, qty))

    order = Order(
        business_id=business_id,
        customer_id=customer_id,
        delivery_address=(delivery_address or "Retrait en boutique").strip(),
        delivery_fee=fee,
        status=OrderStatus.PENDING,
    )
    session.add(order)
    await session.flush()

    total_products_cost = Decimal("0")
    summary_items = []
    for prod, qty in order_lines:
        prod.stock_quantity -= qty
        item_cost = prod.price * qty
        total_products_cost += item_cost
        order_item = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            quantity=qty,
            unit_price_snapshot=prod.price,
        )
        session.add(order_item)
        summary_items.append(f"{qty}x {prod.name} ({int(item_cost)} FCFA)")

    await session.commit()

    short_id = str(order.id)[:8].upper()
    total_general = total_products_cost + fee
    return (
        f"Commande #{short_id} confirmée et enregistrée avec succès !\n"
        f"Articles : {', '.join(summary_items)}\n"
        f"Frais de livraison : {int(fee)} FCFA\n"
        f"Montant total à régler : {int(total_general)} FCFA\n"
        f"Adresse : {order.delivery_address}\n"
        f"Statut : En attente de validation et préparation par la boutique."
    )


async def _get_order_status(
    session: AsyncSession, business_id: uuid.UUID, customer_id: uuid.UUID
) -> str:
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.business_id == business_id, Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        return "Vous n'avez aucune commande enregistrée pour le moment."

    status_labels = {
        OrderStatus.PENDING: "En cours de préparation",
        OrderStatus.CONFIRMED: "Confirmée par la boutique",
        OrderStatus.DELIVERED: "Livrée",
        OrderStatus.CANCELLED: "Annulée",
    }
    status_str = status_labels.get(order.status, order.status.value)
    short_id = str(order.id)[:8].upper()
    total = int(order.total_amount)

    return (
        f"Votre dernière commande est la #{short_id}.\n"
        f"- Statut : {status_str}\n"
        f"- Montant total : {total} FCFA\n"
        f"- Lieu : {order.delivery_address or 'En boutique'}"
    )


async def _generate_invoice(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    order_ref: str | None = None,
) -> str:
    order = None
    if order_ref:
        clean_ref = order_ref.strip().lstrip("#").upper()
        stmt_orders = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.business_id == business_id, Order.customer_id == customer_id)
        )
        orders = (await session.execute(stmt_orders)).scalars().all()
        for o in orders:
            if str(o.id)[:8].upper() == clean_ref or str(o.id).upper() == clean_ref:
                order = o
                break

    if not order:
        stmt_last = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.business_id == business_id, Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        order = (await session.execute(stmt_last)).scalar_one_or_none()

    if not order:
        return "Aucune commande trouvée pour générer une facture."

    # Vérification si une facture existe déjà
    stmt_inv = select(Invoice).where(Invoice.order_id == order.id)
    invoice = (await session.execute(stmt_inv)).scalar_one_or_none()

    subtotal = sum(
        (item.unit_price_snapshot * item.quantity for item in order.items),
        start=Decimal("0"),
    )
    fee = Decimal(str(order.delivery_fee or 0))
    total = subtotal + fee
    short_order_id = str(order.id)[:8].upper()

    if not invoice:
        current_year = datetime.now().year
        inv_number = f"FAC-{current_year}-{short_order_id}"
        invoice = Invoice(
            business_id=business_id,
            order_id=order.id,
            invoice_number=inv_number,
            subtotal=subtotal,
            delivery_fee=fee,
            total=total,
            status="issued",  # En attente de paiement
        )
        session.add(invoice)
        await session.flush()

    business = (
        await session.execute(select(Business).where(Business.id == business_id))
    ).scalar_one()
    customer = (
        await session.execute(select(Customer).where(Customer.id == customer_id))
    ).scalar_one()
    prods = (
        await session.execute(select(Product).where(Product.business_id == business_id))
    ).scalars().all()
    products_map = {p.id: p for p in prods}

    pdf_path = generate_invoice_pdf(
        invoice=invoice,
        order=order,
        business=business,
        customer=customer,
        products_map=products_map,
    )
    invoice.pdf_path = str(pdf_path)
    await session.commit()

    total_fmt = f"{int(total):,}".replace(",", " ")
    status_display = (
        "En attente de paiement (à régler à la livraison)"
        if invoice.status == "issued"
        else "Payée / Acquittée"
    )

    return (
        f"Facture officielle #{invoice.invoice_number} prête !\n"
        f"- Commande associée : #{short_order_id}\n"
        f"- Montant total : {total_fmt} FCFA\n"
        f"- Statut : {status_display}\n"
        f"- Télécharger la facture PDF : {settings.public_base_url.rstrip('/')}/invoices/{invoice.invoice_number}"
    )


async def _escalate_to_human(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    reason: str,
    urgency: str = "normal",
) -> str:
    stmt = (
        select(Conversation)
        .where(
            Conversation.business_id == business_id,
            Conversation.customer_id == customer_id,
        )
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    conv = (await session.execute(stmt)).scalar_one_or_none()
    if conv:
        conv.status = "needs_human"
        conv.handoff_reason = reason
        await session.commit()

    return (
        f"Votre demande a bien été transmise à un conseiller de notre boutique "
        f"(Motif : {reason}). Un responsable humain va prendre le relais ici même sur WhatsApp "
        f"d'ici quelques instants pour vous assister personnellement."
    )


async def _cancel_order(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    order_ref: str | None,
    reason: str,
) -> str:
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.business_id == business_id,
            Order.customer_id == customer_id,
        )
        .order_by(Order.created_at.desc())
    )
    orders = (await session.execute(stmt)).scalars().all()

    if not orders:
        return "Aucune commande trouvée à annuler pour votre compte."

    target_order = None
    if order_ref:
        clean_ref = order_ref.strip().lstrip("#").lower()
        for o in orders:
            if str(o.id).lower().startswith(clean_ref):
                target_order = o
                break

    if not target_order:
        # Prendre la plus récente non livrée / non annulée
        for o in orders:
            if o.status in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
                target_order = o
                break

    if not target_order:
        return "Toutes vos commandes sont déjà livrées ou déjà annulées. Aucune commande active à annuler."

    if target_order.status == OrderStatus.DELIVERED:
        return f"La commande #{str(target_order.id)[:8].upper()} a déjà été livrée et ne peut plus être annulée automatiquement."

    if target_order.status == OrderStatus.CANCELLED:
        return f"La commande #{str(target_order.id)[:8].upper()} a déjà été annulée."

    # Annulation
    target_order.status = OrderStatus.CANCELLED

    # Réapprovisionnement automatique du stock
    for item in target_order.items:
        stmt_p = select(Product).where(Product.id == item.product_id)
        prod = (await session.execute(stmt_p)).scalar_one_or_none()
        if prod:
            prod.stock_quantity += item.quantity

    # Annulation facture associée si existante
    stmt_inv = select(Invoice).where(Invoice.order_id == target_order.id)
    inv = (await session.execute(stmt_inv)).scalar_one_or_none()
    if inv:
        inv.status = "cancelled"

    await session.commit()

    short_id = str(target_order.id)[:8].upper()
    return (
        f"La commande #{short_id} a été annulée avec succès (Motif : {reason}). "
        f"Les articles ont été remis en stock. Si vous aviez effectué un acompte ou besoin d'informations, "
        f"notre équipe reste à votre disposition."
    )


async def _update_order_address(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    new_zone: str,
    order_ref: str | None = None,
) -> str:
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.business_id == business_id,
            Order.customer_id == customer_id,
        )
        .order_by(Order.created_at.desc())
    )
    orders = (await session.execute(stmt)).scalars().all()
    if not orders:
        return "Aucune commande trouvée à modifier pour votre compte."

    target_order = None
    if order_ref:
        clean_ref = order_ref.strip().lstrip("#").lower()
        for o in orders:
            if str(o.id).lower().startswith(clean_ref):
                target_order = o
                break

    if not target_order:
        for o in orders:
            if o.status in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
                target_order = o
                break

    if not target_order:
        return "Aucune commande en attente dont l'adresse peut être modifiée."

    if target_order.status == OrderStatus.DELIVERED:
        return f"La commande #{str(target_order.id)[:8].upper()} a déjà été livrée et son adresse ne peut plus être modifiée."

    # Recherche des zones de livraison
    stmt_z = select(DeliveryZone).where(
        DeliveryZone.business_id == business_id,
        DeliveryZone.active.is_(True),
    )
    zones = (await session.execute(stmt_z)).scalars().all()
    matched_zone: DeliveryZone | None = None
    zone_clean = (new_zone or "").strip().lower()

    for z in zones:
        if zone_clean in z.name.lower() or z.name.lower() in zone_clean:
            matched_zone = z
            break
        if z.keywords:
            keywords_list = [kw.strip().lower() for kw in z.keywords.split(",") if kw.strip()]
            if any(kw in zone_clean or zone_clean in kw for kw in keywords_list):
                matched_zone = z
                break

    if matched_zone:
        new_fee = int(matched_zone.fee)
        target_order.delivery_address = matched_zone.name
        target_order.delivery_fee = Decimal(str(new_fee))
    else:
        new_fee = int(target_order.delivery_fee or 0)
        target_order.delivery_address = new_zone

    # Mettre à jour la facture si elle existe
    stmt_inv = select(Invoice).where(Invoice.order_id == target_order.id)
    inv = (await session.execute(stmt_inv)).scalar_one_or_none()
    inv_str = ""
    if inv:
        inv.delivery_fee = Decimal(str(new_fee))
        inv.total = inv.subtotal + inv.delivery_fee

        # Regénérer le PDF avec les nouveaux montants et nouvelle adresse
        business = (await session.execute(select(Business).where(Business.id == business_id))).scalar_one()
        customer = (await session.execute(select(Customer).where(Customer.id == customer_id))).scalar_one()
        prods = (await session.execute(select(Product).where(Product.business_id == business_id))).scalars().all()
        products_map = {p.id: p for p in prods}
        pdf_path = generate_invoice_pdf(
            invoice=inv,
            order=target_order,
            business=business,
            customer=customer,
            products_map=products_map,
        )
        inv.pdf_path = str(pdf_path)
        inv_str = f"\n- Facture PDF mise à jour : {settings.public_base_url.rstrip('/')}/invoices/{inv.invoice_number}"

    await session.commit()

    short_id = str(target_order.id)[:8].upper()
    total_fmt = f"{int(target_order.total_amount):,}".replace(",", " ")
    fee_fmt = f"{new_fee:,}".replace(",", " ")
    return (
        f"L'adresse de livraison pour votre commande #{short_id} a bien été mise à jour !\n"
        f"- Nouvelle destination : {target_order.delivery_address}\n"
        f"- Frais de livraison : {fee_fmt} FCFA\n"
        f"- Nouveau total de la commande : {total_fmt} FCFA.{inv_str}"
    )


async def _initiate_payment(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    provider: str = "mock",
    customer_phone: str | None = None,
    order_ref: str | None = None,
) -> str:
    """Initie un paiement Mobile Money (Wave, Orange Money ou Espèces) pour la commande."""
    stmt = (
        select(Order)
        .where(Order.business_id == business_id, Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
        .options(selectinload(Order.items), selectinload(Order.customer))
    )
    res = await session.execute(stmt)
    orders = res.scalars().all()

    target_order = None
    if order_ref:
        clean_ref = order_ref.strip().lstrip("#").upper()
        for o in orders:
            if str(o.id).upper().startswith(clean_ref):
                target_order = o
                break
    else:
        # Prendre la dernière commande non annulée et non livrée
        for o in orders:
            if o.status not in (OrderStatus.CANCELLED, OrderStatus.DELIVERED):
                target_order = o
                break

    if not target_order:
        return "Aucune commande en cours trouvée pour initier un paiement."

    order_short = str(target_order.id)[:8].upper()
    total_fmt = f"{int(target_order.total_amount):,}".replace(",", " ")

    # Cas 1 : Paiement en espèces à la livraison
    p_lower = (provider or "cash").lower()
    if p_lower in ("cash", "especes", "espèces", "cash_on_delivery", "livraison"):
        target_order.payment_method = "cash_on_delivery"
        target_order.payment_status = "unpaid"
        await session.commit()
        return (
            f"Votre commande #{order_short} ({total_fmt} FCFA) sera réglée en **espèces à la livraison** directement auprès du coursier.\n"
            f"Veuillez prévoir le montant exact si possible. Merci !"
        )

    # Cas 2 : Paiement Mobile Money via PaymentService
    try:
        payment = await payment_service.initiate_payment(
            session=session,
            business_id=business_id,
            order_id=target_order.id,
            provider=provider,
            customer_phone=customer_phone,
        )

        if "wave" in payment.provider.lower():
            return (
                f"Voici votre lien sécurisé pour régler la commande #{order_short} ({total_fmt} FCFA) via **Wave** :\n"
                f"👉 {payment.checkout_url}\n\n"
                f"Cliquez sur le lien pour valider directement dans votre application Wave.\n"
                f"Dès validation, votre commande sera automatiquement confirmée !"
            )
        elif "orange" in payment.provider.lower():
            phone_str = payment.customer_phone or "votre téléphone"
            return (
                f"Une demande de paiement **Orange Money** de {total_fmt} FCFA a été initiée pour la commande #{order_short} "
                f"vers le numéro {phone_str}.\n"
                f"📱 Vous pouvez également valider votre paiement directement via ce lien sécurisé :\n"
                f"👉 {payment.checkout_url}\n\n"
                f"Réf transaction : `{payment.transaction_reference}`."
            )
        else:
            return (
                f"Session de paiement initiée pour la commande #{order_short} ({total_fmt} FCFA).\n"
                f"Lien de règlement : {payment.checkout_url}"
            )
    except Exception as exc:
        return f"Impossible d'initier le paiement pour la commande #{order_short} : {str(exc)}"


async def _check_payment_status(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    order_ref: str | None = None,
) -> str:
    """Vérifie l'état d'encaissement de la commande."""
    stmt = (
        select(Order)
        .where(Order.business_id == business_id, Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
        .options(selectinload(Order.items), selectinload(Order.payments))
    )
    res = await session.execute(stmt)
    orders = res.scalars().all()

    target_order = None
    if order_ref:
        clean_ref = order_ref.strip().lstrip("#").upper()
        for o in orders:
            if str(o.id).upper().startswith(clean_ref):
                target_order = o
                break
    else:
        for o in orders:
            if o.status != OrderStatus.CANCELLED:
                target_order = o
                break

    if not target_order:
        return "Aucune commande correspondante trouvée."

    order_short = str(target_order.id)[:8].upper()
    total_fmt = f"{int(target_order.total_amount):,}".replace(",", " ")

    if target_order.payment_status == "paid":
        method = target_order.payment_method or "Mobile Money"
        return f"✅ Votre paiement de {total_fmt} FCFA pour la commande #{order_short} via {method} a bien été reçu et validé !"
    elif target_order.payment_status == "pending":
        return f"⏳ Le paiement pour votre commande #{order_short} ({total_fmt} FCFA) est actuellement en attente de confirmation de l'opérateur."
    else:
        return (
            f"ℹ️ Votre commande #{order_short} ({total_fmt} FCFA) est actuellement en attente de règlement.\n"
            f"Souhaitez-vous recevoir un lien de paiement Wave ou Orange Money ?"
        )