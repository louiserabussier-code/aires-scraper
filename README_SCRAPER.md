# Scraper d'enrichissement des équipements — aires.

Enrichit `STATIC_AIRES` (index.html) avec les équipements réels publiés par
Vinci Autoroutes, Sanef, APRR et AREA, sans jamais modifier `index.html`
automatiquement : la sortie est un JSON séparé destiné à ta relecture.

## Limitation importante : réseau

Ce dépôt a été développé/testé depuis un environnement sandbox qui **n'a
aucun accès réseau** vers vinci-autoroutes.com / sanef.com / aprr.fr /
area-autoroute.fr (bloqué au niveau du proxy réseau de l'environnement, pas
au niveau du code). Résultat concret :

- Toute la logique indépendante du réseau (parsing de `STATIC_AIRES`,
  matching flou nom+distance, extraction JSON-LD/mots-clés, robots.txt,
  état résumable, écriture JSON) est **testée par une suite de tests
  unitaires locale** (`pytest`, aucune requête réseau, fixtures
  synthétiques dans `tests/fixtures/`) — voir `python3 -m pytest tests/ -q`.
- Les **sélecteurs et URLs de sitemap** dans `scraper/adapters/{vinci,sanef,
  aprr,area}.py` sont des hypothèses raisonnables, **jamais vérifiées
  contre une vraie page**. Il faut les calibrer toi-même en lançant
  `probe` depuis une machine avec accès internet, avant tout run complet.

## Installation

```bash
pip install -r requirements.txt
```

## Étape 1 — probe (obligatoire avant tout run)

`probe` récupère quelques pages (ou celles que tu donnes explicitement) et
affiche ce qui a été détecté, sans rien écrire sur disque :

```bash
python run_scraper.py probe --operator vinci --limit 5
python run_scraper.py probe --operator vinci --urls https://www.vinci-autoroutes.com/aire-de-xxx
python run_scraper.py probe --operator vinci --urls <url> --save-html /tmp/probe_html  # dump raw HTML for review
```

Si le nom ou les équipements détectés sont faux/vides, ajuste dans
`scraper/adapters/vinci.py` :
- `root_url` / `hub_pattern` / `url_pattern` (découverte en deux temps :
  une page racine `/fr/aires-et-services/` qui liste un lien "hub" par
  autoroute, puis chaque hub qui liste ses pages d'aires - voir
  `crawl_hub_pages` dans `adapters/base.py`. vinci-autoroutes.com n'a pas
  de `/sitemap.xml` fonctionnel (confirmé 404 le 2026-07), d'où ce
  mécanisme à la place d'un sitemap.)
- `EQUIP_SYNONYMS` (mots-clés français par équipement). Deux cas
  particuliers réglés selon la connaissance du réseau Vinci/APRR par
  l'utilisateur : `pmr` ne se déclenche que sur "fauteuil roulant" (les
  sanitaires PMR/parking prioritaire étant déjà quasi-systématiques sur ce
  réseau, les détecter ne donnerait aucun signal utile) ; `animaux` se
  déclenche sur "espace canin" (le vocabulaire réel du site), pas sur le
  mot "animaux" lui-même.
- au besoin, la logique de `BaseAdapter.parse()` dans `adapters/base.py`
  (sélecteurs CSS spécifiques si le site a une structure HTML stable
  plutôt que du texte libre)

Si `probe` affiche `no hub links matching pattern found on .../aires-et-
services/`, c'est que la page racine ne liste pas les autoroutes de la
façon supposée (un lien par autoroute en un seul segment de chemin) :
lance `probe --operator vinci --urls <url racine>` ou partage le HTML de
cette page pour recalibrer `hub_pattern`.

## Étape 2 — vérifier APRR/AREA avant de s'engager

Conformément à la consigne : APRR et AREA sont **désactivés par défaut**
(`config.OPERATORS["aprr"]["enabled_by_default"] = False`). `run
--operator aprr` refuse de tourner tant que tu n'as pas passé `--enable`,
ce qui t'oblige à faire un `probe --operator aprr` d'abord et à juger si
la structure ressemble à celle de vinci-autoroutes.com (même mécanisme
`BaseAdapter`) ou si un adapter dédié serait nécessaire.

```bash
python run_scraper.py probe --operator aprr --limit 5
# Si ça a l'air correct :
python run_scraper.py run --operator aprr --enable --limit 200
```

## Étape 3 — run (résumable)

```bash
python run_scraper.py run --operator vinci --limit 200
```

