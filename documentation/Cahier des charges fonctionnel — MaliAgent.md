# UNIVERSITÉ MUNDIAPOLIS — CASABLANCA

## Faculté des Sciences de l'Ingénieur et des Technologies de l'Information

### Cycle Ingénieur — Génie Informatique

# CAHIER DES CHARGES FONCTIONNEL

## Projet : **MaliAgent**

### Plateforme d'agents intelligents pour l'automatisation du commerce conversationnel

**Étudiant :** Moussa Diakité  
**Filière :** Cycle Ingénieur — Génie Informatique  
**Niveau :** 2ᵉ année cycle ingénieur  
**Année académique :** 2025 – 2026

---

# 1. Présentation générale du projet

## 1.1 Nom du projet

**MaliAgent**

## 1.2 Description

MaliAgent est une plateforme d'agents intelligents destinée dans un premier temps aux commerçants et petites et moyennes entreprises maliennes.

La plateforme a pour objectif de permettre à une entreprise de disposer d'un **agent conversationnel intelligent accessible depuis WhatsApp**, capable d'interagir automatiquement avec ses clients et d'effectuer certaines opérations commerciales à travers des outils sécurisés.

L'agent peut notamment :

- répondre aux questions des clients ;
- présenter les produits disponibles ;
- rechercher un produit ;
- consulter le stock réel ;
- communiquer les prix ;
- prendre une commande ;
- consulter l'état d'une commande ;
- annuler une commande selon les règles de l'entreprise ;
- calculer les frais de livraison ;
- générer une facture ;
- transmettre la conversation à un humain lorsque cela est nécessaire.

Les informations commerciales sont administrées depuis un **dashboard web**.

Le dashboard permet notamment au commerçant de gérer :

- les produits ;
- les catégories ;
- les prix ;
- le stock ;
- les clients ;
- les commandes ;
- les factures ;
- les règles commerciales ;
- la base de connaissances de l'agent.

MaliAgent est conçu comme une plateforme évolutive.

Dans sa première version, le système cible principalement le commerce via WhatsApp. Les versions futures pourront intégrer :

- plusieurs types d'entreprises ;
- le français et le bambara ;
- les interactions vocales ;
- les paiements numériques ;
- la livraison ;
- plusieurs agents spécialisés ;
- plusieurs canaux de communication ;
- plusieurs pays d'Afrique de l'Ouest.

---

# 2. Contexte et problématique

## 2.1 Contexte

Les smartphones et les applications de messagerie sont largement utilisés pour communiquer entre commerçants et clients.

WhatsApp est particulièrement intéressant pour le commerce conversationnel, car les clients peuvent contacter directement une entreprise afin de :

- demander le prix d'un produit ;
- vérifier sa disponibilité ;
- demander des informations ;
- passer une commande ;
- demander les conditions de livraison.

Cependant, lorsque le nombre de clients augmente, la gestion manuelle des conversations devient difficile.

Le commerçant doit simultanément :

- répondre aux messages ;
- rechercher les produits ;
- vérifier le stock ;
- calculer les prix ;
- enregistrer les commandes ;
- suivre les clients ;
- gérer les livraisons ;
- produire les factures.

Cette organisation peut provoquer :

- des délais de réponse importants ;
- des erreurs humaines ;
- des oublis ;
- des réponses incohérentes ;
- des erreurs de stock ;
- une mauvaise traçabilité des commandes.

## 2.2 Problématique

La problématique principale du projet est donc :

> **Comment concevoir une plateforme d'agents intelligents capable d'automatiser une partie du processus commercial d'une entreprise à travers WhatsApp tout en garantissant l'accès à des données commerciales fiables, sécurisées et propres à chaque entreprise ?**

Le projet doit également prendre en compte les particularités du marché malien :

- utilisation importante de la messagerie mobile ;
- importance du FCFA ;
- besoins de communication en français et potentiellement en bambara ;
- qualité variable de la connexion Internet ;
- utilisation de smartphones de différentes capacités ;
- développement progressif du commerce numérique.

---

# 3. Vision du projet

MaliAgent ne doit pas être considéré uniquement comme un chatbot.

La vision du projet est de construire progressivement une **plateforme d'agents IA pour les entreprises africaines**.

Le principe est :

```text
                    MALIAGENT
                        |
       +----------------+----------------+
       |                |                |
    Commerce         Support          Gestion
       |                |                |
       +----------------+----------------+
                        |
                    Agent IA
                        |
              +---------+---------+
              |                   |
            WhatsApp          Dashboard
              |                   |
              +---------+---------+
                        |
                     Backend
                        |
                   PostgreSQL
```

Chaque entreprise dispose de son propre environnement :

```text
MaliAgent
   |
   +--- Boutique Moussa
   |      |
   |      +--- Produits
   |      +--- Stock
   |      +--- Clients
   |      +--- Commandes
   |      +--- RAG
   |      +--- Agent
   |
   +--- Restaurant Awa
          |
          +--- Menus
          +--- Clients
          +--- Commandes
          +--- Agent
```

Le moteur d'intelligence artificielle reste commun, mais les données et les règles sont propres à chaque entreprise.

---

# 4. Objectifs du projet

## 4.1 Objectif général

L'objectif général est de concevoir et développer une plateforme d'agents intelligents permettant aux entreprises d'automatiser leurs interactions commerciales avec leurs clients via WhatsApp.

La solution doit permettre à un agent IA de comprendre les demandes des clients, consulter les informations commerciales réelles de l'entreprise grâce à des outils contrôlés et effectuer certaines opérations commerciales.

---

# 4.2 Objectifs spécifiques

Les objectifs spécifiques sont :

