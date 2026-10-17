"""Даведнікі (пароды, геабатанічнае раянаванне) і апісанне палёў табліцы title.

Гэта адзінае месца, дзе вызначана, якія палі лікавыя, якія даты, якія са спісам:
ім карыстаюцца і анкета ПП, і ўкладка «Інфармацыя аб ПП», і імпарт з Excel.

Подпісы палёў і назвы парод тут беларускія і перакладаюцца праз i18n.tr() пры паказе.
Спісы значэнняў (зоны, акругі, даступнасць, тып узораў...) застаюцца такімі, якімі яны
захоўваюцца ў базе і прыходзяць з Excel: гэта даныя, а не інтэрфейс.
"""
from __future__ import annotations

from dataclasses import dataclass

from .i18n import tr

PORODA_LIST = [
    "А", "АЖ", "АРЧ", "АЙВ", "БР", "ББР", "Б", "ББ", "БП", "БК",
    "БКР", "БКК", "БЯР", "БРК", "БУК", "БХТ", "БХ", "БЗН", "В", "ВШ",
    "ЧШ", "Г", "ГШ", "Д", "ДЛ", "ДН", "ДЧ", "ДК", "ДС", "ДР", "Е",
    "ЕЕ", "ЕК", "ЕЖ", "Ж", "ИВЛ", "ИВБ", "ИВД", "ИВО", "ИВШ", "ИВК",
    "ИЛ", "ИР", "КЗ", "КЛ", "КЛП", "КЛО", "КЛБ", "КЛЯ", "КШ", "КЛН",
    "К", "КС", "КРС", "КРЛ", "Л", "ЛСБ", "ЛЖ", "ЛП", "ЛПК", "ЛПМ",
    "ЛЩ", "МЛ", "МЖX", "МЖ", "ОБЛ", "ОЛX", "ОЛС", "ОЛЧ", "ОС", "ОРХ",
    "ОРГ", "ОРМ", "П", "ПБ", "ПП", "Р", "РК", "С", "СБ", "СВ", "СВД",
    "СИР", "СЛ", "АЛ", "СМР", "СПР", "Т", "ТБ", "ТК", "ТЧ", "ТД",
    "ТУЗ", "ЧР", "ЧРМ", "Ш", "ШП", "Я", "ЯБ"
]

PORODA_DICT = {
    "А": "Акацыя белая", "АЖ": "Акацыя жоўтая", "АРЧ": "Аронія чарнаплодная",
    "АЙВ": "Айва", "БР": "Бераст", "ББР": "Барбарыс", "Б": "Бяроза",
    "ББ": "Бяроза павіслая", "БП": "Бяроза пушыстая", "БК": "Бяроза каменная",
    "БКР": "Бяроза карэльская", "БКК": "Бяроза карлікавая", "БЯР": "Глог",
    "БРК": "Брызгліна", "БУК": "Бук", "БХТ": "Бархат", "БХ": "Бархат амурскі",
    "БЗН": "Бузіна", "В": "Вяз", "ВШ": "Вішня", "ЧШ": "Чарэшня", "Г": "Граб",
    "ГШ": "Груша", "Д": "Дуб", "ДЛ": "Дуб летні", "ДН": "Дуб нізкаствольны",
    "ДЧ": "Дуб чарэшчаты", "ДК": "Дуб чырвоны", "ДС": "Дуб скальны", "ДР": "Дзёран",
    "Е": "Елка", "ЕЕ": "Елка еўрапейская", "ЕК": "Елка калючая", "ЕЖ": "Ажына",
    "Ж": "Бружмель", "ИВЛ": "Вярба ломкая", "ИВБ": "Вярба белая", "ИВД": "Вярба дрэвападобная",
    "ИВО": "Вярба востралістая", "ИВШ": "Вярба шарападобная", "ИВК": "Вярба кустовая",
    "ИЛ": "Ільм", "ИР": "Ірга", "КЗ": "Кізільнік", "КЛ": "Клён",
    "КЛП": "Клён палявы", "КЛО": "Клён востралісты", "КЛБ": "Клён белы",
    "КЛЯ": "Клён ясенялісты", "КШ": "Каштан", "КЛН": "Каліна", "К": "Кедр",
    "КС": "Кедр сібірскі", "КРС": "Крушына слабіцельная", "КРЛ": "Крушына ломкая",
    "Л": "Лістоўніца", "ЛСБ": "Лістоўніца сібірская", "ЛЖ": "Псеўдатсуга",
    "ЛП": "Ліпа", "ЛПК": "Ліпа буйналістая", "ЛПМ": "Ліпа дробналістая",
    "ЛЩ": "Ляшчына", "МЛ": "Маліна", "МЖX": "Ядловец", "МЖ": "Ядловец звычайны",
    "ОБЛ": "Абляпіха", "ОЛX": "Вольха", "ОЛС": "Вольха шэрая", "ОЛЧ": "Вольха чорная",
    "ОС": "Асіна", "ОРХ": "Арэх", "ОРГ": "Арэх грэцкі", "ОРМ": "Арэх маньчжурскі",
    "П": "Піхта", "ПБ": "Піхта белая", "ПП": "Пухіраплоднік", "Р": "Рабіна",
    "РК": "Ракітнік", "С": "Сасна", "СБ": "Сасна Банкса", "СВ": "Сасна Веймутава",
    "СВД": "Свідзіна", "СИР": "Бэз", "СЛ": "Сліва", "АЛ": "Аліча",
    "СМР": "Парэчкі", "СПР": "Спірэя", "Т": "Таполя", "ТБ": "Таполя белая",
    "ТК": "Таполя канадская", "ТЧ": "Таполя чорная", "ТД": "Таполя духмяная",
    "ТУЗ": "Туя заходняя", "ЧР": "Чаромха", "ЧРМ": "Чаромха Маака",
    "Ш": "Шаўкоўніца", "ШП": "Шыпшына", "Я": "Ясень", "ЯБ": "Яблыня"
}

