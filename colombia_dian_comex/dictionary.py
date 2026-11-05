"""Genera el diccionario de datos (`DICCIONARIO.md`).

Se corre con `colombia-dian-dictionary` (o `python -m
colombia_dian_comex.dictionary`) cuando cambian las columnas: por ejemplo,
después de agregar una columna nueva de la DIAN a `mapeo_columnas.csv` y
`esquema_final.csv`, o cuando las tablas cubren un año más.

No compara con la versión anterior: arma el diccionario desde cero con el
estado actual del proyecto. Cada parte sale de una fuente:

- columnas, orden, tipo y notas: `esquema_final.csv`;
- nombres con que la DIAN publicó cada columna: `mapeo_columnas.csv`;
- años en que cada columna tiene datos: `data/processed/cobertura_columnas.parquet`
  (se descarga del release si no está en local).
"""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import polars as pl

from colombia_dian_comex import utils
from colombia_dian_comex.build import COVERAGE_FILENAME, load_final_schema
from colombia_dian_comex.mapping import load_column_mapping
from colombia_dian_comex.pipeline import Flow
from colombia_dian_comex.query import download_release_asset

logger = logging.getLogger(__name__)

DICTIONARY_PATH = utils.project_dir("DICCIONARIO.md")

# Nombre con que se muestra cada tipo de esquema_final.csv.
TYPE_LABELS = {
    "texto": "texto",
    "codigo": "código (texto)",
    "decimal": "número",
    "fecha": "fecha",
    "entero": "entero",
}

INTRO = [
    "# Diccionario de datos",
    "",
    "Columnas de las tablas finales (`data/processed/<flujo>_<año>.parquet`), en el orden en que aparecen. Este archivo se genera con `colombia-dian-dictionary` a partir de [`colombia_dian_comex/esquema_final.csv`](colombia_dian_comex/esquema_final.csv) (tipos), [`colombia_dian_comex/mapeo_columnas.csv`](colombia_dian_comex/mapeo_columnas.csv) (de qué columnas originales sale cada una) y la tabla de cobertura (en qué años tiene datos).",
    "",
    "- **Años con datos**: años en los que la columna tiene al menos un valor. Las consultas no muestran las columnas sin datos en ninguno de los años consultados.",
    "- **Columnas originales**: nombre o nombres con que la DIAN publicó la columna, si alguna vez fue distinto del final. El detalle y la evidencia de cada correspondencia están en `mapeo_columnas.csv`.",
    "- **Tipos**: los códigos, NIT y números de documento son texto, para no perder ceros iniciales; los montos están en la moneda o unidad que indica su nombre (USD, pesos, kg).",
    "- La DIAN no publica descripciones de cada columna más allá de su nombre; la estructura oficial está en la [ficha técnica](docs/Ficha-Tecnica-bases-estadisticas-de-Comercio-Exterior.pdf).",
    "",
]


def year_ranges(years: Sequence[int]) -> str:
    """Write a list of years compactly (e.g. [2001, 2002, 2003, 2007] -> "2001-2003, 2007").

    Args:
        years: Years, in any order.

    Returns:
        Ranges of consecutive years, separated by commas; "ninguno" if empty.
    """
    if not years:
        return "ninguno"
    ordered = sorted(years)
    ranges = []
    start = previous = ordered[0]
    for year in ordered[1:]:
        if year != previous + 1:
            ranges.append((start, previous))
            start = year
        previous = year
    ranges.append((start, previous))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in ranges)


def build_dictionary() -> str:
    """Build the data dictionary from the project's current state.

    Returns:
        The dictionary, as Markdown.
    """
    coverage_path = utils.data_processed_dir(COVERAGE_FILENAME)
    if not coverage_path.exists():
        download_release_asset(COVERAGE_FILENAME)
    df_coverage = pl.read_parquet(coverage_path).filter(pl.col("FILAS_CON_DATOS") > 0)
    df_mapping = load_column_mapping()

    lines = list(INTRO)
    for flow in Flow:
        lines += [
            f"## {flow.value.capitalize()}",
            "",
            "| # | Columna | Tipo | Años con datos | Columnas originales | Nota |",
            "|---|---|---|---|---|---|",
        ]
        df_flow_coverage = df_coverage.filter(pl.col("FLUJO") == flow.value)
        df_flow_mapping = df_mapping.filter(pl.col("FLUJO") == flow.value)
        for order, column, kind, zero_is_empty, note in (
            load_final_schema(flow)
            .select("ORDEN", "COLUMNA", "TIPO", "CERO_ES_VACIO", "NOTA")
            .iter_rows()
        ):
            years = year_ranges(
                df_flow_coverage.filter(pl.col("COLUMNA") == column)["ANIO"].to_list()
            )
            originals = sorted(
                set(
                    df_flow_mapping.filter(pl.col("COLUMNA_FINAL") == column)[
                        "COLUMNA_ORIGINAL"
                    ].to_list()
                )
                - {column}
            )
            notes = [note] if note else []
            if zero_is_empty:
                notes.append('Un 0 ("no aplica") se deja vacío.')
            lines.append(
                f"| {order} | `{column}` | {TYPE_LABELS[kind]} | {years} | "
                f"{', '.join(f'`{name}`' for name in originals)} | {' '.join(notes)} |"
            )
        lines.append("")

    df_dropped = (
        df_mapping.filter(pl.col("COLUMNA_FINAL").is_null())
        .select("FLUJO", "COLUMNA_ORIGINAL")
        .unique()
        .sort("FLUJO", "COLUMNA_ORIGINAL")
    )
    lines += [
        "## Columnas originales eliminadas",
        "",
        'Valen "1" (o vacío) en todas las filas de todos los meses en que aparecen; no tienen información. Siguen en `data/raw/` y `data/interim/`.',
        "",
    ]
    lines += [f"- {flow}: `{column}`" for flow, column in df_dropped.iter_rows()]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada de `colombia-dian-dictionary`.

    Args:
        argv: Argumentos de línea de comandos a parsear. Si es `None`, se
            usan los de `sys.argv`.

    Returns:
        Código de salida del proceso: 0 si el diccionario se escribió bien.
    """
    parser = argparse.ArgumentParser(
        prog="colombia-dian-dictionary",
        description=(
            "Regenera DICCIONARIO.md a partir de esquema_final.csv, "
            "mapeo_columnas.csv y la tabla de cobertura de columnas."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DICTIONARY_PATH,
        metavar="RUTA",
        help="Archivo a escribir. Por defecto, DICCIONARIO.md en la raíz del proyecto.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    args.output.write_text(build_dictionary(), encoding="utf-8")
    logger.info("Diccionario escrito en %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
