"""Construcción de las tablas finales, un archivo por flujo y año.

Toma los meses convertidos en `data/interim/` (todas las columnas como texto,
tal como las publica la DIAN) y, para cada mes:

1. Renombra, reubica o elimina columnas según `mapeo_columnas.csv`, la tabla
   de correspondencia revisada (ver notebook 0.1 y README). Si un mes trae
   una columna que la tabla no contempla, se detiene: una estructura nueva
   hay que revisarla antes de unificarla.
2. Limpia y corrige valores según las decisiones documentadas en el README:
   quita espacios y el ".0" que Excel agrega a los códigos, completa la
   subpartida a 10 dígitos, vacía los "0" que significan "no aplica",
   vacía los números de formulario publicados en notación científica y
   recupera nombres que la DIAN dejó como "no declarado o fuera de lista"
   cuando el código es válido (tablas en `colombia_dian_comex/tablas/`).
3. Agrega `PERIODO` (aaaamm) y los códigos de país M49 armonizados.
4. Asigna el tipo de cada columna según `esquema_final.csv`.

Después de escribir cada año se comprueba que sigue coincidiendo con los
totales de control de la DIAN y se cuenta cuántos valores no se pudieron
convertir a número o fecha, y se registra qué columnas tienen datos en cada
año (`cobertura_columnas.parquet`), que usan las consultas para no mostrar
columnas vacías.
"""

import logging
from functools import cache
from pathlib import Path

import fastexcel
import polars as pl

from colombia_dian_comex import utils
from colombia_dian_comex.mapping import load_column_mapping
from colombia_dian_comex.pipeline import (
    Flow,
    local_control_totals,
    read_control_totals,
    validate_month,
)

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).parent
SCHEMA_PATH = PACKAGE_DIR / "esquema_final.csv"
TABLES_DIR = PACKAGE_DIR / "tablas"
CORRELATIVA_FILENAME = "Correlativa-M-49-y-ALADI-04032025.xlsx"
COVERAGE_FILENAME = "cobertura_columnas.parquet"

# First month DIAN codes countries with M49 (Resolución 2386 de 2023 del DANE).
M49_SINCE = 202501

# Text DIAN writes when it couldn't translate a code into its name.
PLACEHOLDER_PATTERN = r"(?i)no declarad[ao] o fuera de lista"

# Name column -> (code column, table in tablas/) whose placeholder is replaced
# by the name of a valid code (README, decision 4).
RELABELS = {
    Flow.IMPORTACIONES: {
        "TIPO_IMPORTACION": ("COD_TIPO_IMPORTACION", "tipo_importacion"),
        "FORMA_PAGO": ("COD_FORMA_PAGO", "forma_pago"),
    },
    Flow.EXPORTACIONES: {
        "TIPO_DESPACHO": ("TIPO_DECLARACION", "tipo_despacho"),
    },
}

# Columns emptied where DIAN published the number in scientific notation,
# which drops digits (README, decision 5).
SCIENTIFIC_NOTATION_COLUMNS = {
    Flow.IMPORTACIONES: ["IDENTIFICACION_FORMULARIO"],
    Flow.EXPORTACIONES: [],
}
SCIENTIFIC_NOTATION_PATTERN = r"^-?\d+(\.\d+)?[Ee][+-]?\d+$"

# Tariff subheading column, padded to 10 digits.
SUBPARTIDA_COLUMNS = {
    Flow.IMPORTACIONES: "SUBPARTIDA_ARANCELARIA",
    Flow.EXPORTACIONES: "SUBPARTIDA",
}


@cache
def load_final_schema(flow: Flow) -> pl.DataFrame:
    """Read a flow's final columns, in order, with their type and treatment.

    Args:
        flow: Flow whose schema is read.

    Returns:
        One row per final column: ORDEN, COLUMNA, TIPO (texto, codigo,
        decimal, fecha or entero), CERO_ES_VACIO and NOTA.
    """
    return (
        pl.read_csv(SCHEMA_PATH, infer_schema_length=0)
        .filter(pl.col("FLUJO") == flow.value)
        .with_columns(
            pl.col("ORDEN").cast(pl.Int32),
            (pl.col("CERO_ES_VACIO") == "true").alias("CERO_ES_VACIO"),
        )
        .sort("ORDEN")
    )


@cache
def load_code_table(name: str) -> dict[str, str]:
    """Read a code -> name table from colombia_dian_comex/tablas/.

    Args:
        name: Table name, without extension (e.g. "forma_pago").

    Returns:
        Mapping of code to name.
    """
    df_table = pl.read_csv(TABLES_DIR / f"{name}.csv", infer_schema_length=0)
    return dict(zip(df_table["CODIGO"], df_table["NOMBRE"], strict=True))


