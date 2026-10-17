"""Даведнікі (пароды, геабатанічнае раянаванне) і апісанне палёў табліцы title.

Гэта адзінае месца, дзе вызначана, якія палі лікавыя, якія даты, якія са спісам:
ім карыстаюцца і анкета ПП, і ўкладка «Інфармацыя аб ПП», і імпарт з Excel.
"""
from __future__ import annotations

from dataclasses import dataclass

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
    "А": "Акация белая", "АЖ": "Акация желтая", "АРЧ": "Арония чернопл.",
    "АЙВ": "Айва", "БР": "Берест", "ББР": "Барбарис", "Б": "Береза",
    "ББ": "Береза бородав.", "БП": "Береза пушистая", "БК": "Береза каменная",
    "БКР": "Береза карел.", "БКК": "Береза карлик.", "БЯР": "Боярышник",
    "БРК": "Бересклет", "БУК": "Бук", "БХТ": "Бархат", "БХ": "Бархат амур.",
    "БЗН": "Бузина", "В": "Вяз", "ВШ": "Вишня", "ЧШ": "Черешня", "Г": "Граб",
    "ГШ": "Груша", "Д": "Дуб", "ДЛ": "Дуб летний", "ДН": "Дуб низкоств.",
    "ДЧ": "Дуб черешч.", "ДК": "Дуб красный", "ДС": "Дуб скальный", "ДР": "Дерен",
    "Е": "Ель", "ЕЕ": "Ель европ.", "ЕК": "Ель колючая", "ЕЖ": "Ежевика",
    "Ж": "Жимолость", "ИВЛ": "Ива ломкая", "ИВБ": "Ива белая", "ИВД": "Ива древовид.",
    "ИВО": "Ива остролист.", "ИВШ": "Ива шаровидн.", "ИВК": "Ива кустарник.",
    "ИЛ": "Ильм", "ИР": "Ирга", "КЗ": "Кизильник", "КЛ": "Клен",
    "КЛП": "Клен полевой", "КЛО": "Клен остролист.", "КЛБ": "Клен белый",
    "КЛЯ": "Клен ясенелист.", "КШ": "Каштан", "КЛН": "Калина", "К": "Кедр",
    "КС": "Кедр сибирский", "КРС": "Крушина слабит.", "КРЛ": "Крушина ломкая",
    "Л": "Лиственница", "ЛСБ": "Лиственница сиб.", "ЛЖ": "Лжетсуга",
    "ЛП": "Липа", "ЛПК": "Липа крупнолист.", "ЛПМ": "Липа мелколист.",
    "ЛЩ": "Лещина", "МЛ": "Малина", "МЖX": "Можжевельник", "МЖ": "Можжевельник об.",
    "ОБЛ": "Облепиха", "ОЛX": "Ольха", "ОЛС": "Ольха серая", "ОЛЧ": "Ольха черная",
    "ОС": "Осина", "ОРХ": "Орех", "ОРГ": "Орех грецкий", "ОРМ": "Орех манчжур.",
    "П": "Пихта", "ПБ": "Пихта белая", "ПП": "Пузыреплодник", "Р": "Рябина",
    "РК": "Ракитник", "С": "Сосна", "СБ": "Сосна Банкса", "СВ": "Сосна Веймут.",
    "СВД": "Свидина", "СИР": "Сирень", "СЛ": "Слива", "АЛ": "Алыча",
    "СМР": "Смородина", "СПР": "Спирея", "Т": "Тополь", "ТБ": "Тополь белый",
    "ТК": "Тополь канад.", "ТЧ": "Тополь черный", "ТД": "Тополь душист.",
    "ТУЗ": "Туя западная", "ЧР": "Черемуха", "ЧРМ": "Черемуха Маака",
    "Ш": "Шелковица", "ШП": "Шиповник", "Я": "Ясень", "ЯБ": "Яблоня"
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
    label: str                      # подпіс у інтэрфейсе (як у зыходных Excel-табліцах)
    kind: str = "text"              # text | number | integer | date | choice | multiline
    options: tuple[str, ...] = ()   # варыянты для kind == "choice"
    required: bool = False
    hint: str = ""                  # кароткая падказка: адзінкі, фармат


def _f(name: str, label: str, kind: str = "text", options=(), **extra) -> TitleField:
    return TitleField(name, label, kind, tuple(options), **extra)