GEO_ZONA_LIST = ["Евразиатская таёжная", "Европейская широколиственно-лесная"]
GEO_PODZONA_LIST = ["Дубово-темнохвойных подтаежных лесов", "Грабово-дубово-темнохвойных подтаежных лесов",
                    "Широколиственно-сосновых лесов"]
GEO_OKRUG_LIST = ["Западно-Двинский", "Оршанско-Могилевский", "Ошмянско-Минский", "Березинско-Предполесский",
                  "Неманско-Предполесский", "Бугско-Полесский", "Полесско-Приднепровский"]
GEO_RAJON_LIST = ["Браславский", "Дисненский", "Полоцкий", "Суражско-Лучесский", "Березинско-Друтский", "Беседский",
                  "Оршанско-Приднепровский", "Сожский", "Верхнеберезинский", "Минско-Борисовский", "Нарочано-Вилейский",
                  "Центральноберезинский", "Центральнопредполесский", "Чечерско-Приднепровский", "Беловежский",
                  "Волковысско-Новогрудский", "Западнопредполесский", "Налибокский", "Неманский", "Бугско-Припятский",
                  "Пинско-Припятский", "Гомельско-Приднепровский", "Припятско-Мозырский", "Центрально-Полесский",
                  "Южнополесский"]
DOSTUPNOST_LIST = ["Открытый доступ", "Ограниченный доступ", "По запросу"]
TIP_OBRAZTSOV_LIST = ["Керны", "Спилы", "Диски"]

DREVESNAYA_PORODA_LIST = [
    "Pinus sylvestris L.",
    "Picea abies (L.) H.Karst.",
    "Quercus robur L.",
    "Betula pendula Roth",
    "Betula pubescens Ehrh.",
    "Populus tremula L.",
    "Alnus glutinosa (L.) Gaertn.",
    "Alnus incana (L.) Moench",
    "Tilia cordata Mill.",
    "Acer platanoides L.",
    "Fraxinus excelsior L.",
    "Carpinus betulus L.",
    "Ulmus glabra Huds.",
    "Ulmus laevis Pall.",
    "Salix alba L.",
    "Salix caprea L.",
    "Padus avium Mill.",
    "Sorbus aucuparia L.",
    "Malus sylvestris Mill.",
    "Pyrus pyraster (L.) Burgsd."
]

