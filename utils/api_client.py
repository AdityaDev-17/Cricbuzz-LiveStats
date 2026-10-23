"""Cricbuzz API client with on-disk caching to protect the RapidAPI quota."""

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class CricbuzzAPIError(Exception):
    """Raised when the Cricbuzz API call fails."""


class CricbuzzClient:
    """Fetches Cricbuzz endpoints, caching every response as JSON."""

    def __init__(self, cache_dir: Path = PROJECT_ROOT / "data" / "raw", timeout: int = 15):
        host = os.getenv("RAPIDAPI_HOST")
        key = os.getenv("RAPIDAPI_KEY")
        if not host or not key:
            raise CricbuzzAPIError("RAPIDAPI_HOST / RAPIDAPI_KEY missing in .env")
        self.base_url = f"https://{host}"
        self.headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": host}
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.quota_remaining: str = "unknown"

    def fetch(
        self, endpoint: str, cache_name: str, params: dict | None = None, use_cache: bool = True
    ) -> dict:
        """Return JSON for an endpoint; read from cache when available."""
        cache_file = self.cache_dir / f"{cache_name}.json"
        if use_cache and cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))

        try:
            resp = requests.get(
                self.base_url + endpoint, headers=self.headers, params=params, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise CricbuzzAPIError(f"Network error on {endpoint}: {exc}") from exc

        self.quota_remaining = resp.headers.get("x-ratelimit-requests-remaining", "unknown")
        if resp.status_code == 429:
            raise CricbuzzAPIError("Monthly quota exhausted (429).")
        if resp.status_code != 200:
            raise CricbuzzAPIError(f"{endpoint} -> {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"[API] {endpoint} | quota remaining: {self.quota_remaining}")
        return data

    # ---------- Convenience wrappers ----------
    def recent_matches(self, use_cache: bool = True) -> dict:
        return self.fetch("/matches/v1/recent", "matches_recent", use_cache=use_cache)

    def live_matches(self, use_cache: bool = False) -> dict:
        return self.fetch("/matches/v1/live", "matches_live", use_cache=use_cache)

    def match_info(self, match_id: int) -> dict:
        return self.fetch(f"/mcenter/v1/{match_id}", f"match_{match_id}_info")

    def scorecard(self, match_id: int) -> dict:
        return self.fetch(f"/mcenter/v1/{match_id}/hscard", f"match_{match_id}_scorecard")

    def player_info(self, player_id: int) -> dict:
        return self.fetch(f"/stats/v1/player/{player_id}", f"player_{player_id}_info")

    def player_batting(self, player_id: int) -> dict:
        return self.fetch(f"/stats/v1/player/{player_id}/batting", f"player_{player_id}_batting")

    def player_bowling(self, player_id: int) -> dict:
        return self.fetch(f"/stats/v1/player/{player_id}/bowling", f"player_{player_id}_bowling")

    def venue(self, venue_id: int) -> dict:
        return self.fetch(f"/venues/v1/{venue_id}", f"venue_{venue_id}")

    def series_international(self) -> dict:
        return self.fetch("/series/v1/international", "series_international")
