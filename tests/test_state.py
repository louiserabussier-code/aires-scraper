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
