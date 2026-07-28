from pathlib import Path

from scraper.aires_data import load_aires
from scraper.matching import find_match, name_similarity, normalize_name

FIXTURE = Path(__file__).parent / "fixtures" / "mini_index.html"


def test_normalize_strips_prefix_and_accents():
    assert normalize_name("Aire de Remouillé-Est") == "remouille-est"


def test_direction_suffix_is_preserved():
    # Est/Ouest must stay distinguishable - these are different physical sites.
    assert normalize_name("Aire de Remouillé-Est") != normalize_name("Aire de Remouillé-Ouest")


def test_find_match_disambiguates_est_ouest_by_distance():
    aires = load_aires(FIXTURE)
    est = find_match("Aire de Remouillé Est", 47.0198, -1.3958, aires)
    assert est.aire.id == 3001
    assert est.confidence == "high"

    ouest = find_match("Aire de Remouillé Ouest", 47.0198, -1.3958, aires)
    assert ouest.aire.id == 3002


def test_find_match_no_coords_requires_near_exact_name():
    aires = load_aires(FIXTURE)
    result = find_match("Aire des Brouzils", None, None, aires)
    assert result.aire.id == 3003
    # Never "high" without geography to back it up, however good the name
    # match looks - see config.NAME_SIMILARITY_NO_COORDS_THRESHOLD.
    assert result.confidence == "low"


def test_find_match_no_coords_rejects_plausible_but_wrong_name():
    # Real false positive found in production: a scraped "Aire de Boutroux"
    # (A10, western France) fuzzy-matched an unrelated "Aire du Bourdoux"
    # (Hautes-Alpes, ~570km away) at 0.875 name similarity - previously
    # accepted as "high" confidence with no coordinates to catch it.
    aires = load_aires(FIXTURE)
    result = find_match("Aire de Remouille", None, None, aires)  # cf. Remouillé-Est/Ouest
    assert result.aire is None


def test_find_match_rejects_unrelated_far_away_name():
    aires = load_aires(FIXTURE)
    result = find_match("Station Total Marseille", 43.3, 5.4, aires)
    assert result.aire is None
    assert result.confidence == "none"


def test_find_match_rejects_close_but_unrelated_name():
    aires = load_aires(FIXTURE)
    # Right next to Remouillé-Est/Ouest, but not a plausible name match.
    result = find_match("Station-service Michelin", 47.02, -1.396, aires)
    assert result.aire is None
