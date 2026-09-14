"""
Service de génération de factures PDF professionnelles avec ReportLab.

Section RF-013 du cahier des charges fonctionnel.
Génère un document A4 soigné, moderne et lisible avec récapitulatif
des articles, frais de livraison, mentions légales et statut de paiement.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Business, Customer, Invoice, Order, Product


def format_fcfa(amount: Decimal | float | int) -> str:
    """Formate un montant avec séparateur d'espace et devise FCFA (ex. 95 000 FCFA)."""
    val = int(amount)
    return f"{val:,}".replace(",", " ") + " FCFA"


def generate_invoice_pdf(
    invoice: Invoice,
    order: Order,
    business: Business,
    customer: Customer,
    products_map: dict | None = None,
) -> Path:
    """
    Génère le fichier PDF de la facture et retourne son chemin absolu.
    """
    storage_dir = Path("storage") / "invoices"
    storage_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = storage_dir / f"{invoice.invoice_number}.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    primary_color = colors.HexColor("#0F172A")  # Slate foncé
    accent_color = colors.HexColor("#2563EB")   # Bleu pro
    bg_light = colors.HexColor("#F8FAFC")
    border_color = colors.HexColor("#E2E8F0")

    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=22,
        leading=26,
        textColor=primary_color,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "InvoiceSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B"),
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=15,
        textColor=primary_color,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    right_style = ParagraphStyle(
        "RightAlign",
        parent=body_style,
        alignment=2,
    )
    right_bold = ParagraphStyle(
        "RightBold",
        parent=body_bold,
        alignment=2,
    )

    story = []

    # 1. En-tête : Vendeur à gauche, N° Facture à droite
    business_name = business.name
    currency = business.currency or "FCFA"
    date_str = (invoice.created_at or datetime.now()).strftime("%d/%m/%Y")

    status_badge = (
        "ACQUITTÉE (PAYÉE)"
        if invoice.status == "paid"
        else "EN ATTENTE DE PAIEMENT"
    )
    badge_color = (
        colors.HexColor("#16A34A") if invoice.status == "paid" else colors.HexColor("#EA580C")
    )

    header_left = [
        Paragraph(business_name, title_style),
        Paragraph(f"Boutique partenaire MaliAgent • Devise : {currency}", subtitle_style),
        Paragraph(f"Contact WhatsApp : +{business.whatsapp_phone_number}", subtitle_style),
    ]
    header_right = [
        Paragraph("FACTURE COMMERCIALE", ParagraphStyle("HRight", parent=title_style, alignment=2, textColor=accent_color)),
        Paragraph(f"N° Facture : <b>{invoice.invoice_number}</b>", right_style),
        Paragraph(f"Date d'émission : {date_str}", right_style),
        Paragraph(f"Statut : <font color='{badge_color.hexval()}'><b>{status_badge}</b></font>", right_style),
    ]

    header_table = Table(
        [[header_left, header_right]],
        colWidths=[280, 240],
    )
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 20))

    # 2. Informations de commande & Client
    client_phone = customer.whatsapp_phone_number
    delivery_loc = order.delivery_address or "Retrait en boutique"
    order_short_id = str(order.id)[:8].upper()

    info_left = [
        Paragraph("FACTURÉ À :", section_title_style),
        Paragraph(f"Client WhatsApp : <b>+{client_phone}</b>", body_style),
        Paragraph(f"Lieu de livraison : {delivery_loc}", body_style),
    ]
    info_right = [
        Paragraph("DÉTAILS COMMANDE :", section_title_style),
        Paragraph(f"Référence Commande : <b>#{order_short_id}</b>", body_style),
        Paragraph(f"Mode : {delivery_loc}", body_style),
    ]

    info_table = Table(
        [[info_left, info_right]],
        colWidths=[280, 240],
    )
    info_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg_light),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("PADDING", (0, 0), (-1, -1), 12),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(info_table)
    story.append(Spacer(1, 20))

    # 3. Tableau des articles
    table_data = [
        [
            Paragraph("<b>Désignation de l'article</b>", body_bold),
            Paragraph("<b>Qté</b>", ParagraphStyle("C", parent=body_bold, alignment=1)),
            Paragraph("<b>Prix unitaire</b>", right_bold),
            Paragraph("<b>Montant total</b>", right_bold),
        ]
    ]

    for item in order.items:
        prod_name = "Article"
        if products_map and item.product_id in products_map:
            prod_name = products_map[item.product_id].name
        line_total = item.unit_price_snapshot * item.quantity

        table_data.append([
            Paragraph(prod_name, body_style),
            Paragraph(str(item.quantity), ParagraphStyle("C", parent=body_style, alignment=1)),
            Paragraph(format_fcfa(item.unit_price_snapshot), right_style),
            Paragraph(format_fcfa(line_total), right_style),
        ])

    # Ligne de livraison
    fee_val = invoice.delivery_fee or Decimal("0")
    fee_label = "Frais de livraison" if fee_val > 0 else "Retrait en magasin"
    fee_display = format_fcfa(fee_val) if fee_val > 0 else "Gratuit"
    table_data.append([
        Paragraph(f"<i>{fee_label} ({delivery_loc})</i>", body_style),
        Paragraph("1", ParagraphStyle("C", parent=body_style, alignment=1)),
        Paragraph(fee_display, right_style),
        Paragraph(fee_display, right_style),
    ])

    items_table = Table(
        table_data,
        colWidths=[250, 40, 115, 115],
    )
    items_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, primary_color),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 1), (-1, -1), 7),
        ])
    )
    story.append(items_table)
    story.append(Spacer(1, 15))

    # 4. Totaux
    subtotal_str = format_fcfa(invoice.subtotal)
    delivery_str = format_fcfa(invoice.delivery_fee)
    total_str = format_fcfa(invoice.total)

    totals_data = [
        [Paragraph("Sous-total articles :", right_style), Paragraph(subtotal_str, right_bold)],
        [Paragraph("Frais de livraison :", right_style), Paragraph(delivery_str, right_bold)],
        [
            Paragraph("<b>TOTAL NET À PAYER :</b>", ParagraphStyle("TBold", parent=body_bold, alignment=2, fontSize=11, textColor=primary_color)),
            Paragraph(f"<b>{total_str}</b>", ParagraphStyle("TVal", parent=body_bold, alignment=2, fontSize=11, textColor=accent_color)),
        ],
    ]

    totals_table = Table(
        totals_data,
        colWidths=[380, 140],
    )
    totals_table.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("LINEABOVE", (0, 2), (-1, 2), 1, primary_color),
        ])
    )
    story.append(totals_table)
    story.append(Spacer(1, 30))

    # 5. Pied de page & Conditions de règlement
    notice_text = (
        "<b>Modalités de paiement :</b> Règlement à la livraison en espèces ou par transfert d'argent mobile "
        "(Orange Money / Wave) selon les consignes transmises par la boutique.<br/>"
        "Ce document fait foi de commande et de facture commerciale émise via la plateforme <b>MaliAgent</b>."
    )
    notice_box = Table(
        [[Paragraph(notice_text, subtitle_style)]],
        colWidths=[520],
    )
    notice_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg_light),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ])
    )
    story.append(notice_box)

    doc.build(story)
    return pdf_path
