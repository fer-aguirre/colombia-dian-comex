"""Consulta y exportación de las bases de importaciones y exportaciones de la DIAN.

Funciona tanto como librería como CLI (`colombia-dian-query`, o
`python -m colombia_dian_comex` si Windows bloquea el ejecutable):

    from colombia_dian_comex import Consulta, export_query_result, query_data

    consulta = Consulta(years=[2024, 2025], tipo_regimen="i", codigo="2701")
    df_result = query_data(consulta)
    export_query_result(df_result, consulta)

El archivo exportado es CSV por defecto (`formato`/--formato/-f también acepta
"xlsx" y "parquet") y va por defecto al directorio actual; usar
`output_dir`/--output/-o para exportarlo a otra carpeta (que se crea si no
existe). Los notebooks pasan `output_dir=utils.outputs_tables_dir()`. El
nombre del archivo lo arma `Consulta.export_filename` (ver `consulta.py`).

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
from colombia_dian_comex.consulta import TIPO_REGIMEN_MAP, Consulta
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
# Subpartida NANDINA, ya guardada como 10 dígitos sin puntos (ver build).
SUBPARTIDA_COLUMNS = {
    Flow.IMPORTACIONES: "SUBPARTIDA_ARANCELARIA",
    Flow.EXPORTACIONES: "SUBPARTIDA",
}

# Formatos de archivo aceptados para exportar el resultado de una consulta.
EXPORT_FORMATS = ("csv", "xlsx", "parquet")


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
    logger.info("Descargando %s desde %s...", filename, url)
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


def query_data(consulta: Consulta) -> pl.DataFrame:
    """Consulta la base de importaciones o exportaciones de la DIAN.

    Agrega dos columnas derivadas de PERIODO (un entero aaaamm): AÑO y MES.
    Si las tablas de los años consultados no existen localmente, se
    descargan primero desde el release en GitHub (ver RELEASE_DOWNLOAD_URL).

    Args:
        consulta: Parámetros de la búsqueda (régimen, años, nombre,
            subpartida NANDINA y/o NIT).

    Returns:
        DataFrame de polars con las filas que cumplen todos los filtros, sin
        las columnas que no tienen datos en los años consultados.
    """
    flow = consulta.regimen_value

    filters = []
    if consulta.nombre_value is not None:
        # Escapado para que caracteres como "." o "(" se busquen literalmente.
        filters.append(
            pl.col(NAME_COLUMNS[flow]).str.contains(
                f"(?i){re.escape(consulta.nombre_value)}"
            )
        )
    if consulta.nit_values:
        filters.append(pl.col(NIT_COLUMNS[flow]).is_in(consulta.nit_values))
    if consulta.codigo_values:
        # La columna ya tiene solo dígitos, igual que los códigos normalizados.
        filters.append(
            pl.any_horizontal(
                pl.col(SUBPARTIDA_COLUMNS[flow]).str.starts_with(code)
                for code in consulta.codigo_values
            )
        )

    # Hay un archivo por flujo y año, así que el año se filtra eligiendo archivos.
    paths = [
        _local_or_download(final_path(flow, year)) for year in consulta.year_values
    ]
    df_result = (
        pl.scan_parquet(paths)
        .filter(*filters)
        .with_columns(
            (pl.col("PERIODO") // 100).cast(pl.Int64).alias("AÑO"),
            (pl.col("PERIODO") % 100).cast(pl.Int64).alias("MES"),
        )
        .collect()
    )
    return df_result.drop(
        columns_without_data(flow, consulta.year_values), strict=False
    )


def export_query_result(
    df_result: pl.DataFrame,
    consulta: Consulta,
    output_dir: Path | None = None,
    formato: str = "csv",
) -> Path | None:
    """Exporta el resultado de una consulta a un archivo.

    El nombre del archivo se arma a partir de la consulta, con la fecha y
    hora de exportación, hasta segundos (ver `Consulta.export_filename`).

    Args:
        df_result: DataFrame a exportar, resultado de `query_data(consulta)`.
        consulta: La misma consulta usada para obtener `df_result`.
        output_dir: Carpeta donde escribir el archivo. Si es `None`, se usa
            el directorio actual. Se crea automáticamente si no existe.
        formato: Formato de exportación: "csv" (default), "xlsx" o
            "parquet". No distingue mayúsculas/minúsculas.

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

    export_dir = output_dir if output_dir is not None else Path.cwd()
    if not export_dir.exists():
        logger.info("El directorio de salida no existe, se crea: %s", export_dir)
        export_dir.mkdir(parents=True)
    export_path = export_dir / consulta.export_filename(formato)

    logger.info("Exportando %d filas a: %s", df_result.height, export_path)
    if formato == "csv":
        df_result.write_csv(export_path)
    elif formato == "xlsx":
        df_result.write_excel(export_path)
    else:
        df_result.write_parquet(export_path)
    logger.info("Exportación completa.")
    return export_path


