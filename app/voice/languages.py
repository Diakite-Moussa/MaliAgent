"""
Détection et normalisation linguistique : Français & Bambara (Bamanankan).
Sprint V0.5 Voice & Multilingual.
"""

import re

BAMBARA_KEYWORDS = [
    "i ni ce", "i ni sogoma", "i ni tle", "i ni wula", "aw ni ce", "aw ni baara",
    "i ka kene", "ka kene", "tana t'i la", "tana te", "tana tɛ",
    "sɔngɔ", "songɔ", "songo", "wari", "joli ye", "joli", "son oeil joli", "ka san", "ka feere",
    "a bɛ yen", "a be yen", "a tɛ yen", "a te yen", "n b'a fɛ", "n b'a fe",
    "m'b'a fe", "m'b'a fɛ", "hakɛto", "haketo", "an bɛ", "an be", "dɔɔnin",
    "doonin", "kɛmɛ", "keme", "baa kelen", "baa fila", "aywa", "tiɲɛ", "tinye",
    "cogo di", "barika", "i bisimila", "bisimila", "lase", "donni", "sabali", "k'an ben"
]


def detect_language(text: str, default_lang: str = "fr") -> str:
    """
    Détecte si le texte relève du Bambara ('bm') ou du Français ('fr').
    Prend en compte les expressions, salutations et lexique commercial malien.
    """
    if not text:
        return default_lang

    text_lower = text.lower()

    # Détection de mots-clés et expressions caractéristiques du Bambara
    bm_matches = 0
    for kw in BAMBARA_KEYWORDS:
        if kw in text_lower:
            bm_matches += 1

    # Présence de caractères spécifiques à l'alphabet bambara officiel (ɛ, ɔ, ɲ, ŋ)
    special_bm_chars = any(c in text_lower for c in ["ɛ", "ɔ", "ɲ", "ŋ"])
    if special_bm_chars:
        bm_matches += 2

    # Si au moins une expression forte bambara est trouvée
    if bm_matches >= 1:
        return "bm"

    return "fr"
