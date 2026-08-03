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

### Vinci : découverte via page-data.json (pas de scraping HTML rendu)

vinci-autoroutes.com est un site Gatsby. La liste complète des aires par
autoroute n'est **pas** dans le HTML statique des pages hub
(`/fr/aires-et-services/autoroute-a10/`) : le bouton "Voir plus" qu'on y
voit est un contrôle 100% client (aucun lien d'aire dans le HTML servi),
donc une première version qui scrapait ce HTML ne trouvait qu'un
sous-ensemble biaisé (~218 aires sur ~1500, uniquement via des pages de
marques comme mcdonalds/bp qui listent, elles, quelques aires en dur).

À la place, `scraper/adapters/vinci_pagedata.py` récupère directement le
fichier de données Gatsby que React utilise pour hydrater cette liste :
`{base}/page-data/fr/aires-et-services/autoroute-a10/page-data.json` (un
par autoroute réelle, ~30 requêtes au total plutôt que ~1500). Ce fichier
JSON contient déjà, pour chaque aire : nom exact, coordonnées GPS
précises, la catégorie `service` (true/false → "Aire de services"/"Aire de
repos", utilisé pour `km`), et des listes structurées `facilities`
(`machineName` interne, ex. `airedejeux`) et `brands` (`name` +
`categoryCode`, ex. `BUFFET`/`RESTAURATION`).

Mapping `facilities`/`brands` → `equip` (dans `vinci_pagedata.py`,
`FACILITY_MACHINE_NAME_TO_EQUIP` / `BRAND_CATEGORY_TO_EQUIP`) :
- `airedejeux` → `enfants`, `wifi` → `wifi`, `douches` → `douches`
- une marque avec `categoryCode` `BUFFET` ou `RESTAURATION` → `restaurant`
- rien ne mappe encore `animaux`/`pmr`/`eau` de façon structurée sur ce
  réseau (aucune facility de ce type observée) - un filet de sécurité
  repasse quand même `EQUIP_SYNONYMS` sur les noms bruts au cas où une
  correspondrait (ex. une future facility "Espace canin").
- tout le reste (vidange, gonflage, nurserie, bornerecharge, laverie,
  hotel, parkingpl, parkingcaravane, stationservice, gpl, dab,
  boiteauxlettres, produitsregionaux, brumisateur, infotrafic, coworking,
  presse, remarquable, bornesvlr, distribboissonnourriture, marques hors
  BUFFET/RESTAURATION...) n'a pas d'équivalent dans le schéma `equip` de
  l'app mais est conservé tel quel dans `equip_brut` (voir plus bas) plutôt
  que d'être perdu.

`--operator vinci` bascule automatiquement sur ce mécanisme
(`adapter.has_page_data`), `probe`/`run` inclus - `discover()`/`parse()`
(scraping HTML page par page) ne sont plus utilisés pour Vinci du tout.

Si `probe --operator vinci` affiche "No aires found via the bulk data
source", `HIGHWAY_HUB_PATTERN` ou `root_url` dans `vinci_pagedata.py`
doivent être recalibrés - partage le HTML de `/fr/aires-et-services/`.

### Autres opérateurs (sanef, aprr, area)

Sans confirmation qu'ils sont aussi des sites Gatsby avec ce même
mécanisme, ils gardent le scraping HTML classique : `EQUIP_SYNONYMS`
(mots-clés français par équipement, à ajuster dans le fichier de chaque
adaptateur), et `root_url`/`hub_pattern`/`url_pattern` (découverte en deux
temps via `crawl_hub_pages` dans `adapters/base.py` si le site n'a pas de
sitemap fonctionnel). Deux cas particuliers déjà réglés dans
`vinci.py`/`EQUIP_SYNONYMS` (partagé par `aprr.py`/`area.py`) selon la
connaissance du réseau Vinci/APRR par l'utilisateur : `pmr` ne se déclenche
que sur "fauteuil roulant" (les sanitaires PMR/parking prioritaire étant
déjà quasi-systématiques sur ce réseau, les détecter ne donnerait aucun
signal utile) ; `animaux` se déclenche sur "espace canin" (le vocabulaire
réel du site), pas sur le mot "animaux" lui-même.

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

**Si le mécanisme de découverte/extraction d'un opérateur change**
(comme le passage de Vinci au scraping HTML vers `page-data.json`) : le
checkpoint est indexé par URL, et les deux mécanismes peuvent produire les
mêmes URLs pour une même aire - le reprendre tel quel ferait donc
silencieusement ignorer des aires déjà traitées, alors que le nouveau
mécanisme donnerait de meilleures données pour elles. Et comme
`output/enrichment_<op>.jsonl` est en append-only (non dédoublonné par id),
relancer sans vider produirait des entrées en double pour ces aires plutôt
que de les remplacer. Dans ce cas, repartir de zéro pour cet opérateur :

```bash
rm -f state/<op>.jsonl \
      logs/<op>_found.log logs/<op>_not_found.log logs/<op>_new_candidates.log \
      output/enrichment_<op>.jsonl output/enrichment_<op>.json \
      output/new_aires_<op>.jsonl output/new_aires_<op>.json
```
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
  "nom_aire": "Aire de Poitou-Charentes Nord",
  "id": 3011,
  "lat": 46.29697,
  "lng": -0.37694,
  "equip": {"enfants": "ok", "wifi": "ok", "douches": "ok", "restaurant": "ok"},
  "equip_brut": {"facilities": ["Aire de jeux", "Wifi", "Douches", "Vidange", "..."], "brands": ["McDonald's (BUFFET)", "TOTALENERGIES (CARBURANT)"]},
  "equip_source": "vinci",
  "equip_date": "2026-07",
  "source_url": "https://www.vinci-autoroutes.com/fr/aires-et-services/a10/aire-de-poitou-charentes-nord/",
  "match_confidence": "high",
  "name_similarity": 0.952,
  "distance_km": 0.053,
  "extraction_method": "page-data"
}
```

`equip_brut` garde les noms bruts de facilities/marques (y compris celles
hors du schéma `equip`, ex. "Vidange"), pour ta référence - jamais fusionné
dans `equip`.

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
  "km": "Aire de repos",
  "equip": {},
  "equip_brut": {"facilities": ["Aire camping car", "Parking PL", "Electrique"], "brands": []},
  "equip_source": "vinci",
  "equip_date": "2026-07",
  "source_url": "https://www.vinci-autoroutes.com/fr/aires-et-services/a10/aire-de-la-picardiere/",
  "extraction_method": "page-data"
}
```

- `id: null` volontairement : c'est à toi de lui attribuer un id en
  l'ajoutant à `STATIC_AIRES`. `km` est rempli quand la source le permet
  de façon fiable (le flag `service` de Vinci) - reste `null` sinon
  (aucune autre source fiable pour l'inférer).
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
- `logs/<operator>_highway_issues.log` — pour une source en gros (Vinci
  page-data.json) : hub d'autoroute + URL du JSON + raison de l'échec
  (robots interdit, HTTP non-200, JSON invalide, ou JSON récupéré mais 0
  aire dedans). Pas coché dans le checkpoint - retenté à chaque run (~30
  requêtes, pas cher). Si le total d'une run est très inférieur à ce que tu
  attends (ex. 451 au lieu de ~1500), regarde ce fichier en premier avant
  de soupçonner un bug de découverte ou de matching : jusqu'à récemment, ces
  échecs par autoroute n'étaient qu'un warning console éphémère, facile à
  manquer sur une run sans `--limit` qui défile vite.

## Tests

```bash
python3 -m pytest tests/ -q
```
