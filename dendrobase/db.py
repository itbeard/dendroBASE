"""Доступ да PostgreSQL.

Кожны публічны метад выконваецца ў сваёй транзакцыі. Памылкі psycopg2 загортваюцца
ў DatabaseError (або ConnectionFailed, калі злучэнне страчана), каб інтэрфейс не
залежаў ад драйвера. Назвы слупкоў ніколі не ўстаўляюцца ў SQL радком: толькі праз
psycopg2.sql.Identifier і пасля праверкі па спісе слупкоў табліцы.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterable, Iterator, Mapping

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection, cursor as PgCursor

from .config import DatabaseSettings
from .i18n import tr
from .models import CrnRow, FilterCriteria, ProbePoint, ProbeSummary, QueryResult, SeriesMatrix, SeriesValue
from .parsing import natural_key
from .reference import PROBE_KEY, READONLY_COLUMNS, ZONA_NORMALIZATION

log = logging.getLogger(__name__)

REQUIRED_TABLES = ("title", "crn", "series")
GEO_POLYGON_TABLE = "geo_regions_polygons"
_GEOMETRY_COLUMN_NAMES = ("geom", "geometry", "the_geom", "wkb_geometry")


class DatabaseError(Exception):
    """Памылка пры працы з базай даных."""


class ConnectionFailed(DatabaseError):
    """Не атрымалася падключыцца, або злучэнне страчана."""


def _describe(exc: BaseException) -> str:
    message = getattr(exc, "pgerror", None) or str(exc) or exc.__class__.__name__
    return str(message).strip()


def _safe_rollback(conn: PgConnection) -> None:
    try:
        conn.rollback()
    except psycopg2.Error:
        pass


def _year_conditions(alias: str, year_from: int | None, year_to: int | None,
                     params: list[object]) -> list[sql.Composable]:
    conditions: list[sql.Composable] = []
    if year_from is not None:
        conditions.append(sql.SQL("{}.year >= %s").format(sql.Identifier(alias)))
        params.append(year_from)
    if year_to is not None:
        conditions.append(sql.SQL("{}.year <= %s").format(sql.Identifier(alias)))
        params.append(year_to)
    return conditions


class DatabaseManager:
    def __init__(self, settings: DatabaseSettings, *, connect: bool = True) -> None:
        self.settings = settings
        self._conn: PgConnection | None = None
        self._title_columns: list[str] | None = None
        if connect:
            self.connect()

    # ------------------------------------------------------------------ злучэнне
    def connect(self) -> None:
        log.info("Падключэнне да %s", self.settings.describe())
        try:
            self._conn = psycopg2.connect(
                **self.settings.connect_kwargs(), client_encoding="UTF8", connect_timeout=10
            )
        except psycopg2.Error as exc:
            self._conn = None
            raise ConnectionFailed(
                tr("Не атрымалася падключыцца да {target}:\n{error}").format(target=self.settings.describe(), error=_describe(exc))
            ) from exc
        log.info("Падключана да %s", self.settings.describe())

    def close(self) -> None:
        if self._conn is not None:
            try:
                if not self._conn.closed:
                    self._conn.close()
            except psycopg2.Error:
                pass
            self._conn = None
            log.info("Злучэнне з БД зачынена")

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.closed

    def _connection(self) -> PgConnection:
        if not self.is_connected:
            self.connect()
        assert self._conn is not None
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[PgCursor]:
        """Курсор у транзакцыі: commit пры выхадзе, rollback пры выключэнні."""
        conn = self._connection()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except psycopg2.Error as exc:
            if conn.closed:
                log.error("Злучэнне з БД страчана: %s", _describe(exc))
                self.close()
                raise ConnectionFailed(tr("Злучэнне з базай даных страчана:\n{error}").format(error=_describe(exc))) from exc
            _safe_rollback(conn)
            log.error("Памылка SQL: %s", _describe(exc))
            raise DatabaseError(_describe(exc)) from exc
        except BaseException:
            _safe_rollback(conn)
            raise
        finally:
            try:
                cur.close()
            except psycopg2.Error:
                pass

    def _fetchall(self, query: sql.Composable | str, params: object = None) -> list[tuple]:
        with self.transaction() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def _fetchone(self, query: sql.Composable | str, params: object = None) -> tuple | None:
        with self.transaction() as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def _execute(self, query: sql.Composable | str, params: object = None) -> int:
        with self.transaction() as cur:
            cur.execute(query, params)
            return cur.rowcount

    # --------------------------------------------------------------------- схема
    def check_schema(self) -> list[str]:
        """Спіс абавязковых табліц, якіх няма ў базе."""
        rows = self._fetchall(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = ANY(%s)",
            (list(REQUIRED_TABLES),),
        )
        present = {row[0] for row in rows}
        return [table for table in REQUIRED_TABLES if table not in present]

    def table_exists(self, table: str) -> bool:
        row = self._fetchone(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = %s)",
            (table,),
        )
        return bool(row and row[0])

    def table_columns(self, table: str) -> list[str]:
        rows = self._fetchall(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position",
            (table,),
        )
        return [row[0] for row in rows]

    def get_title_columns(self, *, refresh: bool = False) -> list[str]:
        if self._title_columns is None or refresh:
            self._title_columns = self.table_columns("title")
        return list(self._title_columns)

    def count_rows(self, table: str) -> int:
        if table not in REQUIRED_TABLES:
            raise ValueError(f"Невядомая табліца: {table}")
        row = self._fetchone(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
        return int(row[0]) if row else 0

    def has_postgis(self) -> bool:
        try:
            row = self._fetchone("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
        except DatabaseError as exc:
            log.warning("Не атрымалася праверыць PostGIS: %s", exc)
            return False
        return bool(row and row[0])

    def has_geometry_column(self) -> bool:
        return "geom" in self.get_title_columns()

    # --------------------------------------------------------------------- title
    def get_all_probes(self) -> list[str]:
        rows = self._fetchall(
            sql.SQL("SELECT {key} FROM title ORDER BY {key}").format(key=sql.Identifier(PROBE_KEY))
        )
        return [row[0] for row in rows]

    def search_probes(self, text: str) -> list[str]:
        if not text:
            return self.get_all_probes()
        rows = self._fetchall(
            sql.SQL("SELECT {key} FROM title WHERE {key} ILIKE %s ORDER BY {key}").format(
                key=sql.Identifier(PROBE_KEY)
            ),
            (f"%{text}%",),
        )
        return [row[0] for row in rows]

    def list_probes(self, search: str = "") -> list[ProbeSummary]:
        """Кароткія звесткі пра ПП для спіса: парода, гады шкалы, колькасць дрэў, ці ёсць каардынаты."""
        params: list[object] = []
        where = sql.SQL("")
        if search:
            where = sql.SQL(" WHERE {key} ILIKE %s").format(key=sql.Identifier(PROBE_KEY))
            params.append(f"%{search}%")
        query = sql.SQL(
            "SELECT {key}, glavnaya_poroda, drevesnaya_poroda, pervyy_god, posledniy_god, "
            "kolichestvo_derevev_v_shkale_sht, "
            "(shirota_grd IS NOT NULL AND dolgota_grd IS NOT NULL AND shirota_grd <> 0 AND dolgota_grd <> 0) "
            "FROM title{where} ORDER BY {key}"
        ).format(key=sql.Identifier(PROBE_KEY), where=where)

        def as_int(value: object) -> int | None:
            return int(value) if value is not None else None  # type: ignore[call-overload]

        return [
            ProbeSummary(name, poroda, species, as_int(first), as_int(last), as_int(trees), bool(coords))
            for name, poroda, species, first, last, trees, coords in self._fetchall(query, params)
        ]

    def get_probe_info(self, probe: str) -> dict[str, object] | None:
        with self.transaction() as cur:
            cur.execute(
                sql.SQL("SELECT * FROM title WHERE {key} = %s").format(key=sql.Identifier(PROBE_KEY)),
                (probe,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))

    def get_probe_points(self) -> list[ProbePoint]:
        """ПП з каардынатамі для мапы (нулявыя каардынаты лічацца незададзенымі)."""
        rows = self._fetchall(
            sql.SQL(
                "SELECT {key}, shirota_grd, dolgota_grd, glavnaya_poroda, pervyy_god, posledniy_god, "
                "kolichestvo_derevev_v_shkale_sht FROM title "
                "WHERE shirota_grd IS NOT NULL AND dolgota_grd IS NOT NULL ORDER BY {key}"
            ).format(key=sql.Identifier(PROBE_KEY))
        )
        points: list[ProbePoint] = []
        for name, lat, lon, poroda, first_year, last_year, trees in rows:
            if not lat or not lon:
                continue
            points.append(ProbePoint(
                name, float(lat), float(lon), poroda,
                int(first_year) if first_year is not None else None,
                int(last_year) if last_year is not None else None,
                int(trees) if trees is not None else None,
            ))
        return points

    def count_with_coords(self) -> int:
        row = self._fetchone(
            "SELECT count(*) FROM title WHERE shirota_grd IS NOT NULL AND dolgota_grd IS NOT NULL"
        )
        return int(row[0]) if row else 0

    def upsert_title(self, data: Mapping[str, object]) -> None:
        """Дадаць або абнавіць радок ПП. Ключ: n_probnoy_ploshchadi. Слупкі id і geom ігнаруюцца."""
        probe = data.get(PROBE_KEY)
        if not probe:
            raise ValueError(tr("Код пробнай плошчы ({column}) абавязковы").format(column=PROBE_KEY))
        known = set(self.get_title_columns())
        unknown = [column for column in data if column not in known]
        if unknown:
            raise ValueError(tr("У табліцы title няма слупкоў: {columns}").format(columns=", ".join(unknown)))
        columns = [PROBE_KEY] + [c for c in data if c != PROBE_KEY and c not in READONLY_COLUMNS]
        values = [data[c] for c in columns]
        update_columns = columns[1:]
        query = sql.SQL("INSERT INTO title ({cols}) VALUES ({vals})").format(
            cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            vals=sql.SQL(", ").join([sql.Placeholder()] * len(columns)),
        )
        if update_columns:
            query += sql.SQL(" ON CONFLICT ({key}) DO UPDATE SET {sets}").format(
                key=sql.Identifier(PROBE_KEY),
                sets=sql.SQL(", ").join(
                    sql.SQL("{c} = EXCLUDED.{c}").format(c=sql.Identifier(c)) for c in update_columns
                ),
            )
        else:
            query += sql.SQL(" ON CONFLICT ({key}) DO NOTHING").format(key=sql.Identifier(PROBE_KEY))
        self._execute(query, values)
        log.info("ПП %s захавана (%d палёў)", probe, len(update_columns))

    # ----------------------------------------------------------------------- crn
    def get_crn(self, probe: str, year_from: int | None = None, year_to: int | None = None) -> list[CrnRow]:
        params: list[object] = [probe]
        conditions = [sql.SQL("c.{} = %s").format(sql.Identifier(PROBE_KEY))]
        conditions += _year_conditions("c", year_from, year_to, params)
        query = sql.SQL(
            "SELECT c.year, c.num, c.raw, c.std, c.res, c.ars FROM crn c WHERE {} ORDER BY c.year"
        ).format(sql.SQL(" AND ").join(conditions))
        return [CrnRow(*row) for row in self._fetchall(query, params)]

    def upsert_crn_rows(self, probe: str, rows: Iterable[CrnRow], *, overwrite: bool = True) -> int:
        """Запісаць радкі CRN. overwrite=False пакідае існуючыя гады некранутымі. Вяртае лік запісаных."""
        if overwrite:
            conflict = sql.SQL(
                "ON CONFLICT ({key}, year) DO UPDATE SET num = EXCLUDED.num, raw = EXCLUDED.raw, "
                "std = EXCLUDED.std, res = EXCLUDED.res, ars = EXCLUDED.ars"
            )
        else:
            conflict = sql.SQL("ON CONFLICT ({key}, year) DO NOTHING")
        query = sql.SQL(
            "INSERT INTO crn ({key}, year, num, raw, std, res, ars) VALUES (%s, %s, %s, %s, %s, %s, %s) {conflict}"
        ).format(key=sql.Identifier(PROBE_KEY), conflict=conflict.format(key=sql.Identifier(PROBE_KEY)))
        written = 0
        with self.transaction() as cur:
            for row in rows:
                cur.execute(query, (probe, row.year, row.num, row.raw, row.std, row.res, row.ars))
                written += cur.rowcount
        log.info("CRN %s: запісана %d радкоў", probe, written)
        return written

    def upsert_crn(self, probe: str, row: CrnRow) -> int:
        return self.upsert_crn_rows(probe, [row])

    def delete_crn(self, probe: str, year: int) -> int:
        count = self._execute(
            sql.SQL("DELETE FROM crn WHERE {key} = %s AND year = %s").format(key=sql.Identifier(PROBE_KEY)),
            (probe, year),
        )
        log.info("CRN %s: выдалены год %s (%d радкоў)", probe, year, count)
        return count

    # -------------------------------------------------------------------- series
    def get_series_values(self, probe: str, year_from: int | None = None, year_to: int | None = None,
                          name_filter: str | None = None) -> list[SeriesValue]:
        params: list[object] = [probe]
        conditions = [sql.SQL("s.{} = %s").format(sql.Identifier(PROBE_KEY))]
        conditions += _year_conditions("s", year_from, year_to, params)
        if name_filter:
            conditions.append(sql.SQL("s.series_name ILIKE %s"))
            params.append(f"%{name_filter}%")
        query = sql.SQL(
            "SELECT s.year, s.series_name, s.value FROM series s WHERE {} ORDER BY s.year, s.series_name"
        ).format(sql.SQL(" AND ").join(conditions))
        return [SeriesValue(year, name, float(value) if value is not None else None)  # type: ignore[arg-type]
                for year, name, value in self._fetchall(query, params)]

    def get_series_matrix(self, probe: str, year_from: int | None = None,
                          year_to: int | None = None) -> SeriesMatrix | None:
        values = self.get_series_values(probe, year_from, year_to)
        if not values:
            return None
        years = sorted({v.year for v in values})
        names = sorted({v.series_name for v in values}, key=natural_key)
        table = {(v.year, v.series_name): v.value for v in values if v.value is not None}
        return SeriesMatrix(years=years, series=names, values=table)

    def upsert_series_values(self, probe: str, values: Iterable[SeriesValue], *, overwrite: bool = True) -> int:
        conflict = (
            sql.SQL("ON CONFLICT ({key}, series_name, year) DO UPDATE SET value = EXCLUDED.value")
            if overwrite else sql.SQL("ON CONFLICT ({key}, series_name, year) DO NOTHING")
        )
        query = sql.SQL(
            "INSERT INTO series ({key}, year, series_name, value) VALUES (%s, %s, %s, %s) {conflict}"
        ).format(key=sql.Identifier(PROBE_KEY), conflict=conflict.format(key=sql.Identifier(PROBE_KEY)))
        written = 0
        with self.transaction() as cur:
            for item in values:
                cur.execute(query, (probe, item.year, item.series_name, item.value))
                written += cur.rowcount
        log.info("SERIES %s: запісана %d значэнняў", probe, written)
        return written

    def delete_series(self, probe: str, series_name: str, year: int) -> int:
        return self._execute(
            sql.SQL("DELETE FROM series WHERE {key} = %s AND series_name = %s AND year = %s").format(
                key=sql.Identifier(PROBE_KEY)
            ),
            (probe, series_name, year),
        )

    # ------------------------------------------------------------------- фільтры
    def get_unique_drevesnaya_poroda(self) -> list[str]:
        rows = self._fetchall(
            "SELECT DISTINCT drevesnaya_poroda FROM title "
            "WHERE drevesnaya_poroda IS NOT NULL AND drevesnaya_poroda <> '' ORDER BY drevesnaya_poroda"
        )
        return [row[0] for row in rows]

    def get_filtered_crn(self, criteria: FilterCriteria) -> tuple[list[str], list[tuple]]:
        """Выбарка CRN з метаданымі ПП па крытэрыях укладкі «Фільтры і пошук»."""
        params: list[object] = []
        conditions: list[sql.Composable] = []
        equals = (
            ("drevesnaya_poroda", criteria.drevesnaya_poroda),
            ("geobotanicheskaya_zona", criteria.geo_zona),
            ("geobotanicheskaya_podzona", criteria.geo_podzona),
            ("geobotanicheskij_okrug", criteria.geo_okrug),
            ("geobotanicheskij_rajon", criteria.geo_rajon),
        )
        for column, value in equals:
            if value:
                conditions.append(sql.SQL("t.{} = %s").format(sql.Identifier(column)))
                params.append(value)
        if criteria.tip_lesa_keyword:
            conditions.append(sql.SQL("t.tip_lesa ILIKE %s"))
            params.append(f"%{criteria.tip_lesa_keyword}%")
        conditions += _year_conditions("c", criteria.year_from, criteria.year_to, params)
        where = sql.SQL(" AND ").join(conditions) if conditions else sql.SQL("TRUE")

        select = [
            sql.SQL("t.{} AS probe_name").format(sql.Identifier(PROBE_KEY)),
            sql.SQL("t.glavnaya_poroda AS species"),
            sql.SQL("t.drevesnaya_poroda AS wood_species"),
            sql.SQL("t.geobotanicheskaya_zona AS geo_zona"),
            sql.SQL("t.geobotanicheskaya_podzona AS geo_podzona"),
            sql.SQL("t.geobotanicheskij_okrug AS geo_okrug"),
            sql.SQL("t.geobotanicheskij_rajon AS geo_rajon"),
            sql.SQL("t.tip_lesa AS forest_type"),
            sql.SQL("c.year"),
        ] + [sql.SQL("c.{}").format(sql.Identifier(c)) for c in criteria.crn_columns]
        query = sql.SQL(
            "SELECT {select} FROM title t JOIN crn c ON t.{key} = c.{key} WHERE {where} ORDER BY t.{key}, c.year"
        ).format(select=sql.SQL(", ").join(select), key=sql.Identifier(PROBE_KEY), where=where)
        with self.transaction() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        return columns, rows

    # ------------------------------------------------------------------ PostGIS
    def _require_postgis(self) -> None:
        if not self.has_postgis():
            raise DatabaseError(tr("PostGIS не ўсталяваны. Выканайце ў базе: CREATE EXTENSION postgis;"))
        if not self.has_geometry_column():
            raise DatabaseError(tr("У табліцы title няма слупка geom. Выканайце блок PostGIS з schema.sql."))

    def update_geometry(self, probe: str) -> int:
        self._require_postgis()
        count = self._execute(
            sql.SQL(
                "UPDATE title SET geom = ST_SetSRID(ST_MakePoint(dolgota_grd, shirota_grd), 4326) "
                "WHERE {key} = %s AND shirota_grd IS NOT NULL AND dolgota_grd IS NOT NULL "
                "AND shirota_grd <> 0 AND dolgota_grd <> 0"
            ).format(key=sql.Identifier(PROBE_KEY)),
            (probe,),
        )
        log.info("Геаметрыя %s: абноўлена %d радкоў", probe, count)
        return count

    def update_geometry_all(self, *, only_missing: bool = False) -> int:
        self._require_postgis()
        query = (
            "UPDATE title SET geom = ST_SetSRID(ST_MakePoint(dolgota_grd, shirota_grd), 4326) "
            "WHERE shirota_grd IS NOT NULL AND dolgota_grd IS NOT NULL AND shirota_grd <> 0 AND dolgota_grd <> 0"
        )
        if only_missing:
            query += " AND geom IS NULL"
        count = self._execute(query)
        log.info("Геаметрыя: абноўлена %d радкоў", count)
        return count

    # ---------------------------------------------------------------- SQL-акно
    def execute_sql(self, query: str) -> QueryResult:
        """Адвольны SQL з акна «SQL-запыт». Выконваецца як ёсць, у адной транзакцыі."""
        log.info("SQL з акна запытаў: %s", " ".join(query.split())[:500])
        with self.transaction() as cur:
            cur.execute(query)
            if cur.description:
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                return QueryResult(columns=columns, rows=rows, rowcount=len(rows))
            return QueryResult(rowcount=cur.rowcount)

    # ------------------------------------------------------ дапамога імпарту
    def _has_constraint(self, table: str, columns: list[str], types: str) -> bool:
        row = self._fetchone(
            """
            SELECT EXISTS (
              SELECT 1 FROM pg_constraint c
              JOIN pg_class t ON t.oid = c.conrelid
              JOIN pg_namespace n ON n.oid = t.relnamespace
              WHERE t.relname = %s AND n.nspname = current_schema() AND c.contype = ANY(%s::"char"[])
                AND (SELECT array_agg(a.attname::text ORDER BY k.ord)
                     FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
                     JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum) = %s::text[]
            )
            """,
            (table, list(types), columns),
        )
        return bool(row and row[0])

    def ensure_constraints(self) -> list[str]:
        """Дадаць ключы, унікальныя абмежаванні і індэксы, калі іх яшчэ няма. Вяртае паведамленні для логу."""
        messages: list[str] = []
        key = PROBE_KEY

        def run(label: str, statement: str, needed: bool = True) -> None:
            if not needed:
                messages.append(f"{label}: ужо ёсць")
                return
            try:
                self._execute(statement)
                messages.append(f"{label}: дададзена")
            except DatabaseError as exc:
                messages.append(f"{label}: прапушчана ({exc.splitlines()[0]})")

        for table in ("title", "crn", "series"):
            run(f"PRIMARY KEY {table}(id)", f"ALTER TABLE {table} ADD PRIMARY KEY (id)",
                needed=not self._has_constraint(table, ["id"], "p"))
        run(f"UNIQUE title({key})",
            f"ALTER TABLE title ADD CONSTRAINT title_{key}_unique UNIQUE ({key})",
            needed=not self._has_constraint("title", [key], "up"))
        for table in ("crn", "series"):
            run(f"FOREIGN KEY {table}({key}) -> title",
                f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_title FOREIGN KEY ({key}) "
                f"REFERENCES title ({key}) ON DELETE CASCADE",
                needed=not self._has_constraint(table, [key], "f"))
        run("UNIQUE crn(ПП, год)",
            f"ALTER TABLE crn ADD CONSTRAINT crn_probe_year_unique UNIQUE ({key}, year)",
            needed=not self._has_constraint("crn", [key, "year"], "up"))
        run("UNIQUE series(ПП, серыя, год)",
            f"ALTER TABLE series ADD CONSTRAINT series_probe_series_year_unique UNIQUE ({key}, series_name, year)",
            needed=not self._has_constraint("series", [key, "series_name", "year"], "up"))
        run("INDEX crn(ПП, год)", f"CREATE INDEX IF NOT EXISTS idx_crn_plot_year ON crn ({key}, year)")
        run("INDEX series(ПП, год)", f"CREATE INDEX IF NOT EXISTS idx_series_plot_year ON series ({key}, year)")
        if self.has_postgis() and self.has_geometry_column():
            run("INDEX title(geom)", "CREATE INDEX IF NOT EXISTS idx_title_geom ON title USING GIST (geom)")
        else:
            messages.append("INDEX title(geom): прапушчана, няма PostGIS або слупка geom")
        return messages

    def set_journal_number(self, probe: str, value: str) -> int:
        return self._execute(
            sql.SQL("UPDATE title SET n_journal = %s WHERE LOWER({key}) = LOWER(%s)").format(
                key=sql.Identifier(PROBE_KEY)
            ),
            (value, probe),
        )

    def assign_geobotany_from_polygons(self, table: str = GEO_POLYGON_TABLE) -> int:
        """Ачысціць геабатанічныя палі ўсіх ПП і запоўніць іх па палігонах табліцы раянавання.

        Увага: значэнні, уведзеныя ўручную, губляюцца. Усё адбываецца ў адной транзакцыі.
        """
        self._require_postgis()
        if not self.table_exists(table):
            raise DatabaseError(f"Табліца {table} не існуе")
        columns = self.table_columns(table)
        geometry_column = next((c for c in columns if c.lower() in _GEOMETRY_COLUMN_NAMES), None)
        if geometry_column is None:
            raise DatabaseError(f"У табліцы {table} няма слупка з геаметрыяй")
        mapping = {
            "zone": "geobotanicheskaya_zona",
            "subzone": "geobotanicheskaya_podzona",
            "okrug": "geobotanicheskij_okrug",
            "text": "geobotanicheskij_rajon",
        }
        assignments = [
            sql.SQL("{} = g.{}").format(sql.Identifier(target), sql.Identifier(source))
            for source, target in mapping.items() if source in columns
        ]
        if not assignments:
            raise DatabaseError(f"У табліцы {table} няма слупкоў zone / subzone / okrug / text")
        with self.transaction() as cur:
            cur.execute(
                "UPDATE title SET geobotanicheskaya_zona = NULL, geobotanicheskaya_podzona = NULL, "
                "geobotanicheskij_okrug = NULL, geobotanicheskij_rajon = NULL"
            )
            cleared = cur.rowcount
            cur.execute(
                sql.SQL(
                    "UPDATE title AS t SET {sets} FROM {table} AS g "
                    "WHERE t.geom IS NOT NULL AND ST_Within(t.geom, g.{geom})"
                ).format(
                    sets=sql.SQL(", ").join(assignments),
                    table=sql.Identifier(table),
                    geom=sql.Identifier(geometry_column),
                )
            )
            updated = cur.rowcount
        log.info("Геабатанічныя палі: ачышчана %d, запоўнена па палігонах %d", cleared, updated)
        return updated

    def normalize_zones(self, mapping: Mapping[str, str] = ZONA_NORMALIZATION) -> int:
        total = 0
        with self.transaction() as cur:
            for wrong, correct in mapping.items():
                cur.execute(
                    "UPDATE title SET geobotanicheskaya_zona = %s WHERE geobotanicheskaya_zona = %s",
                    (correct, wrong),
                )
                total += cur.rowcount
        return total