@cache
def load_aladi_to_m49() -> dict[str, str]:
    """Read DIAN's official ALADI -> M49 country code correspondence.

    The correlativa lists some ALADI codes twice (e.g. 720, a current and a
    former country); the active row wins. ALADI codes without an M49 code
    (former countries, Colombian free trade zones, "no declarados") are left
    out, so they become null instead of a guessed code.

    Returns:
        Mapping of ALADI code to M49 code, both as text without padding.
    """
    df_corr = (
        fastexcel.read_excel(utils.project_dir("docs", CORRELATIVA_FILENAME))
        .load_sheet(0, header_row=6, dtypes="string")
        .to_polars()
        .rename({"Código M49": "M49", "Código ALADI": "ALADI"})
        .filter(
            pl.col("ALADI").str.contains(r"^\d+$"),
            pl.col("M49").str.contains(r"^\d+$"),
        )
        .sort(pl.col("Activo") == "1", descending=True)
        .unique("ALADI", keep="first")
    )
    return dict(zip(df_corr["ALADI"], df_corr["M49"], strict=True))


def interim_months(flow: Flow, year: int) -> list[int]:
    """List the converted months of a flow's year in data/interim/.

    Args:
        flow: Flow of the months.
        year: Year of the months.

    Returns:
        The months, as yyyymm, sorted.
    """
    folder = utils.data_interim_dir(flow.value, str(year))
    return sorted(
        int(path.stem[-6:]) for path in folder.glob(f"{flow.value}_??????.parquet")
    )


def _rename_month(
    lf: pl.LazyFrame, flow: Flow, period: int, df_mapping: pl.DataFrame
) -> pl.LazyFrame:
    """Rename, move or drop one month's original columns per the mapping table.

    Args:
        lf: The month's converted parquet, every column as text.
        flow: Flow of the month.
        period: Month, as yyyymm.
        df_mapping: The mapping table, from `load_column_mapping`.

    Returns:
        The month with its final column names (columns mapped to nothing dropped).

    Raises:
        ValueError: If a column has no mapping row for the month (a new
            layout, to be reviewed) or two columns map to the same final one.
    """
    df_month_map = df_mapping.filter(
        pl.col("FLUJO") == flow.value,
        pl.col("DESDE") <= period,
        # An empty HASTA means the column is still current ("hasta hoy").
        pl.col("HASTA").is_null() | (pl.col("HASTA") >= period),
    )
    final_names = dict(
        zip(
            df_month_map["COLUMNA_ORIGINAL"], df_month_map["COLUMNA_FINAL"], strict=True
        )
    )
    columns = lf.collect_schema().names()
    unmapped = [column for column in columns if column not in final_names]
    if unmapped:
        raise ValueError(
            f"{flow} {period}: columnas que mapeo_columnas.csv no contempla para ese mes: "
            f"{unmapped}. Revisar la estructura y agregarlas al mapeo antes de seguir."
        )
    # Dropped columns are only those that hold nothing but "1" (README); if
    # one ever carries another value, it has information and must be reviewed.
    dropped = [column for column in columns if final_names[column] is None]
    if dropped:
        df_values = lf.select(
            pl.col(dropped)
            .str.strip_chars()
            .replace("", None)
            .drop_nulls()
            .unique()
            .implode()
        ).collect()
        unexpected = {
            column: values
            for column in dropped
            if (values := [v for v in df_values[column][0] if v not in ("1", "1.0")])
        }
        if unexpected:
            raise ValueError(
                f"{flow} {period}: columnas marcadas como eliminadas traen valores "
                f"distintos de '1': {unexpected}. Revisar antes de seguir."
            )
    renames = {
        column: final_names[column]
        for column in columns
        if final_names[column] is not None
    }
    targets = list(renames.values())
    if len(targets) != len(set(targets)):
        raise ValueError(
            f"{flow} {period}: dos columnas van a la misma columna final: {renames}"
        )
    return lf.select(list(renames)).rename(renames)


def _typed(column: str, kind: str) -> pl.Expr:
    """Convert a cleaned text column to its final type.

    Args:
        column: Column name.
        kind: Type from esquema_final.csv.

    Returns:
        Expression with the typed column. Values that can't be converted
        become null; `typing_losses` counts them.
    """
    value = pl.col(column)
    if kind == "decimal":
        return value.cast(pl.Float64, strict=False)
    if kind == "fecha":
        # Only full yyyymmdd dates; anything else (yyyymm, codes) becomes null.
        return pl.when(value.str.contains(r"^\d{8}$")).then(
            value.str.to_date("%Y%m%d", strict=False)
        )
    if kind == "entero":
        return value.cast(pl.Int32, strict=False)
    return value


