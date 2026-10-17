"""Мовы інтэрфейсу.

Зыходныя радкі ў кодзе напісаны па-беларуску і абгорнуты ў tr(). Для беларускай мовы tr()
вяртае радок як ёсць, для іншых шукае пераклад у каталогу; калі перакладу няма, застаецца
беларускі тэкст. Радкі з падстаноўкамі перакладаюцца да .format(): tr("ПП {probe}").format(probe=...).

Мова выбіраецца карыстальнікам у наладах (гл. ui.preferences) і ставіцца праз set_language()
да пабудовы вокнаў. Па змаўчанні англійская.
"""
from __future__ import annotations

DEFAULT_LANGUAGE = "en"
# Назвы моў паказваюцца ў наладах на самой мове і не перакладаюцца.
LANGUAGE_NAMES: dict[str, str] = {"be": "Беларуская", "en": "English"}

_current = DEFAULT_LANGUAGE


def available_languages() -> tuple[str, ...]:
    return tuple(LANGUAGE_NAMES)


def normalize_language(value: object) -> str:
    """Код мовы з налад або асяроддзя: "be", "be-BY", "EN_us" → "be" / "en"; невядомае → па змаўчанні."""
    code = str(value or "").strip().lower().replace("_", "-").split("-")[0]
    return code if code in LANGUAGE_NAMES else DEFAULT_LANGUAGE


def set_language(code: object) -> str:
    """Зрабіць мову бягучай. Вяртае фактычна выбраны код."""
    global _current
    _current = normalize_language(code)
    return _current


def get_language() -> str:
    return _current


def tr(text: str) -> str:
    """Пераклад беларускага радка на бягучую мову. Без перакладу вяртаецца зыходны тэкст."""
    if _current == "be" or not text:
        return text
    catalog = _CATALOGS.get(_current)
    if not catalog:
        return text
    return catalog.get(text, text)