- Développer un agent conversationnel basé sur un LLM.
- Connecter l'agent à WhatsApp grâce à WhatsApp Cloud API.
- Mettre en place un webhook permettant de recevoir les messages WhatsApp.
- Permettre à l'agent de répondre automatiquement aux clients.
- Mettre en place une gestion des conversations.
- Maintenir le contexte des conversations.
- Connecter l'agent à une base de connaissances avec RAG.
- Permettre à l'agent d'utiliser des outils backend.
- Permettre à l'agent de rechercher des produits.
- Permettre à l'agent de vérifier le stock.
- Permettre à l'agent de créer des commandes.
- Permettre à l'agent de consulter les commandes.
- Permettre à l'agent d'annuler certaines commandes.
- Permettre le calcul sécurisé des frais de livraison.
- Permettre la génération de factures.
- Développer un dashboard web pour le commerçant.
- Assurer l'isolation des données entre les différentes entreprises.
- Empêcher le LLM d'accéder directement à PostgreSQL.
- Garantir que les informations financières proviennent du backend.
- Prévoir un système d'escalade vers un humain.
- Préparer l'évolution vers la voix et le multilingue.
- Préparer l'évolution vers une plateforme multi-entreprises.

---

# 5. Périmètre du projet

Le projet est organisé en plusieurs versions afin de distinguer le **MVP réellement développé** des fonctionnalités futures.

# 5.1 Version V0.1 — AI Core

Cette version constitue le cœur technique de MaliAgent.

Fonctionnalités :

- intégration du LLM ;
- définition du comportement de l'agent ;
- système de prompt ;
- gestion du contexte ;
- mémoire conversationnelle courte ;
- validation des entrées ;
- gestion des erreurs ;
- guardrails ;
- RAG ;
- pgvector ;
- tools/function calling ;
- sécurité ;
- conteneurisation Docker.

Outils principaux :

```text
search_products()
get_product()
check_stock()
create_order()
get_order()
cancel_order()
calculate_delivery()
create_invoice()
get_invoice()
```

---

# 5.2 Version V0.2 — Agent WhatsApp

Cette version connecte l'agent à WhatsApp.

Fonctionnalités :

- configuration WhatsApp Business Platform ;
- WhatsApp Cloud API ;
- webhook ;
- réception des messages ;
- envoi des réponses ;
- gestion des sessions ;
- historique des conversations ;
- identification des clients ;
- traitement des erreurs ;
- premiers tests avec un numéro réel.

Architecture :

```text
Client
   |
WhatsApp
   |
WhatsApp Cloud API
   |
Webhook
   |
FastAPI
   |
MaliAgent
   |
WhatsApp Cloud API
   |
Client
```

---

# 5.3 Version V0.3 — Commerce Agent

Cette version ajoute les fonctionnalités commerciales.

## Produits

- création ;
- modification ;
- suppression ;
- recherche ;
- catégories ;
- variantes ;
- tailles ;
- couleurs ;
- photos ;
- prix ;
- promotions.

## Stock

- quantité disponible ;
- mise à jour du stock ;
- vérification automatique ;
- historique des mouvements.

## Clients

- création automatique ;
- identification par numéro WhatsApp ;
- informations client ;
- historique des commandes.

## Commandes

- création ;
- consultation ;
- modification ;
- annulation ;
- historique ;
- statut.

Statuts possibles :

```text
PENDING
CONFIRMED
PREPARING
READY
OUT_FOR_DELIVERY
DELIVERED
CANCELLED
```

## Livraison

- adresse ;
- zone ;
- frais ;
- estimation ;
- règles de livraison.

---

# 5.4 Version V0.4 — Business Agent

Fonctionnalités :

- factures PDF ;
- numérotation ;
- client ;
- produits ;
- quantité ;
- prix ;
- total ;
- statut de facture ;
- statistiques commerciales ;
- notifications ;
- transfert vers un humain.

Le paiement à la livraison constitue le premier mode de paiement prévu.

L'architecture doit toutefois permettre l'ajout futur de services de paiement numérique.

---

# 5.5 Version V0.5 — Voice & Multilingual

Fonctionnalités futures :

- messages vocaux WhatsApp ;
- transcription automatique ;
- détection de langue ;
- français ;
- bambara ;
- anglais ;
- génération de réponse vocale ;
- synthèse vocale.

Architecture :

```text
Message vocal
      |
     STT
      |
Détection langue
      |
   MaliAgent
      |
    TTS
      |
Message vocal
      |
   WhatsApp
```

---

# 5.6 Version V0.6 — Multi-business

MaliAgent devient configurable pour plusieurs types
d'entreprises.

Exemples :

- boutiques ;
- restaurants ;
- salons de beauté ;
- tailleurs ;
- magasins de téléphones ;
- artisans ;
- entreprises agricoles ;
- services ;
- autres PME.

Le moteur IA reste commun mais la configuration change selon l'entreprise.

---

# 5.7 Version V1.0 — Plateforme SaaS

La plateforme doit permettre à plusieurs entreprises d'utiliser MaliAgent.

Chaque entreprise dispose de :

- son propre compte ;
- ses propres utilisateurs ;
- ses propres produits ;
- son propre stock ;
- ses propres clients ;
- ses propres commandes ;
- ses propres factures ;
- sa propre base de connaissances ;
- sa propre configuration d'agent ;
- son propre numéro WhatsApp.

---

# 5.8 Versions futures

## V1.5 — Multi-Agent

Introduction de plusieurs agents spécialisés :

```text
                  Orchestrateur
                       |
       +---------------+---------------+
       |               |               |
    Sales Agent   Support Agent   Inventory Agent
       |               |               |
       +---------------+---------------+
                       |
                  Business Data
```

Agents possibles :

- Sales Agent ;
- Support Agent ;
- Finance Agent ;
- Inventory Agent ;
- Marketing Agent ;
- Delivery Agent.

## V2.0 — Logistique

Fonctionnalités :

- application livreur ;
- missions de livraison ;
- navigation ;
- suivi ;
- statut de livraison ;
- preuve de livraison ;
- géolocalisation ;
- historique.

## V2.5 — MaliAgent Pay

Fonctionnalités futures :

- paiement à la livraison ;
- Mobile Money ;
- paiement en ligne ;
- paiements partiels ;
- remboursements ;
- portefeuille ;
- transactions ;
- reçus ;
- webhooks ;
- idempotence ;
- vérification des signatures ;
- détection d'anomalies.

## V3.0 — MaliAgent AI Ecosystem

