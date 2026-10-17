from pathlib import Path

from dendrobase.paths import APP_NAME, app_data_dir, default_log_dir


def test_directories_are_absolute_and_named_after_app():
    for directory in (app_data_dir(), default_log_dir()):
        assert isinstance(directory, Path) and directory.is_absolute()
        assert APP_NAME.lower() in str(directory).lower()
