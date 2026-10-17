"""Дыялогі: даведка пародаў, майстар новай ПП (3 крокі), увод CRN і SERIES з буфера, SQL-запыт, налады."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..db import DatabaseError, DatabaseManager
from ..i18n import LANGUAGE_NAMES, tr
from ..models import CrnRow, SeriesValue
from ..parsing import coerce_title_values, parse_clipboard_table, parse_crn_table, parse_series_table
from ..reference import CRN_COLUMNS, PORODA_DICT, PROBE_KEY, TITLE_SECTIONS, field_label
from .feedback import ask_yes_no, show_error
from .preferences import Preferences
from .theme import PAD, THEMES, app_font, prepare_toplevel
from .title_form import TitleForm
from .widgets import (HintLabel, ScrollableFrame, add_tooltip, clear_tree, copy_to_clipboard, fill_tree, make_treeview,
                      read_clipboard, set_columns, tree_to_tsv)

ChangeCallback = Callable[[str], None]
Notify = Callable[..., None]
_READ_ONLY_SQL = ("select", "with", "explain", "show", "table", "values")
CRN_NUMERIC = {"year": 0, "num": 0, "raw": 3, "std": 3, "res": 3, "ars": 3}


def _modal(parent: tk.Misc, title: str, size: str, min_size: tuple[int, int] = (560, 400)) -> tk.Toplevel:
    """Дыялог паверх галоўнага акна, без мадальнага захопу: на macOS з Tk 8.6.12 лакальны захоп
    перыядычна «з'ядае» клікі і ў дыялогу, і ў галоўным акне пасля яго закрыцця."""
    dialog = tk.Toplevel(parent)
    prepare_toplevel(dialog)  # светлы/цёмны выгляд, абраны ў наладах
    dialog.title(title)
    dialog.geometry(size)
    dialog.minsize(*min_size)
    dialog.transient(parent.winfo_toplevel())
    dialog.bind("<Escape>", lambda _e: dialog.destroy())
    dialog.after_idle(dialog.lift)
    return dialog


def _bottom_bar(dialog: tk.Toplevel) -> tuple[ttk.Frame, HintLabel]:
    """Ніжні радок дыялога: кнопкі і радок падказак для віджэтаў гэтага акна."""
    bar = ttk.Frame(dialog, padding=(PAD * 2, 6, PAD * 2, PAD))
    bar.pack(side="bottom", fill="x")
    hint = HintLabel(dialog, dialog, default="")
    hint.pack(side="bottom", fill="x", padx=PAD * 2, pady=(0, 2))
    return bar, hint


def _header(dialog: tk.Misc, title: str, hint: str = "") -> None:
    box = ttk.Frame(dialog, padding=(PAD * 2, PAD, PAD * 2, 4))
    box.pack(fill="x")
    ttk.Label(box, text=title, style="Title.TLabel").pack(anchor="w")
    if hint:
        ttk.Label(box, text=hint, style="Subtitle.TLabel", wraplength=900, justify="left").pack(anchor="w", pady=(2, 0))


def _errors_text(errors: list[str], limit: int = 10) -> str:
    shown = errors[:limit]
    if len(errors) > limit:
        shown.append(tr("... і яшчэ {count}").format(count=len(errors) - limit))
    return "\n".join(shown)


class PorodaHelpDialog:
    """Расшыфроўка скарачэнняў парод з жывым пошукам."""

    def __init__(self, parent: tk.Misc) -> None:
        self.dialog = _modal(parent, tr("Даведка: расшыфроўка пародаў"), "520x640", (400, 300))
        _header(self.dialog, tr("Скарачэнні парод дрэў"), tr("Пачніце набіраць скарачэнне або назву, спіс адфільтруецца."))
        self.search = ttk.Entry(self.dialog)
        self.search.pack(fill="x", padx=PAD * 2, pady=(0, 6))
        self.search.bind("<KeyRelease>", lambda _e: self._fill())
        code = tr("Скарачэнне")
        self.tree = make_treeview(self.dialog, (code, tr("Поўная назва")), horizontal=False)
        self.tree.column(code, width=110, stretch=False)
        self.tree.master.pack(fill="both", expand=True, padx=PAD * 2)
        ttk.Button(self.dialog, text=tr("Зачыніць"), command=self.dialog.destroy).pack(pady=PAD)
        self._fill()
        self.search.focus_set()

    def _fill(self) -> None:
        needle = self.search.get().strip().lower()
        clear_tree(self.tree)
        names = [(code, tr(name)) for code, name in sorted(PORODA_DICT.items())]
        fill_tree(self.tree, (
            (code, name) for code, name in names
            if not needle or needle in code.lower() or needle in name.lower()
        ))