La plateforme pourra évoluer vers un écosystème comprenant :

- commerce ;
- agents IA ;
- voix ;
- finance ;
- logistique ;
- analytics ;
- marketplace ;
- automatisation.

## V4.0 — Extension Afrique de l'Ouest

Extension potentielle vers :

- Sénégal ;
- Côte d'Ivoire ;
- Burkina Faso ;
- Niger ;
- Guinée ;
- Mauritanie.

L'architecture devra permettre l'adaptation :

- des langues ;
- des monnaies ;
- des moyens de paiement ;
- des règles commerciales ;
- de la fiscalité ;
- de la logistique.

---

# 6. Acteurs du système

## 6.1 Client

Le client est l'utilisateur final qui communique avec l'entreprise.

Il utilise principalement WhatsApp.

Il peut :

- envoyer des messages ;
- demander des informations ;
- rechercher des produits ;
- demander les prix ;
- vérifier la disponibilité ;
- passer une commande ;
- consulter une commande ;
- demander une facture ;
- demander des informations sur la livraison.

Le client n'accède pas directement au dashboard.

---

# 6.2 Commerçant / Administrateur

Le commerçant utilise le dashboard pour administrer son entreprise.

Il peut :

- gérer les produits ;
- gérer le stock ;
- consulter les commandes ;
- gérer les clients ;
- gérer les factures ;
- configurer l'agent ;
- gérer les documents de connaissance ;
- consulter les statistiques.

---

# 6.3 Administrateur de plateforme

Dans la version multi-entreprises, l'administrateur de la plateforme peut :

- créer des entreprises ;
- activer ou désactiver une entreprise ;
- gérer les comptes ;
- superviser la plateforme ;
- consulter les statistiques globales ;
- gérer les paramètres globaux.

---

# 6.4 Agent IA

L'agent IA constitue le composant intelligent de la plateforme.

Il peut :

- comprendre les demandes ;
- maintenir le contexte ;
- utiliser les connaissances de l'entreprise ;
- appeler les outils disponibles ;
- générer une réponse ;
- détecter certaines situations nécessitant une intervention humaine.

L'agent ne doit pas prendre de décision financière en inventant des informations.

---

# 6.5 Administrateur humain / opérateur

Un opérateur humain peut reprendre une conversation lorsqu'une intervention est nécessaire.

L'agent doit transmettre le contexte disponible afin d'éviter au client de répéter toutes ses informations.

---

# 7. Fonctionnalités principales

# RF-001 — Réception d'un message WhatsApp

Le système doit recevoir les messages envoyés au numéro WhatsApp connecté à MaliAgent.

Flux :

```text
Client
 ↓
WhatsApp
 ↓
Meta
 ↓
Webhook FastAPI
```

Priorité : Très haute.

---

# RF-002 — Traitement du message

Le backend doit transmettre le message reçu à l'agent IA.

L'agent doit analyser :

- le contenu ;
- le contexte de conversation ;
- l'identité du client ;
- l'entreprise concernée ;
- les règles commerciales.

Priorité : Très haute.

---

# RF-003 — Réponse automatique

L'agent doit pouvoir générer une réponse adaptée au client.

La réponse est envoyée à WhatsApp par le backend.

Priorité : Très haute.

---

# RF-004 — Gestion des conversations

Le système doit conserver l'historique des conversations.

Une conversation doit être associée à :

- un client ;
- une entreprise ;
- un numéro WhatsApp ;
- une date ;
- des messages ;
- un statut.

Priorité : Haute.

---

# RF-005 — Gestion du contexte

L'agent doit conserver le contexte nécessaire d'une conversation.

Exemple :

Client :

> Je veux le Samsung A15.

Agent :

> Quelle couleur souhaitez-vous ?

Client :

> Noir.

L'agent doit comprendre que « noir » concerne le Samsung A15 précédemment demandé.

Priorité : Haute.

---

# RF-006 — Recherche de produits

L'agent doit pouvoir rechercher un produit dans le catalogue.

Exemple :

> « Avez-vous un Samsung A15 ? »

L'agent utilise :

```text
search_products()
```

Le backend consulte la base de données.

Priorité : Très haute.

---

# RF-007 — Consultation du stock

L'agent doit pouvoir consulter le stock réel.

Exemple :

```text
check_stock(product_id)
```

Le stock retourné doit provenir de PostgreSQL.

L'agent ne doit jamais inventer une quantité.

Priorité : Très haute.

---

# RF-008 — Communication du prix

Le prix communiqué au client doit provenir des données commerciales enregistrées.

Exemple :

```text
get_product(product_id)
```

Le LLM ne doit jamais inventer un prix.

Priorité : Très haute.

---

# RF-009 — Création d'une commande

Le client doit pouvoir passer une commande depuis WhatsApp.

Exemple :

> « Je prends deux Samsung A15 noirs. »

L'agent vérifie :

1. le produit ;
2. la variante ;
3. le stock ;
4. la quantité ;
5. les informations du client ;
6. la livraison.

Puis il utilise :

```text
create_order()
```

Le backend crée réellement la commande.

Priorité : Très haute.

---

# RF-010 — Consultation d'une commande

Le client doit pouvoir demander l'état de sa commande.

Exemple :

> « Où est ma commande ? »

L'agent utilise :

```text
get_order()
```

Le backend retourne le statut réel.

Priorité : Haute.

---

# RF-011 — Annulation d'une commande

Le client peut demander l'annulation d'une commande lorsqu'elle respecte les règles définies par l'entreprise.

Le backend doit vérifier que l'annulation est autorisée.

L'agent ne doit pas annuler directement une commande sans passer par l'outil backend.

Priorité : Haute.

---

# RF-012 — Calcul de livraison

L'agent doit pouvoir calculer les frais de livraison selon les règles du commerce.

Exemple :

```text
calculate_delivery(zone)
```

Le calcul est effectué par le backend.

Le LLM ne doit pas inventer les frais.

Priorité : Haute.

---

# RF-013 — Génération de facture

Le système doit permettre de générer une facture correspondant à une commande.

