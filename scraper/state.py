"""Resumable per-operator run state + found/not-found/new-candidate progress logs.

Checkpoint is an append-only JSONL file of processed source URLs, written
after each page so a Ctrl-C or crash mid-run loses at most one in-flight
request. On startup we replay it to know what to skip.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("scraper.state")

_OUTCOMES = ("found", "not_found", "new_candidate")


class RunState:
    def __init__(self, operator_key: str, state_dir: str = "state", logs_dir: str = "logs"):
        self.operator_key = operator_key
        self.state_dir = Path(state_dir)
        self.logs_dir = Path(logs_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.checkpoint_path = self.state_dir / f"{operator_key}.jsonl"
        self.found_log_path = self.logs_dir / f"{operator_key}_found.log"
        self.not_found_log_path = self.logs_dir / f"{operator_key}_not_found.log"
        self.new_candidates_log_path = self.logs_dir / f"{operator_key}_new_candidates.log"

        self._processed_urls: set[str] = set()
        self._counts = {outcome: 0 for outcome in _OUTCOMES}
        self._load_checkpoint()

    def _load_checkpoint(self) -> None:
        if not self.checkpoint_path.exists():
            return
        with self.checkpoint_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                self._processed_urls.add(entry["url"])
                outcome = entry.get("outcome")
                self._counts[outcome if outcome in _OUTCOMES else "not_found"] += 1
        log.info(
            "%s: resuming, %d URLs already processed (%d found, %d not found, %d new candidates)",
            self.operator_key,
            len(self._processed_urls),
            self._counts["found"],
            self._counts["not_found"],
            self._counts["new_candidate"],
        )

    def is_processed(self, url: str) -> bool:
        return url in self._processed_urls

    def _append_checkpoint(self, url: str, outcome: str) -> None:
        with self.checkpoint_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"url": url, "outcome": outcome}) + "\n")
        self._processed_urls.add(url)

    def log_found(self, url: str, aire_id: int, aire_nom: str, confidence: str) -> None:
        self._append_checkpoint(url, "found")
        self._counts["found"] += 1
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.found_log_path.open("a", encoding="utf-8") as f:
            f.write(f"{ts}\t{url}\t-> id={aire_id} nom={aire_nom!r} confidence={confidence}\n")

    def log_not_found(self, url: str, reason: str) -> None:
        self._append_checkpoint(url, "not_found")
        self._counts["not_found"] += 1
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.not_found_log_path.open("a", encoding="utf-8") as f:
            f.write(f"{ts}\t{url}\t-> {reason}\n")

    def log_new_candidate(self, url: str, nom: str, lat: float, lng: float) -> None:
        self._append_checkpoint(url, "new_candidate")
        self._counts["new_candidate"] += 1
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.new_candidates_log_path.open("a", encoding="utf-8") as f:
            f.write(f"{ts}\t{url}\t-> nom={nom!r} lat={lat} lng={lng}\n")

    @property
    def counts(self) -> dict:
        return dict(self._counts)
