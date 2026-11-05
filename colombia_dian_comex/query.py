"""Consulta y exportación de las bases de importaciones y exportaciones de la DIAN.

Funciona tanto como librería (`from colombia_dian_comex.query import query_comex`)
como CLI (`python -m colombia_dian_comex.query importaciones --years 2024
--subpartida 2701`). El archivo exportado es CSV por defecto
(`formato`/--formato/-f también acepta "xlsx" y "parquet") y va por defecto
al directorio actual; usar `output_dir`/--output/-o para exportarlo a otra
carpeta (que se crea si no existe). El notebook de consulta pasa
`output_dir=utils.outputs_tables_dir()` para que sus exports vayan a
`outputs/tables/`.

El resultado no incluye las columnas que no tienen ningún dato en los años
consultados (por ejemplo, las de la estructura de 2001-2004 en una consulta
de 2020-2026), según la tabla de cobertura que arma `build`. Las columnas
con datos, aunque sean todos 0, se mantienen: un 0 es un valor (por ejemplo,
"no se cobró antidumping").

Si las tablas de un año o la tabla de cobertura no están en
`data/processed/`, se descargan del release más reciente del repositorio en
GitHub.
"""

import argparse
import logging
import re
from collections.abc import Sequence
from pathlib import Path

import polars as pl
import requests
from tqdm.auto import tqdm

from colombia_dian_comex import utils
from colombia_dian_comex.build import COVERAGE_FILENAME, final_path
from colombia_dian_comex.pipeline import Flow

logger = logging.getLogger(__name__)

# Release único "datos", con un archivo por flujo y año (ver
# .github/workflows/update-data.yml).
RELEASE_DOWNLOAD_URL = (
    "https://github.com/fer-aguirre/colombia-dian-comex/releases/download/datos/"
)

# Columnas que usa cada filtro, por flujo. El nombre y el NIT son los de la
# empresa colombiana que importa o exporta. En exportaciones, el nombre del
# exportador solo existe desde 2007; antes solo está el NIT.
NAME_COLUMNS = {
    Flow.IMPORTACIONES: "NOMBRE_IMPORTADOR",
    Flow.EXPORTACIONES: "RAZON_SOCIAL_EXPORTADOR",
}
NIT_COLUMNS = {
    Flow.IMPORTACIONES: "NIT_IMPORTADOR",
    Flow.EXPORTACIONES: "NIT_EXPORTADOR",
}
SUBPARTIDA_COLUMNS = {
    Flow.IMPORTACIONES: "SUBPARTIDA_ARANCELARIA",
    Flow.EXPORTACIONES: "SUBPARTIDA",
}

# Formatos de archivo aceptados para exportar el resultado de una consulta.
EXPORT_FORMATS = ("csv", "xlsx", "parquet")

# Matches any character that isn't a digit, to strip separators from codes.
NON_DIGIT_PATTERN = re.compile(r"\D+")


def _digits(code: str) -> str:
    """Strip separators from a subpartida or NIT (e.g. "27.01" -> "2701").

    Args:
        code: Code, with or without separators.

    Returns:
        The code with any non-digit characters removed.
    """
    return NON_DIGIT_PATTERN.sub("", code)


