# MaliAgent

Plateforme d'agents IA pour commerce conversationnel via WhatsApp.

## Statut

Phase MVP — voir `documentation/Cahier des charges fonctionnel — MaliAgent.md`.

## Stack

- Backend : FastAPI + PostgreSQL + SQLAlchemy
- LLM : Ollama Cloud (phase MVP) via une couche d'abstraction `LLMProvider` (changement de provider prévu en production)
- Canal : WhatsApp Cloud API
- Frontend dashboard : Angular (à venir)

## Démarrage rapide

```bash
cp .env.example .env
# renseigner OLLAMA_API_KEY dans .env (clé depuis ollama.com/settings/keys)

docker compose up -d          # lance PostgreSQL
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Valider le tool calling avant d'aller plus loin

```bash
python scripts/test_tool_calling.py
```

Ce script teste le modèle Ollama Cloud configuré sur une série de messages en français avec des tools factices. Objectif : confirmer que le tool calling est assez fiable avant de construire le reste de l'agent dessus.

## Structure

```
app/
  core/        # configuration
  db/          # connexion base de données
  llm/         # couche d'abstraction LLM (base.py = interface, providers/ = implémentations)
  main.py      # point d'entrée FastAPI
scripts/
  test_tool_calling.py
documentation/
  Cahier des charges fonctionnel — MaliAgent.md
```
