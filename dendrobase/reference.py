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


TITLE_FIELDS: tuple[TitleField, ...] = (
    TitleField("n_probnoy_ploshchadi", "N пробной площади"),
    TitleField("shirota_grd", "Широта, грд", "number"),
    TitleField("dolgota_grd", "Долгота, грд", "number"),
    TitleField("vysota_nad_u_m", "Высота над у.м.", "number"),
    TitleField("strana", "Страна"),
    TitleField("oblast", "Область"),
    TitleField("rayon", "Район"),
    TitleField("blizhajshij_naselennyj_punkt", "Ближайший населенный пункт"),
    TitleField("leskhoz", "Лесхоз"),
    TitleField("lesnichestvo", "Лесничество"),
    TitleField("kvartal", "Квартал"),
    TitleField("vydel", "Выдел"),
    TitleField("god_lesoustrojstva", "Год лесоустройства", "integer"),
    TitleField("geobotanicheskaya_zona", "Геоботаническая зона", "choice", tuple(GEO_ZONA_LIST)),
    TitleField("geobotanicheskaya_podzona", "Геоботаническая подзона", "choice", tuple(GEO_PODZONA_LIST)),
    TitleField("geobotanicheskij_okrug", "Геоботанический округ", "choice", tuple(GEO_OKRUG_LIST)),
    TitleField("geobotanicheskij_rajon", "Геоботанический район", "choice", tuple(GEO_RAJON_LIST)),
    TitleField("tip_lesa", "Тип леса", "choice", tuple(TIP_LESA_LIST)),
    TitleField("tum", "ТУМ"),
    TitleField("glavnaya_poroda", "Главная порода", "choice", tuple(PORODA_LIST)),
    TitleField("koef_sostava", "Коэфф. состава", "number"),
    TitleField("sostav_drevoj", "Состав"),
    TitleField("vozrast", "Возраст средний", "number"),
    TitleField("predely_variacii", "Пределы вариации"),
    TitleField("klass_vozrasta", "Класс возраста"),
    TitleField("srednyaya_vysota_m", "Средняя высота, м", "number"),
    TitleField("srednij_diametr_sm", "Средний диаметр, см", "number"),
    TitleField("polnota", "Полнота", "number"),
    TitleField("zapas_kub_m", "Запас, куб.м.", "number"),
    TitleField("associaciya", "Ассоциация"),
    TitleField("landshaft", "Ландшафт"),
    TitleField("urochishche", "Урочище"),
    TitleField("forma_relefa", "Форма рельефа"),
    TitleField("pochva", "Почва"),
    TitleField("kategoriya_zemel", "Категория земель"),
    TitleField("proiskhozhdenie", "Происхождение"),
    TitleField("ploshchad_vydela", "Площадь выдела", "number"),
    TitleField("kategoriya_zashchitnosti", "Категория защитности"),
    TitleField("bonitet", "Бонитет"),
    TitleField("podrost", "Подрост"),
    TitleField("podlesok", "Подлесок"),
    TitleField("vozdejstvie", "Воздействие"),
    TitleField("dopolnitelnaya_informaciya", "Дополнительная информация", "multiline"),
    TitleField("n_dendrokhronologicheskoj_shkaly", "N дендрохронологической шкалы"),
    TitleField("n_journal", "N журнала"),
    TitleField("drevesnaya_poroda", "Древесная порода", "choice", tuple(DREVESNAYA_PORODA_LIST)),
    TitleField("data_otbora_obraztsov", "Дата отбора образцов", "date"),
    TitleField("data_predostavleniya_v_bazu_dannykh", "Дата предоставления в базу данных", "date"),
    TitleField("tip_obraztsov", "Тип образцов", "choice", tuple(TIP_OBRAZTSOV_LIST)),
    TitleField("otbor_obraztsov_avtor", "Отбор образцов (автор)"),
    TitleField("izmerenie_obraztsov_avtor", "Измерение образцов (автор)"),
    TitleField("verifikatsiya_avtor", "Верификация (автор)"),
    TitleField("standartizatsiya_avtor", "Стандартизация (автор)"),
    TitleField("kolichestvo_derevev_v_shkale_sht", "Количество деревьев в шкале, шт", "integer"),
    TitleField("protyazhennost_shkaly_let", "Протяженность шкалы, лет", "integer"),
    TitleField("pervyy_god", "Первый год", "integer"),
    TitleField("posledniy_god", "Последний год", "integer"),
    TitleField("mezhserialnyj_kof_korrelyatsii", "Межсериальный коэффициент корреляции", "number"),
    TitleField("srednij_kof_chuvstvitelnosti", "Средний коэффициент чувствительности", "number"),
    TitleField("dostupnost", "Доступность", "choice", tuple(DOSTUPNOST_LIST)),
    TitleField("opisanie", "Описание", "multiline"),
)

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
