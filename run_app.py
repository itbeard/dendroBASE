#!/usr/bin/env python3
"""Лаўнчар для запуску двайным клікам. Тое ж самае, што `python -m dendrobase`.

На Windows можна запускаць праз pythonw.exe, каб не адкрывалася кансоль.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dendrobase.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