La facture doit contenir :

- numéro ;
- client ;
- produits ;
- quantités ;
- prix unitaires ;
- sous-total ;
- frais de livraison ;
- montant total ;
- date ;
- statut.

La génération du PDF doit être réalisée côté backend.

Priorité : Haute.

---

# RF-014 — Base de connaissances

Le commerçant doit pouvoir fournir des documents et informations concernant son entreprise.

Exemples :

- politique de retour ;
- horaires ;
- conditions de livraison ;
- présentation de l'entreprise ;
- catalogue PDF ;
- FAQ ;
- conditions commerciales.

Ces documents sont transformés en connaissances utilisables par l'agent.

Priorité : Haute.

---

# RF-015 — Recherche RAG

L'agent doit pouvoir rechercher les informations pertinentes dans la base de connaissances avant de répondre.

Architecture :

```text
Document
   ↓
Découpage
   ↓
Embeddings
   ↓
pgvector
   ↓
Recherche sémantique
   ↓
Contexte
   ↓
LLM
```

Priorité : Haute.

---

# RF-016 — Utilisation des outils

L'agent doit pouvoir appeler des outils contrôlés.

Outils principaux :

```text
search_products()
get_product()
check_stock()
create_order()
get_order()
cancel_order()
calculate_delivery()
create_invoice()
get_invoice()
```

Le backend contrôle l'exécution de chaque outil.

Priorité : Très haute.

---

# RF-017 — Protection contre les hallucinations

L'agent doit respecter les règles suivantes :

- ne jamais inventer un produit ;
- ne jamais inventer un prix ;
- ne jamais inventer un stock ;
- ne jamais inventer une commande ;
- ne jamais inventer une facture ;
- ne jamais effectuer de calcul financier critique uniquement à partir du LLM ;
- utiliser les outils lorsqu'une donnée réelle est nécessaire ;
- signaler l'incertitude lorsqu'il ne possède pas suffisamment d'informations.

Priorité : Très haute.

---

# RF-018 — Transfert vers un humain

Lorsqu'une situation dépasse les capacités de l'agent, celui-ci doit pouvoir transférer la conversation à un opérateur humain.

Situations possibles :

- demande complexe ;
- plainte ;
- problème de paiement ;
- demande inhabituelle ;
- incertitude élevée ;
- demande explicitement humaine.

Priorité : Haute.

---

# RF-019 — Gestion des produits

Le dashboard doit permettre au commerçant de :

- créer un produit ;
- modifier un produit ;
- supprimer un produit ;
- rechercher un produit ;
- classer un produit ;
- ajouter une image ;
- définir son prix ;
- définir son stock ;
- définir ses variantes.

Exemple :

```text
Samsung A15
Prix : 85 000 FCFA
Stock : 10
Couleur : Noir
Couleur : Bleu
```

Priorité : Très haute.

---

# RF-020 — Gestion du stock

Le commerçant doit pouvoir :

- consulter le stock ;
- ajouter du stock ;
- diminuer le stock ;
- consulter l'historique ;
- recevoir des alertes de stock faible.

Le stock doit être modifié uniquement par des opérations backend contrôlées.

Priorité : Très haute.

---

# RF-021 — Gestion des commandes

Le dashboard doit afficher :

- numéro ;
- client ;
- produits ;
- quantité ;
- montant ;
- livraison ;
- statut ;
- date.

Le commerçant doit pouvoir modifier le statut selon les permissions.

Priorité : Très haute.

---

# RF-022 — Gestion des clients

Le système doit créer et gérer les profils clients.

Informations :

- nom ;
- téléphone ;
- adresse ;
- historique ;
- commandes ;
- date de création.

Le numéro WhatsApp peut constituer l'identifiant permettant de reconnaître un client.

Priorité : Haute.

---

# RF-023 — Configuration de l'agent

Le commerçant doit pouvoir configurer son agent.

Configuration possible :

### Profil de l'entreprise

- nom ;
- type d'entreprise ;
- description ;
- adresse ;
- horaires ;
- langue ;
- devise.

### Identité de l'agent

- nom de l'agent ;
- ton ;
- style de communication ;
- langue ;
- niveau de formalité.

### Règles commerciales

Exemple :

```text
- Livraison uniquement à Bamako
- Frais de livraison : 1 000 FCFA
- Paiement à la livraison
- Vérifier le stock avant toute confirmation
- Ne jamais inventer le prix
- Transférer au commerçant en cas d'incertitude
```

### Outils activés

Le commerçant peut disposer d'un ensemble d'outils autorisés selon son abonnement ou son type d'entreprise.

---

# RF-024 — Gestion de plusieurs entreprises

Le système doit supporter plusieurs entreprises.

Chaque entreprise doit disposer de données isolées.

Exemple :

```text
Boutique Moussa
     |
     +--- Produits
     +--- Clients
     +--- Commandes
     +--- RAG

Restaurant Awa
     |
     +--- Menus
     +--- Clients
     +--- Commandes
     +--- RAG
```

Une entreprise ne doit jamais pouvoir accéder aux données d'une autre.

Priorité : Très haute pour la version SaaS.

---

# RF-025 — Gestion des utilisateurs d'une entreprise

Le système doit permettre au responsable d'une entreprise de gérer ses utilisateurs.

Selon les droits :

- administrateur ;
- vendeur ;
- opérateur ;
- responsable de stock ;
- responsable des commandes.

Cette fonctionnalité sera progressivement enrichie dans la version SaaS.

---

# RF-026 — Tableau de bord

Le dashboard doit présenter des informations synthétiques.

Exemples :

```text
Commandes aujourd'hui       25
Chiffre d'affaires          850 000 FCFA
Produits en stock           143
Stock faible                 12
Clients                      89
Conversations                57
```

Le dashboard doit également afficher les commandes récentes et les alertes importantes.

---

# 8. Règles métier

## RB-001 — Isolation des entreprises

Une entreprise ne peut accéder qu'à ses propres données.

## RB-002 — Source de vérité

PostgreSQL constitue la source de vérité pour :

