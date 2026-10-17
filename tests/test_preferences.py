from dendrobase.ui.preferences import Preferences, load_preferences, save_preferences
from dendrobase.ui.ui_state import load_ui_state, save_ui_state


def test_defaults_are_english_and_system_theme(tmp_path):
    assert load_preferences(tmp_path / "missing.json") == Preferences(language="en", theme="system")


def test_round_trip_keeps_other_ui_state(tmp_path):
    path = tmp_path / "ui_state.json"
    save_ui_state({"geometry": "1400x860+10+10"}, path)
    save_preferences(Preferences(language="be", theme="dark"), path)
    assert load_preferences(path) == Preferences(language="be", theme="dark")
    assert load_ui_state(path)["geometry"] == "1400x860+10+10"


def test_invalid_values_fall_back_to_defaults(tmp_path):
    path = tmp_path / "ui_state.json"
    save_ui_state({"language": "klingon", "theme": "neon"}, path)
    assert load_preferences(path) == Preferences()
    assert Preferences(language="BE", theme="Dark").normalized() == Preferences(language="be", theme="dark")