class AddProbeDialog:
    """Крок 1 з 3: анкета новай пробнай плошчы. Далей па жаданні CRN і SERIES."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager, on_change: ChangeCallback | None = None,
                 notify: Notify | None = None) -> None:
        self.parent = parent
        self.db = db
        self.on_change = on_change
        self.notify = notify
        self.saved_probe: str | None = None
        self.dialog = _modal(parent, tr("Новая пробная плошча"), "1200x820", (800, 500))
        _header(self.dialog, tr("Крок 1 з 3  ·  Новая пробная плошча"),
                tr("Палі з * абавязковыя. Пасля захавання можна адразу ўставіць CRN і SERIES з буфера абмену."))

        buttons, self.hint = _bottom_bar(self.dialog)
        ttk.Button(buttons, text=tr("Расшыфроўка пародаў"), command=lambda: PorodaHelpDialog(self.dialog)).pack(side="left")
        ttk.Button(buttons, text=tr("Захаваць і перайсці да CRN  →"), command=self.save_and_continue).pack(side="right")
        ttk.Button(buttons, text=tr("Захаваць"), command=self.save_only).pack(side="right", padx=4)
        ttk.Button(buttons, text=tr("Адмена"), command=self.dialog.destroy).pack(side="right", padx=4)

        self.error_label = ttk.Label(self.dialog, text="", style="Error.TLabel", wraplength=1100, justify="left")
        self.error_label.pack(fill="x", padx=PAD * 2)
        scroll = ScrollableFrame(self.dialog)
        scroll.pack(fill="both", expand=True)
        self.form = TitleForm(scroll.inner, TITLE_SECTIONS, columns=2)
        self.form.frame.pack(fill="both", expand=True, padx=PAD)
        self.form.focus_first()

    def _save(self) -> str | None:
        raw = self.form.values()
        data, errors = coerce_title_values(raw)
        probe = data.get(PROBE_KEY)
        if not probe:
            self.form.mark_errors([PROBE_KEY])
            self.error_label.configure(text=tr("Поле «{label}» абавязковае.").format(label=field_label(PROBE_KEY)))
            self.form.focus_field(PROBE_KEY)
            return None
        if errors:
            invalid = [name for name, text in raw.items() if text and name not in data]
            self.form.mark_errors(invalid)
            self.error_label.configure(text=tr("Праверце палі: {errors}").format(errors="; ".join(errors)))
            if invalid:
                self.form.focus_field(invalid[0])
            return None
        self.form.mark_errors(())
        self.error_label.configure(text="")
        payload = {name: value for name, value in data.items() if value is not None}
        try:
            self.db.upsert_title(payload)
            if payload.get("shirota_grd") and payload.get("dolgota_grd") \
                    and self.db.has_postgis() and self.db.has_geometry_column():
                self.db.update_geometry(str(probe))
        except (DatabaseError, ValueError) as exc:
            show_error(tr("Памылка захавання"), tr("Не атрымалася захаваць ПП:\n{error}").format(error=exc), exc,
                       parent=self.dialog)
            return None
        self.saved_probe = str(probe)
        if self.notify:
            self.notify(tr("ПП {probe} створана.").format(probe=probe), kind="ok")
        if self.on_change:
            self.on_change(self.saved_probe)
        return self.saved_probe

    def save_and_continue(self) -> None:
        probe = self._save()
        if probe:
            self.dialog.destroy()
            CrnDialog(self.parent, self.db, probe, on_change=self.on_change, notify=self.notify, chain=True)

    def save_only(self) -> None:
        if self._save():
            self.dialog.destroy()


_CRN_EXAMPLE = "year\tnum\traw\tstd\tres\tars\n1900\t12\t1.234\t1.012\t0.998\t1.003\n1901\t12\t1.198\t0.987\t1.004\t0.991"
_SERIES_EXAMPLE = "year\t1\t1a\t2\n1900\t1.52\t1.40\t\n1901\t1.61\t1.45\t1.38"


class CrnDialog:
    """Масавы ўвод CRN: даныя капіююцца з Excel і ўстаўляюцца з буфера абмену."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager, probe: str, on_change: ChangeCallback | None = None,
                 notify: Notify | None = None, *, chain: bool = False) -> None:
        self.parent = parent
        self.db = db
        self.probe = probe
        self.on_change = on_change
        self.notify = notify
        self.chain = chain
        self.rows: list[CrnRow] = []
        self.dialog = _modal(parent, tr("CRN для {probe}").format(probe=probe), "1000x680")
        title = tr("Крок 2 з 3  ·  CRN для {probe}") if chain else tr("Абагульненая храналогія CRN для {probe}")
        _header(self.dialog, title.format(probe=probe),
                tr("Вылучыце ў Excel слупкі year, num, raw, std, res, ars (загаловак неабавязковы, парадак па назвах), "
                   "скапіруйце і націсніце «Уставіць з буфера абмену». Дзесятковая коска прымаецца."))
        example = ttk.Frame(self.dialog, padding=(PAD * 2, 0))
        example.pack(fill="x")
        ttk.Label(example, text=tr("Прыклад:"), style="Hint.TLabel").pack(side="left", anchor="n")
        ttk.Label(example, text=_CRN_EXAMPLE.replace("\t", "    "), font=app_font(fixed=True, size_delta=-1),
                  style="Hint.TLabel", justify="left").pack(side="left", padx=PAD)

        buttons, self.hint = _bottom_bar(self.dialog)
        if chain:
            ttk.Button(buttons, text=tr("Прапусціць CRN"), command=self.skip).pack(side="left")
            ttk.Button(buttons, text=tr("Захаваць і перайсці да SERIES  →"), command=self.save_and_continue).pack(side="right")
            ttk.Button(buttons, text=tr("Захаваць і скончыць"), command=self.save_only).pack(side="right", padx=4)
        else:
            ttk.Button(buttons, text=tr("Зачыніць"), command=self.dialog.destroy).pack(side="left")
            ttk.Button(buttons, text=tr("Захаваць"), command=self.save_only).pack(side="right")

        toolbar = ttk.Frame(self.dialog, padding=(PAD * 2, PAD, PAD * 2, 4))
        toolbar.pack(fill="x")
        paste = ttk.Button(toolbar, text=tr("Уставіць з буфера абмену"), command=self.paste)
        paste.pack(side="left")
        add_tooltip(paste, tr("Ctrl+V у гэтым акне робіць тое ж самае."))
        ttk.Button(toolbar, text=tr("Ачысціць"), command=self.clear).pack(side="left", padx=4)
        self.status = ttk.Label(toolbar, text=tr("Радкоў: {count}").format(count=0), style="Subtitle.TLabel")
        self.status.pack(side="left", padx=PAD)
        for sequence in ("<Control-v>", "<Command-v>"):
            self.dialog.bind(sequence, lambda _e: self.paste())

        self.tree = make_treeview(self.dialog, CRN_COLUMNS, numeric=CRN_NUMERIC, horizontal=False)
        self.tree.master.pack(fill="both", expand=True, padx=PAD * 2)

    def paste(self) -> None:
        text = read_clipboard(self.dialog)
        if not text.strip():
            self.status.configure(text=tr("Буфер абмену пусты: спачатку скапіруйце табліцу з Excel."), style="Error.TLabel")
            return
        rows, errors = parse_crn_table(parse_clipboard_table(text))
        self.rows.extend(rows)
        fill_tree(self.tree, rows)
        self.status.configure(text=tr("Радкоў: {count}").format(count=len(self.rows)), style="Subtitle.TLabel")
        if errors:
            self.status.configure(text=tr("Радкоў: {count}; прапушчана: {skipped}. {errors}").format(
                count=len(self.rows), skipped=len(errors), errors=_errors_text(errors, 3).replace("\n", " ")),
                style="Warn.TLabel")

    def clear(self) -> None:
        self.rows.clear()
        clear_tree(self.tree)
        self.status.configure(text=tr("Радкоў: {count}").format(count=0), style="Subtitle.TLabel")

    def _save(self) -> bool:
        if not self.rows:
            return True
        try:
            written = self.db.upsert_crn_rows(self.probe, self.rows)
        except DatabaseError as exc:
            show_error(tr("Памылка"), tr("Не атрымалася захаваць CRN:\n{error}").format(error=exc), exc, parent=self.dialog)
            return False
        if self.notify:
            self.notify(tr("CRN {probe}: захавана радкоў: {count}").format(probe=self.probe, count=written), kind="ok")
        if self.on_change:
            self.on_change(self.probe)
        return True

    def save_and_continue(self) -> None:
        if self._save():
            self.dialog.destroy()
            SeriesDialog(self.parent, self.db, self.probe, on_change=self.on_change, notify=self.notify, chain=True)

    def save_only(self) -> None:
        if self._save():
            self.dialog.destroy()

    def skip(self) -> None:
        self.dialog.destroy()
        SeriesDialog(self.parent, self.db, self.probe, on_change=self.on_change, notify=self.notify, chain=True)