def unify_month(flow: Flow, period: int, typed: bool = True) -> pl.LazyFrame:
    """Turn one converted month into the flow's final columns.

    Args:
        flow: Flow of the month.
        period: Month, as yyyymm.
        typed: If False, every column is returned as cleaned text, before
            converting types (to count values lost in the conversion).

    Returns:
        The month with every final column, in order, as in esquema_final.csv.
    """
    df_schema = load_final_schema(flow)
    path = utils.data_interim_dir(
        flow.value, str(period // 100), f"{flow.value}_{period}.parquet"
    )
    lf = _rename_month(pl.scan_parquet(path), flow, period, load_column_mapping())

    present = lf.collect_schema().names()
    original_columns = [
        c for c in df_schema["COLUMNA"] if c != "PERIODO" and not c.endswith("_M49")
    ]
    lf = lf.with_columns(
        # Columns the month doesn't have are added empty.
        *[
            pl.lit(None, dtype=pl.String).alias(c)
            for c in original_columns
            if c not in present
        ],
    )
    # Surrounding spaces stripped and empty text as null, in every column.
    lf = lf.with_columns(
        pl.col(c).str.strip_chars().replace("", None) for c in original_columns
    )

    kinds = dict(zip(df_schema["COLUMNA"], df_schema["TIPO"], strict=True))
    codes = [c for c in original_columns if kinds[c] == "codigo"]
    zero_is_empty = df_schema.filter(pl.col("CERO_ES_VACIO"))["COLUMNA"].to_list()
    subpartida = SUBPARTIDA_COLUMNS[flow]
    lf = lf.with_columns(
        # Excel stores many codes as numbers: "3.0" -> "3", "9.000000" -> "9".
        pl.col(c).str.replace(r"^(-?\d+)\.0+$", "${1}")
        for c in codes
    ).with_columns(
        pl.col(subpartida).str.zfill(10),
        *[
            pl.when(pl.col(c).str.contains(r"^0+$"))
            .then(None)
            .otherwise(pl.col(c))
            .alias(c)
            for c in zero_is_empty
        ],
        *[
            pl.when(pl.col(c).str.contains(SCIENTIFIC_NOTATION_PATTERN))
            .then(None)
            .otherwise(pl.col(c))
            .alias(c)
            for c in SCIENTIFIC_NOTATION_COLUMNS[flow]
        ],
    )

    relabels = []
    for name_column, (code_column, table) in RELABELS[flow].items():
        recovered = pl.col(code_column).replace_strict(
            load_code_table(table), default=None
        )
        missing = pl.col(name_column).is_null() | pl.col(name_column).str.contains(
            PLACEHOLDER_PATTERN
        )
        relabels.append(
            pl.when(missing & recovered.is_not_null())
            .then(recovered)
            .otherwise(pl.col(name_column))
            .alias(name_column)
        )
    lf = lf.with_columns(relabels)

    aladi_to_m49 = load_aladi_to_m49()
    m49 = [
        (
            pl.col(c[:-4])
            if period >= M49_SINCE
            else pl.col(c[:-4]).replace_strict(aladi_to_m49, default=None)
        ).alias(c)
        for c in df_schema["COLUMNA"]
        if c.endswith("_M49")
    ]
    lf = lf.with_columns(*m49, pl.lit(str(period)).alias("PERIODO"))

    if typed:
        return lf.select(_typed(c, kinds[c]).alias(c) for c in df_schema["COLUMNA"])
    return lf.select(df_schema["COLUMNA"].to_list())


def final_path(flow: Flow, year: int) -> Path:
    """Where a flow's final table for one year is stored.

    Args:
        flow: Flow of the table.
        year: Year of the table.

    Returns:
        data/processed/<flow>_<year>.parquet.
    """
    return utils.data_processed_dir(f"{flow.value}_{year}.parquet")


def build_year(flow: Flow, year: int) -> Path:
    """Build a flow's final table for one year from its converted months.

    Written to a temporary file and renamed into place, so a failure never
    leaves a half-written table.

    Args:
        flow: Flow of the table.
        year: Year of the table.

    Returns:
        Path to the table.

    Raises:
        ValueError: If the year has no converted months.
    """
    periods = interim_months(flow, year)
    if not periods:
        raise ValueError(f"No hay meses convertidos de {flow} {year} en data/interim/.")
    path = final_path(flow, year)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    pl.concat([unify_month(flow, period) for period in periods]).sink_parquet(
        tmp_path, compression="zstd", compression_level=9
    )
    tmp_path.replace(path)
    return path


def typing_losses(flow: Flow, year: int) -> pl.DataFrame:
    """Count values that couldn't be converted to their final type.

    A value is lost when the cleaned text isn't empty nor only zeros but its
    typed value is: text in a number column, or something other than a valid
    yyyymmdd date in a date column (e.g. 20010229, 2008513 or 200111).

    Args:
        flow: Flow of the table.
        year: Year of the table.

    Returns:
        One row per column with lost values: FLUJO, ANIO, COLUMNA, TIPO,
        FILAS_PERDIDAS and EJEMPLOS (up to 5 distinct lost values).
    """
    df_schema = load_final_schema(flow).filter(
        pl.col("TIPO").is_in(["decimal", "fecha", "entero"])
    )
    lf_text = pl.concat(
        [
            unify_month(flow, period, typed=False)
            for period in interim_months(flow, year)
        ]
    )
    rows = []
    for column, kind in df_schema.select("COLUMNA", "TIPO").iter_rows():
        # Only zeros mean "no date" / "no value", not a lost value.
        lost = (
            pl.col(column).is_not_null()
            & ~pl.col(column).str.contains(r"^0+$")
            & _typed(column, kind).is_null()
        )
        df_lost = lf_text.select(
            lost.sum().alias("FILAS"),
            pl.col(column)
            .filter(lost)
            .unique()
            .head(5)
            .str.join(", ")
            .alias("EJEMPLOS"),
        ).collect()
        if df_lost["FILAS"][0]:
            rows.append(
                {
                    "FLUJO": flow.value,
                    "ANIO": year,
                    "COLUMNA": column,
                    "TIPO": kind,
                    "FILAS_PERDIDAS": df_lost["FILAS"][0],
                    "EJEMPLOS": df_lost["EJEMPLOS"][0],
                }
            )
    return pl.DataFrame(
        rows,
        schema={
            "FLUJO": pl.String,
            "ANIO": pl.Int32,
            "COLUMNA": pl.String,
            "TIPO": pl.String,
            "FILAS_PERDIDAS": pl.Int64,
            "EJEMPLOS": pl.String,
        },
    )


def validate_year(flow: Flow, year: int) -> pl.DataFrame:
    """Compare every month of a final table with DIAN's control totals.

    Args:
        flow: Flow of the table.
        year: Year of the table.

    Returns:
        One row per month and measure: FLUJO, PERIODO, MEDIDA, DATOS,
        CONTROL and OK, like `pipeline.validation_report`.
    """
    df_totals = read_control_totals(local_control_totals(flow))
    lf = pl.scan_parquet(final_path(flow, year))
    periods = (
        lf.select(pl.col("PERIODO").unique()).collect()["PERIODO"].sort().to_list()
    )
    rows = [
        {
            "FLUJO": flow.value,
            "PERIODO": period,
            "MEDIDA": check.measure,
            "DATOS": check.data,
            "CONTROL": check.control,
            "OK": check.ok,
        }
        for period in periods
        for check in validate_month(
            flow, period, df_totals, lf.filter(pl.col("PERIODO") == period)
        )
    ]
    return pl.DataFrame(rows)


def year_coverage(flow: Flow, year: int) -> pl.DataFrame:
    """Count, for each column of a final table, its rows with data.

    Args:
        flow: Flow of the table.
        year: Year of the table.

    Returns:
        One row per column: FLUJO, ANIO, COLUMNA, FILAS and FILAS_CON_DATOS.
    """
    lf = pl.scan_parquet(final_path(flow, year))
    columns = lf.collect_schema().names()
    counts = (
        lf.select(
            pl.len().alias("__FILAS"), *[pl.col(c).count().alias(c) for c in columns]
        )
        .collect()
        .row(0, named=True)
    )
    return pl.DataFrame(
        {
            "FLUJO": flow.value,
            "ANIO": year,
            "COLUMNA": columns,
            "FILAS": counts["__FILAS"],
            "FILAS_CON_DATOS": [counts[c] for c in columns],
        },
        schema={
            "FLUJO": pl.String,
            "ANIO": pl.Int32,
            "COLUMNA": pl.String,
            "FILAS": pl.Int64,
            "FILAS_CON_DATOS": pl.Int64,
        },
    )


def update_coverage(df_new: pl.DataFrame) -> Path:
    """Replace the given flows' and years' rows in the coverage table.

    Args:
        df_new: Coverage rows from `year_coverage`.

    Returns:
        Path to data/processed/cobertura_columnas.parquet.
    """
    path = utils.data_processed_dir(COVERAGE_FILENAME)
    if path.exists():
        keys = df_new.select("FLUJO", "ANIO").unique()
        df_new = pl.concat(
            [pl.read_parquet(path).join(keys, on=["FLUJO", "ANIO"], how="anti"), df_new]
        )
    df_new.sort("FLUJO", "ANIO", "COLUMNA").write_parquet(path)
    return path