- Respecte `robots.txt` de chaque domaine (parsé via `urllib.robotparser`) ;
  toute URL interdite est journalée dans `logs/<op>_not_found.log`, jamais
  récupérée.
- Au moins 2.5–3.2s (jitter) entre deux requêtes vers le même domaine, plus
  le `Crawl-delay` du robots.txt si celui-ci est plus grand.
- Progression écrite au fil de l'eau dans `state/<op>.jsonl` (une ligne par
  URL traitée) → un Ctrl-C ou crash ne perd que la requête en cours ;
  relancer la même commande reprend où ça s'est arrêté.
- Chaque aire scrapée est comparée à `STATIC_AIRES` par nom (flou,
  normalisé, accents/préfixes "aire de" retirés — mais **jamais** les
  suffixes Est/Ouest/Nord/Sud, deux aires jumelles à quelques centaines de
  mètres n'ayant souvent que ça pour se distinguer) + distance
  géographique (seuils dans `config.py`). Les correspondances ambiguës
  sont journalisées avec `match_confidence: "low"`, jamais fusionnées
  silencieusement.
- N'extrait que des **faits** (présence/absence d'équipement), jamais de
  texte éditorial : JSON-LD `amenityFeature` structuré en priorité, sinon
  détection par mot-clé + négation ("fermé", "hors service"...) phrase par
  phrase.

## Sortie

`output/enrichment_<operator>.json` — un tableau de :

```json
{
  "nom_aire": "Aire des Brouzils",
  "id": 3003,
  "equip": {"restaurant": "ok", "wifi": "ok", "douches": "nok"},
  "equip_source": "vinci",
  "equip_date": "2026-07",
  "source_url": "https://www.vinci-autoroutes.com/...",
  "match_confidence": "high",
  "name_similarity": 0.92,
  "distance_km": 0.02,
  "extraction_method": "jsonld"
}
```

Les entrées de plusieurs opérateurs pour la même aire ne sont **pas
fusionnées** entre elles (pour ne pas masquer un conflit ou décider à ta
place) : à toi de trancher lors de l'intégration dans `index.html`.

## Aires manquantes de STATIC_AIRES

Vinci publie de vraies coordonnées GPS (via JSON-LD `geo`) pour ses aires,
contrairement à `STATIC_AIRES` qui n'en a pas toujours (ex. "Aire sans
nom"). Quand une aire scrapée ne correspond à aucune entrée existante (ni
par nom+distance, ni par nom seul), au lieu de simplement la journaler
comme "non trouvée", le script la propose comme **nouvelle entrée** dans
`output/new_aires_<operator>.json` :

```json
{
  "nom_aire": "Aire de La Picardière",
  "id": null,
  "status": "new_candidate",
  "lat": 47.535025308926,
  "lng": 0.96258012533176,
  "equip": {},
  "equip_source": "vinci",
  "equip_date": "2026-07",
  "source_url": "https://www.vinci-autoroutes.com/fr/aires-et-services/a10/aire-de-la-picardiere/",
  "extraction_method": "none"
}
```

- `id: null` volontairement : c'est à toi de lui attribuer un id (et de
  remplir `km`, la catégorie "Aire de repos"/"Aire de services" - le
  script ne l'invente pas) en l'ajoutant à `STATIC_AIRES`.
- Ceci nécessite des coordonnées scrapées (sinon impossible de proposer une
  entrée géolocalisée) : sans lat/lng, le cas reste journalisé comme
  "not found" classique.
- Les candidats déjà proposés dans un run précédent (même resumé après
  interruption) sont rechargés au démarrage et comparés aux nouveaux via le
  même matching flou nom+distance, pour ne pas proposer deux fois la même
  aire manquante si une deuxième URL y mène (ex. sens opposé de
  l'autoroute) - journalisé dans `logs/<op>_not_found.log` comme
  `duplicate of already-proposed new aire`.
- Ce dédoublonnage reste **par opérateur** : si vinci et sanef proposaient
  chacun la même aire manquante (frontière de réseau, cas rare), tu verrais
  deux candidats séparés - à trancher lors de l'intégration, comme pour les
  conflits d'équipements entre opérateurs.

## Logs de progression

- `logs/<operator>_found.log` — URL → aire correspondante + confiance
- `logs/<operator>_not_found.log` — URL → raison (robots interdit, pas de
  nom trouvé, pas d'équipement détecté, pas de correspondance dans
  `STATIC_AIRES`, doublon d'un candidat déjà proposé...)
- `logs/<operator>_new_candidates.log` — URL → nom + coordonnées proposées
  comme nouvelle aire

## Tests

```bash
python3 -m pytest tests/ -q
```
