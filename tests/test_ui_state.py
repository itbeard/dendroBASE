from dendrobase.ui.ui_state import load_ui_state, save_ui_state


def test_round_trip_and_merge(tmp_path):
    path = tmp_path / "state" / "ui_state.json"
    assert load_ui_state(path) == {}
    save_ui_state({"geometry": "1400x860+10+10", "sash": 300}, path)
    save_ui_state({"last_probe": "pp01"}, path)
    assert load_ui_state(path) == {"geometry": "1400x860+10+10", "sash": 300, "last_probe": "pp01"}


def test_corrupted_file_is_ignored(tmp_path):
    path = tmp_path / "ui_state.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_ui_state(path) == {}
    path.write_text("[1, 2]", encoding="utf-8")
    assert load_ui_state(path) == {}
