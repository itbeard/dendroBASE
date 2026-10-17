"""Праверка бібліятэкі Tk, з якой сапраўды працуе гэты інтэрпрэтатар Python."""
from __future__ import annotations

import logging
import sys
import tkinter as tk

from ..i18n import tr

log = logging.getLogger("dendrobase.ui")
MIN_AQUA_TK = "8.6.13"


class UnsupportedTkError(RuntimeError):
    """Версія Tk мае вядомую памылку апрацоўкі клікаў на macOS."""


def check_tk_runtime(root: tk.Misc) -> None:
    """Не блытаць версію Tk з Tcl (info patchlevel) або акругленай tk.TkVersion.

    Tk 8.6.12 губляе падзеі мышы на macOS, незалежна ад тэмы ttk і grab.
    Выпраўленне знаходзіцца ў натыўнай бібліятэцы, а не ў Python-bindings:
    https://github.com/python/cpython/issues/110218
    """
    version = str(root.tk.call("package", "require", "Tk"))
    window_system = str(root.tk.call("tk", "windowingsystem"))
    log.info("Python executable: %s; Tcl %s; Tk %s; window system: %s; scaling: %s",
             sys.executable, root.tk.call("info", "patchlevel"), version,
             window_system, root.tk.call("tk", "scaling"))
    if window_system == "aqua" and int(root.tk.call("package", "vcompare", version, MIN_AQUA_TK)) < 0:
        raise UnsupportedTkError(tr(
            "Гэты Python выкарыстоўвае Tk {version}. На macOS патрэбны Tk {minimum} або навейшы: "
            "стары Tk губляе клікі па кнопках, спісах і іншых элементах інтэрфейсу.\n\n"
            "Інтэрпрэтатар: {executable}\n\n"
            "Запусціце праграму праз .venv/bin/python -m dendrobase, калі асяроддзе з новым Tk "
            "ужо створана. Інакш усталюйце Python з новым Tk і стварыце віртуальнае асяроддзе нанова "
            "(README → «Кнопкі не рэагуюць на клік»). Абнаўленне pip-пакетаў не абнаўляе Tk."
        ).format(version=version, minimum=MIN_AQUA_TK, executable=sys.executable))
