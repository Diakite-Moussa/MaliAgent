"""
Module de Géocodage et de Zonage Intelligent de Bamako (V2.2).
Associe des coordonnées GPS (latitude, longitude) issues de WhatsApp
à la commune et au quartier de Bamako correspondants, avec application du tarif fixe.
"""

import math
from decimal import Decimal

# Coordonnées de référence des communes et quartiers clés du District de Bamako
BAMAKO_COMMUNE_CENTROIDS = [
    {
        "commune": "Commune IV",
        "name": "Commune IV (ACI 2000, Hamdallaye, Lafiabougou)",
        "neighborhood": "Lafiabougou / ACI 2000 / Sebenikoro",
        "lat": 12.6280,
        "lon": -8.0320,
        "fee": Decimal("1000"),
        "delivery_delay": "1 à 2 heures",
    },
    {
        "commune": "Commune III",
        "name": "Commune III (Centre commercial, Darsalam, Koulouba)",
        "neighborhood": "Centre commercial / Darsalam / Bamako Coura",
        "lat": 12.6520,
        "lon": -8.0150,
        "fee": Decimal("1500"),
        "delivery_delay": "1 à 2 heures",
    },
    {
        "commune": "Commune II",
        "name": "Commune II (Hippodrome, Médina Coura, Bagadadji, Bozola)",
        "neighborhood": "Hippodrome / Médina Coura / Zone Industrielle",
        "lat": 12.6580,
        "lon": -7.9850,
        "fee": Decimal("1500"),
        "delivery_delay": "1 à 2 heures",
    },
    {
        "commune": "Commune I",
        "name": "Commune I (Djelibougou, Korofina, Doumanzana, Fadjiguila)",
        "neighborhood": "Djelibougou / Korofina / Doumanzana",
        "lat": 12.6780,
        "lon": -7.9450,
        "fee": Decimal("1500"),
        "delivery_delay": "2 à 3 heures",
    },
    {
        "commune": "Commune V",
        "name": "Commune V (Badalabougou, Baco Djicoroni, Torokorobougou, Daoudabougou)",
        "neighborhood": "Badalabougou / Baco Djicoroni / Daoudabougou",
        "lat": 12.6050,
        "lon": -7.9950,
        "fee": Decimal("1500"),
        "delivery_delay": "1 à 2 heures",
    },
    {
        "commune": "Commune VI",
        "name": "Commune VI (Faladié, Sogoniko, Banankabougou, Yirimadio, Kalaban Coura)",
        "neighborhood": "Faladié / Sogoniko / Yirimadio / Sénou",
        "lat": 12.5920,
        "lon": -7.9420,
        "fee": Decimal("2000"),
        "delivery_delay": "2 à 3 heures",
    },
    {
        "commune": "Kati / Périphérie Nord",
        "name": "Zone Périphérique (Kati, Kambila)",
        "neighborhood": "Kati ville / Sananfara",
        "lat": 12.7440,
        "lon": -8.0720,
        "fee": Decimal("2500"),
        "delivery_delay": "3 à 4 heures",
    },
]


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance en kilomètres entre deux points GPS via la formule Haversine."""
    r = 6371.0  # Rayon terrestre en km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def resolve_bamako_zone_from_gps(latitude: float, longitude: float) -> dict:
    """
    Détermine la zone de livraison et le tarif forfaitaire de Bamako à partir de coordonnées GPS.
    Retourne les informations enrichies : nom de zone, quartier estimé, tarif, délai et lien Google Maps.
    """
    best_zone = None
    min_distance = float("inf")

    for zone in BAMAKO_COMMUNE_CENTROIDS:
        dist = haversine_distance_km(latitude, longitude, zone["lat"], zone["lon"])
        if dist < min_distance:
            min_distance = dist
            best_zone = zone

    maps_url = f"https://www.google.com/maps/dir/?api=1&destination={latitude},{longitude}"

    # Si le point est à plus de 35 km du centre de Bamako -> Hors agglomération
    if min_distance > 35.0:
        return {
            "commune": "Hors District",
            "zone_name": "Hors District de Bamako",
            "neighborhood": "Zone hors agglomération de Bamako",
            "fee": Decimal("3500"),
            "delivery_delay": "Sur devis ou 24h",
            "distance_km": round(min_distance, 2),
            "latitude": latitude,
            "longitude": longitude,
            "maps_url": maps_url,
            "formatted_label": f"Hors District de Bamako ({int(3500)} FCFA)",
        }

    assert best_zone is not None
    return {
        "commune": best_zone["commune"],
        "zone_name": best_zone["name"],
        "neighborhood": best_zone["neighborhood"],
        "fee": best_zone["fee"],
        "delivery_delay": best_zone["delivery_delay"],
        "distance_km": round(min_distance, 2),
        "latitude": latitude,
        "longitude": longitude,
        "maps_url": maps_url,
        "formatted_label": f"{best_zone['commune']} ({best_zone['neighborhood']}) — {int(best_zone['fee'])} FCFA",
    }
