# Alerte auto NL — Golf 7.5 R-Line / Audi A3 8V2 S line

Surveille **Marktplaats.nl** et **AutoScout24.nl** toutes les 20 minutes, garde une base complète
des annonces et t'envoie un **WhatsApp** à chaque nouvelle annonce qui colle à tes critères.

**Critères (modifiables dans `config.json`)** — GTI : budget propre dans `max_price_ht_by_model`
- VW Golf 7.5 R-Line, Golf 7.5 GTI ou Audi A3 8V2 S line, 2017–2020
- Boîte automatique (DSG / S tronic)
- Toit ouvrant / panoramique
- Intérieur R-Line / S line (« confirmé » si l'annonce le dit clairement, sinon « à vérifier »)
- TVA récupérable uniquement (BTW verrekenbaar / BTW-auto) — les voitures « marge » sont écartées
- ≤ 17 000 € HT, ≤ 160 000 km

**Ce que tu reçois**
- ✅ annonce qui coche tout · 🟡 annonce presque bonne à vérifier (intérieur ou TVA non précisés) · 📉 baisse de prix
- Un tableau en ligne (GitHub Pages) avec toute la base, filtres, et un export CSV pour Excel
- Un score « vs comparables » : écart du prix HT avec la médiane des annonces du même modèle et de la même année

---

## Installation (≈ 10 min, faisable depuis le téléphone)

### 1. Choisir le canal de notification
Le script envoie sur **tous** les canaux que tu configures (secrets GitHub, étape 3).

**A. WhatsApp via Green-API (recommandé, gratuit)**
1. Crée un compte sur **green-api.com** → console → crée une instance **Developer** (gratuite, envois illimités, 3 conversations max).
2. Scanne le QR code avec **un deuxième numéro WhatsApp** (vieux téléphone, carte prépayée, ou WhatsApp Business sur un autre numéro).
   ⚠️ Si tu scannes avec ton numéro principal, les alertes arrivent « de toi-même » : pas de sonnerie ni de notification.
3. Note `apiUrl`, `idInstance` et `apiTokenInstance` affichés dans la console.
4. Secrets : `GREENAPI_URL` (= apiUrl), `GREENAPI_ID`, `GREENAPI_TOKEN`, `WHATSAPP_TO` (ton numéro principal, ex. `+32470123456`).

**B. CallMeBot** (gratuit, mais complet en ce moment)
Quand le numéro réapparaît sur callmebot.com : envoie-lui `I allow callmebot to send me messages`,
puis secrets `CALLMEBOT_PHONE` et `CALLMEBOT_APIKEY`.

**C. Telegram (secours, 2 minutes)**
Sur Telegram, écris à **@BotFather** → `/newbot` → copie le token. Envoie un message à ton bot, puis ouvre
`https://api.telegram.org/bot<TOKEN>/getUpdates` pour lire ton `chat.id`.
Secrets : `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`.

### 2. Créer le dépôt GitHub
1. Crée un compte sur github.com si besoin.
2. **New repository** → nom `auto-alerte` → **Public** (minutes d'Actions illimitées et tableau gratuit ; tes clés restent secrètes).
3. **Add file → Upload files** → dépose tout le contenu du zip (y compris le dossier `.github`) → **Commit**.
   - Sur téléphone, si le dossier `.github` ne passe pas : **Add file → Create new file**, nom `.github/workflows/scan.yml`, colle le contenu du fichier.

### 3. Ajouter les secrets
**Settings → Secrets and variables → Actions → New repository secret**
Ajoute les secrets du ou des canaux choisis à l'étape 1 (noms exacts indiqués ci-dessus).

### 4. Activer le tableau en ligne
**Settings → Pages** → Source : *Deploy from a branch* → Branch `main`, dossier `/docs` → **Save**.
L'adresse sera `https://TON-PSEUDO.github.io/auto-alerte/`. Colle-la dans `config.json` → `dashboard_url`
pour qu'elle apparaisse dans les messages.

### 5. Lancer le premier scan
**Actions** → accepte l'activation des workflows → **Scan annonces → Run workflow**.
Le premier passage lit toutes les annonces (15–30 min), remplit la base **sans spammer**, puis t'envoie
un seul message récapitulatif. Ensuite : un message par nouvelle annonce.

---

## Réglages utiles (`config.json`)
| Clé | Rôle |
|---|---|
| `max_price_ht`, `max_km`, `year_min`, `year_max` | tes limites |
| `notify_statuses` | `["match"]` pour ne recevoir que les annonces 100 % confirmées |
| `include_variant` | `false` pour exclure la Golf break (Variant) |
| `full_sweep_every_hours` | fréquence du balayage complet (détecte les annonces retirées et les baisses de prix) |

## Bon à savoir
- **Prix HT** = prix affiché ÷ 1,21, sauf si l'annonce donne un prix excl. BTW.
- Aux Pays-Bas le prix affiché inclut la **BPM**. Pour un export vers la Belgique, demande toujours le
  **prix export excl. BTW et excl. rest-BPM** : il est souvent nettement plus bas que l'annonce.
- L'achat intracommunautaire HT suppose un numéro de TVA belge valide (vérifiable sur VIES) au nom de l'acheteur.
- La détection « intérieur » et « TVA » lit le texte des annonces : confirme toujours avec le vendeur.
- Si un site bloque les serveurs GitHub, tu reçois un WhatsApp « source bloquée » et le tableau l'indique.
  Le script tourne alors aussi sur n'importe quel PC : `pip install requests` puis `python scan.py`.
- Tests hors-ligne : `pip install pytest && python -m pytest -q`
