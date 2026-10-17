-- =====================================================================
-- DendroBASE: схема базы даных
--
-- УВАГА: гэтая схема адноўлена па кодзе DendroBASE_tkinter.py і
-- Add_to_base_new.py, а не выгружана з рэальнай базы. Тыпы слупкоў
-- выведзены з таго, як праграма іх апрацоўвае (лік / тэкст / дата).
-- Калі ў вас ёсць дзеючая база, лепш замяніць гэты файл рэальнай схемай:
--     pg_dump --schema-only -p 5433 -U postgres postgres > schema.sql
--
-- Выкананне:
--     psql -p 5433 -U postgres -d postgres -f schema.sql
-- =====================================================================

-- ---------------------------------------------------------------------
-- title: пробныя плошчы (ПП) і метаданыя дэндрахраналагічнай шкалы.
-- Адзін радок = адна пробная плошча. Натуральны ключ: n_probnoy_ploshchadi.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS title (
    id                                  serial PRIMARY KEY,
    n_probnoy_ploshchadi                text NOT NULL UNIQUE,   -- код ПП (= назва Excel-файла пры імпарце)

    -- Месцазнаходжанне
    shirota_grd                         double precision,       -- шырата, градусы
    dolgota_grd                         double precision,       -- даўгата, градусы
    vysota_nad_u_m                      double precision,       -- вышыня над узроўнем мора
    strana                              text,
    oblast                              text,
    rayon                               text,
    blizhajshij_naselennyj_punkt        text,
    leskhoz                             text,
    lesnichestvo                        text,
    kvartal                             text,
    vydel                               text,
    god_lesoustrojstva                  integer,

    -- Геабатанічнае раянаванне (запаўняецца ўручную або з geo_regions_polygons)
    geobotanicheskaya_zona              text,
    geobotanicheskaya_podzona           text,
    geobotanicheskij_okrug              text,
    geobotanicheskij_rajon              text,

    -- Характарыстыка дрэвастану
    tip_lesa                            text,
    tum                                 text,
    glavnaya_poroda                     text,                   -- скарачэнне пароды (гл. PORODA_DICT у кодзе)
    koef_sostava                        double precision,
    sostav_drevoj                       text,
    vozrast                             double precision,
    predely_variacii                    text,
    klass_vozrasta                      text,
    srednyaya_vysota_m                  double precision,
    srednij_diametr_sm                  double precision,
    polnota                             double precision,
    zapas_kub_m                         double precision,
    associaciya                         text,
    landshaft                           text,
    urochishche                         text,
    forma_relefa                        text,
    pochva                              text,
    kategoriya_zemel                    text,
    proiskhozhdenie                     text,
    ploshchad_vydela                    double precision,
    kategoriya_zashchitnosti            text,
    bonitet                             text,
    podrost                             text,
    podlesok                            text,
    vozdejstvie                         text,
    dopolnitelnaya_informaciya          text,

    -- Дэндрахраналагічная шкала
    n_dendrokhronologicheskoj_shkaly    text,
    n_journal                           text,                   -- нумар у журнале (з dendro_point_living.xlsx)
    drevesnaya_poroda                   text,                   -- лацінская назва віду
    data_otbora_obraztsov               date,
    data_predostavleniya_v_bazu_dannykh date,
    tip_obraztsov                       text,                   -- Керны / Спилы / Диски
    otbor_obraztsov_avtor               text,
    izmerenie_obraztsov_avtor           text,
    verifikatsiya_avtor                 text,
    standartizatsiya_avtor              text,
    kolichestvo_derevev_v_shkale_sht    integer,
    protyazhennost_shkaly_let           integer,
    pervyy_god                          integer,
    posledniy_god                       integer,
    mezhserialnyj_kof_korrelyatsii      double precision,
    srednij_kof_chuvstvitelnosti        double precision,
    dostupnost                          text,                   -- Открытый доступ / Ограниченный доступ / По запросу
    opisanie                            text
    -- слупок geom дадаецца ў блоку PostGIS у канцы файла
);

-- ---------------------------------------------------------------------
-- crn: абагульненая храналогія пробнай плошчы, адзін радок на год.
-- raw / std / res / ars - варыянты храналогіі (сырая, стандартызаваная,
-- рэзідуальная, ARSTAN), num - колькасць серый за год.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crn (
    id                      serial PRIMARY KEY,
    n_probnoy_ploshchadi    text NOT NULL REFERENCES title (n_probnoy_ploshchadi) ON DELETE CASCADE,
    year                    integer NOT NULL,
    num                     double precision,
    raw                     double precision,
    std                     double precision,
    res                     double precision,
    ars                     double precision,
    CONSTRAINT crn_probe_year_unique UNIQUE (n_probnoy_ploshchadi, year)
);

-- ---------------------------------------------------------------------
-- series: індывідуальныя серыі (асобныя дрэвы/керны) у "доўгім" фармаце:
-- адзін радок = (ПП, серыя, год, значэнне). Назва серыі - тэкст (1, 1a, 13b...).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS series (
    id                      serial PRIMARY KEY,
    n_probnoy_ploshchadi    text NOT NULL REFERENCES title (n_probnoy_ploshchadi) ON DELETE CASCADE,
    year                    integer NOT NULL,
    series_name             text NOT NULL,
    value                   double precision,
    CONSTRAINT series_probe_series_year_unique UNIQUE (n_probnoy_ploshchadi, series_name, year)
);

-- Індэксы (тыя ж, што стварае Add_to_base_new.py)
CREATE INDEX IF NOT EXISTS idx_crn_plot_year    ON crn    (n_probnoy_ploshchadi, year);
CREATE INDEX IF NOT EXISTS idx_series_plot_year ON series (n_probnoy_ploshchadi, year);

-- ---------------------------------------------------------------------
-- PostGIS (неабавязкова, але патрэбна для карты і кнопак "Абнавіць геаметрыю").
-- Калі PostGIS не ўсталяваны, закаментуйце або выдаліце гэты блок:
-- праграма працуе і без яго, толькі геаметрыя будзе недаступная.
-- ---------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS postgis;

-- Пункт у WGS84; праграма разлічвае яго з shirota_grd / dolgota_grd
ALTER TABLE title ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);
CREATE INDEX IF NOT EXISTS idx_title_geom ON title USING GIST (geom);

-- Неабавязкова: табліца палігонаў геабатанічнага раянавання, якую
-- Add_to_base_new.py выкарыстоўвае для аўтазапаўнення палёў geobotanicheskaya_*.
-- У праекце яе няма: яна загружаецца з шэйп-файла (напрыклад, shp2pgsql або QGIS)
-- і павінна мець слупкі zone, subzone, okrug, text і геаметрыю geom.
