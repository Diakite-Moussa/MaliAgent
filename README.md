# 🇲🇱 MaliAgent — Commerce Conversationnel Intelligent sur WhatsApp

**MaliAgent** est une plateforme SaaS d'agents IA autonomes conçue pour automatiser la relation client et les ventes des commerçants maliens directement sur WhatsApp.

Le système prend en charge la recherche de catalogue, le calcul des frais de livraison par quartier de Bamako, la confirmation de commande, l'émission de factures PDF avec QR Code et le suivi en temps réel via un tableau de bord commerçant.

---

## 🏗️ Architecture Technique

- **Backend** : FastAPI (Python 3.12+), SQLAlchemy 2.0 (Async), Psycopg 3.
- **Base de données** : PostgreSQL 16 avec isolation stricte **Multi-Tenant** (`business_id`).
- **Intelligence Artificielle** : Couche d'abstraction `LLMProvider` (Ollama Cloud / modèle 120B) avec **Tool Calling** déterministe contre la base de données.
- **Canal Client** : Meta WhatsApp Cloud API avec vérification de signature cryptographique **HMAC-SHA256**.
- **Sécurité** : Authentification **JWT** (JSON Web Token), hash **bcrypt**, en-têtes CORS restreints, rate limiting.
- **Facturation** : Génération automatisée de factures PDF conformes (ReportLab) accessibles par URL publique sécurisée.
- **Frontend** : Dashboard Commerçant en **Angular 21** (Standalone Components, Signals réactifs, Glassmorphic Emerald Theme).

---

## 🚀 Démarrage Rapide

### 1. Cloner et configurer l'environnement

```bash
cp .env.example .env
# Renseigner vos clés API dans le fichier .env (OLLAMA_API_KEY, META_APP_SECRET...)
```

### 2. Démarrer la base de données PostgreSQL

```bash
docker compose up -d postgres
```

### 3. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

### 4. Initialiser la base de données et les données du Pilote

```bash
# Initialisation des tables
python scripts/init_db.py

# Injection des produits de démonstration (électronique, mode, zones de livraison Bamako)
python scripts/seed_pilot_data.py

# Création d'un utilisateur administrateur pour le Dashboard
python scripts/create_user.py
```

### 5. Démarrer le Backend FastAPI

```bash
uvicorn app.main:app --reload --port 8000
```
- Documentation interactive Swagger : [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check : [http://localhost:8000/health](http://localhost:8000/health)

### 6. Démarrer le Dashboard Angular

Dans un nouveau terminal :
```bash
cd dashboard
npm install
npm start
```
- Accès au dashboard commerçant : [http://localhost:4300](http://localhost:4300)

---

## 🧪 Tests & Validation Automatisée

Le projet intègre une suite de tests complète validant le respect du cahier des charges :

### 1. Tests Formels Pytest (Sécurité & Multi-Tenant)
```bash
python -m pytest tests/ -v
```
- **Isolation Multi-Tenant** : vérifie qu'une boutique ne peut ni voir ni altérer les produits, commandes ou clients d'une autre boutique.
- **Sécurité des Accès** : rejet strict (HTTP 401) des requêtes non authentifiées sur le dashboard.
- **Sécurité Webhook** : validation du challenge Meta et rejet (HTTP 403) des requêtes sans signature HMAC-SHA256 valide.

### 2. Scénarios Conversationnels Pilote E2E (End-to-End)
```bash
python scripts/test_pilot_e2e_scenarios.py
```
Ce script simule les 5 scénarios clés du parcours client WhatsApp :
1. **Recherche produit & consultation stock** (Galaxy A15, écouteurs...).
2. **Calcul de livraison géolocalisé** (zones tarifaires Bamako : Faladié, ACI 2000, Badalabougou...).
3. **Passation de commande multi-tours** avec confirmation explicite.
4. **Génération et téléchargement de facture PDF**.
5. **Gestion des ruptures de stock & escalade humaine (SAV)**.

### 3. Tests des Endpoints Dashboard
```bash
python scripts/test_dashboard_api.py
```

---

## 🐳 Déploiement en Production (Docker & Nginx)

Le projet fournit les configurations prêtes pour la production :
- `Dockerfile` : image Python allégée multi-stage pour l'API.
- `docker-compose.yml` : orchestration PostgreSQL + API backend.
- `nginx.conf` : reverse-proxy avec terminaison HTTPS/TLS, limitation de débit (rate limiting) et protection anti-brute force.
- `.env.production` : gabarit de variables d'environnement de production.

---

## 📁 Structure du Projet

```
MaliAgent/
├── app/
│   ├── agent/          # Orchestrateur de dialogue et boucle Tool Calling
│   ├── api/            # Routes FastAPI (Auth, Dashboard, Commandes, Produits, Factures)
│   ├── core/           # Configuration, Sécurité JWT, Dépendances, Logging
│   ├── db/             # Session SQLAlchemy asynchrone
│   ├── llm/            # Abstraction providers (Ollama Cloud...)
│   ├── models/         # Modèles relationnels (User, Business, Order, Product...)
│   ├── services/       # Moteur de génération PDF ReportLab
│   ├── tools/          # Définitions et exécuteurs des outils métier (DB réelle)
│   └── whatsapp/       # Client et Webhook Meta Cloud API
├── dashboard/          # Application Frontend Angular 21 (SPA réactive)
├── documentation/      # Cahier des charges et guide de soutenance
├── scripts/            # Scripts d'initialisation, seeds et tests de démonstration
├── tests/              # Suite de tests automatisés Pytest
├── storage/            # Stockage local des factures PDF générées
├── docker-compose.yml  # Orchestration des conteneurs
├── Dockerfile          # Image conteneur Backend
└── nginx.conf          # Configuration Reverse-Proxy Nginx
```
