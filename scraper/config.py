"""Central configuration: rate limits, contact info, per-operator base settings."""
from __future__ import annotations

# Contact info advertised in the User-Agent so site operators can reach you
# if they have a question about the crawl. Fill in before running for real.
CONTACT_EMAIL = "louiserabussier@gmail.com"
USER_AGENT = (
    f"aires-scraper/0.1 (+mailto:{CONTACT_EMAIL}; "
    f"low-rate equipment-facts enrichment for a personal travel app; "
    f"respects robots.txt)"
)

# Hard floor between two requests to the *same* domain, regardless of what
# robots.txt says (robots Crawl-delay is respected too, and wins if larger).
MIN_DELAY_SECONDS = 2.5
MAX_DELAY_SECONDS = 3.2

REQUEST_TIMEOUT_SECONDS = 20

# Matching thresholds (matching.py)
NAME_SIMILARITY_THRESHOLD = 0.62
MAX_MATCH_DISTANCE_KM = 3.0
# Ambiguous zone: logged for manual review instead of auto-accepted.
NAME_SIMILARITY_REVIEW_THRESHOLD = 0.5
MAX_MATCH_DISTANCE_REVIEW_KM = 6.0

# Without any scraped coordinates, distance can't rule out a false positive
# at all - character-level similarity between two unrelated French place
# names is dangerously easy to fake (many "Saint-X ... Est/Ouest" style
# names). Confirmed on real data: "Aire du Bourdoux" (Hautes-Alpes) vs a
# scraped "Aire de Boutroux" scored 0.875 on name alone and would have been
# accepted as a *high*-confidence match despite being ~570km apart. So a
# name-only match is NEVER "high", and needs a much stricter bar than the
# geo-backed thresholds above to be proposed even as "low".
NAME_SIMILARITY_NO_COORDS_THRESHOLD = 0.9

EQUIP_KEYS = ("restaurant", "animaux", "enfants", "pmr", "douches", "eau", "wifi")

OPERATORS = {
    "vinci": {
        "label": "Vinci Autoroutes (ASF / Cofiroute / Escota)",
        "base_url": "https://www.vinci-autoroutes.com",
        "enabled_by_default": True,
    },
    "sanef": {
        "label": "Sanef",
        "base_url": "https://www.sanef.com",
        "enabled_by_default": True,
    },
    "aprr": {
        "label": "APRR",
        "base_url": "https://www.aprr.fr",
        "enabled_by_default": False,  # gated behind a successful --probe run
    },
    "area": {
        "label": "AREA",
        "base_url": "https://www.area-autoroute.fr",
        "enabled_by_default": False,  # gated behind a successful --probe run
    },
}
