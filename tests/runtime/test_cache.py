from plux.runtime.cache import EntryPointsCache
from plux.runtime.metadata import build_entry_point_index, parse_entry_points_text


def test_cache_get_entry_points():
    result = EntryPointsCache.instance().get_entry_points()

    assert result
    assert result == EntryPointsCache.instance().get_entry_points()


def test_cache_get_entry_points_creates_parseable_file(tmp_path):
    # a white box test for caching
    index = EntryPointsCache.instance()._build_and_store_index(tmp_path)
    assert index

    files = list(tmp_path.glob("*.entry_points.txt"))
    assert files
    assert index == build_entry_point_index(parse_entry_points_text(files[0].read_text()))