# Палі згрупаваны па сэнсе: так яны паказваюцца ў анкеце і на ўкладцы «Інфармацыя аб ПП».
TITLE_SECTIONS: tuple[tuple[str, tuple[TitleField, ...]], ...] = (
    ("Ідэнтыфікацыя", (
        _f("n_probnoy_ploshchadi", "N пробной площади", required=True, hint="Унікальны код ПП. Змяніць пасля стварэння нельга."),
        _f("n_dendrokhronologicheskoj_shkaly", "N дендрохронологической шкалы"),
        _f("n_journal", "N журнала"),
        _f("drevesnaya_poroda", "Древесная порода", "choice", DREVESNAYA_PORODA_LIST, hint="Лацінская назва віду. Можна ўвесці сваю."),
        _f("glavnaya_poroda", "Главная порода", "choice", PORODA_LIST, hint="Скарачэнне пароды, расшыфроўка ў меню «Даведка»."),
        _f("dostupnost", "Доступность", "choice", DOSTUPNOST_LIST),
    )),
    ("Месцазнаходжанне", (
        _f("shirota_grd", "Широта, грд", "number", hint="Дзесятковыя градусы, напрыклад 53.9. Коска таксама прымаецца."),
        _f("dolgota_grd", "Долгота, грд", "number", hint="Дзесятковыя градусы, напрыклад 27.5."),
        _f("vysota_nad_u_m", "Высота над у.м.", "number", hint="Метры."),
        _f("strana", "Страна"),
        _f("oblast", "Область"),
        _f("rayon", "Район"),
        _f("blizhajshij_naselennyj_punkt", "Ближайший населенный пункт"),
        _f("leskhoz", "Лесхоз"),
        _f("lesnichestvo", "Лесничество"),
        _f("kvartal", "Квартал"),
        _f("vydel", "Выдел"),
        _f("god_lesoustrojstva", "Год лесоустройства", "integer"),
        _f("landshaft", "Ландшафт"),
        _f("urochishche", "Урочище"),
        _f("forma_relefa", "Форма рельефа"),
        _f("pochva", "Почва"),
    )),
    ("Геабатанічнае раянаванне", (
        _f("geobotanicheskaya_zona", "Геоботаническая зона", "choice", GEO_ZONA_LIST),
        _f("geobotanicheskaya_podzona", "Геоботаническая подзона", "choice", GEO_PODZONA_LIST),
        _f("geobotanicheskij_okrug", "Геоботанический округ", "choice", GEO_OKRUG_LIST),
        _f("geobotanicheskij_rajon", "Геоботанический район", "choice", GEO_RAJON_LIST),
    )),
    ("Дрэвастан", (
        _f("tip_lesa", "Тип леса", "choice", TIP_LESA_LIST, hint="Можна ўвесці сваё значэнне."),
        _f("tum", "ТУМ"),
        _f("koef_sostava", "Коэфф. состава", "number"),
        _f("sostav_drevoj", "Состав", hint="Формула складу, напрыклад 7С3Б."),
        _f("vozrast", "Возраст средний", "number", hint="Гадоў. Толькі лік; дыяпазон запішыце ў «Пределы вариации»."),
        _f("predely_variacii", "Пределы вариации"),
        _f("klass_vozrasta", "Класс возраста"),
        _f("srednyaya_vysota_m", "Средняя высота, м", "number"),
        _f("srednij_diametr_sm", "Средний диаметр, см", "number"),
        _f("polnota", "Полнота", "number"),
        _f("zapas_kub_m", "Запас, куб.м.", "number"),
        _f("bonitet", "Бонитет"),
        _f("associaciya", "Ассоциация"),
        _f("kategoriya_zemel", "Категория земель"),
        _f("proiskhozhdenie", "Происхождение"),
        _f("ploshchad_vydela", "Площадь выдела", "number", hint="Гектары."),
        _f("kategoriya_zashchitnosti", "Категория защитности"),
        _f("podrost", "Подрост"),
        _f("podlesok", "Подлесок"),
        _f("vozdejstvie", "Воздействие"),
    )),
    ("Дэндрахраналагічная шкала", (
        _f("data_otbora_obraztsov", "Дата отбора образцов", "date", hint="дд.мм.гггг"),
        _f("data_predostavleniya_v_bazu_dannykh", "Дата предоставления в базу данных", "date", hint="дд.мм.гггг"),
        _f("tip_obraztsov", "Тип образцов", "choice", TIP_OBRAZTSOV_LIST),
        _f("kolichestvo_derevev_v_shkale_sht", "Количество деревьев в шкале, шт", "integer"),
        _f("protyazhennost_shkaly_let", "Протяженность шкалы, лет", "integer"),
        _f("pervyy_god", "Первый год", "integer"),
        _f("posledniy_god", "Последний год", "integer"),
        _f("mezhserialnyj_kof_korrelyatsii", "Межсериальный коэффициент корреляции", "number"),
        _f("srednij_kof_chuvstvitelnosti", "Средний коэффициент чувствительности", "number"),
    )),
    ("Аўтары", (
        _f("otbor_obraztsov_avtor", "Отбор образцов (автор)"),
        _f("izmerenie_obraztsov_avtor", "Измерение образцов (автор)"),
        _f("verifikatsiya_avtor", "Верификация (автор)"),
        _f("standartizatsiya_avtor", "Стандартизация (автор)"),
    )),
    ("Нататкі", (
        _f("dopolnitelnaya_informaciya", "Дополнительная информация", "multiline"),
        _f("opisanie", "Описание", "multiline"),
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
    field = FIELD_BY_NAME.get(column)
    return field.label if field else column


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
