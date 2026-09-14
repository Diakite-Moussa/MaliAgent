# 🇲🇱 MaliAgent — Guide de Présentation du MVP (Soutenance)

Ce document sert de support pour présenter et soutenir le projet **MaliAgent (Sprint 8 — Stabilisation)**. Il met en valeur les choix d'architecture, la sécurité mise en œuvre et le déroulement de la démonstration en direct.

---

## 1. Contexte & Problématique Résolue

- **Contexte local** : Au Mali, l'immense majorité du commerce digital s'effectue sur **WhatsApp**, mais de façon purement manuelle.
- **Pain points des commerçants** :
  - Saturation par les questions répétitives sur les prix et le stock disponible.
  - Erreurs fréquentes sur les tarifs de livraison à Bamako (Rive Droite vs Rive Gauche).
  - Absence de facturation formelle ou de traçabilité des commandes.
  - Perte de clients en soirée et pendant les heures de fermeture.
- **La solution MaliAgent** : Un agent conversationnel autonome connecté à la base de données réelle de la boutique, capable de conclure la vente, calculer la livraison exacte, générer une facture PDF officielle et alerter le commerçant en cas de besoin.

---

## 2. Piliers d'Architecture & Choix Techniques

| Composant | Technologie | Rôle & Justification |
|---|---|---|
| **Backend API** | FastAPI + Python 3.12 | Haute performance asynchrone, typage strict avec Pydantic. |
| **Persistance** | PostgreSQL 16 + SQLAlchemy 2.0 Async | Robustesse relationnelle, intégrité référentielle, isolation multi-tenant. |
| **Agent IA** | LLMProvider + Tool Calling déterministe | L'IA ne "devine" rien : elle appelle obligatoirement des fonctions Python interrogant la DB. |
| **Messagerie** | Meta WhatsApp Cloud API | Canal natif de l'utilisateur, signature cryptographique HMAC-SHA256. |
| **Facturation** | ReportLab | Génération instantanée de factures PDF avec QR Code et statut de paiement. |
| **Frontend** | Angular 21 (Standalone, Signals) | Tableau de bord commerçant moderne, suivi des KPIs en temps réel, auth JWT. |

---

## 3. Déroulé Idéal de la Démonstration (Scénarios Validés)

Pour une soutenance percutante, suivre les **5 étapes conversationnelles réelles** validées par le script `test_pilot_e2e_scenarios.py` :

### 🟢 Scénario 1 : Consultation du Catalogue & Détection d'Intention
- **Message client** : *"Bonjour, vous vendez des téléphones Samsung ?"*
- **Action de l'Agent** : Appelle `search_products(query="Samsung")`.
- **Réponse WhatsApp** : Présentation claire et aérée (interdiction stricte des tableaux Markdown illisibles sur smartphone) avec prix en FCFA et stock disponible.

### 🟢 Scénario 2 : Calcul Intelligent de la Livraison à Bamako
- **Message client** : *"Je suis à Faladié, combien coûte la livraison ?"*
- **Action de l'Agent** : Appelle `calculate_delivery(zone="Faladié")`.
- **Réponse WhatsApp** : Détecte la Zone 2 (Rive Droite, Commune VI) et annonce le tarif exact de 1 500 FCFA.

### 🟢 Scénario 3 : Passation de Commande & Confirmation Explicite
- **Message client** : *"Je veux acheter le Galaxy A15."*
- **Règle métier** : L'agent présente un récapitulatif complet et **exige une confirmation explicite** avant de créer la commande.
- **Message client** : *"Oui, je confirme."*
- **Action de l'Agent** : Appelle `create_order(...)`, réserve le stock et fournit le numéro de commande `#...`.

### 🟢 Scénario 4 : Facturation Instantanée PDF
- **Message client** : *"Pouvez-vous m'envoyer la facture ?"*
- **Action de l'Agent** : Appelle `generate_invoice(...)`.
- **Résultat** : Un lien direct vers la facture PDF officielle mise en page avec numéro fiscal, montant et QR Code.

### 🟢 Scénario 5 : SAV, Rupture Partielle & Escalade Humaine
- **Cas 1 (Rupture partielle)** : Si un produit est en rupture, l'agent propose immédiatement une alternative en stock.
- **Cas 2 (Demande humaine)** : *"Je souhaite négocier le prix avec le responsable."*
- **Action de l'Agent** : Appelle `escalate_to_human(...)`, met la conversation en pause pour l'IA et notifie le Dashboard commerçant avec une bannière urgente.

---

## 4. Sécurité & Conformité (Points Clés pour le Jury)

1. **Isolation Multi-Tenant absolue** :
   - Chaque requête API et appel d'outil est strictement borné par le `business_id` extrait du token JWT vérifié.
   - Une boutique `Alpha` ne peut sous aucun prétexte consulter ou modifier les stocks, clients ou commandes de la boutique `Beta` (100% couvert par la suite de tests Pytest).
2. **Protection Webhook Meta** :
   - Vérification de l'en-tête `X-Hub-Signature-256` via HMAC-SHA256 avec `META_APP_SECRET` pour bloquer toute injection de faux messages.
3. **Sécurité Web & CORS** :
   - Restriction stricte des origines CORS au dashboard commerçant.
   - Protection anti-brute force configurée sur Nginx (rate limiting dédié sur `/api/auth/login`).

---

## 5. Commandes de Validation pour la Présentation

```bash
# 1. Lancer la suite de tests de sécurité
python -m pytest tests/ -v

# 2. Lancer la simulation conversationnelle E2E
python scripts/test_pilot_e2e_scenarios.py

# 3. Lancer l'interface commerçant
cd dashboard && npm start
```