def _build_parser() -> argparse.ArgumentParser:
    """Construye el parser de argumentos de la CLI `colombia-dian-query`.

    Returns:
        Parser de argparse configurado con las opciones de la consulta.
    """
    parser = argparse.ArgumentParser(
        prog="colombia-dian-query",
        description=(
            "Consulta las bases de importaciones o exportaciones de la DIAN por año, "
            "nombre del importador/exportador, subpartida NANDINA (--codigo) y/o "
            "NIT, y exporta el resultado (CSV por defecto, o XLSX/Parquet con "
            "--formato) en el directorio actual o en la carpeta indicada con "
            "--output. Debe indicarse --nombre, --codigo y/o --nit."
        ),
    )
    parser.add_argument(
        "-r",
        "--tipo-regimen",
        type=str.lower,
        required=True,
        choices=list(TIPO_REGIMEN_MAP),
        help="Base a consultar: i (importaciones) o e (exportaciones).",
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
            "distingue mayúsculas/minúsculas). En exportaciones, solo desde 2007, y a "
            'veces figura como "PERSONA NATURAL": para no perder filas, usar --nit.'
        ),
    )
    parser.add_argument(
        "-c",
        "--codigo",
        type=str,
        nargs="+",
        default=None,
        metavar="SUBPARTIDA",
        help=(
            "Una o más subpartidas arancelarias NANDINA (10 dígitos) o su comienzo, "
            "con o sin puntos (ej. --codigo 2701 84.71)."
        ),
    )
    parser.add_argument(
        "--nit",
        type=str,
        nargs="+",
        default=None,
        metavar="NIT",
        help=(
            "Uno o más NIT del importador o exportador, sin dígito de verificación. "
            "Los puntos o guiones se ignoran."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="RUTA",
        help=(
            "Carpeta donde escribir el archivo exportado. Por defecto es el "
            "directorio actual. Se crea automáticamente si no existe."
        ),
    )
    parser.add_argument(
        "-f",
        "--formato",
        type=str.lower,
        default="csv",
        choices=EXPORT_FORMATS,
        metavar="FORMATO",
        help="Formato de exportación: csv (default), xlsx o parquet. No distingue mayúsculas/minúsculas.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Muestra mensajes de registro detallados (nivel DEBUG) en vez de solo INFO.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada de `colombia-dian-query` y `python -m colombia_dian_comex`.

    Args:
        argv: Argumentos de línea de comandos a parsear. Si es `None`, se
            usan los de `sys.argv`.

    Returns:
        Código de salida del proceso: 0 si la consulta se ejecutó
        correctamente. Si los argumentos son inválidos, argparse termina el
        proceso con código 2.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    try:
        consulta = Consulta(
            years=args.years,
            tipo_regimen=args.tipo_regimen,
            nombre=args.nombre,
            codigo=args.codigo,
            nit=args.nit,
        )
    except ValueError as error:
        parser.error(str(error))

    df_result = query_data(consulta)
    export_query_result(
        df_result, consulta, output_dir=args.output, formato=args.formato
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