class SeriesDialog:
    """Масавы ўвод SERIES: першы слупок год, далей слупкі з назвамі серый."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager, probe: str, on_change: ChangeCallback | None = None,
                 notify: Notify | None = None, *, chain: bool = False) -> None:
        self.parent = parent
        self.db = db
        self.probe = probe
        self.on_change = on_change
        self.notify = notify
        self.values: list[SeriesValue] = []
        self.dialog = _modal(parent, tr("SERIES для {probe}").format(probe=probe), "1000x680")
        title = tr("Крок 3 з 3  ·  SERIES для {probe}") if chain else tr("Індывідуальныя серыі для {probe}")
        _header(self.dialog, title.format(probe=probe),
                tr("Скапіруйце з Excel табліцу разам з загалоўкам: першы слупок год, наступныя слупкі - назвы серый "
                   "(1, 1a, 13b...) з іх значэннямі. Пустыя ячэйкі прапускаюцца."))
        example = ttk.Frame(self.dialog, padding=(PAD * 2, 0))
        example.pack(fill="x")
        ttk.Label(example, text=tr("Прыклад:"), style="Hint.TLabel").pack(side="left", anchor="n")
        ttk.Label(example, text=_SERIES_EXAMPLE.replace("\t", "    "), font=app_font(fixed=True, size_delta=-1),
                  style="Hint.TLabel", justify="left").pack(side="left", padx=PAD)

        buttons, self.hint = _bottom_bar(self.dialog)
        ttk.Button(buttons, text=tr("Прапусціць SERIES") if chain else tr("Зачыніць"),
                   command=self.dialog.destroy).pack(side="left")
        ttk.Button(buttons, text=tr("Захаваць і скончыць") if chain else tr("Захаваць"), command=self.save).pack(side="right")

        toolbar = ttk.Frame(self.dialog, padding=(PAD * 2, PAD, PAD * 2, 4))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text=tr("Уставіць з буфера абмену"), command=self.paste).pack(side="left")
        ttk.Button(toolbar, text=tr("Ачысціць"), command=self.clear).pack(side="left", padx=4)
        self.status = ttk.Label(toolbar, text=tr("Значэнняў: {count}").format(count=0), style="Subtitle.TLabel")
        self.status.pack(side="left", padx=PAD)
        for sequence in ("<Control-v>", "<Command-v>"):
            self.dialog.bind(sequence, lambda _e: self.paste())

        self.tree = make_treeview(self.dialog)
        self.tree.master.pack(fill="both", expand=True, padx=PAD * 2)

    def paste(self) -> None:
        text = read_clipboard(self.dialog)
        if not text.strip():
            self.status.configure(text=tr("Буфер абмену пусты: спачатку скапіруйце табліцу з Excel."), style="Error.TLabel")
            return
        values, errors = parse_series_table(parse_clipboard_table(text))
        if values:
            self.values = values
            self._show_preview()
        if errors:
            self.status.configure(text=tr("{status}; праблемы: {errors}").format(
                status=self.status.cget("text"), errors=_errors_text(errors, 3).replace("\n", " ")), style="Warn.TLabel")

    def _show_preview(self) -> None:
        names = sorted({v.series_name for v in self.values}, key=lambda n: (len(n), n))
        years = sorted({v.year for v in self.values})
        table = {(v.year, v.series_name): v.value for v in self.values}
        set_columns(self.tree, ["year", *names], width=80, numeric={"year": 0, **{n: 3 for n in names}})
        fill_tree(self.tree, ([year] + [table.get((year, name)) for name in names] for year in years))
        self.status.configure(text=tr("Значэнняў: {values}  ·  серый: {series}  ·  гадоў: {years}").format(
            values=len(self.values), series=len(names), years=len(years)), style="Subtitle.TLabel")

    def clear(self) -> None:
        self.values = []
        set_columns(self.tree, [])
        self.status.configure(text=tr("Значэнняў: {count}").format(count=0), style="Subtitle.TLabel")

    def save(self) -> None:
        if self.values:
            try:
                written = self.db.upsert_series_values(self.probe, self.values)
            except DatabaseError as exc:
                show_error(tr("Памылка"), tr("Не атрымалася захаваць SERIES:\n{error}").format(error=exc), exc,
                           parent=self.dialog)
                return
            if self.notify:
                self.notify(tr("SERIES {probe}: захавана значэнняў: {count}").format(probe=self.probe, count=written), kind="ok")
            if self.on_change:
                self.on_change(self.probe)
        self.dialog.destroy()


class SqlQueryDialog:
    """Выкананне адвольнага SQL з паказам выніку."""

    def __init__(self, parent: tk.Misc, db: DatabaseManager, notify: Notify | None = None) -> None:
        self.db = db
        self.notify = notify
        self.dialog = _modal(parent, tr("SQL-запыт"), "1000x700")
        _header(self.dialog, tr("SQL-запыт"),
                tr("Ctrl+Enter выконвае запыт. Запыты, якія мяняюць даныя, патрабуюць пацверджання."))
        main = ttk.Frame(self.dialog, padding=(PAD * 2, 0, PAD * 2, PAD))
        main.pack(fill="both", expand=True)

        paned = ttk.PanedWindow(main, orient="vertical")
        paned.pack(fill="both", expand=True)
        editor = ttk.Frame(paned)
        paned.add(editor, weight=1)
        self.text = tk.Text(editor, wrap="none", height=8, font=app_font(fixed=True), undo=True)
        vertical = ttk.Scrollbar(editor, orient="vertical", command=self.text.yview)
        horizontal = ttk.Scrollbar(editor, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        horizontal.pack(side="bottom", fill="x")
        self.text.pack(side="left", fill="both", expand=True)
        vertical.pack(side="right", fill="y")
        self.text.insert("1.0", "SELECT n_probnoy_ploshchadi, drevesnaya_poroda, pervyy_god, posledniy_god\nFROM title\nORDER BY 1;")
        self.text.focus_set()

        results = ttk.Frame(paned)
        paned.add(results, weight=2)
        bar = ttk.Frame(results)
        bar.pack(fill="x", pady=6)
        ttk.Button(bar, text=tr("Выканаць"), command=self.execute).pack(side="left")
        ttk.Button(bar, text=tr("Уставіць з буфера"), command=self.paste).pack(side="left", padx=4)
        ttk.Button(bar, text=tr("Ачысціць"), command=lambda: self.text.delete("1.0", "end")).pack(side="left")
        self.status = ttk.Label(bar, text=tr("Гатова."), style="Subtitle.TLabel")
        self.status.pack(side="left", padx=PAD)
        ttk.Button(bar, text=tr("Капіраваць вынік"), command=self.copy_result).pack(side="right")
        self.result = make_treeview(results)
        self.result.master.pack(fill="both", expand=True)
        for sequence in ("<Control-Return>", "<Command-Return>"):
            self.dialog.bind(sequence, lambda _e: self.execute())

    def paste(self) -> None:
        self.text.insert("insert", read_clipboard(self.dialog))

    def execute(self) -> None:
        query = self.text.get("1.0", "end").strip()
        if not query:
            self.status.configure(text=tr("Увядзіце SQL-запыт."), style="Warn.TLabel")
            return
        if not query.lower().startswith(_READ_ONLY_SQL):
            if not ask_yes_no(tr("Пацверджанне"), tr("Запыт можа змяніць або выдаліць даныя. Выканаць?"), parent=self.dialog):
                return
        self.status.configure(text=tr("Выкананне запыту..."), style="Subtitle.TLabel")
        self.dialog.update_idletasks()
        try:
            result = self.db.execute_sql(query)
        except DatabaseError as exc:
            self.status.configure(text=tr("Памылка: {error}").format(error=str(exc).splitlines()[0]), style="Error.TLabel")
            show_error(tr("Памылка SQL"), str(exc), exc, parent=self.dialog)
            return
        if result.has_rows:
            set_columns(self.result, result.columns)
            fill_tree(self.result, result.rows)
            self.status.configure(text=tr("Знойдзена радкоў: {count}").format(count=result.rowcount), style="Ok.TLabel")
        else:
            set_columns(self.result, [])
            self.status.configure(text=tr("Выканана. Закранута радкоў: {count}").format(count=result.rowcount), style="Ok.TLabel")

    def copy_result(self) -> None:
        if not self.result.get_children():
            self.status.configure(text=tr("Няма даных для капіравання."), style="Warn.TLabel")
            return
        copy_to_clipboard(self.dialog, tree_to_tsv(self.result))
        self.status.configure(text=tr("Скапіравана радкоў: {count}").format(count=len(self.result.get_children())),
                              style="Ok.TLabel")


class SettingsDialog:
    """Налады інтэрфейсу: мова і тэма. Прымяняюцца кнопкай «Захаваць» праз on_apply."""

    THEME_LABELS = (("system", "Як у сістэме"), ("light", "Светлая"), ("dark", "Цёмная"))

    def __init__(self, parent: tk.Misc, preferences: Preferences, on_apply: Callable[[Preferences], bool]) -> None:
        self.on_apply = on_apply
        self.language = tk.StringVar(value=preferences.language)
        self.theme = tk.StringVar(value=preferences.theme)
        self.dialog = _modal(parent, tr("Налады"), "520x420", (440, 360))
        _header(self.dialog, tr("Налады"), tr("Мова і тэма прымяняюцца адразу і захоўваюцца паміж запускамі."))

        buttons, self.hint = _bottom_bar(self.dialog)
        ttk.Button(buttons, text=tr("Захаваць"), command=self.save).pack(side="right")
        ttk.Button(buttons, text=tr("Адмена"), command=self.dialog.destroy).pack(side="right", padx=4)

        body = ttk.Frame(self.dialog, padding=(PAD * 2, PAD, PAD * 2, 0))
        body.pack(fill="both", expand=True)
        languages = ttk.LabelFrame(body, text=tr("Мова інтэрфейсу"), style="Section.TLabelframe", padding=(PAD, 2, PAD, PAD))
        languages.pack(fill="x")
        for code, name in LANGUAGE_NAMES.items():
            ttk.Radiobutton(languages, text=name, value=code, variable=self.language).pack(anchor="w", pady=2)
        themes = ttk.LabelFrame(body, text=tr("Тэма"), style="Section.TLabelframe", padding=(PAD, 2, PAD, PAD))
        themes.pack(fill="x", pady=(PAD, 0))
        for code, label in self.THEME_LABELS:
            if code in THEMES:
                ttk.Radiobutton(themes, text=tr(label), value=code, variable=self.theme).pack(anchor="w", pady=2)
        ttk.Label(body, text=tr("Адкрытыя вокны CRN, SERIES і SQL застаюцца на ранейшай мове да закрыцця."),
                  style="Hint.TLabel", wraplength=460, justify="left").pack(anchor="w", pady=(PAD, 0))
        self.dialog.bind("<Return>", lambda _e: self.save())

    def values(self) -> Preferences:
        return Preferences(language=self.language.get(), theme=self.theme.get()).normalized()

    def save(self) -> None:
        if self.on_apply(self.values()):
            self.dialog.destroy()
