"""
Unit tests for data/locations.search_locations -- the function that powers
/story-setup's starting_location autocomplete and is what actually lets the
owner search across all 100+ locations despite Discord's 25-suggestion
display cap (see the docstring on search_locations for how that works).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.locations import LOCATIONS, search_locations


def test_empty_query_returns_up_to_limit():
    results = search_locations("", limit=10)
    assert len(results) == 10


def test_search_matches_display_name_substring():
    results = search_locations("cemetery")
    names = [loc["display_name"] for loc in results]
    assert "Foggy Cemetery" in names


def test_search_matches_key_with_underscores_replaced():
    # "foggy cemetery" (spaces) should still match key "foggy_cemetery"
    results = search_locations("foggy cemetery")
    keys = [loc["key"] for loc in results]
    assert "foggy_cemetery" in keys


def test_search_matches_category():
    results = search_locations("transit", limit=100)
    assert len(results) == len([loc for loc in LOCATIONS if loc["category"] == "transit"])


def test_search_is_case_insensitive():
    lower = search_locations("cemetery")
    upper = search_locations("CEMETERY")
    assert [l["key"] for l in lower] == [l["key"] for l in upper]


def test_search_prioritizes_prefix_matches():
    # "Foggy Cemetery" starts with "foggy"; "Foggy Ferry Terminal" also
    # starts with "foggy" -- both should rank above any location that only
    # contains "foggy" elsewhere in the name (none currently do, but this
    # locks in the intended ordering behavior either way).
    results = search_locations("foggy")
    assert all(loc["display_name"].lower().startswith("foggy") for loc in results)


def test_search_respects_limit_even_with_many_matches():
    # "a" appears in a large fraction of display names -- confirm we never
    # return more than the Discord-imposed cap regardless of pool size.
    results = search_locations("a", limit=5)
    assert len(results) <= 5


def test_search_no_match_returns_empty():
    results = search_locations("xyzzynonexistentlocation")
    assert results == []


def test_search_pool_is_not_capped_at_25():
    # The actual point of autocomplete over static choices: the underlying
    # searchable pool must be able to exceed Discord's 25-choice limit.
    assert len(LOCATIONS) > 25
    results = search_locations("", limit=len(LOCATIONS))
    assert len(results) == len(LOCATIONS)
