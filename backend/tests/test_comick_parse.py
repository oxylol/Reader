"""Offline tests for comick adapter parsing (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.comick import _parse_number, _series_from_json  # noqa: E402


def test_parse_number():
    assert _parse_number("12.5") == (12.5, "12.5")
    assert _parse_number("7") == (7.0, "7")
    assert _parse_number(None) == (0.0, "")
    assert _parse_number("Extra") == (0.0, "Extra")


def test_series_from_json_full():
    payload = {
        "comic": {
            "hid": "abc123",
            "slug": "solo-leveling",
            "title": "Solo Leveling",
            "country": "kr",
            "status": 2,
            "desc": "Weakest hunter becomes strongest.",
            "year": 2018,
            "content_rating": "safe",
            "bayesian_rating": "9.1",
            "user_follow_count": 12345,
            "md_titles": [{"title": "Na Honjaman Level Up"}],
            "md_covers": [{"b2key": "cover.jpg"}],
            "md_comic_md_genres": [
                {"md_genres": {"name": "Action"}},
                {"md_genres": {"name": "Fantasy"}},
            ],
        }
    }
    s = _series_from_json(payload)
    assert s.source == "comick"
    assert s.source_id == "abc123"
    assert s.title == "Solo Leveling"
    assert s.type == "manhwa"  # kr
    assert s.status == "completed"  # 2
    assert s.year == 2018
    assert s.rating == 9.1
    assert s.follow_count == 12345
    assert s.cover_url.endswith("/cover.jpg")
    assert "Action" in s.tags and "Fantasy" in s.tags
    assert "Na Honjaman Level Up" in s.alt_titles


def test_series_from_json_minimal():
    s = _series_from_json({"hid": "x", "title": "T", "country": "jp"})
    assert s.type == "manga"
    assert s.status == "unknown"
    assert s.cover_url == ""


if __name__ == "__main__":
    test_parse_number()
    test_series_from_json_full()
    test_series_from_json_minimal()
    print("all comick parse tests passed")
