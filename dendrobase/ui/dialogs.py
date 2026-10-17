"""Дыялогі: даведка пародаў, новая ПП, увод CRN і SERIES з буфера абмену, SQL-запыт."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..db import DatabaseError, DatabaseManager
from ..models import CrnRow, SeriesValue
from ..parsing import coerce_title_values, parse_clipboard_table, parse_crn_table, parse_series_table
from ..reference import CRN_COLUMNS, PORODA_DICT, PROBE_KEY, TITLE_FIELDS
from .feedback import ask_yes_no, show_error, show_info, show_warning
from .title_form import TitleForm
from .widgets import (ScrollableFrame, app_font, clear_tree, copy_to_clipboard, fill_tree, make_treeview,
                      read_clipboard, set_columns, tree_to_tsv)

ChangeCallback = Callable[[str], None]
_READ_ONLY_SQL = ("select", "with", "explain", "show", "table", "values")


def _modal(parent: tk.Misc, title: str, size: str) -> tk.Toplevel:
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry(size)
    dialog.minsize(480, 320)
    dialog.transient(parent.winfo_toplevel())
    try:
        dialog.grab_set()
    except tk.TclError:  # акно яшчэ не паказана (напрыклад, у тэстах)
        pass
    return dialog


def _errors_text(errors: list[str], limit: int = 12) -> str:
    shown = errors[:limit]
    if len(errors) > limit:
        shown.append(f"... і яшчэ {len(errors) - limit}")
    return "\n".join(shown)


class PorodaHelpDialog:
    """Расшыфроўка скарачэнняў парод."""

    def __init__(self, parent: tk.Misc) -> None:
        self.dialog = _modal(parent, "Даведка: расшыфроўка пародаў", "520x640")
        ttk.Label(self.dialog, text="Расшыфроўка скарачэнняў парод дрэў",
                  font=app_font(bold=True, size_delta=2)).pack(pady=10)
        self.tree = make_treeview(self.dialog, ("Скарачэнне", "Поўная назва"), horizontal=False)
        self.tree.column("Скарачэнне", width=110, stretch=False)
        self.tree.column("Поўная назва", width=340)
        fill_tree(self.tree, sorted(PORODA_DICT.items()))
        self.tree.master.pack(fill="both", expand=True, padx=10, pady=5)
        ttk.Button(self.dialog, text="Зачыніць", command=self.dialog.destroy).pack(pady=10)


class AddProbeDialog:
    """Анкета новай пробнай плошчы, далей па жаданні CRN і SERIES."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager, on_change: ChangeCallback | None = None) -> None:
        self.parent = parent
        self.db = db
        self.on_change = on_change
        self.saved_probe: str | None = None
        self.dialog = _modal(parent, "Дадаць новую пробную плошчу", "1300x800")

        buttons = ttk.Frame(self.dialog)
        buttons.pack(side="bottom", fill="x", padx=10, pady=8)
        ttk.Button(buttons, text="Захаваць і перайсці да CRN", command=self.save_and_continue).pack(side="left", padx=4)
        ttk.Button(buttons, text="Толькі захаваць (без CRN)", command=self.save_only).pack(side="left", padx=4)
        ttk.Button(buttons, text="Адмена", command=self.dialog.destroy).pack(side="left", padx=4)
        ttk.Button(buttons, text="? Расшыфроўка пародаў",
                   command=lambda: PorodaHelpDialog(self.dialog)).pack(side="right", padx=4)

        scroll = ScrollableFrame(self.dialog)
        scroll.pack(fill="both", expand=True)
        self.form = TitleForm(scroll.inner, TITLE_FIELDS, columns=3)
        self.form.frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.form.focus_first()

    def _save(self) -> str | None:
        data, errors = coerce_title_values(self.form.values())
        probe = data.get(PROBE_KEY)
        if not probe:
            show_warning("Папярэджанне", "Поле «N пробной площади» абавязковае.", parent=self.dialog)
            return None
        if errors:
            show_warning("Праверце значэнні", "Гэтыя палі не ўдалося разабраць:\n" + _errors_text(errors),
                         parent=self.dialog)
            return None
        payload = {name: value for name, value in data.items() if value is not None}
        try:
            self.db.upsert_title(payload)
            if payload.get("shirota_grd") and payload.get("dolgota_grd") \
                    and self.db.has_postgis() and self.db.has_geometry_column():
                self.db.update_geometry(str(probe))
        except (DatabaseError, ValueError) as exc:
            show_error("Памылка захавання", f"Не атрымалася захаваць ПП:\n{exc}", exc, parent=self.dialog)
            return None
        self.saved_probe = str(probe)
        if self.on_change:
            self.on_change(self.saved_probe)
        return self.saved_probe

    def save_and_continue(self) -> None:
        probe = self._save()
        if probe:
            self.dialog.destroy()
            CrnDialog(self.parent, self.db, probe, on_change=self.on_change, chain=True)

    def save_only(self) -> None:
        probe = self._save()
        if probe:
            show_info("Поспех", f"ПП {probe} захавана.", parent=self.parent)
            self.dialog.destroy()