TIP_LESA_LIST = [
    "Баг-м", "Баг-мп", "Баг", "Сосняк", "Ельнік", "Дуброва", "Черноольховый",
    "Березняк", "Осинник", "Липняк", "Кленовник", "Пойменный", "Суходольный"
]



# Спісы вышэй: значэнні, якія захоўваюцца ў базе (па-руску, як у зыходных Excel-табліцах).
# Так імпарт прыводзіць розныя напісанні зоны да аднаго, якое ёсць у GEO_ZONA_LIST
ZONA_NORMALIZATION = {
    "Евразиатская таежная": "Евразиатская таёжная",
    "Евроазиатская таёжная": "Евразиатская таёжная",
    "Еўраазіяцкая таёжная": "Евразиатская таёжная",
}

PROBE_KEY = "n_probnoy_ploshchadi"
READONLY_COLUMNS = frozenset({"id", "geom"})

CRN_COLUMNS = ("year", "num", "raw", "std", "res", "ars")
CRN_VALUE_COLUMNS = ("raw", "std", "res", "ars")


@dataclass(frozen=True)
class TitleField:
    """Апісанне аднаго поля анкеты пробнай плошчы."""
    name: str                       # назва слупка ў табліцы title
    label: str                      # подпіс у інтэрфейсе (па-беларуску; перакладаецца праз tr())
    kind: str = "text"              # text | number | integer | date | choice | multiline
    options: tuple[str, ...] = ()   # варыянты для kind == "choice"
    required: bool = False
    hint: str = ""                  # кароткая падказка: адзінкі, фармат (перакладаецца праз tr())


def _f(name: str, label: str, kind: str = "text", options=(), **extra) -> TitleField:
    return TitleField(name, label, kind, tuple(options), **extra)


