"""Акно «Імпарт даных з Excel»: тое ж, што каманда python -m dendrobase.excel_import, толькі з інтэрфейсу.

Імпарт выконваецца ў асобным патоку з уласным злучэннем з БД (гл. excel_import.run), таму галоўнае
акно не замірае. Паток не чапае Tk: падзеі ходу працы (ImportProgress) кладуцца ў чаргу, а акно
забірае іх па таймеры і дапісвае ў журнал радок за радком. Пасля завяршэння (і пасля памылкі, бо
частка файлаў магла быць імпартавана) выклікаецца on_change, каб галоўнае акно перачытала базу.
"""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Callable

from ..config import Settings
from ..i18n import tr
from .dialogs import _bottom_bar, _header, _modal
from .feedback import ask_yes_no
from .theme import PAD, PALETTE, app_font
from .widgets import add_tooltip

if TYPE_CHECKING:  # excel_import цягне pandas, таму падчас працы імпартуецца толькі па націску кнопкі
    from ..excel_import import ImportProgress, ImportStats

log = logging.getLogger("dendrobase.ui")
Notify = Callable[..., None]
Runner = Callable[..., "ImportStats"]  # excel_import.run або яго дубль у тэстах
POLL_MS = 100
_TAG_COLORS = {"ok": "ok", "warn": "warn", "error": "danger", "muted": "muted"}


