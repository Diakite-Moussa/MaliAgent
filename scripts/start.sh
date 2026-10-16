#!/bin/sh
set -e

echo "=== Démarrage de MaliAgent ==="

# Exécution de l'initialisation de la base de données (création extension vector et tables)
if [ "${RUN_INIT_DB:-true}" = "true" ]; then
    echo "Initialisation et migration de la base de données..."
    python scripts/init_db.py || echo "Avertissement : init_db a retourné un code d'erreur ou les tables existent déjà."
fi

# Démarrage de l'application FastAPI avec Uvicorn
PORT_TO_USE="${PORT:-8000}"
WORKERS_TO_USE="${WORKERS:-2}"

echo "Lancement de Uvicorn sur 0.0.0.0:${PORT_TO_USE} avec ${WORKERS_TO_USE} workers..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT_TO_USE}" --workers "${WORKERS_TO_USE}"