- produits ;
- prix ;
- stock ;
- clients ;
- commandes ;
- factures.

## RB-003 — Le LLM ne possède pas d'accès direct à PostgreSQL

Le LLM doit passer par les outils exposés par le backend.

```text
LLM
 |
Tool
 |
Backend
 |
PostgreSQL
```

## RB-004 — Vérification du stock

Une commande ne peut être confirmée sans vérification du stock.

## RB-005 — Prix

Le prix doit être récupéré depuis le backend.

## RB-006 — Calcul financier

Les montants importants doivent être calculés par le backend.

## RB-007 — Commande

Une commande ne peut être créée que par le service backend correspondant.

## RB-008 — Annulation

Une commande ne peut être annulée que si son statut permet l'annulation.

## RB-009 — Livraison

Les frais doivent être calculés selon les règles configurées pour l'entreprise.

## RB-010 — Transfert humain

L'agent doit pouvoir transférer une conversation à un humain lorsqu'il ne peut pas fournir une réponse fiable.

## RB-011 — Contexte entreprise

L'agent doit toujours connaître l'entreprise correspondant à la conversation.

## RB-012 — Confidentialité

Les données d'une entreprise ne doivent jamais être utilisées pour répondre à une autre entreprise.

---

# 9. Architecture fonctionnelle

L'architecture principale de MaliAgent est :

```text
                         CLIENT
                            |
                            |
                        WhatsApp
                            |
                            |
                 WhatsApp Cloud API
                            |
                            |
                         Webhook
                            |
                            ▼
                       FastAPI
                            |
                            ▼
                    Agent MaliAgent
                            |
              +-------------+-------------+
              |             |             |
              ▼             ▼             ▼
             LLM           RAG          Tools
              |             |             |
           Qwen/Ollama   pgvector      Backend
                                           |
                                           ▼
                                      PostgreSQL
```

Dashboard :

```text
Commerçant
     |
     ▼
Dashboard Web
     |
     ▼
FastAPI
     |
     ▼
PostgreSQL
```

WhatsApp et le dashboard utilisent donc le même backend et la même source de données.

---

# 10. Architecture de l'agent IA

L'agent repose sur plusieurs composants.

```text
Message utilisateur
       |
       ▼
Analyse de l'intention
       |
       ▼
Contexte conversationnel
       |
       +------ RAG
       |
       +------ Tools
       |
       ▼
      LLM
       |
       ▼
Validation
       |
       ▼
Réponse
```

L'orchestration pourra être réalisée avec LangGraph.

---

# 11. RAG et base de connaissances

Le RAG permet à l'agent d'utiliser les informations spécifiques à l'entreprise.

Exemples :

- conditions de retour ;
- horaires ;
- politique de livraison ;
- présentation ;
- FAQ ;
- documents commerciaux.

Pipeline :

```text
Document
   ↓
Extraction du texte
   ↓
Chunking
   ↓
Embedding
   ↓
PostgreSQL + pgvector
   ↓
Recherche sémantique
   ↓
Contexte envoyé au LLM
```

Le RAG ne remplace pas la base de données commerciale.

Par exemple :

**RAG :**

> « La boutique accepte les retours sous sept jours. »

**PostgreSQL :**

> Samsung A15 — Stock : 10 — Prix : 85 000 FCFA.

Les deux systèmes ont donc des responsabilités différentes.

---

# 12. Architecture des Tools

Les tools permettent à l'agent d'effectuer des actions réelles.

Exemple :

```text
Client :
"Est-ce que vous avez le Samsung A15 ?"

       ↓

MaliAgent

       ↓

search_products()

       ↓

Backend

       ↓

PostgreSQL

       ↓

Résultat réel

       ↓

MaliAgent

       ↓

WhatsApp
```

Cette architecture permet de réduire les hallucinations.

---

# 13. Modèle de données

La base de données principale sera PostgreSQL.

Les principales entités sont :

```text
Business
User
Customer
Product
Category
ProductVariant
Stock
Order
OrderItem
Invoice
Conversation
Message
KnowledgeDocument
KnowledgeChunk
AgentConfiguration
DeliveryZone
DeliveryRule
Tool
AuditLog
```

---

# 13.1 Business

```text
businesses

id
name
type
description
phone
address
currency
status
created_at
updated_at
```

---

# 13.2 User

```text
users

id
business_id
first_name
last_name
email
phone
password_hash
role
status
created_at
updated_at
```

---

# 13.3 Customer

```text
customers

id
business_id
name
phone
email
address
created_at
updated_at
```

---

# 13.4 Product

```text
products

id
business_id
category_id
name
description
price
stock_quantity
status
created_at
updated_at
```

---

# 13.5 Category

```text
categories

id
business_id
name
description
```

---

# 13.6 ProductVariant

```text
product_variants

id
product_id
name
value
stock_quantity
price
```

Exemple :

```text
Couleur = Noir
Taille = XL
```

---

# 13.7 Order

```text
orders

id
business_id
customer_id
status
subtotal
delivery_fee
total
delivery_address
created_at
updated_at
```

---

# 13.8 OrderItem

```text
order_items

id
order_id
product_id
quantity
unit_price
total
```

---

# 13.9 Invoice

```text
invoices

id
business_id
order_id
invoice_number
subtotal
delivery_fee
total
status
pdf_path
created_at
```

---

# 13.10 Conversation

```text
conversations

id
business_id
customer_id
channel
status
created_at
updated_at
```

---

# 13.11 Message

```text
messages

id
conversation_id
sender
content
message_type
created_at
```

Types :

```text
USER
AGENT
HUMAN
SYSTEM
```

---

# 13.12 KnowledgeDocument

```text
knowledge_documents

id
business_id
name
source
content
created_at
updated_at
```

---

# 13.13 KnowledgeChunk

```text
knowledge_chunks

id
document_id
content
embedding
metadata
```

L'embedding est stocké dans PostgreSQL grâce à pgvector.

---

# 13.14 AgentConfiguration

```text
agent_configurations

id
business_id
agent_name
system_prompt
language
tone
enabled
created_at
updated_at
```

