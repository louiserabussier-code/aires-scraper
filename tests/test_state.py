from scraper.state import RunState


def test_resumes_from_checkpoint(tmp_path):
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"

    s1 = RunState("vinci", state_dir=str(state_dir), logs_dir=str(logs_dir))
    s1.log_found("https://a", 1, "Aire A", "high")
    s1.log_not_found("https://b", "no match")
    s1.log_new_candidate("https://c", "Aire Nouvelle", 47.5, 0.9)

    s2 = RunState("vinci", state_dir=str(state_dir), logs_dir=str(logs_dir))
    assert s2.is_processed("https://a") is True
    assert s2.is_processed("https://b") is True
    assert s2.is_processed("https://c") is True
    assert s2.is_processed("https://d") is False
    assert s2.counts == {"found": 1, "not_found": 1, "new_candidate": 1}


def test_found_and_not_found_logs_written(tmp_path):
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    s = RunState("sanef", state_dir=str(state_dir), logs_dir=str(logs_dir))
    s.log_found("https://a", 42, "Aire Test", "low")

    found_log = (logs_dir / "sanef_found.log").read_text(encoding="utf-8")
    assert "id=42" in found_log
    assert "Aire Test" in found_log


def test_new_candidate_log_written(tmp_path):
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    s = RunState("vinci", state_dir=str(state_dir), logs_dir=str(logs_dir))
    s.log_new_candidate("https://a", "Aire de La Picardiere", 47.53, 0.96)

    log_text = (logs_dir / "vinci_new_candidates.log").read_text(encoding="utf-8")
    assert "Aire de La Picardiere" in log_text
    assert "47.53" in log_text


def test_highway_issue_logged_but_not_checkpointed(tmp_path):
    # A bulk-source hub failure (e.g. one of 29 page-data.json fetches
    # 404ing) isn't an aire-level found/not-found and shouldn't be
    # checkpointed - it should be retried fresh on the next run instead of
    # silently skipped forever, unlike aire URLs.
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    s = RunState("vinci", state_dir=str(state_dir), logs_dir=str(logs_dir))

    hub_url = "https://www.vinci-autoroutes.com/fr/aires-et-services/autoroute-a83/"
    data_url = "https://www.vinci-autoroutes.com/page-data/fr/aires-et-services/autoroute-a83/page-data.json"
    s.log_highway_issue(hub_url, data_url, "page-data.json returned HTTP 404")

    assert s.highway_issue_count == 1
    assert s.is_processed(hub_url) is False
    assert s.is_processed(data_url) is False
    assert s.counts == {"found": 0, "not_found": 0, "new_candidate": 0}

    log_text = (logs_dir / "vinci_highway_issues.log").read_text(encoding="utf-8")
    assert hub_url in log_text
    assert data_url in log_text
    assert "404" in log_text

    # Not checkpointed -> a fresh RunState for the same operator doesn't
    # remember it either.
    s2 = RunState("vinci", state_dir=str(state_dir), logs_dir=str(logs_dir))
    assert s2.highway_issue_count == 0