class ImportDialog:
    """Папка, опцыі, кнопка «Пачаць імпарт», індыкатар і журнал ходу працы."""

    def __init__(self, parent: tk.Misc, settings: Settings, on_change: Callable[[], None] | None = None,
                 notify: Notify | None = None, *, runner: Runner | None = None) -> None:
        self.settings = settings
        self.on_change = on_change
        self.notify = notify
        self.runner = runner
        self.running = False
        self.stats: ImportStats | None = None
        self.error: BaseException | None = None
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._poll_id: str | None = None
        self._close_when_finished = False

        self.dialog = _modal(parent, tr("Імпарт даных з Excel"), "1000x700", (760, 480))
        self.dialog.protocol("WM_DELETE_WINDOW", self.close)
        self.dialog.bind("<Escape>", lambda _e: self.close())
        self.dialog.bind("<Destroy>", self._on_destroy, add="+")
        _header(self.dialog, tr("Імпарт даных з Excel"),
                tr("Адзін файл .xlsx = адна пробная плошча (назва файла = код ПП), унутры лісты title, crn і series. "
                   "Нязменныя файлы, апрацаваныя раней, прапускаюцца па стане імпарту ў папцы."))

        buttons, self.hint = _bottom_bar(self.dialog)
        self.start_button = ttk.Button(buttons, text=tr("Пачаць імпарт"), command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(buttons, text=tr("Спыніць"), command=self.cancel)
        self.stop_button.pack(side="left", padx=4)
        add_tooltip(self.stop_button, tr("Імпарт спыніцца пасля бягучага файла; зробленае застаецца ў базе."))
        self.close_button = ttk.Button(buttons, text=tr("Зачыніць"), command=self.close)
        self.close_button.pack(side="right")

        body = ttk.Frame(self.dialog, padding=(PAD * 2, 0, PAD * 2, 0))
        body.pack(fill="both", expand=True)

        folder_row = ttk.Frame(body)
        folder_row.pack(fill="x")
        ttk.Label(folder_row, text=tr("Папка з Excel-файламі:")).pack(side="left")
        self.folder_var = tk.StringVar(value=str(settings.excel_folder) if settings.excel_folder else "")
        self.folder_entry = ttk.Entry(folder_row, textvariable=self.folder_var)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(6, 4))
        add_tooltip(self.folder_entry, tr("Па змаўчанні DENDROBASE_EXCEL_FOLDER з .env."))
        self.browse_button = ttk.Button(folder_row, text=tr("Выбраць…"), command=self.choose_folder)
        self.browse_button.pack(side="left")

        options = ttk.Frame(body)
        options.pack(fill="x", pady=(6, 0))
        self.overwrite_var = tk.BooleanVar(value=False)
        self.reimport_var = tk.BooleanVar(value=False)
        self.journal_var = tk.BooleanVar(value=True)
        self.geometry_var = tk.BooleanVar(value=True)
        self.option_checks: list[ttk.Checkbutton] = []
        checks = (
            (self.overwrite_var, tr("Перапісваць існуючыя радкі CRN і SERIES"),
             tr("Без гэтага гады, якія ўжо ёсць у базе, не чапаюцца: дадаюцца толькі новыя.")),
            (self.reimport_var, tr("Апрацаваць усе файлы нанова"),
             tr("Не зважаць на стан імпарту ў папцы (dendrobase_import_state.json).")),
            (self.journal_var, tr("Запоўніць № журнала з dendro_point_living.xlsx"),
             tr("Файл шукаецца ў той жа папцы; без яго этап прапускаецца.")),
            (self.geometry_var, tr("Разлічыць геаметрыю ПП (PostGIS)"),
             tr("Толькі для ПП без geom. Без PostGIS этап прапускаецца.")),
        )
        for index, (variable, label, hint) in enumerate(checks):
            check = ttk.Checkbutton(options, text=label, variable=variable)
            check.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, PAD * 2), pady=2)
            add_tooltip(check, hint)
            self.option_checks.append(check)

        progress_row = ttk.Frame(body)
        progress_row.pack(fill="x", pady=(PAD, 4))
        self.progress = ttk.Progressbar(progress_row, orient="horizontal", mode="determinate", maximum=1, value=0)
        self.progress.pack(side="left", fill="x", expand=True)
        self.counter = ttk.Label(progress_row, text="", style="Subtitle.TLabel", width=14, anchor="e")
        self.counter.pack(side="left", padx=(PAD, 0))
        self.status = ttk.Label(body, text=tr("Гатова да імпарту."), style="Subtitle.TLabel", wraplength=900,
                                justify="left")
        self.status.pack(fill="x")
        # зводка доўгая: пераносіцца па бягучай шырыні акна, а не абразаецца
        self.status.bind("<Configure>", lambda e: self.status.configure(wraplength=max(e.width - 4, 200)), add="+")

        log_frame = ttk.Frame(body)
        log_frame.pack(fill="both", expand=True, pady=(4, PAD))
        self.log = tk.Text(log_frame, wrap="word", height=12, font=app_font(fixed=True, size_delta=-1),
                           state="disabled")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for tag, color in _TAG_COLORS.items():
            self.log.tag_configure(tag, foreground=PALETTE[color])
        self._set_running(False)

    # ------------------------------------------------------------------ кіраванне
    def choose_folder(self) -> None:
        current = self.folder_var.get().strip()
        initial = current if current and Path(current).expanduser().is_dir() else str(Path.home())
        chosen = filedialog.askdirectory(title=tr("Папка з Excel-файламі"), initialdir=initial, parent=self.dialog)
        if chosen:
            self.folder_var.set(chosen)

    def options(self) -> dict[str, bool]:
        """Опцыі для excel_import.run у тым выглядзе, у якім іх прымае каманда."""
        return {"overwrite": self.overwrite_var.get(), "reimport": self.reimport_var.get(),
                "journal": self.journal_var.get(), "geometry": self.geometry_var.get()}

    def start(self) -> None:
        if self.running:
            return
        text = self.folder_var.get().strip()
        folder = Path(text).expanduser()
        if not text:
            self._set_status(tr("Задайце папку з Excel-файламі."), "Error.TLabel")
            self.folder_entry.focus_set()
            return
        if not folder.is_dir():
            self._set_status(tr("Папка не існуе: {folder}").format(folder=folder), "Error.TLabel")
            self.folder_entry.focus_set()
            return
        runner = self.runner
        if runner is None:
            from ..excel_import import run  # pandas грузіцца толькі тут, а не пры старце праграмы
            runner = run
        options = self.options()
        self.stats, self.error = None, None
        self._clear_log()
        self.progress.configure(maximum=1, value=0)
        self.counter.configure(text="")
        self._stop.clear()
        self._queue = queue.Queue()
        self._set_running(True)
        self._set_status(tr("Імпарт ідзе…"), "Subtitle.TLabel")
        self._append(tr("Папка: {folder}").format(folder=folder), "muted")
        log.info("Імпарт з Excel з інтэрфейсу: %s, опцыі %s", folder, options)
        self._thread = threading.Thread(target=self._work, args=(runner, folder, options), daemon=True,
                                        name="dendrobase-import")
        self._thread.start()
        self._schedule_poll()

    def cancel(self) -> None:
        """Папрасіць паток спыніцца: бягучы файл дапрацоўваецца, наступныя не чапаюцца."""
        if not self.running or self._stop.is_set():
            return
        self._stop.set()
        self.stop_button.state(["disabled"])
        self._set_status(tr("Спыняецца пасля бягучага файла…"), "Warn.TLabel")

    def close(self) -> None:
        if self.running:
            if not ask_yes_no(tr("Імпарт ідзе"), tr("Імпарт яшчэ не завершаны. Спыніць яго і зачыніць акно?"),
                              parent=self.dialog):
                return
            self._close_when_finished = True
            self.cancel()
            return
        self.dialog.destroy()

    def log_text(self) -> str:
        return self.log.get("1.0", "end-1c")

    # --------------------------------------------------------------------- паток
    def _work(self, runner: Runner, folder: Path, options: dict[str, bool]) -> None:
        """Цела фонавага патоку: ніякіх зваротаў да Tk, толькі чарга."""
        try:
            stats = runner(self.settings, folder, progress=lambda event: self._queue.put(("progress", event)),
                           should_stop=self._stop.is_set, **options)
        except Exception as exc:  # noqa: BLE001 - любая памылка патоку павінна дайсці да акна, а не згубіцца
            log.error("Імпарт з Excel спынены памылкай", exc_info=exc)
            self._queue.put(("error", exc))
        else:
            self._queue.put(("done", stats))

    def _schedule_poll(self) -> None:
        self._poll_id = self.dialog.after(POLL_MS, self._poll)

    def _poll(self) -> None:
        self._poll_id = None
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "progress":
                    self._show_progress(payload)
                elif kind == "done":
                    self._finish(payload)
                else:
                    self._fail(payload)
        except queue.Empty:
            pass
        if self.running and self.dialog.winfo_exists():
            self._schedule_poll()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is not self.dialog:
            return
        self._stop.set()  # акно знішчана (напрыклад, выхад з праграмы): паток спыняецца пасля бягучага файла
        if self._poll_id is not None:
            try:
                self.dialog.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None

    # ------------------------------------------------------------- адлюстраванне
    def _show_progress(self, event: ImportProgress) -> None:
        if event.stage == "scan":
            self.progress.configure(maximum=max(event.total, 1), value=0)
            self.counter.configure(text=tr("{done} з {total}").format(done=0, total=event.total))
            self._append(tr("Знойдзена Excel-файлаў: {count}").format(count=event.total), "muted")
        elif event.stage in ("file", "unchanged"):
            self.progress.configure(value=event.done)
            self.counter.configure(text=tr("{done} з {total}").format(done=event.done, total=event.total))
            if event.result is None:
                self._append(tr("{file}: без змен, прапушчаны").format(file=event.file), "muted")
                return
            result = event.result
            if result.status == "error":
                self._append(f"{event.file}: {result.error}", "error")
            elif result.status == "skipped":
                self._append(tr("{file}: прапушчаны").format(file=event.file), "warn")
            else:
                self._append(tr("{file} → ПП {probe}: CRN {crn} радкоў, SERIES {series} значэнняў").format(
                    file=event.file, probe=result.probe, crn=result.crn_rows, series=result.series_rows))
            for warning in result.warnings:
                self._append(f"    ⚠ {warning}", "warn")
        elif event.stage == "journal":
            if event.count is None:
                self._append(tr("Файла dendro_point_living.xlsx няма, № журнала не абнаўляецца."), "muted")
            else:
                self._append(tr("№ журнала абноўлены для {count} ПП.").format(count=event.count))
        elif event.stage == "geometry":
            if event.count is None:
                self._append(tr("PostGIS не ўсталяваны або няма слупка geom: геаметрыя не абноўлена."), "warn")
            else:
                self._append(tr("Геаметрыя разлічана для {count} ПП.").format(count=event.count))
        elif event.stage == "geobotany":
            self._append(tr("Геабатанічныя палі запоўнены для {count} ПП.").format(count=event.count))

    def _finish(self, stats: ImportStats) -> None:
        self.stats = stats
        self._set_running(False)
        summary = stats.summary()
        if stats.cancelled:
            text, style, kind = tr("Імпарт спынены. {summary}").format(summary=summary), "Warn.TLabel", "warn"
        elif stats.errors:
            text, style, kind = (tr("Імпарт завершаны з памылкамі. {summary}").format(summary=summary),
                                 "Warn.TLabel", "warn")
        else:
            text, style, kind = tr("Імпарт завершаны. {summary}").format(summary=summary), "Ok.TLabel", "ok"
        self._set_status(text, style)
        self._append(text, kind)
        self._after_run(text, kind)

    def _fail(self, exc: BaseException) -> None:
        self.error = exc
        self._set_running(False)
        text = tr("Імпарт спынены памылкай: {error}").format(error=exc)
        self._set_status(text, "Error.TLabel")
        self._append(text, "error")
        self._after_run(text, "error")

    def _after_run(self, text: str, kind: str) -> None:
        """Галоўнае акно перачытвае базу (нешта магло быць імпартавана і да памылкі) і атрымлівае паведамленне."""
        if self.on_change:
            self.on_change()
        if self.notify:
            self.notify(text, kind=kind)
        if self._close_when_finished and self.dialog.winfo_exists():
            self.dialog.destroy()

    def _set_running(self, running: bool) -> None:
        self.running = running
        state = ["disabled"] if running else ["!disabled"]
        for widget in (self.start_button, self.browse_button, self.folder_entry, *self.option_checks):
            widget.state(state)
        self.stop_button.state(["!disabled"] if running else ["disabled"])

    def _set_status(self, text: str, style: str) -> None:
        self.status.configure(text=text, style=style)

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append(self, text: str, tag: str | None = None) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", (tag,) if tag else ())
        self.log.see("end")
        self.log.configure(state="disabled")