---

# 13.15 DeliveryZone

```text
delivery_zones

id
business_id
name
fee
estimated_time
active
```

---

# 13.16 AuditLog

```text
audit_logs

id
business_id
user_id
action
entity_type
entity_id
created_at
details
```

---

# 14. Gestion multi-tenant

La plateforme doit être conçue selon une architecture multi-tenant.

Exemple :

```text
                    MaliAgent
                        |
        +---------------+---------------+
        |               |               |
        ▼               ▼               ▼
   Business A      Business B      Business C
        |               |               |
       DB              DB              DB
```

Dans une première architecture, les données peuvent être stockées dans une base PostgreSQL commune avec un identifiant `business_id`.

Exemple :

```text
products

id | business_id | name | price | stock
1  | A           | A15  | 85000 | 10
2  | B           | Riz  | 12000 | 50
```

Toutes les requêtes backend doivent obligatoirement filtrer par `business_id`.

---

# 15. Configuration d'un agent pour une entreprise

L'entreprise n'a pas besoin d'entraîner un nouveau modèle IA.

MaliAgent utilise un moteur IA commun.

La personnalisation s'effectue par configuration.

Exemple :

```text
Entreprise :
Boutique Moussa

Type :
Commerce électronique

Langues :
Français + Bambara

Devise :
FCFA

Livraison :
Bamako

Frais :
1 000 FCFA

Paiement :
À la livraison
```

Puis :

```text
Agent :
Moussa AI

Ton :
Professionnel et chaleureux

Règles :
- Ne jamais inventer le stock
- Vérifier le stock avant commande
- Ne jamais inventer les prix
- Transférer à l'humain en cas de problème
```

L'agent devient ainsi spécifique à l'entreprise sans entraîner un nouveau modèle.

---

# 16. Intégration WhatsApp

Le fonctionnement prévu est :

```text
                    Client
                      |
                      ▼
                  WhatsApp
                      |
                      ▼
            WhatsApp Cloud API
                      |
                      ▼
                  Webhook
                      |
                      ▼
                  FastAPI
                      |
                      ▼
                MaliAgent
                      |
             +--------+--------+
             |                 |
             ▼                 ▼
            RAG              Tools
             |                 |
             ▼                 ▼
          pgvector         PostgreSQL
             |                 |
             +--------+--------+
                      |
                      ▼
                  Réponse
                      |
                      ▼
            WhatsApp Cloud API
                      |
                      ▼
                    Client
```

WhatsApp constitue donc le **canal de communication**.

Le backend reste responsable de la logique métier et des données.

---

# 17. Dashboard Web

Le dashboard constitue l'interface de gestion de l'entreprise.

## Tableau de bord

Il doit afficher :

- nombre de commandes ;
- chiffre d'affaires ;
- produits ;
- stock ;
- clients ;
- conversations ;
- alertes.

## Gestion des produits

Fonctionnalités :

- ajout ;
- modification ;
- suppression ;
- recherche ;
- filtrage ;
- catégories ;
- variantes ;
- images.

## Gestion du stock

Fonctionnalités :

- stock disponible ;
- mouvements ;
- seuil d'alerte ;
- historique.

## Gestion des commandes

Fonctionnalités :

- liste ;
- recherche ;
- filtres ;
- détails ;
- changement de statut ;
- historique.

## Gestion des clients

Fonctionnalités :

- liste ;
- recherche ;
- profil ;
- historique des commandes.

## Gestion de l'agent

Fonctionnalités :

- nom ;
- langue ;
- ton ;
- règles ;
- outils ;
- connaissances ;
- activation/désactivation.

---

# 18. Sécurité

La sécurité constitue une exigence importante du projet.

## 18.1 Authentification

Le backend doit utiliser un mécanisme sécurisé d'authentification.

Technologies prévues :

- JWT ;
- Refresh Token ;
- BCrypt/Argon2 pour les mots de passe.

## 18.2 Autorisation

Chaque utilisateur doit disposer uniquement des permissions nécessaires.

## 18.3 Isolation des données

Une entreprise ne doit jamais pouvoir consulter les données d'une autre.

## 18.4 Protection des API

Les API doivent être protégées contre :

- accès non autorisé ;
- injection ;
- abus ;
- requêtes invalides ;
- manipulation des paramètres.

## 18.5 Protection du LLM

Le système doit empêcher le LLM d'exécuter directement des requêtes SQL.

Architecture interdite :

```text
LLM
 |
SQL
 |
PostgreSQL
```

Architecture retenue :

```text
LLM
 |
Tool
 |
Backend
 |
Service métier
 |
PostgreSQL
```

---

# 19. Gestion des erreurs

Le système doit gérer :

- message WhatsApp invalide ;
- API indisponible ;
- timeout ;
- erreur LLM ;
- erreur RAG ;
- produit inexistant ;
- stock insuffisant ;
- commande invalide ;
- problème de livraison ;
- problème de base de données.

En cas d'erreur, l'agent doit fournir une réponse compréhensible.

Exemple :

> « Désolé, je rencontre actuellement un problème pour vérifier le stock. Je vais transmettre votre demande à notre équipe. »

---

# 20. Notifications

Les notifications pourront être utilisées pour :

- nouvelle commande ;
- commande annulée ;
- stock faible ;
- nouvelle conversation nécessitant un humain ;
- commande livrée.

---

# 21. Performance

Le système doit être conçu pour fournir des réponses rapides.

Objectifs :

- réception rapide des messages ;
- traitement optimisé ;
- requêtes PostgreSQL optimisées ;
- indexation ;
- pagination ;
- cache lorsque nécessaire.

Les opérations critiques telles que les commandes et les stocks doivent privilégier la cohérence des données plutôt qu'une réponse artificiellement rapide.

---

# 22. Disponibilité

Le backend doit pouvoir fonctionner sur un serveur distant.

Architecture de déploiement :

```text
Internet
   |
   ▼
Nginx
   |
   ▼
FastAPI
   |
   +------ PostgreSQL
   |
   +------ pgvector
   |
   +------ Ollama / LLM
```

