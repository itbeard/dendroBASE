# DendroBASE

[Беларуская](#беларуская) · [English](#english)

## Беларуская

DendroBASE — настольная праграма для працы з дэндрахраналагічнымі данымі Беларусі. Яна дапамагае захоўваць апісанні пробных плошчаў, храналогіі і вымярэнні гадавых кольцаў у адной базе, знаходзіць патрэбныя даныя і рыхтаваць выбаркі для даследаванняў. Працуе на Windows, macOS і Linux.

### Што можна рабіць

- **Весці карткі пробных плошчаў (ПП):** месцазнаходжанне, каардынаты, дрэвавыя пароды, апісанне дрэвастану, звесткі пра ўзоры і аўтараў.
- **Праглядаць храналогіі CRN:** абагульненыя даныя па гадах у табліцы і на графіку (`raw`, `std`, `res`, `ars`), з магчымасцю рэдагаваць запісы.
- **Праглядаць індывідуальныя серыі SERIES:** вымярэнні асобных дрэў або кернаў, параўноўваць іх на графіку і выбіраць дыяпазон гадоў.
- **Шукаць і адбіраць даныя** па коду ПП, пародзе, геабатанічным раянаванні, тыпе лесу і гадах.
- **Дадаваць даныя з Excel** праз імпарт файлаў або капіраванне табліц. Вынікі можна капіяваць назад у Excel ці захоўваць у CSV.
- **Бачыць пробныя плошчы на мапе** па іх каардынатах. Мапа адкрываецца ў браўзеры і патрабуе інтэрнэту; яе можна захаваць як HTML.

### Як змяніць мову інтэрфейсу

Пры першым запуску інтэрфейс ангельскі. Каб пераключыцца на беларускую:

1. Адкрыйце **Tools → Settings…**.
2. У раздзеле **Interface language** выберыце **Беларуская**.
3. Націсніце **Save**.

Каб вярнуць ангельскую, адкрыйце **Інструменты → Налады…**, выберыце **English** і націсніце **Захаваць**. Налады таксама адкрываюцца праз `Ctrl+,` (на macOS — `Cmd+,`).

Мова змяняецца адразу і запамінаецца. Там жа можна выбраць светлую, цёмную або сістэмную тэму. Уведзеныя і імпартаваныя даныя застаюцца на сваёй мове.

### Устаноўка і запуск

Падрыхтоўка патрэбная толькі адзін раз. Праграма выкарыстоўвае Python, а даныя захоўвае ў PostgreSQL з PostGIS. Ніжэй — запуск базы праз Docker, які стварае яе аўтаматычна.

#### 1. Падрыхтуйце камп'ютар

- **Windows і macOS:** усталюйце [Python](https://www.python.org/downloads/) версіі 3.10 або навейшай з кампанентам Tcl/Tk (Tkinter), патрэбным для вокнаў праграмы. На macOS патрэбны Tk 8.6.13 або навейшы; версію можна паглядзець у акне, якое адкрывае каманда `python3 -m tkinter`.
- **Linux:** усталюйце Python 3.10 або навейшы, Tkinter і падтрымку віртуальных асяроддзяў. Для Ubuntu / Debian каманда прыведзена ніжэй.
- Усталюйце і запусціце [Docker Desktop](https://docs.docker.com/desktop/), выбраўшы сваю аперацыйную сістэму.
- Спампуйце і распакуйце файлы праекта. На GitHub гэта **Code → Download ZIP**.

#### 2. Падрыхтуйце праграму

Адкрыйце **PowerShell** на Windows або **Тэрмінал** на macOS / Linux. Перайдзіце ў папку праекта, дзе ляжыць `README.md`: увядзіце `cd "шлях да папкі праекта"`, падставіўшы свой шлях. Далей выконвайце каманды па чарзе.

**Windows (PowerShell):**

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

**macOS:**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
open -e .env
```

**Linux (Ubuntu / Debian):**

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
nano .env
```

У іншых дыстрыбутывах Linux усталюйце гэтыя кампаненты праз свой менеджар пакетаў, затым выканайце каманды пачынаючы з `python3 -m venv .venv`.

#### 3. Задайце пароль базы

Апошняя каманда адкрые файл налад `.env`. У радку `DENDROBASE_DB_PASSWORD=` дапішыце свой пароль пасля знака `=`. Астатнія налады пакіньце як ёсць. Захавайце файл і зачыніце рэдактар. У nano: `Ctrl+O`, `Enter`, затым `Ctrl+X`.

Калі ў вашай установе ўжо ёсць падрыхтаваная база DendroBASE, запішыце ў `.env` яе адрас, порт, назву базы, імя карыстальніка і пароль, атрыманыя ў адміністратара. У гэтым выпадку Docker і каманда `docker compose` не патрэбныя.

#### 4. Запусціце DendroBASE

Пераканайцеся, што Docker Desktop працуе. У той жа папцы праекта выканайце:

**Windows (PowerShell):**

```powershell
docker compose up -d --wait
.\.venv\Scripts\python.exe -m dendrobase
```

**macOS / Linux:**

```bash
docker compose up -d --wait
.venv/bin/python -m dendrobase
```

Першая каманда падрыхтуе базу і дачакаецца яе гатоўнасці, другая адкрые праграму. Першы запуск можа заняць некалькі хвілін: Docker спампоўвае патрэбныя файлы. Новая база спачатку пустая — дадайце свае даныя.

**Для наступных запускаў паўтарайце толькі крок 4**, адкрыўшы тэрмінал у папцы праекта. Захаваныя даныя застаюцца пасля закрыцця праграмы і перазапуску камп'ютара.

### Першыя крокі ў праграме

1. **Дадайце ПП:** **Файл → Новая пробная плошча…**. Запоўніце картку; затым можна ўставіць табліцы CRN і SERIES, скапіраваныя з Excel.
2. **Праглядзіце даныя:** выберыце ПП у спісе злева. Справа будуць яе апісанне, храналогія і індывідуальныя серыі. Змены ў картцы захоўвайце кнопкай **Захаваць змены**.
3. **Зрабіце выбарку:** на ўкладцы **Фільтры і пошук** задайце ўмовы і націсніце **Знайсці**. Кнопкі **Капіраваць** і **Экспарт…** дазваляюць перанесці вынікі ў Excel або іншую праграму для аналізу.

### Імпарт з Excel

Адкрыйце **Інструменты → Імпарт даных…**, выберыце папку з файламі і націсніце **Пачаць імпарт**.

Адзін файл `.xlsx` або `.xlsm` адпавядае адной ПП. Назва файла без пашырэння становіцца кодам ПП у ніжнім рэгістры: напрыклад, `PP01.xlsx` → `pp01`. Унутры чакаюцца лісты:

- **`title`** — абавязковы: два слупкі, назва параметра і значэнне. Назвы параметраў — як у зыходнай анкеце, па-руску: напрыклад, `Широта,грд`, `Долгота, грд`, `Древесная порода`, `Первый год`.
- **`crn`** — першы слупок з гадамі, далей слупкі з загалоўкамі `num`, `raw`, `std`, `res`, `ars`. Незапоўненыя паказчыкі можна прапусціць.
- **`series`** — першы слупок з гадамі, далей слупкі з назвамі серый у загалоўках і вымярэннямі па гадах.

Лісты `crn` і `series` неабавязковыя: даныя можна дадаць пазней. Пры апрацоўцы файла апісанне ПП абнаўляецца; існуючыя значэнні CRN і SERIES замяняюцца толькі з опцыяй **Перапісваць існуючыя радкі CRN і SERIES**. Раней апрацаваныя нязменныя файлы звычайна прапускаюцца.

Калі ў `.env` зададзена `DENDROBASE_EXCEL_FOLDER`, праграма пры запуску правярае гэтую папку ў фоне. Калі там ёсць файлы, якія яшчэ не імпартаваліся або змяніліся пасля імпарту, над радком стану з'яўляецца паведамленне з кнопкай **Імпартаваць…**: яна адкрывае акно імпарту з гэтай папкай. Кнопка **Схаваць** прыбірае паведамленне да наступнага запуску або імпарту.

### Логі і паведамленні пра памылкі

Калі праграма паказвае акно **Нечаканая памылка**, поўны тэкст памылкі і месца ў кодзе, дзе яна ўзнікла, запісваюцца ў файл логаў. Дакладны шлях да файла паказвае меню **Даведка → Дзе файл логаў**. Звычайна ён знаходзіцца тут:

- **Windows:** `C:\Users\<імя>\AppData\Local\DendroBASE\logs\dendrobase.log` — у адрасны радок Правадніка можна ўставіць `%LOCALAPPDATA%\DendroBASE\logs`.
- **macOS:** `~/Library/Logs/DendroBASE/dendrobase.log`
- **Linux:** `~/.local/state/dendrobase/logs/dendrobase.log`

Калі файл дарастае да 1 МБ, ён перайменоўваецца ў `dendrobase.log.1` (захоўваюцца тры такія копіі), а запіс працягваецца ў новы файл. Імпарт з Excel, запушчаны з каманднага радка, піша ў асобны файл `excel_import.log` у той жа папцы.

Налады логаў задаюцца ў `.env`: `DENDROBASE_LOG_DIR=` — іншая папка для файлаў логаў, `DENDROBASE_LOG_LEVEL=DEBUG` — больш падрабязныя запісы (па змаўчанні `INFO`).

Калі паведамляеце распрацоўшчыку пра памылку, дашліце файл логаў цалкам або скапіруйце з яго апошнія радкі, пачынаючы са слова `Traceback`.

---

## English

DendroBASE is a desktop application for working with dendrochronological data from Belarus. It keeps sample plot descriptions, chronologies and tree-ring measurements in one database, helping researchers find data and prepare datasets for analysis. It runs on Windows, macOS and Linux.

### What you can do

- **Manage sample plot records:** location, coordinates, tree species, forest stand descriptions, samples and contributors.
- **View CRN chronologies:** annual master chronology data in tables and charts (`raw`, `std`, `res`, `ars`), with tools to edit records.
- **View individual SERIES:** measurements from individual trees or cores, compare them on a chart and select a year range.
- **Find and filter data** by plot code, species, geobotanical area, forest type and years.
- **Bring in data from Excel** by importing files or pasting tables. Copy results back to Excel or export them as CSV.
- **View sample plots on a map** using their coordinates. The map opens in your browser and needs an internet connection; you can also save it as HTML.

### Change the interface language

The interface starts in English. To change it:

1. Open **Tools → Settings…**.
2. Under **Interface language**, choose **Беларуская** or **English**.
3. Click **Save**.

If the interface is already in Belarusian, open **Інструменты → Налады…**, choose **English** and click **Захаваць**. You can also open settings with `Ctrl+,` (`Cmd+,` on macOS).

The language changes immediately and is remembered. The same window offers light, dark and system themes. Entered and imported data stay in their original language.

### Install and run

Setup is needed only once. The application uses Python and stores data in PostgreSQL with PostGIS. The instructions below use Docker to create the database automatically.

#### 1. Prepare your computer

- **Windows and macOS:** install [Python](https://www.python.org/downloads/) 3.10 or newer with the Tcl/Tk (Tkinter) component used for the application windows. On macOS, Tk 8.6.13 or newer is required; run `python3 -m tkinter` to see the version in a small test window.
- **Linux:** install Python 3.10 or newer, Tkinter and virtual environment support. The Ubuntu / Debian command is included below.
- Install and start [Docker Desktop](https://docs.docker.com/desktop/), choosing your operating system.
- Download and extract the project files. On GitHub, use **Code → Download ZIP**.

#### 2. Prepare the application

Open **PowerShell** on Windows or **Terminal** on macOS / Linux. Go to the project folder containing `README.md`: type `cd "path to the project folder"`, replacing the text in quotes with your folder's location. Then run the following commands one at a time.

**Windows (PowerShell):**

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

**macOS:**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
open -e .env
```

**Linux (Ubuntu / Debian):**

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
nano .env
```

On other Linux distributions, install these components with your package manager, then follow the commands starting with `python3 -m venv .venv`.

#### 3. Set a database password

The last command opens the `.env` settings file. Find `DENDROBASE_DB_PASSWORD=` and add your own password after `=`. Leave the other settings as they are. Save the file and close the editor. In nano, press `Ctrl+O`, `Enter`, then `Ctrl+X`.

If your institution already has a configured DendroBASE database, enter its address, port, database name, username and password in `.env`, using the details provided by your administrator. In that case, Docker and the `docker compose` command are unnecessary.

#### 4. Start DendroBASE

Make sure Docker Desktop is running. From the same project folder, run:

**Windows (PowerShell):**

```powershell
docker compose up -d --wait
.\.venv\Scripts\python.exe -m dendrobase
```

**macOS / Linux:**

```bash
docker compose up -d --wait
.venv/bin/python -m dendrobase
```

The first command prepares the database and waits until it is ready; the second opens the application. The first launch may take a few minutes while Docker downloads the required files. A new database starts empty, ready for your data.

**For later launches, repeat only step 4**, opening the terminal in the project folder. Saved data remain after closing the application or restarting your computer.

### First steps in the application

1. **Add a plot:** choose **File → New sample plot…**. Fill in the plot record, then optionally paste CRN and SERIES tables copied from Excel.
2. **Browse your data:** select a plot in the list on the left. Its description, chronology and individual series appear on the right. Click **Save changes** after editing the plot record.
3. **Prepare a dataset:** open **Filters and search**, choose your conditions and click **Search**. Use **Copy** or **Export…** to take the results into Excel or another analysis tool.

### Import from Excel

Open **Tools → Import data…**, select the folder containing your files and click **Start import**.

Each `.xlsx` or `.xlsm` file represents one plot. The filename without its extension becomes the lowercase plot code: for example, `PP01.xlsx` → `pp01`. The expected worksheets are:

- **`title`** — required: two columns containing parameter names and values. Use the Russian parameter names from the original plot form, such as `Широта,грд` (latitude), `Долгота, грд` (longitude), `Древесная порода` (tree species) and `Первый год` (first year).
- **`crn`** — years in the first column, followed by columns headed `num`, `raw`, `std`, `res`, `ars`. Unavailable measures may be omitted.
- **`series`** — years in the first column, followed by columns headed with series names and containing annual measurements.

The `crn` and `series` worksheets are optional; you can add their data later. Processing a file updates its plot description; existing CRN and SERIES values are replaced only when **Overwrite existing CRN and SERIES rows** is selected. Previously processed files that have not changed are normally skipped.

If `DENDROBASE_EXCEL_FOLDER` is set in `.env`, the application checks that folder in the background on startup. When it contains files that have not been imported yet, or that changed after the import, a notice with an **Import…** button appears above the status bar; the button opens the import window for that folder. **Hide** removes the notice until the next start or import.

### Logs and error reports

When the application shows an **Unexpected error** dialog, the full error text and the place in the code where it occurred are written to the log file. The exact path is shown under **Help → Log file location**. By default the file is here:

- **Windows:** `C:\Users\<name>\AppData\Local\DendroBASE\logs\dendrobase.log` — you can paste `%LOCALAPPDATA%\DendroBASE\logs` into the Explorer address bar.
- **macOS:** `~/Library/Logs/DendroBASE/dendrobase.log`
- **Linux:** `~/.local/state/dendrobase/logs/dendrobase.log`

When the file reaches 1 MB it is renamed to `dendrobase.log.1` (three such copies are kept) and logging continues in a fresh file. The Excel import run from the command line writes to a separate `excel_import.log` in the same folder.

Logging is configured in `.env`: `DENDROBASE_LOG_DIR=` selects another folder for the log files, and `DENDROBASE_LOG_LEVEL=DEBUG` enables more detailed output (the default is `INFO`).

When reporting a problem, attach the whole log file or copy its last lines starting from the word `Traceback`.