def download_release_asset(filename: str) -> Path:
    """Download a file from the latest GitHub release into data/processed/.

    Downloads to a temporary file first and renames it into place only once
    complete, so an interrupted download never leaves a truncated file that
    looks like a valid cached file on the next run.

    Args:
        filename: Name of the file in the release (e.g. "importaciones_2024.parquet").

    Returns:
        Path to the downloaded file.

    Raises:
        requests.HTTPError: If the file can't be downloaded.
    """
    url = RELEASE_DOWNLOAD_URL + filename
    destination = utils.data_processed_dir(filename)
    logger.info("%s no encontrado localmente. Descargando desde %s...", filename, url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_name(f"{destination.name}.tmp")
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        with (
            tmp_path.open("wb") as file_,
            tqdm(
                total=total, unit="B", unit_scale=True, desc=f"Descargando {filename}"
            ) as progress,
        ):
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                file_.write(chunk)
                progress.update(len(chunk))
    tmp_path.replace(destination)
    return destination


def _local_or_download(path: Path) -> Path:
    """Return a data/processed/ file, downloading it first if it's missing.

    Args:
        path: Expected local path of the file.

    Returns:
        The same path, once the file exists.
    """
    return path if path.exists() else download_release_asset(path.name)


def columns_without_data(flow: Flow, years: Sequence[int]) -> list[str]:
    """List the columns that have no data in any of the given years.

    Covers both the columns that didn't exist in those years (older or
    newer column layouts of the DIAN files) and those that exist but are
    always empty. Columns whose values are all 0 do have data and aren't
    listed.

    Args:
        flow: Flow queried.
        years: Years queried.

    Returns:
        Names of the columns to leave out of the result, sorted.
    """
    df_coverage = pl.read_parquet(
        _local_or_download(utils.data_processed_dir(COVERAGE_FILENAME))
    )
    return sorted(
        df_coverage.filter(
            pl.col("FLUJO") == flow.value, pl.col("ANIO").is_in(list(years))
        )
        .group_by("COLUMNA")
        .agg(pl.col("FILAS_CON_DATOS").sum())
        .filter(pl.col("FILAS_CON_DATOS") == 0)["COLUMNA"]
        .to_list()
    )


def query_comex(
    flujo: str | Flow,
    years: int | Sequence[int],
    nombre: str | None = None,
    nit: str | Sequence[str] | None = None,
    subpartida: str | Sequence[str] | None = None,
) -> pl.DataFrame:
    """Consulta las tablas de importaciones o exportaciones de la DIAN.

    Args:
        flujo: "importaciones" o "exportaciones".
        years: Año o lista de años a consultar (no hace falta que sean consecutivos).
        nombre: Nombre (o parte del nombre) del importador o exportador. Se
            busca como texto literal y no distingue mayúsculas/minúsculas. En
            exportaciones, el nombre solo existe desde 2007; antes buscar por NIT.
        nit: NIT o lista de NIT del importador o exportador (sin dígito de
            verificación). Los puntos o guiones se ignoran.
        subpartida: Subpartida arancelaria o lista de subpartidas, completas
            (10 dígitos) o solo el comienzo (ej. "2701" o "27.01").

    Returns:
        DataFrame de polars con las filas que cumplen todos los filtros, sin
        las columnas que no tienen datos en los años consultados.

    Raises:
        ValueError: Si no se indica ninguno de `nombre`, `nit` o `subpartida`.
    """
    flow = Flow(flujo)
    if nombre is None and nit is None and subpartida is None:
        raise ValueError("Debe indicar al menos `nombre`, `nit` o `subpartida`.")
    years_list = [years] if isinstance(years, int) else list(years)

    filters = []
    if nombre is not None:
        # Escapado para que caracteres como "." o "(" se busquen literalmente.
        filters.append(
            pl.col(NAME_COLUMNS[flow]).str.contains(f"(?i){re.escape(nombre)}")
        )
    if nit is not None:
        nits = [_digits(value) for value in ([nit] if isinstance(nit, str) else nit)]
        filters.append(pl.col(NIT_COLUMNS[flow]).is_in(nits))
    if subpartida is not None:
        codes = [
            _digits(code)
            for code in ([subpartida] if isinstance(subpartida, str) else subpartida)
        ]
        filters.append(
            pl.any_horizontal(
                pl.col(SUBPARTIDA_COLUMNS[flow]).str.starts_with(code) for code in codes
            )
        )

    paths = [_local_or_download(final_path(flow, year)) for year in years_list]
    df_result = pl.scan_parquet(paths).filter(*filters).collect()
    return df_result.drop(columns_without_data(flow, years_list), strict=False)


def export_query_result(
    df_result: pl.DataFrame,
    flujo: str | Flow,
    query_years: int | Sequence[int],
    query_nombre: str | None = None,
    query_nit: str | Sequence[str] | None = None,
    query_subpartida: str | Sequence[str] | None = None,
    output_dir: Path | None = None,
    formato: str = "csv",
) -> Path | None:
    """Exporta el resultado de una consulta a un archivo.

    El nombre del archivo se arma con los parámetros de la consulta: flujo,
    nombre, NIT, subpartida y rango de años.

    Args:
        df_result: DataFrame a exportar.
        flujo: Flujo consultado.
        query_years: Año o lista de años consultados.
        query_nombre: Nombre consultado (o None).
        query_nit: NIT consultado(s) (o None).
        query_subpartida: Subpartida(s) consultada(s) (o None).
        output_dir: Carpeta donde escribir el archivo. Si es `None`, se usa
            el directorio actual. Se crea automáticamente si no existe.
        formato: "csv" (default), "xlsx" o "parquet". No distingue
            mayúsculas/minúsculas.

    Returns:
        La ruta del archivo generado, o None si no había filas para exportar.

    Raises:
        ValueError: Si `formato` no es uno de EXPORT_FORMATS.
    """
    formato = formato.lower()
    if formato not in EXPORT_FORMATS:
        raise ValueError(
            f"formato inválido: {formato!r}. Valores válidos: {EXPORT_FORMATS}."
        )
    if df_result.height == 0:
        logger.info("La consulta no devolvió filas. No se generó ningún archivo.")
        return None

    years_list = [query_years] if isinstance(query_years, int) else list(query_years)
    start_year, end_year = min(years_list), max(years_list)
    year_suffix = (
        f"{start_year}-{end_year}" if start_year != end_year else str(start_year)
    )

    name_parts = [Flow(flujo).value]
    if query_nombre:
        # Solo letras, números y guiones bajos, para que sea un nombre de archivo válido.
        name_parts.append(re.sub(r"\W+", "_", query_nombre.strip().lower()).strip("_"))
    for query_codes in (query_nit, query_subpartida):
        if query_codes:
            codes = [query_codes] if isinstance(query_codes, str) else query_codes
            name_parts.append("-".join(_digits(code) for code in codes))

    export_dir = output_dir if output_dir is not None else Path.cwd()
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"{'_'.join(name_parts)}_{year_suffix}.{formato}"

    logger.info("Exportando %d filas a: %s", df_result.height, export_path)
    if formato == "csv":
        df_result.write_csv(export_path)
    elif formato == "xlsx":
        df_result.write_excel(export_path)
    else:
        df_result.write_parquet(export_path)
    return export_path


def _build_parser() -> argparse.ArgumentParser:
    """Construye el parser de argumentos de la CLI de consulta.

    Returns:
        Parser de argparse configurado con las opciones de la consulta.
    """
    parser = argparse.ArgumentParser(
        prog="colombia-dian-query",
        description=(
            "Consulta las bases de importaciones o exportaciones de la DIAN por año, "
            "nombre o NIT del importador/exportador y/o subpartida, y exporta el "
            "resultado (CSV por defecto, o XLSX/Parquet con --formato) en el "
            "directorio actual o en la carpeta indicada con --output. Debe "
            "indicarse --nombre, --nit y/o --subpartida."
        ),
    )
    parser.add_argument(
        "flujo",
        type=str.lower,
        choices=[flow.value for flow in Flow],
        help="importaciones o exportaciones.",
    )
    parser.add_argument(
        "-y",
        "--years",
        type=int,
        nargs="+",
        required=True,
        metavar="AÑO",
        help="Uno o más años a consultar, separados por espacios (ej. --years 2024 2025).",
    )
    parser.add_argument(
        "-n",
        "--nombre",
        type=str,
        default=None,
        help=(
            "Nombre (o parte del nombre) del importador o exportador (texto literal, no "
            "distingue mayúsculas/minúsculas). En exportaciones, solo desde 2007."
        ),
    )
    parser.add_argument(
        "--nit",
        type=str,
        nargs="+",
        default=None,
        metavar="NIT",
        help="Uno o más NIT del importador o exportador, sin dígito de verificación.",
    )
    parser.add_argument(
        "-s",
        "--subpartida",
        type=str,
        nargs="+",
        default=None,
        metavar="SUBPARTIDA",
        help="Una o más subpartidas (o su comienzo), con o sin puntos (ej. --subpartida 2701 84.71).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="RUTA",
        help="Carpeta donde escribir el archivo. Por defecto, el directorio actual.",
    )
    parser.add_argument(
        "-f",
        "--formato",
        type=str.lower,
        default="csv",
        choices=EXPORT_FORMATS,
        metavar="FORMATO",
        help="Formato de exportación: csv (default), xlsx o parquet.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Muestra mensajes de registro detallados (nivel DEBUG) en vez de solo INFO.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada de `python -m colombia_dian_comex.query`.

    Args:
        argv: Argumentos de línea de comandos a parsear. Si es `None`, se
            usan los de `sys.argv`.

    Returns:
        Código de salida del proceso: 0 si la consulta se ejecutó bien.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )
    if args.nombre is None and args.nit is None and args.subpartida is None:
        parser.error("Debe indicar al menos --nombre, --nit o --subpartida.")

    df_result = query_comex(
        args.flujo, args.years, args.nombre, args.nit, args.subpartida
    )
    export_query_result(
        df_result,
        args.flujo,
        args.years,
        args.nombre,
        args.nit,
        args.subpartida,
        output_dir=args.output,
        formato=args.formato,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