# ---------------------------------------------------------------------------------------- каталогі
# Ключ: беларускі радок з кода, значэнне: пераклад. Паўната каталога правяраецца тэстам tests/test_i18n.py.
_EN: dict[str, str] = {
    # --- агульнае
    "Памылка": "Error",
    "Пацверджанне": "Confirm",
    "Захаваць": "Save",
    "Адмена": "Cancel",
    "Зачыніць": "Close",
    "Ачысціць": "Clear",
    "Прымяніць": "Apply",
    "Усе гады": "All years",
    "Гады з": "Years from",
    "па": "to",
    "Экспарт…": "Export…",
    "Капіраваць": "Copy",
    "Абнавіць спіс": "Refresh list",
    "Адкрыць мапу ў браўзеры": "Open map in browser",
    "Няма даных для капіравання.": "No data to copy.",
    "Няма даных для экспарту.": "No data to export.",
    "Не атрымалася захаваць файл:\n{error}": "Could not save the file:\n{error}",
    "Спачатку выберыце пробную плошчу.": "Select a sample plot first.",
    "Код": "Code",
    "Парода": "Species",
    "Гады": "Years",
    "Усе файлы": "All files",
    "CSV (коска)": "CSV (comma)",
    "Тэкст з табуляцыямі": "Tab-separated text",
    "Няма даных для графіка": "No data for the chart",
    # --- запуск (__main__, runtime, config, feedback)
    "Памылка налад": "Configuration error",
    "Несумяшчальная версія Tk": "Incompatible Tk version",
    " або ": " or ",
    "Няма злучэння з базай даных": "No database connection",
    "{error}\n\nПраверце, што сервер PostgreSQL запушчаны, і налады ў файле {env}.":
        "{error}\n\nCheck that the PostgreSQL server is running and the settings in {env}.",
    "Памылка базы даных": "Database error",
    "У базе няма табліц": "Tables missing in the database",
    "У базе {db} няма табліц: {tables}.\n\nВыканайце schema.sql (гл. README, раздзел «Стварэнне табліц»).":
        "The database {db} has no tables: {tables}.\n\nRun schema.sql (see README, section “Creating tables”).",
    "Гэты Python выкарыстоўвае Tk {version}. На macOS патрэбны Tk {minimum} або навейшы: "
    "стары Tk губляе клікі па кнопках, спісах і іншых элементах інтэрфейсу.\n\n"
    "Інтэрпрэтатар: {executable}\n\n"
    "Запусціце праграму праз .venv/bin/python -m dendrobase, калі асяроддзе з новым Tk "
    "ужо створана. Інакш усталюйце Python з новым Tk і стварыце віртуальнае асяроддзе нанова "
    "(README → «Кнопкі не рэагуюць на клік»). Абнаўленне pip-пакетаў не абнаўляе Tk.":
        "This Python uses Tk {version}. On macOS Tk {minimum} or newer is required: "
        "older Tk loses clicks on buttons, lists and other interface elements.\n\n"
        "Interpreter: {executable}\n\n"
        "Run the program with .venv/bin/python -m dendrobase if an environment with a newer Tk "
        "already exists. Otherwise install a Python with a newer Tk and recreate the virtual environment "
        "(README → “Buttons do not respond to clicks”). Upgrading pip packages does not upgrade Tk.",
    "{name} павінен быць лікам, атрымана: {value}": "{name} must be a number, got: {value}",
    "{name} па-за дыяпазонам 1..65535: {value}": "{name} is out of the range 1..65535: {value}",
    "{name} павінен быць адным з {choices}, атрымана: {value}": "{name} must be one of {choices}, got: {value}",
    "Нечаканая памылка": "Unexpected error",
    "{error}\n\nПадрабязнасці запісаны ў файл логаў.": "{error}\n\nDetails were written to the log file.",
    # --- db
    "Не атрымалася падключыцца да {target}:\n{error}": "Could not connect to {target}:\n{error}",
    "Злучэнне з базай даных страчана:\n{error}": "The database connection was lost:\n{error}",
    "Код пробнай плошчы ({column}) абавязковы": "The plot code ({column}) is required",
    "У табліцы title няма слупкоў: {columns}": "The title table has no columns: {columns}",
    "PostGIS не ўсталяваны. Выканайце ў базе: CREATE EXTENSION postgis;":
        "PostGIS is not installed. Run in the database: CREATE EXTENSION postgis;",
    "У табліцы title няма слупка geom. Выканайце блок PostGIS з schema.sql.":
        "The title table has no geom column. Run the PostGIS block of schema.sql.",
    # --- parsing
    "не лік: {value}": "not a number: {value}",
    "не цэлы лік: {value}": "not an integer: {value}",
    "не дата: {value}": "not a date: {value}",
    "няма года": "no year",
    "радок {number}: {error}": "row {number}: {error}",
    "патрэбны радок загалоўка з назвамі серый і хаця б адзін радок даных":
        "a header row with series names and at least one data row are required",
    "у загалоўку няма назваў серый": "the header has no series names",
    "назвы серый паўтараюцца: {names}": "duplicate series names: {names}",
    "радок {number}: год {value} не лік": "row {number}: year {value} is not a number",
    "радок {number}, серыя {name}: {value} не лік": "row {number}, series {name}: {value} is not a number",
    # --- maps
    "Парода: {species}": "Species: {species}",
    "Гады: {years}": "Years: {years}",
    "н/д": "n/a",
    # --- галоўнае акно: меню
    "Файл": "File",
    "Новая пробная плошча…": "New sample plot…",
    "Выйсці": "Quit",
    "Праўка": "Edit",
    "Захаваць змены ПП": "Save plot changes",
    "Дадаць CRN да выбранай ПП…": "Add CRN to selected plot…",
    "Дадаць SERIES да выбранай ПП…": "Add SERIES to selected plot…",
    "Абнавіць геаметрыю выбранай ПП": "Update geometry of selected plot",
    "Абнавіць геаметрыю ўсіх ПП": "Update geometry of all plots",
    "Інструменты": "Tools",
    "SQL-запыт…": "SQL query…",
    "Налады…": "Settings…",
    "Даведка": "Help",
    "Расшыфроўка пародаў": "Species abbreviations",
    "Гарачыя клавішы": "Keyboard shortcuts",
    "Дзе файл логаў": "Log file location",
    "Аб праграме": "About",
    # --- галоўнае акно: макет і паведамленні
    "Пробныя плошчы": "Sample plots",
    "Пошук па коду ПП…": "Search by plot code…",
    "Ctrl+F ставіць курсор сюды, Esc ачышчае.": "Ctrl+F moves the cursor here, Esc clears it.",
    "+  Новая пробная плошча": "+  New sample plot",
    "Ctrl+N. Майстар у тры крокі: анкета ПП, CRN, SERIES.": "Ctrl+N. Three-step wizard: plot form, CRN, SERIES.",
    "Дадаць CRN да выбранай…": "Add CRN to selected…",
    "Дадаць SERIES да выбранай…": "Add SERIES to selected…",
    "Інфармацыя аб ПП": "Plot info",
    "CRN храналогія": "CRN chronology",
    "Фільтры і пошук": "Filters and search",
    "Мапа": "Map",
    "Не атрымалася прачытаць спіс ПП:\n{error}": "Could not read the plot list:\n{error}",
    "{count} знойдзена": "{count} found",
    "Спачатку выберыце пробную плошчу са спіса.": "Select a sample plot from the list first.",
    "Для ПП {probe} не зададзены каардынаты: спачатку ўвядзіце шырату і даўгату.":
        "Plot {probe} has no coordinates: enter latitude and longitude first.",
    "Геаметрыя для {probe} абноўлена.": "Geometry for {probe} updated.",
    "Геаметрыя не абноўлена: праверце, што каардынаты не нулявыя.":
        "Geometry not updated: check that the coordinates are not zero.",
    "Няма ПП з каардынатамі для абнаўлення.": "No plots with coordinates to update.",
    "Будзе абноўлена геаметрыя для {count} ПП. Працягнуць?": "Geometry will be updated for {count} plots. Continue?",
    "Геаметрыя абноўлена для {count} ПП.": "Geometry updated for {count} plots.",
    "Ctrl+N   новая пробная плошча\n"
    "Ctrl+F   пошук у спісе ПП\n"
    "Ctrl+S   захаваць змены на ўкладцы «Інфармацыя аб ПП»\n"
    "F5       абнавіць спіс\n"
    "Enter    прымяніць фільтр па гадах / запусціць пошук\n"
    "Ctrl+V   уставіць табліцу ў вокнах CRN і SERIES\n"
    "Ctrl+Enter   выканаць SQL-запыт\n"
    "Ctrl+,   налады\n"
    "Ctrl+Q   выйсці\n\n"
    "На macOS замест Ctrl працуе Cmd.":
        "Ctrl+N   new sample plot\n"
        "Ctrl+F   search the plot list\n"
        "Ctrl+S   save changes on the “Plot info” tab\n"
        "F5       refresh the list\n"
        "Enter    apply the year filter / run the search\n"
        "Ctrl+V   paste a table in the CRN and SERIES windows\n"
        "Ctrl+Enter   run the SQL query\n"
        "Ctrl+,   settings\n"
        "Ctrl+Q   quit\n\n"
        "On macOS use Cmd instead of Ctrl.",
    "Файл логаў": "Log file",
    "Файл логаў не ствараўся, логі ідуць толькі ў кансоль.": "No log file was created; logs go to the console only.",
    "DendroBASE {version}\n\n"
    "База дэндрахраналагічных даных Беларусі: пробныя плошчы, храналогіі CRN "
    "і індывідуальныя серыі ў PostgreSQL/PostGIS.\n\n"
    "Падключэнне: {connection}":
        "DendroBASE {version}\n\n"
        "Dendrochronological database of Belarus: sample plots, CRN chronologies "
        "and individual series in PostgreSQL/PostGIS.\n\n"
        "Connection: {connection}",
    "Налады захаваны.": "Settings saved.",
    # --- налады
    "Налады": "Settings",
    "Мова і тэма прымяняюцца адразу і захоўваюцца паміж запускамі.":
        "Language and theme apply immediately and are kept between sessions.",
    "Мова інтэрфейсу": "Interface language",
    "Тэма": "Theme",
    "Як у сістэме": "Follow system",
    "Светлая": "Light",
    "Цёмная": "Dark",
    "Адкрытыя вокны CRN, SERIES і SQL застаюцца на ранейшай мове да закрыцця.":
        "Open CRN, SERIES and SQL windows keep the previous language until closed.",
    # --- радок стану
    "ПП: {probe}": "Plot: {probe}",
    "PostGIS: ёсць": "PostGIS: yes",
    "PostGIS: няма": "PostGIS: no",
    # --- укладка «Інфармацыя аб ПП»
    "{count} дрэў": "{count} trees",
    "без каардынат": "no coordinates",
    "Іншыя слупкі": "Other columns",
    "Пробная плошча не выбрана": "No sample plot selected",
    "●  Незахаваныя змены": "●  Unsaved changes",
    "Выберыце ПП у спісе злева або стварыце новую (Ctrl+N).":
        "Select a plot in the list on the left or create a new one (Ctrl+N).",
    "Захаваць змены": "Save changes",
    "Ctrl+S. Захоўваюцца толькі змененыя палі.": "Ctrl+S. Only changed fields are saved.",
    "Адкаціць": "Revert",
    "Вярнуць значэнні з базы, адмяніўшы незахаваныя змены.": "Reload values from the database, discarding unsaved changes.",
    "Толькі запоўненыя палі": "Filled fields only",
    "Схаваць пустыя палі, каб бачыць толькі тое, што вядома пра ПП.": "Hide empty fields to see only what is known about the plot.",
    "Незахаваныя змены": "Unsaved changes",
    "Захаваць змены ў ПП {probe}?": "Save changes to plot {probe}?",
    "Не атрымалася прачытаць ПП {probe}:\n{error}": "Could not read plot {probe}:\n{error}",
    "Нельга захаваць, праверце палі: {errors}": "Cannot save, check the fields: {errors}",
    "Няма змен для захавання.": "No changes to save.",
    "Памылка захавання": "Save error",
    "Не атрымалася захаваць змены:\n{error}": "Could not save changes:\n{error}",
    "ПП {probe}: захавана палёў: {count} ({labels})": "Plot {probe}: fields saved: {count} ({labels})",
    # --- укладка CRN
    "Абагульненая храналогія": "Master chronology",
    "Enter у полі года таксама прымяняе фільтр.": "Enter in a year field also applies the filter.",
    "На графіку:": "On chart:",
    "Захаваць табліцу ў CSV або тэкставы файл.": "Save the table to a CSV or text file.",
    "Скапіраваць табліцу ў буфер абмену для ўстаўкі ў Excel.": "Copy the table to the clipboard for pasting into Excel.",
    "Дадаць або змяніць радок": "Add or edit a row",
    "Захаваць радок": "Save row",
    "Выдаліць выбраны": "Delete selected",
    "Клік па радку табліцы запаўняе форму. Год з існуючым запісам абнаўляе яго.":
        "Clicking a table row fills the form. A year that already exists updates that record.",
    "Гады фільтра павінны быць цэлымі лікамі.": "Filter years must be integers.",
    "Не атрымалася прачытаць CRN:\n{error}": "Could not read CRN:\n{error}",
    "Няма радкоў CRN для гэтай ПП.": "No CRN rows for this plot.",
    "{count} гадоў": "{count} years",
    "сярэдняе raw {mean}": "mean raw {mean}",
    "CRN: скапіравана радкоў: {count}": "CRN: rows copied: {count}",
    "Экспарт CRN": "Export CRN",
    "CRN: захавана радкоў: {count} у {path}": "CRN: rows saved: {count} to {path}",
    "Увядзіце год.": "Enter a year.",
    "Некарэктнае значэнне: {error}": "Invalid value: {error}",
    "Не атрымалася захаваць запіс:\n{error}": "Could not save the record:\n{error}",
    "CRN {probe}: запіс за {year} год захаваны.": "CRN {probe}: record for {year} saved.",
    "Выберыце радок у табліцы.": "Select a row in the table.",
    "Выдаліць запіс CRN за {year} год?": "Delete the CRN record for {year}?",
    "Не атрымалася выдаліць запіс:\n{error}": "Could not delete the record:\n{error}",
    "CRN {probe}: запіс за {year} год выдалены.": "CRN {probe}: record for {year} deleted.",
    # --- укладка SERIES
    "Індывідуальныя серыі": "Individual series",
    "Вылучыць серыю:": "Highlight series:",
    "Вылучаная серыя малюецца тоўстай чырвонай лініяй, астатнія шэрыя.":
        "The highlighted series is drawn as a thick red line, the rest in grey.",
    "Не атрымалася прачытаць SERIES:\n{error}": "Could not read SERIES:\n{error}",
    "Няма даных": "No data",
    "{years} гадоў  ·  {series} серый  ·  {first}–{last}": "{years} years  ·  {series} series  ·  {first}–{last}",
    "SERIES: скапіравана радкоў: {count}": "SERIES: rows copied: {count}",
    "Экспарт SERIES": "Export SERIES",
    "SERIES: захавана радкоў: {count} у {path}": "SERIES: rows saved: {count} to {path}",
    # --- укладка «Фільтры і пошук»
    "Умовы выбаркі": "Query conditions",
    "Пустое поле не абмяжоўвае выбарку. Enter запускае пошук.": "An empty field does not restrict the query. Enter runs the search.",
    "Парода і раянаванне": "Species and zoning",
    "Дрэвавая парода:": "Tree species:",
    "Геабатанічная зона:": "Geobotanical zone:",
    "Падзона:": "Subzone:",
    "Акруга:": "District:",
    "Раён:": "Region:",
    "Тып лесу змяшчае:": "Forest type contains:",
    "Пошук па частцы назвы без уліку рэгістру, напрыклад «мш».": "Case-insensitive search by part of the name, e.g. “мш”.",
    "Гады і від храналогіі": "Years and chronology type",
    "Слупкі CRN:": "CRN columns:",
    "Знайсці": "Search",
    "Скінуць": "Reset",
    "Вынікі": "Results",
    "Задайце ўмовы і націсніце «Знайсці».": "Set the conditions and press “Search”.",
    "Гады павінны быць цэлымі лікамі.": "Years must be integers.",
    "Выкананне запыту...": "Running the query…",
    "Памылка запыту": "Query error",
    "Не атрымалася выканаць пошук:\n{error}": "The search failed:\n{error}",
    "Знойдзена радкоў: {rows}  ·  ПП: {probes}": "Rows found: {rows}  ·  plots: {probes}",
    "Фільтры: скапіравана радкоў: {count}": "Filters: rows copied: {count}",
    "Экспарт выбаркі": "Export results",
    "Выбарка: захавана радкоў: {count} у {path}": "Results: rows saved: {count} to {path}",
    # --- укладка «Мапа»
    "Мапа храналогій": "Chronology map",
    "Інтэрактыўная мапа (падкладка OpenTopoMap на даных OpenStreetMap) з маркерамі ўсіх ПП, якія маюць каардынаты.":
        "Interactive map (OpenTopoMap tiles based on OpenStreetMap data) with markers for every plot that has coordinates.",
    "Захаваць як HTML…": "Save as HTML…",
    "Ніжэй толькі ПП з каардынатамі. Падвойны клік адкрывае ПП. "
    "Каардынаты ўводзяцца на ўкладцы «Інфармацыя аб ПП» у дзесятковых градусах.":
        "Only plots with coordinates are listed below. Double-click opens the plot. "
        "Coordinates are entered on the “Plot info” tab in decimal degrees.",
    "Шырата": "Latitude",
    "Даўгата": "Longitude",
    "Не атрымалася прачытаць каардынаты:\n{error}": "Could not read coordinates:\n{error}",
    "ПП з каардынатамі: {with_coords} з {total}": "Plots with coordinates: {with_coords} of {total}",
    "Няма пробных плошчаў з каардынатамі.": "No sample plots with coordinates.",
    "Не атрымалася стварыць мапу:\n{error}": "Could not create the map:\n{error}",
    "Мапа з {count} ПП адкрыта ў браўзеры.": "Map with {count} plots opened in the browser.",
    "Мапа захавана": "Map saved",
    "Браўзер не адкрыўся. Адкрыйце файл уручную:\n{path}": "The browser did not open. Open the file manually:\n{path}",
    "Захаваць мапу": "Save map",
    "Не атрымалася захаваць мапу:\n{error}": "Could not save the map:\n{error}",
    "Мапа з {count} ПП захавана: {path}": "Map with {count} plots saved: {path}",
    # --- дыялогі
    "... і яшчэ {count}": "… and {count} more",
    "Даведка: расшыфроўка пародаў": "Reference: species abbreviations",
    "Скарачэнні парод дрэў": "Tree species abbreviations",
    "Пачніце набіраць скарачэнне або назву, спіс адфільтруецца.": "Start typing an abbreviation or a name to filter the list.",
    "Скарачэнне": "Abbreviation",
    "Поўная назва": "Full name",
    "Новая пробная плошча": "New sample plot",
    "Крок 1 з 3  ·  Новая пробная плошча": "Step 1 of 3  ·  New sample plot",
    "Палі з * абавязковыя. Пасля захавання можна адразу ўставіць CRN і SERIES з буфера абмену.":
        "Fields marked * are required. After saving you can paste CRN and SERIES from the clipboard right away.",
    "Захаваць і перайсці да CRN  →": "Save and continue to CRN  →",
    "Поле «{label}» абавязковае.": "The field “{label}” is required.",
    "Праверце палі: {errors}": "Check the fields: {errors}",
    "Не атрымалася захаваць ПП:\n{error}": "Could not save the plot:\n{error}",
    "ПП {probe} створана.": "Plot {probe} created.",
    "CRN для {probe}": "CRN for {probe}",
    "Крок 2 з 3  ·  CRN для {probe}": "Step 2 of 3  ·  CRN for {probe}",
    "Абагульненая храналогія CRN для {probe}": "CRN master chronology for {probe}",
    "Вылучыце ў Excel слупкі year, num, raw, std, res, ars (загаловак неабавязковы, парадак па назвах), "
    "скапіруйце і націсніце «Уставіць з буфера абмену». Дзесятковая коска прымаецца.":
        "In Excel select the columns year, num, raw, std, res, ars (header optional, order by names), "
        "copy them and press “Paste from clipboard”. A decimal comma is accepted.",
    "Прыклад:": "Example:",
    "Прапусціць CRN": "Skip CRN",
    "Захаваць і перайсці да SERIES  →": "Save and continue to SERIES  →",
    "Захаваць і скончыць": "Save and finish",
    "Уставіць з буфера абмену": "Paste from clipboard",
    "Ctrl+V у гэтым акне робіць тое ж самае.": "Ctrl+V in this window does the same.",
    "Радкоў: {count}": "Rows: {count}",
    "Буфер абмену пусты: спачатку скапіруйце табліцу з Excel.": "The clipboard is empty: copy a table from Excel first.",
    "Радкоў: {count}; прапушчана: {skipped}. {errors}": "Rows: {count}; skipped: {skipped}. {errors}",
    "Не атрымалася захаваць CRN:\n{error}": "Could not save CRN:\n{error}",
    "CRN {probe}: захавана радкоў: {count}": "CRN {probe}: rows saved: {count}",
    "SERIES для {probe}": "SERIES for {probe}",
    "Крок 3 з 3  ·  SERIES для {probe}": "Step 3 of 3  ·  SERIES for {probe}",
    "Індывідуальныя серыі для {probe}": "Individual series for {probe}",
    "Скапіруйце з Excel табліцу разам з загалоўкам: першы слупок год, наступныя слупкі - назвы серый "
    "(1, 1a, 13b...) з іх значэннямі. Пустыя ячэйкі прапускаюцца.":
        "Copy a table from Excel together with its header: the first column is the year, the following columns "
        "are series names (1, 1a, 13b…) with their values. Empty cells are skipped.",
    "Прапусціць SERIES": "Skip SERIES",
    "Значэнняў: {count}": "Values: {count}",
    "{status}; праблемы: {errors}": "{status}; problems: {errors}",
    "Значэнняў: {values}  ·  серый: {series}  ·  гадоў: {years}": "Values: {values}  ·  series: {series}  ·  years: {years}",
    "Не атрымалася захаваць SERIES:\n{error}": "Could not save SERIES:\n{error}",
    "SERIES {probe}: захавана значэнняў: {count}": "SERIES {probe}: values saved: {count}",
    "SQL-запыт": "SQL query",
    "Ctrl+Enter выконвае запыт. Запыты, якія мяняюць даныя, патрабуюць пацверджання.":
        "Ctrl+Enter runs the query. Queries that modify data ask for confirmation.",
    "Выканаць": "Run",
    "Уставіць з буфера": "Paste",
    "Гатова.": "Ready.",
    "Капіраваць вынік": "Copy result",
    "Увядзіце SQL-запыт.": "Enter an SQL query.",
    "Запыт можа змяніць або выдаліць даныя. Выканаць?": "The query may modify or delete data. Run it?",
    "Памылка: {error}": "Error: {error}",
    "Памылка SQL": "SQL error",
    "Знойдзена радкоў: {count}": "Rows found: {count}",
    "Выканана. Закранута радкоў: {count}": "Done. Rows affected: {count}",
    "Скапіравана радкоў: {count}": "Rows copied: {count}",
    # --- анкета ПП: секцыі
    "Ідэнтыфікацыя": "Identification",
    "Месцазнаходжанне": "Location",
    "Геабатанічнае раянаванне": "Geobotanical zoning",
    "Дрэвастан": "Forest stand",
    "Дэндрахраналагічная шкала": "Tree-ring chronology",
    "Аўтары": "Authors",
    "Нататкі": "Notes",
    # --- анкета ПП: палі
    "№ пробнай плошчы": "Plot No.",
    "№ дэндрахраналагічнай шкалы": "Chronology No.",
    "№ журнала": "Journal No.",
    "Дрэвавая парода": "Tree species",
    "Галоўная парода": "Main species",
    "Даступнасць": "Availability",
    "Шырата, град": "Latitude, deg",
    "Даўгата, град": "Longitude, deg",
    "Вышыня над узр. м., м": "Elevation, m a.s.l.",
    "Краіна": "Country",
    "Вобласць": "Region (oblast)",
    "Раён": "District",
    "Бліжэйшы населены пункт": "Nearest settlement",
    "Лясгас": "Forestry enterprise",
    "Лясніцтва": "Forest district",
    "Квартал": "Compartment",
    "Выдзел": "Stand (subcompartment)",
    "Год лесаўпарадкавання": "Forest inventory year",
    "Ландшафт": "Landscape",
    "Урочышча": "Tract",
    "Форма рэльефу": "Landform",
    "Глеба": "Soil",
    "Геабатанічная зона": "Geobotanical zone",
    "Геабатанічная падзона": "Geobotanical subzone",
    "Геабатанічная акруга": "Geobotanical district",
    "Геабатанічны раён": "Geobotanical region",
    "Тып лесу": "Forest type",
    "ТУМ": "Site conditions type (TUM)",
    "Каэф. складу": "Composition coefficient",
    "Склад": "Stand composition",
    "Сярэдні ўзрост": "Mean age",
    "Межы варыяцыі": "Age range",
    "Клас узросту": "Age class",
    "Сярэдняя вышыня, м": "Mean height, m",
    "Сярэдні дыяметр, см": "Mean diameter, cm",
    "Паўната": "Stand density",
    "Запас, куб. м": "Growing stock, m³",
    "Баніцет": "Site index (bonitet)",
    "Асацыяцыя": "Association",
    "Катэгорыя зямель": "Land category",
    "Паходжанне": "Origin",
    "Плошча выдзела": "Stand area",
    "Катэгорыя ахоўнасці": "Protection category",
    "Падрост": "Regeneration",
    "Падлесак": "Understorey",
    "Уздзеянне": "Disturbance",
    "Дата адбору ўзораў": "Sampling date",
    "Дата перадачы ў базу даных": "Date submitted to the database",
    "Тып узораў": "Sample type",
    "Колькасць дрэў у шкале, шт.": "Trees in chronology",
    "Працягласць шкалы, гадоў": "Chronology length, years",
    "Першы год": "First year",
    "Апошні год": "Last year",
    "Міжсерыйны каэфіцыент карэляцыі": "Inter-series correlation",
    "Сярэдні каэфіцыент адчувальнасці": "Mean sensitivity",
    "Адбор узораў (аўтар)": "Sampling (author)",
    "Вымярэнне ўзораў (аўтар)": "Measurement (author)",
    "Верыфікацыя (аўтар)": "Verification (author)",
    "Стандартызацыя (аўтар)": "Standardisation (author)",
    "Дадатковая інфармацыя": "Additional information",
    "Апісанне": "Description",
    # --- анкета ПП: падказкі
    "Унікальны код ПП. Змяніць пасля стварэння нельга.": "Unique plot code. It cannot be changed after creation.",
    "Лацінская назва віду. Можна ўвесці сваю.": "Latin species name. You may enter your own.",
    "Скарачэнне пароды, расшыфроўка ў меню «Даведка».": "Species abbreviation; the list is in the Help menu.",
    "Дзесятковыя градусы, напрыклад 53.9. Коска таксама прымаецца.": "Decimal degrees, e.g. 53.9. A comma is also accepted.",
    "Дзесятковыя градусы, напрыклад 27.5.": "Decimal degrees, e.g. 27.5.",
    "Метры.": "Metres.",
    "Можна ўвесці сваё значэнне.": "You may enter your own value.",
    "Формула складу, напрыклад 7С3Б.": "Composition formula, e.g. 7С3Б.",
    "Гадоў. Толькі лік; дыяпазон запішыце ў «Межы варыяцыі».": "Years. A single number; put a range into “Age range”.",
    "дд.мм.гггг": "dd.mm.yyyy",
    "Гектары.": "Hectares.",
    # --- пароды дрэў (PORODA_DICT)
    "Акацыя белая": "White acacia (black locust)",
    "Акацыя жоўтая": "Yellow acacia (Siberian peashrub)",
    "Аронія чарнаплодная": "Black chokeberry",
    "Айва": "Quince",
    "Бераст": "Field elm",
    "Барбарыс": "Barberry",
    "Бяроза": "Birch",
    "Бяроза павіслая": "Silver birch",
    "Бяроза пушыстая": "Downy birch",
    "Бяроза каменная": "Erman's birch",
    "Бяроза карэльская": "Karelian birch",
    "Бяроза карлікавая": "Dwarf birch",
    "Глог": "Hawthorn",
    "Брызгліна": "Spindle tree",
    "Бук": "Beech",
    "Бархат": "Cork tree",
    "Бархат амурскі": "Amur cork tree",
    "Бузіна": "Elder",
    "Вяз": "Elm",
    "Вішня": "Sour cherry",
    "Чарэшня": "Sweet cherry",
    "Граб": "Hornbeam",
    "Груша": "Pear",
    "Дуб": "Oak",
    "Дуб летні": "Summer oak",
    "Дуб нізкаствольны": "Low-stem oak",
    "Дуб чарэшчаты": "Pedunculate oak",
    "Дуб чырвоны": "Red oak",
    "Дуб скальны": "Sessile oak",
    "Дзёран": "Dogwood (Cornus)",
    "Елка": "Spruce",
    "Елка еўрапейская": "Norway spruce",
    "Елка калючая": "Blue spruce",
    "Ажына": "Blackberry",
    "Бружмель": "Honeysuckle",
    "Вярба ломкая": "Crack willow",
    "Вярба белая": "White willow",
    "Вярба дрэвападобная": "Tree willow",
    "Вярба востралістая": "Sharp-leaf willow",
    "Вярба шарападобная": "Globe willow",
    "Вярба кустовая": "Shrub willow",
    "Ільм": "Wych elm",
    "Ірга": "Serviceberry",
    "Кізільнік": "Cotoneaster",
    "Клён": "Maple",
    "Клён палявы": "Field maple",
    "Клён востралісты": "Norway maple",
    "Клён белы": "Sycamore maple",
    "Клён ясенялісты": "Ash-leaved maple",
    "Каштан": "Chestnut",
    "Каліна": "Guelder rose",
    "Кедр": "Stone pine (cedar)",
    "Кедр сібірскі": "Siberian stone pine",
    "Крушына слабіцельная": "Purging buckthorn",
    "Крушына ломкая": "Alder buckthorn",
    "Лістоўніца": "Larch",
    "Лістоўніца сібірская": "Siberian larch",
    "Псеўдатсуга": "Douglas fir",
    "Ліпа": "Linden",
    "Ліпа буйналістая": "Large-leaved linden",
    "Ліпа дробналістая": "Small-leaved linden",
    "Ляшчына": "Hazel",
    "Маліна": "Raspberry",
    "Ядловец": "Juniper",
    "Ядловец звычайны": "Common juniper",
    "Абляпіха": "Sea buckthorn",
    "Вольха": "Alder",
    "Вольха шэрая": "Grey alder",
    "Вольха чорная": "Black alder",
    "Асіна": "Aspen",
    "Арэх": "Walnut",
    "Арэх грэцкі": "Common walnut",
    "Арэх маньчжурскі": "Manchurian walnut",
    "Піхта": "Fir",
    "Піхта белая": "Silver fir",
    "Пухіраплоднік": "Ninebark",
    "Рабіна": "Rowan",
    "Ракітнік": "Broom",
    "Сасна": "Pine",
    "Сасна Банкса": "Jack pine",
    "Сасна Веймутава": "Weymouth pine",
    "Свідзіна": "Common dogwood (Swida)",
    "Бэз": "Lilac",
    "Сліва": "Plum",
    "Аліча": "Cherry plum",
    "Парэчкі": "Currant",
    "Спірэя": "Spiraea",
    "Таполя": "Poplar",
    "Таполя белая": "White poplar",
    "Таполя канадская": "Canadian poplar",
    "Таполя чорная": "Black poplar",
    "Таполя духмяная": "Balsam poplar",
    "Туя заходняя": "Northern white cedar",
    "Чаромха": "Bird cherry",
    "Чаромха Маака": "Maack's bird cherry",
    "Шаўкоўніца": "Mulberry",
    "Шыпшына": "Dog rose",
    "Ясень": "Ash",
    "Яблыня": "Apple",
}

_CATALOGS: dict[str, dict[str, str]] = {"en": _EN}