Les différents services peuvent être conteneurisés avec Docker.

---

# 23. Technologies

## Backend

- Python 3.12 ;
- FastAPI ;
- Pydantic ;
- SQLAlchemy ;
- PostgreSQL.

## Intelligence artificielle

- LLM ;
- Qwen ;
- Ollama ;
- LangGraph ;
- RAG ;
- Embeddings ;
- pgvector ;
- Function Calling / Tools.

## Communication

- WhatsApp Cloud API ;
- Webhooks.

## Frontend

- Angular ;
- TypeScript ;
- Angular Material.

## Documents

- ReportLab pour la génération des factures PDF.

## Conteneurisation

- Docker ;
- Docker Compose.

## Tests

- Pytest ;
- tests unitaires ;
- tests d'intégration ;
- tests des tools ;
- tests API.

---

# 23.1 Stratégie LLM et abstraction du provider

Le choix du modèle de langage n'est pas figé dans le temps.

Le projet distingue deux phases :

```text
Phase MVP / développement
   ↓
Ollama Cloud (API hébergée par Ollama)

Phase production
   ↓
Modèle à déterminer selon les besoins réels
(coûts, volumes, souveraineté des données, qualité du tool calling)
```

## 23.1.1 Ollama Cloud pour le MVP

Ollama Cloud permet d'exécuter des modèles hébergés (ex. `gpt-oss:120b`, `kimi-k2.6`, `deepseek-v4-flash`) sans dépendre d'un GPU local, via :

- l'exécution directe (`ollama run <modele>:cloud`) ;
- ou l'API cloud (`https://ollama.com`) avec une clé API (`OLLAMA_API_KEY`).

Ce choix permet de développer et tester rapidement sans investissement matériel, tout en restant dans l'écosystème Ollama.

Point de vigilance : les plans Ollama Cloud (Free / Pro / Max) appliquent des quotas mesurés en temps GPU, avec réinitialisation par session (5h) et par semaine. Il faut vérifier que le plan choisi couvre le volume de messages attendu pendant les tests pilotes.

## 23.1.2 Changement de modèle en production

Le modèle utilisé en phase MVP n'est pas nécessairement celui utilisé en production. Le choix définitif dépendra des besoins réels observés (coûts, volumes, exigences de souveraineté des données de certains commerçants, qualité du tool calling en français).

Cette contrainte impose une exigence d'architecture :

> **Le LLM ne doit jamais être appelé directement depuis la logique métier ou les tools. Il doit être accédé via une couche d'abstraction (interface `LLMProvider`), afin de permettre un changement de provider sans réécrire l'agent, les tools ou les prompts.**

Structure attendue :

```text
agent/
  llm/
    base.py              # interface abstraite (generate, tool_call, etc.)
    ollama_provider.py
    <autre>_provider.py  # ajouté au moment du changement de modèle
  tools/
  orchestrator.py         # dépend de l'interface, jamais d'un provider précis
```

## 23.1.3 Compatibilité du tool calling entre providers

Les différents fournisseurs de LLM (Ollama, OpenAI, Anthropic, etc.) n'utilisent pas exactement le même format de function calling / tool calling.

Afin de limiter le travail de migration au moment du changement de modèle, le projet privilégie l'une des approches suivantes :

- utiliser la route compatible OpenAI exposée par Ollama (`/v1/...`), ce format étant largement repris par d'autres fournisseurs cloud ;
- ou définir un schéma de tools interne indépendant du provider, avec un adaptateur par provider traduisant vers/depuis son format spécifique.

Cette exigence s'applique dès la phase MVP, même si un seul provider (Ollama Cloud) est utilisé au départ.

---

# 24. Planning prévisionnel du MVP

Le MVP peut être réalisé sur environ **12 à 16 semaines**.

## Semaine 1–2 — Architecture

- conception ;
- initialisation du projet ;
- PostgreSQL ;
- modèles ;
- API ;
- Docker ;
- sécurité de base.

## Semaine 3–4 — Agent IA

- intégration Qwen/Ollama ;
- prompts ;
- contexte ;
- mémoire ;
- LangGraph ;
- premières réponses.

## Semaine 5–6 — Tools + RAG

- recherche produit ;
- stock ;
- commandes ;
- outils ;
- pgvector ;
- documents ;
- recherche sémantique.

## Semaine 7–8 — Commerce

- produits ;
- catégories ;
- stock ;
- clients ;
- commandes ;
- livraison.

## Semaine 9–10 — WhatsApp

- Meta ;
- Cloud API ;
- webhook ;
- réception ;
- réponse ;
- historique.

## Semaine 11–12 — Dashboard

- authentification ;
- produits ;
- stock ;
- commandes ;
- clients ;
- configuration agent.

## Semaine 13–14 — Facturation

- factures ;
- PDF ;
- statistiques ;
- notifications.

## Semaine 15–16 — Finalisation

- tests ;
- sécurité ;
- optimisation ;
- Docker ;
- déploiement ;
- documentation ;
- démonstration.

---

# 25. Tests

Le projet doit comporter plusieurs catégories de tests.

## Tests unitaires

Tester :

- services ;
- calculs ;
- règles métier ;
- tools.

## Tests API

Tester :

- authentification ;
- produits ;
- commandes ;
- clients ;
- stock.

## Tests agent

Tester :

```text
Question
   ↓
Agent
   ↓
Tool
   ↓
Résultat
   ↓
Réponse
```

## Tests de sécurité

Vérifier :

- isolation des entreprises ;
- permissions ;
- accès non autorisés ;
- tokens ;
- données sensibles.

## Tests WhatsApp

Tester :

- réception ;
- réponse ;
- erreurs ;
- conversations ;
- commandes.

---

# 26. Critères d'acceptation du MVP

Le MVP est considéré comme fonctionnel lorsque les scénarios suivants sont réalisés.

### Scénario 1 — Question produit

Client :

> « Avez-vous Samsung A15 ? »

Le système :

1. reçoit le message ;
2. identifie l'entreprise ;
3. recherche le produit ;
4. vérifie les informations ;
5. répond sur WhatsApp.

