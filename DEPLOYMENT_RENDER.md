# Guide de Déploiement de MaliAgent sur Render

Ce guide explique pas à pas comment déployer **MaliAgent** (API FastAPI, Base de données PostgreSQL avec `pgvector`, et Dashboard Angular) sur la plateforme Cloud [Render](https://render.com).

---

## Architecture sur Render

Le déploiement se compose de 3 services :
1. **`maliagent-db`** : Base de données gérée PostgreSQL 16 (avec extension `pgvector`).
2. **`maliagent-api`** : Web Service FastAPI conteneurisé sous Docker (gère le backend, les webhooks WhatsApp et l'IA).
3. **`maliagent-dashboard`** : Static Site pour l'application Angular (Dashboard Commerçant & Espace Livreur).

---

## Méthode 1 : Déploiement automatique en 1 clic (Render Blueprint) **[Recommandé]**

Grâce au fichier [`render.yaml`](./render.yaml) inclus dans le projet, Render configure et relie automatiquement les 3 briques.

### Étapes :
1. Poussez votre code sur votre dépôt GitHub ou GitLab :
   ```bash
   git add .
   git commit -m "feat: configuration déploiement Render"
   git push origin <votre-branche>
   ```
2. Rendez-vous sur votre compte **[Render Dashboard](https://dashboard.render.com/)**.
3. Cliquez sur le bouton bleu **New +** en haut à droite, puis sélectionnez **Blueprint**.
4. Connectez votre dépôt Git `MaliAgent`.
5. Render détecte automatiquement le fichier `render.yaml` et affiche la liste des ressources créées :
   - `maliagent-db` (Postgres)
   - `maliagent-api` (Web Service Docker)
   - `maliagent-dashboard` (Static Site Angular)
6. Cliquez sur **Apply**.
7. Une fois le déploiement lancé, renseignez les variables d'environnement secrètes dans l'onglet **Environment** de `maliagent-api` (voir la section *Variables d'environnement* ci-dessous).

---

## Méthode 2 : Déploiement manuel via le Dashboard Render

Si vous préférez créer chaque service manuellement :

### 1. Créer la base de données PostgreSQL
1. Sur Render, cliquez sur **New + > PostgreSQL**.
2. Nom : `maliagent-db`.
3. Database : `maliagent`.
4. User : `maliagent`.
5. Région : `Frankfurt (EU Central)` *(meilleure latence pour l'Afrique de l'Ouest)*.
6. Plan : `Free` (ou supérieur).
7. Cliquez sur **Create Database**.
8. Une fois provisionnée, copiez l'**Internal Database URL**.

### 2. Créer le Web Service API Backend
1. Cliquez sur **New + > Web Service**.
2. Sélectionnez votre dépôt Git `MaliAgent`.
3. Nom : `maliagent-api`.
4. Runtime : **Docker**.
5. Région : `Frankfurt (EU Central)`.
6. Health Check Path : `/health`.
7. Dans **Environment Variables**, ajoutez les variables listées ci-dessous.
8. Cliquez sur **Create Web Service**.

### 3. Créer le Dashboard Frontend (Angular)
1. Cliquez sur **New + > Static Site**.
2. Connectez le même dépôt Git.
3. Nom : `maliagent-dashboard`.
4. Root Directory : `dashboard`.
5. Build Command : `npm install && npm run build`.
6. Publish Directory : `dist/dashboard/browser`.
7. Dans l'onglet **Redirects / Rewrites**, ajoutez une règle :
   - Source : `/*`
   - Destination : `/index.html`
   - Action : `Rewrite`
8. Cliquez sur **Create Static Site**.

---

## Variables d'Environnement de l'API (`maliagent-api`)

| Variable | Exemple / Valeur | Description |
|---|---|---|
| `ENV` | `prod` | Mode d'exécution production |
| `DATABASE_URL` | *(Lien automatique Render ou Internal DB URL)* | URL de connexion PostgreSQL |
| `PORT` | `8000` *(Injecté par Render)* | Port d'écoute du serveur |
| `PUBLIC_BASE_URL` | `https://maliagent-api.onrender.com` | URL publique de votre API Render |
| `CORS_ORIGINS` | `https://maliagent-dashboard.onrender.com` | URL autorisée pour les requêtes du Dashboard |
| `JWT_SECRET_KEY` | *(Clé aléatoire de 64 caractères)* | Clé pour signer les tokens d'authentification |
| `JWT_ALGORITHM` | `HS256` | Algorithme JWT |
| `JWT_EXPIRE_MINUTES`| `1440` | Durée de session (24h) |
| `OLLAMA_API_KEY` | `votre_cle_ollama` | Clé API Ollama Cloud pour le LLM |
| `OLLAMA_BASE_URL` | `https://ollama.com` | Point d'entrée de l'API LLM |
| `OLLAMA_MODEL` | `gpt-oss:120b-cloud` | Modèle de conversation WhatsApp |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Modèle d'embeddings pour RAG / FAQ |
| `WHATSAPP_ACCESS_TOKEN` | `votre_token_meta` | Token permanent WhatsApp Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | `votre_phone_number_id` | Identifiant du numéro de téléphone Meta |
| `WHATSAPP_VERIFY_TOKEN` | `votre_token_verification` | Token de vérification du Webhook Meta |
| `META_APP_SECRET` | `votre_app_secret` | Secret pour valider la signature X-Hub-Signature |
| `PAYMENT_MODE` | `simulation` *(ou `production`)* | Mode de paiement Mobile Money |
| `PAYMENT_PROVIDER`| `mock` *(ou `wave`, `orange_money`)* | Passerelle de paiement active |
| `RUN_INIT_DB` | `true` | Crée automatiquement les tables et `vector` |

---

## Configuration du Webhook Meta WhatsApp

Une fois votre service `maliagent-api` déployé :
1. Rendez-vous sur le portail [Meta for Developers](https://developers.facebook.com/).
2. Allez dans votre application > **WhatsApp > Configuration**.
3. **URL de rappel (Callback URL)** :  
   `https://maliagent-api.onrender.com/webhook`
4. **Jeton de vérification (Verify Token)** :  
   La valeur que vous avez définie dans `WHATSAPP_VERIFY_TOKEN`.
5. Cliquez sur **Vérifier et enregistrer**.
6. Dans **Champs Webhook**, abonnez-vous au champ `messages`.

---

## Configuration du Dashboard pour contacter l'API

Puisque le Dashboard Angular est déployé en Static Site sur son propre domaine (ex: `https://maliagent-dashboard.onrender.com`) :
- Dans l'API (`maliagent-api`), assurez-vous que `CORS_ORIGINS` contient l'URL du dashboard :  
  `https://maliagent-dashboard.onrender.com`
- Dans le navigateur, vous pouvez pointer vers l'API en renseignant dans le localStorage :  
  `localStorage.setItem('maliagent_api_url', 'https://maliagent-api.onrender.com')`  
  ou en mettant à jour la constante dans [`dashboard/src/environments/environment.prod.ts`](./dashboard/src/environments/environment.prod.ts).

---

## Initialisation des données de démo ou Super Admin

Pour créer le premier utilisateur Super Admin en production :
1. Dans le Dashboard Render, ouvrez le service `maliagent-api`.
2. Allez dans l'onglet **Shell**.
3. Exécutez :
   ```bash
   python scripts/create_super_admin.py
   ```
   ou pour peupler des données de test :
   ```bash
   python scripts/seed_pilot_data.py
   ```