# Палі згрупаваны па сэнсе: так яны паказваюцца ў анкеце і на ўкладцы «Інфармацыя аб ПП».
TITLE_SECTIONS: tuple[tuple[str, tuple[TitleField, ...]], ...] = (
    ("Ідэнтыфікацыя", (
        _f("n_probnoy_ploshchadi", "№ пробнай плошчы", required=True, hint="Унікальны код ПП. Змяніць пасля стварэння нельга."),
        _f("n_dendrokhronologicheskoj_shkaly", "№ дэндрахраналагічнай шкалы"),
        _f("n_journal", "№ журнала"),
        _f("drevesnaya_poroda", "Дрэвавая парода", "choice", DREVESNAYA_PORODA_LIST, hint="Лацінская назва віду. Можна ўвесці сваю."),
        _f("glavnaya_poroda", "Галоўная парода", "choice", PORODA_LIST, hint="Скарачэнне пароды, расшыфроўка ў меню «Даведка»."),
        _f("dostupnost", "Даступнасць", "choice", DOSTUPNOST_LIST),
    )),
    ("Месцазнаходжанне", (
        _f("shirota_grd", "Шырата, град", "number", hint="Дзесятковыя градусы, напрыклад 53.9. Коска таксама прымаецца."),
        _f("dolgota_grd", "Даўгата, град", "number", hint="Дзесятковыя градусы, напрыклад 27.5."),
        _f("vysota_nad_u_m", "Вышыня над узр. м., м", "number", hint="Метры."),
        _f("strana", "Краіна"),
        _f("oblast", "Вобласць"),
        _f("rayon", "Раён"),
        _f("blizhajshij_naselennyj_punkt", "Бліжэйшы населены пункт"),
        _f("leskhoz", "Лясгас"),
        _f("lesnichestvo", "Лясніцтва"),
        _f("kvartal", "Квартал"),
        _f("vydel", "Выдзел"),
        _f("god_lesoustrojstva", "Год лесаўпарадкавання", "integer"),
        _f("landshaft", "Ландшафт"),
        _f("urochishche", "Урочышча"),
        _f("forma_relefa", "Форма рэльефу"),
        _f("pochva", "Глеба"),
    )),
    ("Геабатанічнае раянаванне", (
        _f("geobotanicheskaya_zona", "Геабатанічная зона", "choice", GEO_ZONA_LIST),
        _f("geobotanicheskaya_podzona", "Геабатанічная падзона", "choice", GEO_PODZONA_LIST),
        _f("geobotanicheskij_okrug", "Геабатанічная акруга", "choice", GEO_OKRUG_LIST),
        _f("geobotanicheskij_rajon", "Геабатанічны раён", "choice", GEO_RAJON_LIST),
    )),
    ("Дрэвастан", (
        _f("tip_lesa", "Тып лесу", "choice", TIP_LESA_LIST, hint="Можна ўвесці сваё значэнне."),
        _f("tum", "ТУМ"),
        _f("koef_sostava", "Каэф. складу", "number"),
        _f("sostav_drevoj", "Склад", hint="Формула складу, напрыклад 7С3Б."),
        _f("vozrast", "Сярэдні ўзрост", "number", hint="Гадоў. Толькі лік; дыяпазон запішыце ў «Межы варыяцыі»."),
        _f("predely_variacii", "Межы варыяцыі"),
        _f("klass_vozrasta", "Клас узросту"),
        _f("srednyaya_vysota_m", "Сярэдняя вышыня, м", "number"),
        _f("srednij_diametr_sm", "Сярэдні дыяметр, см", "number"),
        _f("polnota", "Паўната", "number"),
        _f("zapas_kub_m", "Запас, куб. м", "number"),
        _f("bonitet", "Баніцет"),
        _f("associaciya", "Асацыяцыя"),
        _f("kategoriya_zemel", "Катэгорыя зямель"),
        _f("proiskhozhdenie", "Паходжанне"),
        _f("ploshchad_vydela", "Плошча выдзела", "number", hint="Гектары."),
        _f("kategoriya_zashchitnosti", "Катэгорыя ахоўнасці"),
        _f("podrost", "Падрост"),
        _f("podlesok", "Падлесак"),
        _f("vozdejstvie", "Уздзеянне"),
    )),
    ("Дэндрахраналагічная шкала", (
        _f("data_otbora_obraztsov", "Дата адбору ўзораў", "date", hint="дд.мм.гггг"),
        _f("data_predostavleniya_v_bazu_dannykh", "Дата перадачы ў базу даных", "date", hint="дд.мм.гггг"),
        _f("tip_obraztsov", "Тып узораў", "choice", TIP_OBRAZTSOV_LIST),
        _f("kolichestvo_derevev_v_shkale_sht", "Колькасць дрэў у шкале, шт.", "integer"),
        _f("protyazhennost_shkaly_let", "Працягласць шкалы, гадоў", "integer"),
        _f("pervyy_god", "Першы год", "integer"),
        _f("posledniy_god", "Апошні год", "integer"),
        _f("mezhserialnyj_kof_korrelyatsii", "Міжсерыйны каэфіцыент карэляцыі", "number"),
        _f("srednij_kof_chuvstvitelnosti", "Сярэдні каэфіцыент адчувальнасці", "number"),
    )),
    ("Аўтары", (
        _f("otbor_obraztsov_avtor", "Адбор узораў (аўтар)"),
        _f("izmerenie_obraztsov_avtor", "Вымярэнне ўзораў (аўтар)"),
        _f("verifikatsiya_avtor", "Верыфікацыя (аўтар)"),
        _f("standartizatsiya_avtor", "Стандартызацыя (аўтар)"),
    )),
    ("Нататкі", (
        _f("dopolnitelnaya_informaciya", "Дадатковая інфармацыя", "multiline"),
        _f("opisanie", "Апісанне", "multiline"),
    )),
)

TITLE_FIELDS: tuple[TitleField, ...] = tuple(field for _, fields in TITLE_SECTIONS for field in fields)

FIELD_BY_NAME: dict[str, TitleField] = {f.name: f for f in TITLE_FIELDS}
NUMBER_FIELDS = frozenset(f.name for f in TITLE_FIELDS if f.kind == "number")
INTEGER_FIELDS = frozenset(f.name for f in TITLE_FIELDS if f.kind == "integer")
DATE_FIELDS = frozenset(f.name for f in TITLE_FIELDS if f.kind == "date")