### Scénario 2 — Stock

Client :

> « Il reste combien de Samsung A15 ? »

L'agent consulte le backend.

Il fournit le stock réel.

### Scénario 3 — Commande

Client :

> « Je prends deux Samsung A15. »

Le système :

1. identifie le produit ;
2. vérifie le stock ;
3. récupère les informations nécessaires ;
4. calcule le montant ;
5. crée la commande ;
6. confirme la commande.

### Scénario 4 — Dashboard

Le commerçant ouvre le dashboard.

Il voit :

```text
Nouvelle commande
Samsung A15 × 2
Total : 170 000 FCFA
```

### Scénario 5 — Isolation

Une entreprise A ne peut pas accéder aux produits ou commandes d'une entreprise B.

### Scénario 6 — Incertitude

Si l'agent ne connaît pas la réponse :

```text
Agent
  ↓
Impossible de répondre de manière fiable
  ↓
Transfert vers humain
```

---

# 27. Limites du projet

Le projet présente certaines limites.

## WhatsApp

L'agent dépend de la disponibilité d'Internet et des services WhatsApp/Meta.

L'agent WhatsApp ne peut donc pas fonctionner entièrement hors connexion.

## Intelligence artificielle

Un LLM peut produire des réponses incorrectes.

Le projet doit donc utiliser :

- RAG ;
- tools ;
- validation ;
- règles métier ;
- contrôle backend.

## Données

La qualité des réponses dépend de la qualité des données fournies par l'entreprise.

## Paiement

Le paiement numérique ne constitue pas une fonctionnalité centrale du premier MVP.

Il sera intégré progressivement dans les versions futures.

---

# 28. Différenciation de MaliAgent

MaliAgent ne cherche pas uniquement à créer un chatbot supplémentaire.

La différenciation repose sur plusieurs axes.

## 28.1 Adaptation au contexte malien

La plateforme est pensée pour :

- le FCFA ;
- les habitudes commerciales locales ;
- les petites entreprises ;
- WhatsApp ;
- les connexions variables ;
- le français ;
- le bambara à terme.

## 28.2 Agent connecté aux données réelles

L'agent ne répond pas uniquement à partir de connaissances générales.

Il peut consulter :

- catalogue ;
- stock ;
- commandes ;
- clients ;
- règles commerciales.

## 28.3 Commerce conversationnel

WhatsApp devient un véritable canal commercial.

Le client peut :

```text
Question
   ↓
Produit
   ↓
Stock
   ↓
Commande
   ↓
Livraison
   ↓
Facture
```

## 28.4 Plateforme configurable

MaliAgent utilise un moteur commun mais chaque entreprise possède sa propre configuration.

## 28.5 Évolution vers un écosystème

La vision à long terme dépasse le chatbot :

```text
Commerce
   +
IA
   +
WhatsApp
   +
Voix
   +
Paiement
   +
Logistique
   +
Multi-Agent
```

---

# 29. Perspectives

Les principales perspectives sont :

### Court terme

- améliorer le RAG ;
- améliorer les tools ;
- améliorer la sécurité ;
- connecter WhatsApp ;
- développer le dashboard ;
- tester avec des entreprises pilotes.

### Moyen terme

- français + bambara ;
- messages vocaux ;
- paiement mobile ;
- livraison ;
- analytics ;
- multi-business.

### Long terme

- multi-agent ;
- marketplace ;
- finance ;
- logistique ;
- expansion régionale ;
- automatisation avancée des entreprises.

---

# 30. Vision finale

La vision finale de MaliAgent peut être représentée comme suit :

```text
                         MALIAGENT
                             |
       +---------------------+---------------------+
       |                     |                     |
   COMMERCE                IA                    BUSINESS
       |                     |                     |
   Produits              LLM                  Dashboard
   Stock                 RAG                  Analytics
   Commandes             Tools                Reports
       |                     |                     |
       +---------------------+---------------------+
                             |
                        COMMUNICATION
                             |
                +------------+------------+
                |                         |
             WhatsApp                   Voix
                |                         |
                +------------+------------+
                             |
                         LOGISTIQUE
                             |
                         Livraison
                             |
                          PAIEMENT
                             |
                       Mobile Money
                             |
                     Afrique de l'Ouest
```

MaliAgent commence donc par un cas d'utilisation relativement ciblé :

> **Un agent commercial intelligent connecté à WhatsApp.**

Mais l'architecture est conçue pour permettre une évolution progressive vers :

> **une plateforme d'agents intelligents destinée aux entreprises africaines.**

---

# 31. Conclusion

MaliAgent est un projet visant à exploiter les capacités des modèles de langage et des architectures agentiques pour automatiser une partie des interactions commerciales des entreprises.

La première version se concentre sur l'intégration entre WhatsApp, un backend intelligent et les données commerciales de l'entreprise.

L'utilisation de tools permet à l'agent d'effectuer des opérations réelles tout en maintenant une séparation entre le modèle de langage et la base de données.

Le système repose ainsi sur une architecture dans laquelle :

```text
WhatsApp
    ↓
FastAPI
    ↓
MaliAgent
    ↓
LLM + RAG + Tools
    ↓
Services métier
    ↓
PostgreSQL
```

Cette architecture permet de construire un système plus fiable qu'un simple chatbot et constitue une base évolutive pour intégrer ultérieurement la voix, le multilingue, le paiement, la logistique, les agents spécialisés et plusieurs entreprises.

Le projet représente ainsi une application concrète de plusieurs concepts avancés du génie informatique et de l'intelligence artificielle :

- Large Language Models ;
- RAG ;
- Agents IA ;
- Tool Calling ;
- architectures backend ;
- API REST ;
- bases de données ;
- systèmes multi-tenant ;
- sécurité ;
- intégration de services externes ;
- automatisation des processus métier.

MaliAgent constitue donc un projet évolutif dont le premier objectif est de démontrer la faisabilité technique d'un **agent commercial intelligent connecté à WhatsApp**, avant d'évoluer progressivement vers une plateforme complète destinée au marché africain.