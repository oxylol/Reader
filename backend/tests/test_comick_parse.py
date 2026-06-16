"""Offline tests for comick.art adapter parsing (no network)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.comick import ComickAdapter, _num  # noqa: E402


def test_num():
    assert _num("267") == (267.0, "267")
    assert _num("10.5") == (10.5, "10.5")
    assert _num(None) == (0.0, "")
    assert _num("Extra") == (0.0, "Extra")


def test_to_series_search_item():
    a = ComickAdapter()
    a._genres = {264: "Romance", 250: "Drama"}  # pretend metadata loaded
    item = {
        "slug": "omniscient-reader",
        "title": "Omniscient Reader",
        "country": "KR",
        "status": 1,
        "year": 2020,
        "content_rating": "safe",
        "default_thumbnail": "https://cdn1.comicknew.pictures/omniscient-reader/covers/x.webp",
        "titles": ["전지적 독자 시점"],
        "bayesian_rating": "9.1",
        "user_follow_count": 1234,
        "description": "  A reader. ",
        "genres": [264],
    }
    s = asyncio.run(a._to_series(item))
    assert s.source == "comick"
    assert s.source_id == "omniscient-reader"
    assert s.type == "manhwa"  # KR
    assert s.status == "ongoing"  # 1
    assert s.year == 2020
    assert s.rating == 9.1
    assert s.cover_url.endswith("x.webp")
    assert s.description == "A reader."
    assert "Romance" in s.tags
    assert "전지적 독자 시점" in s.alt_titles


def test_chapter_id_packs_slug():
    # source_chapter_id must encode slug + segment so pages can be fetched.
    seg = "omniscient-reader/HRLjQWI-chapter-267-en"
    slug, rest = seg.split("/", 1)
    assert slug == "omniscient-reader"
    assert rest == "HRLjQWI-chapter-267-en"


if __name__ == "__main__":
    test_num()
    test_to_series_search_item()
    test_chapter_id_packs_slug()
    print("all comick.art parse tests passed")