class CrnDialog:
    """Масавы ўвод CRN: даныя капіююцца з Excel і ўстаўляюцца з буфера абмену."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager, probe: str,
                 on_change: ChangeCallback | None = None, *, chain: bool = False) -> None:
        self.parent = parent
        self.db = db
        self.probe = probe
        self.on_change = on_change
        self.chain = chain
        self.rows: list[CrnRow] = []
        self.dialog = _modal(parent, f"Увод CRN храналогіі для {probe}", "1100x700")

        ttk.Label(self.dialog, text=f"Даданне CRN храналогіі для ПП: {probe}",
                  font=app_font(bold=True, size_delta=2)).pack(pady=(8, 2))
        ttk.Label(self.dialog, foreground="blue",
                  text="Скапіруйце з Excel слупкі year, num, raw, std, res, ars (загаловак неабавязковы) "
                       "і націсніце «Уставіць з буфера абмену».").pack(pady=(0, 6))

        buttons = ttk.Frame(self.dialog)
        buttons.pack(fill="x", padx=8, pady=4)
        ttk.Button(buttons, text="Уставіць з буфера абмену", command=self.paste).pack(side="left", padx=4)
        ttk.Button(buttons, text="Ачысціць табліцу", command=self.clear).pack(side="left", padx=4)
        if chain:
            ttk.Button(buttons, text="Захаваць і перайсці да SERIES", command=self.save_and_continue).pack(side="left", padx=4)
            ttk.Button(buttons, text="Толькі захаваць CRN", command=self.save_only).pack(side="left", padx=4)
            ttk.Button(buttons, text="Прапусціць CRN", command=self.skip).pack(side="left", padx=4)
        else:
            ttk.Button(buttons, text="Захаваць", command=self.save_only).pack(side="left", padx=4)
            ttk.Button(buttons, text="Зачыніць", command=self.dialog.destroy).pack(side="left", padx=4)

        self.tree = make_treeview(self.dialog, CRN_COLUMNS)
        self.tree.master.pack(fill="both", expand=True, padx=8, pady=6)
        self.status = ttk.Label(self.dialog, text="Радкоў: 0", foreground="blue")
        self.status.pack(pady=(0, 6))

    def paste(self) -> None:
        text = read_clipboard(self.dialog)
        if not text.strip():
            show_warning("Буфер абмену пусты", "Спачатку скапіруйце табліцу з Excel.", parent=self.dialog)
            return
        rows, errors = parse_crn_table(parse_clipboard_table(text))
        self.rows.extend(rows)
        fill_tree(self.tree, rows)
        self.status.configure(text=f"Радкоў: {len(self.rows)}")
        if errors:
            show_warning("Частка радкоў прапушчана", _errors_text(errors), parent=self.dialog)

    def clear(self) -> None:
        self.rows.clear()
        clear_tree(self.tree)
        self.status.configure(text="Радкоў: 0")

    def _save(self) -> bool:
        if not self.rows:
            return True
        try:
            written = self.db.upsert_crn_rows(self.probe, self.rows)
        except DatabaseError as exc:
            show_error("Памылка", f"Не атрымалася захаваць CRN:\n{exc}", exc, parent=self.dialog)
            return False
        show_info("Поспех", f"Захавана {written} запісаў CRN для {self.probe}.", parent=self.dialog)
        if self.on_change:
            self.on_change(self.probe)
        return True

    def save_and_continue(self) -> None:
        if self._save():
            self.dialog.destroy()
            SeriesDialog(self.parent, self.db, self.probe, on_change=self.on_change, chain=True)

    def save_only(self) -> None:
        if self._save():
            self.dialog.destroy()

    def skip(self) -> None:
        self.dialog.destroy()
        SeriesDialog(self.parent, self.db, self.probe, on_change=self.on_change, chain=True)


class SeriesDialog:
    """Масавы ўвод SERIES: першы слупок год, далей слупкі з назвамі серый."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager, probe: str,
                 on_change: ChangeCallback | None = None, *, chain: bool = False) -> None:
        self.parent = parent
        self.db = db
        self.probe = probe
        self.on_change = on_change
        self.values: list[SeriesValue] = []
        self.dialog = _modal(parent, f"Увод SERIES для {probe}", "1100x700")

        ttk.Label(self.dialog, text=f"Даданне SERIES для ПП: {probe}",
                  font=app_font(bold=True, size_delta=2)).pack(pady=(8, 2))
        ttk.Label(self.dialog, foreground="blue",
                  text="Скапіруйце з Excel табліцу разам з загалоўкам: першы слупок год, "
                       "наступныя слупкі - назвы серый з іх значэннямі.").pack(pady=(0, 6))

        buttons = ttk.Frame(self.dialog)
        buttons.pack(fill="x", padx=8, pady=4)
        ttk.Button(buttons, text="Уставіць з буфера абмену", command=self.paste).pack(side="left", padx=4)
        ttk.Button(buttons, text="Ачысціць табліцу", command=self.clear).pack(side="left", padx=4)
        ttk.Button(buttons, text="Захаваць і скончыць" if chain else "Захаваць", command=self.save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Прапусціць SERIES" if chain else "Зачыніць", command=self.dialog.destroy).pack(side="left", padx=4)

        self.tree = make_treeview(self.dialog)
        self.tree.master.pack(fill="both", expand=True, padx=8, pady=6)
        self.status = ttk.Label(self.dialog, text="Значэнняў: 0", foreground="blue")
        self.status.pack(pady=(0, 6))

    def paste(self) -> None:
        text = read_clipboard(self.dialog)
        if not text.strip():
            show_warning("Буфер абмену пусты", "Спачатку скапіруйце табліцу з Excel.", parent=self.dialog)
            return
        values, errors = parse_series_table(parse_clipboard_table(text))
        if values:
            self.values = values
            self._show_preview()
        if errors:
            show_warning("Праверце даныя", _errors_text(errors), parent=self.dialog)

    def _show_preview(self) -> None:
        names = sorted({v.series_name for v in self.values}, key=lambda n: (len(n), n))
        years = sorted({v.year for v in self.values})
        table = {(v.year, v.series_name): v.value for v in self.values}
        set_columns(self.tree, ["year", *names], width=80)
        fill_tree(self.tree, ([year] + [table.get((year, name)) for name in names] for year in years))
        self.status.configure(text=f"Значэнняў: {len(self.values)}, серый: {len(names)}, гадоў: {len(years)}")

    def clear(self) -> None:
        self.values = []
        set_columns(self.tree, [])
        self.status.configure(text="Значэнняў: 0")

    def save(self) -> None:
        if self.values:
            try:
                written = self.db.upsert_series_values(self.probe, self.values)
            except DatabaseError as exc:
                show_error("Памылка", f"Не атрымалася захаваць SERIES:\n{exc}", exc, parent=self.dialog)
                return
            show_info("Поспех", f"Захавана {written} значэнняў SERIES для {self.probe}.", parent=self.dialog)
            if self.on_change:
                self.on_change(self.probe)
        self.dialog.destroy()


class SqlQueryDialog:
    """Выкананне адвольнага SQL з паказам выніку."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager) -> None:
        self.db = db
        self.dialog = _modal(parent, "SQL Запыт", "1000x700")
        main = ttk.Frame(self.dialog)
        main.pack(fill="both", expand=True, padx=6, pady=6)

        ttk.Label(main, text="SQL Запыт:", font=app_font(bold=True)).pack(anchor="w", pady=2)
        editor = ttk.Frame(main)
        editor.pack(fill="both", expand=True, pady=4)
        self.text = tk.Text(editor, wrap="none", height=10, font=app_font(fixed=True), undo=True)
        vertical = ttk.Scrollbar(editor, orient="vertical", command=self.text.yview)
        horizontal = ttk.Scrollbar(editor, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        horizontal.pack(side="bottom", fill="x")
        self.text.pack(side="left", fill="both", expand=True)
        vertical.pack(side="right", fill="y")

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=4)
        ttk.Button(buttons, text="Выканаць", command=self.execute).pack(side="left", padx=4)
        ttk.Button(buttons, text="Уставіць з буфера", command=self.paste).pack(side="left", padx=4)
        ttk.Button(buttons, text="Ачысціць", command=lambda: self.text.delete("1.0", "end")).pack(side="left", padx=4)
        self.dialog.bind("<Control-Return>", lambda _e: self.execute())

        ttk.Label(main, text="Вынік:", font=app_font(bold=True)).pack(anchor="w", pady=2)
        self.result = make_treeview(main)
        self.result.master.pack(fill="both", expand=True, pady=4)

        status_bar = ttk.Frame(main)
        status_bar.pack(fill="x", pady=4)
        self.status = ttk.Label(status_bar, text="Гатова. Ctrl+Enter выконвае запыт.", foreground="blue")
        self.status.pack(side="left")
        ttk.Button(status_bar, text="Капіраваць вынік у буфер", command=self.copy_result).pack(side="right", padx=4)

    def paste(self) -> None:
        self.text.insert("insert", read_clipboard(self.dialog))

    def execute(self) -> None:
        query = self.text.get("1.0", "end").strip()
        if not query:
            show_warning("Папярэджанне", "Увядзіце SQL запыт.", parent=self.dialog)
            return
        if not query.lower().startswith(_READ_ONLY_SQL):
            if not ask_yes_no("Пацверджанне", "Запыт можа змяніць або выдаліць даныя. Выканаць?", parent=self.dialog):
                return
        self.status.configure(text="Выкананне запыту...", foreground="orange")
        self.dialog.update_idletasks()
        try:
            result = self.db.execute_sql(query)
        except DatabaseError as exc:
            self.status.configure(text=f"Памылка: {str(exc).splitlines()[0]}", foreground="red")
            show_error("Памылка SQL", str(exc), exc, parent=self.dialog)
            return
        if result.has_rows:
            set_columns(self.result, result.columns)
            fill_tree(self.result, result.rows)
            self.status.configure(text=f"Выканана. Знойдзена радкоў: {result.rowcount}", foreground="green")
        else:
            set_columns(self.result, [])
            self.status.configure(text=f"Выканана. Закранута радкоў: {result.rowcount}", foreground="green")

    def copy_result(self) -> None:
        if not self.result.get_children():
            show_warning("Папярэджанне", "Няма даных для капіравання.", parent=self.dialog)
            return
        copy_to_clipboard(self.dialog, tree_to_tsv(self.result))
        self.status.configure(text=f"Скапіравана радкоў: {len(self.result.get_children())}", foreground="blue")
