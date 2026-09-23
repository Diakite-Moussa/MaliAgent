"""
Formatteur audio et nettoyeur de texte pour la synthèse vocale (TTS).
Transforme les réponses textuelles de commerce (avec émojis, listes et markdown)
en phrases parlées naturelles, fluides et directes pour les notes vocales WhatsApp.
"""

import re


def clean_text_for_speech(text: str, language: str = "fr") -> str:
    """
    Nettoie un texte brut de réponse WhatsApp pour le rendre agréable et naturel à l'oreille :
    - Supprime les émojis, symboles de bullet points, coches, flèches
    - Supprime les parenthèses de stock techniques (ex: '(5 unités en stock)', '(disponible)')
    - Supprime le markdown (*, _, ~, #, >)
    - Remplace les acronymes : 'FCFA' -> 'francs CFA', 'Go' -> 'gigas'
    - Formate les tirets et deux-points pour une diction naturelle
    """
    if not text:
        return ""

    t = text

    # 1. Enlever balises HTML/XML éventuelles
    t = re.sub(r"<[^>]+>", "", t)

    # 2. Normaliser les espaces insécables et tirets Unicode en caractères standards
    t = re.sub(r"[\u00a0\u1680\u2000-\u200b\u202f\u205f\u3000]", " ", t)
    t = re.sub(r"[\u2010-\u2015]", "-", t)

    # 3. Supprimer les parenthèses techniques de stock et disponibilité
    t = re.sub(r"\([^\)]*stock[^\)]*\)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\([^\)]*unit[^\)]*\)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\([^\)]*disponible[^\)]*\)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\bdisponible\b", "", t, flags=re.IGNORECASE)

    # 4. Supprimer les émojis
    t = re.sub(r"[\U00010000-\U0010ffff]", "", t)
    t = re.sub(r"[✅📦📍🚚📱👉🛒💳🌟✨🙌🛑⚠️🏷️•✔️❌]", "", t)

    # 5. Supprimer le markdown
    t = re.sub(r"[\*\_\~`#]", "", t)

    # 6. Remplacer les devises et acronymes (avec gestion des espaces collés)
    if language == "bm":
        t = re.sub(r"(\d+)\s*FCFA\b", r"\1 FCFA", t, flags=re.IGNORECASE)
    else:
        t = re.sub(r"(\d+)\s*F\s*CFA\b", r"\1 francs CFA", t, flags=re.IGNORECASE)
        t = re.sub(r"(\d+)\s*FCFA\b", r"\1 francs CFA", t, flags=re.IGNORECASE)
        t = re.sub(r"\bFCFA\b", "francs CFA", t, flags=re.IGNORECASE)

    t = re.sub(r"(\d+)\s*Go\b", r"\1 gigas", t, flags=re.IGNORECASE)
    t = re.sub(r"\bex\s*:\s*", "par exemple ", t, flags=re.IGNORECASE)

    # 7. Conversion des montants et nombres en toutes lettres pour une élocution naturelle
    if language == "fr":
        # Rassembler les séparateurs de milliers (ex: '350 000' -> '350000')
        t = re.sub(r"(\d+)\s+(\d{3})\b", r"\1\2", t)
        t = re.sub(r"(\d+)\s+(\d{3})\b", r"\1\2", t)

        try:
            import num2words  # type: ignore[import-not-found, import-untyped]

            def _num_repl(m):
                val = int(m.group(0))
                # On convertit en toutes lettres les nombres >= 100 (prix, frais, etc.)
                if val >= 100:
                    return num2words.num2words(val, lang="fr")
                return str(val)

            t = re.sub(r"\b\d+\b", _num_repl, t)
        except ImportError:
            pass

    # 8. Nettoyer les puces et tirets
    t = re.sub(r"^[•\->]\s*", "", t, flags=re.MULTILINE)

    # 9. Formater les listes produits "Produit - Neuf : Prix" -> "Produit Neuf est à Prix"
    lines = []
    for line in t.splitlines():
        line = line.strip()
        if not line:
            continue
        if language == "bm":
            line = re.sub(r"\s*:\s*", " sɔngɔ ye ", line)
        else:
            line = re.sub(r"\s*:\s*", " est à ", line)
        line = re.sub(r"\s*-\s*", " ", line)
        lines.append(line)

    cleaned = " ".join(lines)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_spoken_and_display_text(raw_text: str, language: str = "fr") -> tuple[str, str]:
    """
    Extrait le texte spécifique à prononcer à l'oral (<voice>...</voice>)
    et le texte riche à afficher par écrit dans la discussion WhatsApp.

    Retourne:
        tuple (spoken_text, display_text)
    """
    if not raw_text:
        return "", ""

    voice_match = re.search(r"<voice>(.*?)</voice>", raw_text, flags=re.DOTALL | re.IGNORECASE)
    if voice_match:
        spoken_raw = voice_match.group(1).strip()
        spoken_text = clean_text_for_speech(spoken_raw, language=language)
        display_text = re.sub(r"<voice>.*?</voice>", "", raw_text, flags=re.DOTALL | re.IGNORECASE).strip()
        return spoken_text, display_text

    spoken_text = clean_text_for_speech(raw_text, language=language)
    return spoken_text, raw_text.strip()
