"""Offline tests for MangaDex adapter parsing (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.mangadex import (  # noqa: E402
    _manga_to_series,
    _parse_number,
    _pick_lang,
    _slugify,
)


def test_pick_lang():
    assert _pick_lang({"en": "Hi", "ja": "やあ"}) == "Hi"
    assert _pick_lang({"ja": "やあ"}) == "やあ"
    assert _pick_lang(None) == ""


def test_parse_number():
    assert _parse_number("12.5") == (12.5, "12.5")
    assert _parse_number("7") == (7.0, "7")
    assert _parse_number(None) == (0.0, "")
    assert _parse_number("Oneshot") == (0.0, "Oneshot")


def test_slugify():
    assert _slugify("Solo Leveling: Ragnarok!") == "solo-leveling-ragnarok"


def test_manga_to_series():
    m = {
        "id": "abc-uuid",
        "attributes": {
            "title": {"en": "Solo Leveling"},
            "altTitles": [{"ko": "나 혼자만 레벨업"}],
            "description": {"en": "Weak hunter becomes strongest."},
            "status": "completed",
            "year": 2018,
            "contentRating": "safe",
            "originalLanguage": "ko",
            "tags": [
                {"attributes": {"name": {"en": "Action"}}},
                {"attributes": {"name": {"en": "Fantasy"}}},
            ],
            "rating": {"bayesian": 8.9},
        },
        "relationships": [
            {"type": "cover_art", "attributes": {"fileName": "cover.jpg"}}
        ],
    }
    s = _manga_to_series(m)
    assert s.source == "mangadex"
    assert s.source_id == "abc-uuid"
    assert s.title == "Solo Leveling"
    assert s.type == "manhwa"  # ko
    assert s.status == "completed"
    assert s.year == 2018
    assert s.rating == 8.9
    assert s.cover_url.endswith("/abc-uuid/cover.jpg.512.jpg")
    assert "Action" in s.tags and "Fantasy" in s.tags


def test_manga_to_series_minimal():
    s = _manga_to_series({"id": "x", "attributes": {"originalLanguage": "ja"}})
    assert s.type == "manga"
    assert s.status == "unknown"
    assert s.cover_url == ""


if __name__ == "__main__":
    test_pick_lang()
    test_parse_number()
    test_slugify()
    test_manga_to_series()
    test_manga_to_series_minimal()
    print("all mangadex parse tests passed")