def field_kind(column: str) -> str:
    """Тып поля па назве слупка; невядомыя слупкі лічацца тэкставымі."""
    field = FIELD_BY_NAME.get(column)
    return field.kind if field else "text"


def field_label(column: str) -> str:
    """Подпіс поля на бягучай мове інтэрфейсу; невядомыя слупкі паказваюцца як ёсць."""
    field = FIELD_BY_NAME.get(column)
    return tr(field.label) if field else column


# Адпаведнасць назваў параметраў на лісце «title» Excel-файла слупкам БД.
# Ключы ў ніжнім рэгістры. Пры супастаўленні спачатку шукаецца дакладнае
# супадзенне, потым самы доўгі ключ, які змяшчаецца ў назве параметра
# (гл. excel_import.map_param), таму «коэфф. состава» не блытаецца з «состав».
EXCEL_PARAM_MAPPING: dict[str, str] = {
    "широта,грд": "shirota_grd",
    "широта, грд": "shirota_grd",
    "долгота, грд": "dolgota_grd",
    "долгота,грд": "dolgota_grd",
    "высота над у.м.": "vysota_nad_u_m",
    "главная порода": "glavnaya_poroda",
    "последний год": "posledniy_god",
    "средняя высота, м": "srednyaya_vysota_m",
    "полнота": "polnota",
    "состав": "sostav_drevoj",
    "возраст средний": "vozrast",
    "средний диаметр, см": "srednij_diametr_sm",
    "запас, куб.м.": "zapas_kub_m",
    "древесная порода": "drevesnaya_poroda",
    "геоботаническая зона": "geobotanicheskaya_zona",
    "геоботаническая подзона": "geobotanicheskaya_podzona",
    "геоботанический округ": "geobotanicheskij_okrug",
    "геоботанический район": "geobotanicheskij_rajon",
    "страна": "strana",
    "область": "oblast",
    "район": "rayon",
    "ближайший населенный пункт": "blizhajshij_naselennyj_punkt",
    "лесхоз": "leskhoz",
    "лесничество": "lesnichestvo",
    "квартал": "kvartal",
    "выдел": "vydel",
    "год лесоустройства": "god_lesoustrojstva",
    "тип леса": "tip_lesa",
    "тум": "tum",
    "коэфф. состава": "koef_sostava",
    "пределы вариации": "predely_variacii",
    "класс возраста": "klass_vozrasta",
    "ассоциация": "associaciya",
    "ландшафт": "landshaft",
    "урочище": "urochishche",
    "форма рельефа": "forma_relefa",
    "почва": "pochva",
    "категория земель": "kategoriya_zemel",
    "происхождение": "proiskhozhdenie",
    "площадь выдела": "ploshchad_vydela",
    "категория защитности": "kategoriya_zashchitnosti",
    "бонитет": "bonitet",
    "подрост": "podrost",
    "подлесок": "podlesok",
    "воздействие": "vozdejstvie",
    "дополнительная информация": "dopolnitelnaya_informaciya",
    "n дендрохронологической шкалы": "n_dendrokhronologicheskoj_shkaly",
    "дата отбора образцов": "data_otbora_obraztsov",
    "дата предоставления в базу данных": "data_predostavleniya_v_bazu_dannykh",
    "тип образцов": "tip_obraztsov",
    "отбор образцов (автор)": "otbor_obraztsov_avtor",
    "измерение образцов (автор)": "izmerenie_obraztsov_avtor",
    "верификация (автор)": "verifikatsiya_avtor",
    "стандартизация (автор)": "standartizatsiya_avtor",
    "количество деревьев в шкале, шт": "kolichestvo_derevev_v_shkale_sht",
    "протяженность шкалы, лет": "protyazhennost_shkaly_let",
    "первый год": "pervyy_god",
    "межсериальный коэффициент корреляции": "mezhserialnyj_kof_korrelyatsii",
    "средний коэффициент чувствительности": "srednij_kof_chuvstvitelnosti",
    "доступность": "dostupnost",
    "описание": "opisanie",
    "n журнала": "n_journal",
    "n журналу": "n_journal",
    "n_journal": "n_journal",
    "номер в журнале": "n_journal",
}
