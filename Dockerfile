# =========================================================
# MaliAgent Backend — Dockerfile de production / staging
# =========================================================

FROM python:3.12-slim

# Empêche Python d'écrire des fichiers .pyc et force l'affichage immédiat des logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances système pour psycopg et polices de génération PDF (ReportLab)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copie du code source et dossiers nécessaires
COPY app/ ./app
COPY scripts/ ./scripts
COPY storage/ ./storage

# Création des dossiers storage s'ils n'existent pas
RUN mkdir -p /app/storage/invoices /app/storage/audio/outgoing /app/storage/products

# Rendre le script de démarrage exécutable
RUN chmod +x /app/scripts/start.sh

# Port par défaut (Render injecte sa propre variable PORT)
ENV PORT=8000
EXPOSE 8000

# Commande de démarrage par défaut
CMD ["/app/scripts/start.sh"]

