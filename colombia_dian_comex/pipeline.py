"""Pipeline de las bases estadísticas de comercio exterior de la DIAN.

Lo usan tanto los notebooks (para armar el dataset en local) como la
actualización automática. Los pasos son:

1. Listado (`list_remote_files`): los archivos publicados en las dos
   bibliotecas de SharePoint de la DIAN (importaciones y exportaciones), con
   su tamaño y fecha de modificación, a través de la API REST pública del
   sitio. Las páginas de las bibliotecas piden login, pero la API no.
2. Descarga (`download_file`, `download_all`): cada zip mensual (y los
   totales de control) en `data/raw/<flujo>/<año>/`. La DIAN corrige meses ya
   publicados, así que una versión nueva se guarda al lado de la anterior,
   sin pisarla. Las descargas se pueden retomar: lo ya descargado se saltea y
   un archivo cortado a la mitad sigue desde el último byte recibido.
3. Conversión (`convert_month_to_parquet`): el único xlsx de cada zip a
   parquet en `data/interim/`, con todas las columnas como texto, tal como
   vienen. Los nombres y la cantidad de columnas cambian a lo largo de los
   años (ver notebook 0.1), así que tipar y unificar columnas es un paso
   posterior.
4. Validación (`validate_month`, `validation_report`): filas, valores y pesos
   de cada mes contra los totales de control que publica la DIAN.
"""

import logging
import os
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

import fastexcel
import polars as pl
import requests
from tqdm.auto import tqdm

from colombia_dian_comex import utils

logger = logging.getLogger(__name__)

DIAN_BASE_URL = "https://www.dian.gov.co"
DIAN_SITE_PATH = "/dian/cifras"
# El sitio de la DIAN rechaza algunos pedidos sin un User-Agent de navegador.
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
REQUEST_TIMEOUT_SECONDS = 120

# Pausa entre pedidos al servidor de la DIAN, para no sobrecargarlo. También es
# la base de la espera entre reintentos, que se duplica en cada uno.
REQUEST_DELAY_SECONDS = 2.0

# Intentos por archivo antes de darlo por fallido. Cada intento retoma desde
# el último byte recibido.
DOWNLOAD_ATTEMPTS = 5

# Carpeta (dentro de data/interim/) de las descargas a medio terminar.
PARTIAL_DOWNLOADS_DIRNAME = "descargas_parciales"

# Primer año publicado.
FIRST_YEAR = 2001

# Months in Spanish, as they appear in the file names ("..._2026_Julio.zip").
MONTH_NAMES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)

# Monthly archive, e.g. "07_Importaciones_2026_Julio.zip". A newer version
# downloaded next to an older one gets the server timestamp appended
# ("07_Importaciones_2026_Julio_20260921150342.zip"), since data/raw/ is
# never overwritten.
MONTHLY_ZIP_PATTERN = re.compile(
    r"^(?P<month>\d{2})_(?P<flow>Importaciones|Exportaciones)_(?P<year>\d{4})"
    r"_(?P<month_name>[A-Za-z]+)(?:_\d{14})?\.zip$"
)

# Control totals archive, e.g. "Totales-de-control-Importaciones-2026.zip" or
# "Totales-Exportaciones-2026.zip". The year in the name is the last year it
# covers; every file covers 2001 onwards, one sheet per year.
TOTALS_ZIP_PATTERN = re.compile(
    r"^Totales-(?:de-control-)?(?P<flow>Importaciones|Exportaciones)-(?P<year>\d{4})"
    r"(?:_\d{14})?\.zip$"
)

# Data columns summed to compare each month with DIAN's control totals.
# Keys are the control totals' measures; values are the data column with the
# same meaning, which has the same name in every year checked (2001, 2026).
CONTROL_MEASURES = {
    "importaciones": {
        "CIF_USD": "VALOR_CIF_USD",
        "FOB_USD": "VALOR_FOB_USD",
        "PESO_NETO_KG": "PESO_NETO",
    },
    "exportaciones": {
        "FOB_USD": "VALOR_FOB_USD",
        "PESO_NETO_KG": "PESO_NETO_KGS",
    },
}

# Control totals headers, normalized (uppercase, no spaces or symbols), mapped
# to the measure names above. "MES" (imports) and "FECHA" (exports) identify
# the month.
CONTROL_HEADERS = {
    "CIFUS": "CIF_USD",
    "FOBUS": "FOB_USD",
    "PESONETO": "PESO_NETO_KG",
    "PESONETOKGM": "PESO_NETO_KG",
    "REGISTROS": "REGISTROS",
    "MES": "PERIODO",
    "FECHA": "PERIODO",
}

# Maximum relative difference between a month's summed values and its control
# total. The xlsx values are rounded to cents, so sums differ from DIAN's by a
# few cents (e.g. 0.15 USD out of 7,488 million in 2026-07 imports).
CONTROL_RELATIVE_TOLERANCE = 1e-6


class Flow(StrEnum):
    """Flujo de comercio exterior, con el nombre de su biblioteca en la DIAN."""

    IMPORTACIONES = "importaciones"
    EXPORTACIONES = "exportaciones"

    @property
    def library(self) -> str:
        """Server-relative path of the flow's SharePoint document library."""
        return f"{DIAN_SITE_PATH}/Basesestadisticas{self.value}"


@dataclass(frozen=True)
class RemoteFile:
    """Un archivo publicado en una biblioteca de la DIAN.

    Attributes:
        flow: Flujo al que pertenece.
        name: Nombre del archivo en la DIAN.
        size: Tamaño en bytes, según el servidor.
        modified: Última modificación, según el servidor (UTC).
    """

    flow: Flow
    name: str
    size: int
    modified: datetime

    @property
    def url(self) -> str:
        """Download URL of the file."""
        return f"{DIAN_BASE_URL}{self.flow.library}/{self.name}"

    @property
    def version(self) -> str:
        """Modification time as yyyymmddhhmmss, to identify the version."""
        return self.modified.strftime("%Y%m%d%H%M%S")

    @property
    def period(self) -> int | None:
        """Month of a monthly archive as yyyymm, or None for other files."""
        match = MONTHLY_ZIP_PATTERN.match(self.name)
        if match is None:
            return None
        return int(match["year"]) * 100 + int(match["month"])

    @property
    def is_control_totals(self) -> bool:
        """Whether the file is the flow's control totals archive."""
        return TOTALS_ZIP_PATTERN.match(self.name) is not None


def list_remote_files(flow: Flow) -> list[RemoteFile]:
    """List every file published in a flow's document library.

    Uses SharePoint's REST API, which DIAN's site serves without login.

    Args:
        flow: Flow whose library is listed.

    Returns:
        Every file in the library, sorted by name.

    Raises:
        requests.HTTPError: If the listing can't be fetched.
    """
    url = (
        f"{DIAN_BASE_URL}{DIAN_SITE_PATH}/_api/web/"
        f"GetFolderByServerRelativeUrl('{flow.library}')/Files"
    )
    response = requests.get(
        url,
        params={"$select": "Name,Length,TimeLastModified", "$top": "5000"},
        headers={**REQUEST_HEADERS, "Accept": "application/json;odata=nometadata"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    files = [
        RemoteFile(
            flow=flow,
            name=item["Name"],
            size=int(item["Length"]),
            # e.g. "2026-09-21T15:03:42Z"
            modified=datetime.fromisoformat(item["TimeLastModified"]),
        )
        for item in response.json()["value"]
    ]
    unknown = [
        file.name
        for file in files
        if file.period is None and not file.is_control_totals
    ]
    if unknown:
        logger.warning("Archivos con nombre no reconocido en %s: %s", flow, unknown)
    return sorted(files, key=lambda file: file.name)


def _raw_dir(remote: RemoteFile) -> Path:
    """Folder under data/raw/ where a remote file is stored.

    Args:
        remote: File on the server.

    Returns:
        data/raw/<flow>/<year>/ for monthly archives, or
        data/raw/<flow>/totales/ for control totals.
    """
    if remote.period is None:
        return utils.data_raw_dir(remote.flow.value, "totales")
    return utils.data_raw_dir(remote.flow.value, str(remote.period // 100))


def local_versions(remote: RemoteFile) -> list[Path]:
    """Find the local versions of a remote file, oldest first.

    Args:
        remote: File on the server.

    Returns:
        Paths of the original download and of every newer version saved next
        to it, sorted by modification time (set to the server's).
    """
    folder = _raw_dir(remote)
    if not folder.exists():
        return []
    stem = Path(remote.name).stem
    versions = [
        path
        for path in folder.glob(f"{stem}*.zip")
        if path.stem == stem or re.fullmatch(rf"{re.escape(stem)}_\d{{14}}", path.stem)
    ]
    return sorted(versions, key=lambda path: path.stat().st_mtime)


def _is_same_version(path: Path, remote: RemoteFile) -> bool:
    """Tell whether a local file is the same version as the one on the server.

    Args:
        path: Local file.
        remote: File on the server.

    Returns:
        True if both have the same size and modification time (to the second).
    """
    stat = path.stat()
    return (
        stat.st_size == remote.size
        and abs(stat.st_mtime - remote.modified.timestamp()) < 1
    )


def _partial_path(remote: RemoteFile) -> Path:
    """Where an unfinished download of a remote file is kept.

    Partial downloads live outside data/raw/, which only ever holds complete
    files. The server version is part of the name, so bytes of two different
    versions of a file are never mixed when a download is resumed.

    Args:
        remote: File on the server.

    Returns:
        data/interim/descargas_parciales/<flow>/<name>.<version>.part.
    """
    return utils.data_interim_dir(
        PARTIAL_DOWNLOADS_DIRNAME,
        remote.flow.value,
        f"{remote.name}.{remote.version}.part",
    )


def _fetch_to_partial(remote: RemoteFile, partial_path: Path) -> None:
    """Fetch the rest of a file into its partial download, retrying on failure.

    Each attempt asks the server only for the bytes not downloaded yet (an
    HTTP Range request, which DIAN's server supports). If the server answers
    with the whole file instead, the partial download starts over. Connection
    errors are retried after an increasing pause.

    Args:
        remote: File to download.
        partial_path: Partial download to complete, from `_partial_path`.

    Raises:
        requests.RequestException: If every attempt fails.
    """
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        done = partial_path.stat().st_size if partial_path.exists() else 0
        if done >= remote.size:
            return
        headers = (
            {**REQUEST_HEADERS, "Range": f"bytes={done}-"} if done else REQUEST_HEADERS
        )
        try:
            with requests.get(
                remote.url,
                headers=headers,
                stream=True,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                response.raise_for_status()
                # 206 = the server sent only the missing bytes; 200 = the whole file.
                mode = "ab" if response.status_code == 206 else "wb"
                with partial_path.open(mode) as file_:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        file_.write(chunk)
            return
        except (requests.ConnectionError, requests.Timeout) as error:
            if attempt == DOWNLOAD_ATTEMPTS:
                raise
            pause = REQUEST_DELAY_SECONDS * 2**attempt
            logger.warning(
                "%s: se cortó la descarga (%s). Reintento %d de %d en %.0f s...",
                remote.name,
                error,
                attempt,
                DOWNLOAD_ATTEMPTS - 1,
                pause,
            )
            time.sleep(pause)


def download_file(remote: RemoteFile) -> Path:
    """Download a file into data/raw/, unless that version is already there.

    The download can be resumed: bytes go to a partial file outside data/raw/
    (see `_partial_path`), and an interrupted download, whether by a dropped
    connection or by stopping the process, continues from where it stopped
    the next time it is called. Only once the file is complete and checked
    (size and zip structure) is it moved into data/raw/.

    data/raw/ is never overwritten: if an older version of the file exists,
    the new one is saved next to it as <name>_<server timestamp>.zip. The
    file's modification time is set to the server's, so later runs can tell
    whether the local copy is current.

    Args:
        remote: File to download, from `list_remote_files`.

    Returns:
        Path to the local file.

    Raises:
        requests.RequestException: If the download fails after every retry.
        ValueError: If the downloaded file is bigger than the server listed,
            or isn't a valid zip.
    """
    versions = local_versions(remote)
    if versions and _is_same_version(versions[-1], remote):
        return versions[-1]

    stem = Path(remote.name).stem
    name = remote.name if not versions else f"{stem}_{remote.version}.zip"
    path = _raw_dir(remote) / name

    partial_path = _partial_path(remote)
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    # Partial downloads of older server versions can't be resumed: discard them.
    for stale in partial_path.parent.glob(f"{remote.name}.*.part"):
        if stale != partial_path:
            stale.unlink()

    done = partial_path.stat().st_size if partial_path.exists() else 0
    logger.info(
        "Descargando %s (%.1f MB)%s...",
        remote.name,
        remote.size / 1e6,
        f", se retoma desde {done / 1e6:.1f} MB" if done else "",
    )
    _fetch_to_partial(remote, partial_path)

    size = partial_path.stat().st_size
    if size != remote.size or not zipfile.is_zipfile(partial_path):
        # A corrupt partial download would fail the same way on every retry.
        partial_path.unlink()
        raise ValueError(
            f"{remote.name}: se descargaron {size} bytes (el servidor informa "
            f"{remote.size}) o el zip no es válido. Se descarta; volver a correr."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    partial_path.replace(path)
    timestamp = remote.modified.timestamp()
    os.utime(path, (timestamp, timestamp))
    time.sleep(REQUEST_DELAY_SECONDS)
    return path


def download_all(remotes: list[RemoteFile]) -> tuple[list[Path], list[str]]:
    """Download every given file, skipping those already downloaded.

    Meant for long runs (the full history is ~63 GB): a file that fails after
    every retry is reported and skipped instead of stopping the run, and
    running it again only fetches what is still missing, resuming partial
    downloads.

    Args:
        remotes: Files to download, from `list_remote_files`.

    Returns:
        The local paths of the files downloaded (or already there), and the
        names of the files that failed.
    """
    paths = []
    failed = []
    for remote in tqdm(remotes, desc="Descargando", unit="archivo"):
        try:
            paths.append(download_file(remote))
        except (requests.RequestException, ValueError) as error:
            logger.error("%s: falló la descarga (%s).", remote.name, error)
            failed.append(remote.name)
    if failed:
        logger.warning(
            "%d archivo(s) no se pudieron descargar: %s. Volver a correr para "
            "reintentarlos; lo ya descargado no se vuelve a bajar.",
            len(failed),
            failed,
        )
    return paths, failed


def _newest_by_mtime(paths: list[Path]) -> Path:
    """Pick the newest file by modification time (set to the server's).

    Args:
        paths: Local versions of the same file.

    Returns:
        The most recent one.
    """
    return max(paths, key=lambda path: path.stat().st_mtime)


def local_monthly_zips(flow: Flow) -> dict[int, Path]:
    """Find the newest local version of every monthly zip of a flow.

    Args:
        flow: Flow whose zips are looked up under data/raw/<flow>/.

    Returns:
        Mapping of period (yyyymm) to its newest zip, sorted by period.
    """
    versions: dict[int, list[Path]] = {}
    for path in utils.data_raw_dir(flow.value).glob("*/*.zip"):
        match = MONTHLY_ZIP_PATTERN.match(path.name)
        if match is not None:
            period = int(match["year"]) * 100 + int(match["month"])
            versions.setdefault(period, []).append(path)
    return {period: _newest_by_mtime(versions[period]) for period in sorted(versions)}


def local_control_totals(flow: Flow) -> Path:
    """Find the newest local version of a flow's control totals.

    Args:
        flow: Flow whose totals are looked up under data/raw/<flow>/totales/.

    Returns:
        Path to the newest control totals zip.

    Raises:
        FileNotFoundError: If the control totals haven't been downloaded.
    """
    paths = [
        path
        for path in utils.data_raw_dir(flow.value, "totales").glob("*.zip")
        if TOTALS_ZIP_PATTERN.match(path.name)
    ]
    if not paths:
        raise FileNotFoundError(
            f"No hay totales de control de {flow} en data/raw/; correr la descarga."
        )
    return _newest_by_mtime(paths)


def _single_xlsx_member(zf: zipfile.ZipFile) -> str:
    """Name of the only xlsx file inside a DIAN zip.

    Args:
        zf: Open zip archive.

    Returns:
        Name of the xlsx member.

    Raises:
        ValueError: If the zip doesn't hold exactly one xlsx file.
    """
    members = [name for name in zf.namelist() if name.lower().endswith(".xlsx")]
    if len(members) != 1:
        raise ValueError(f"Se esperaba un único xlsx en el zip, hay: {members}")
    return members[0]


def interim_path(flow: Flow, period: int) -> Path:
    """Where the converted parquet of one month is stored.

    Args:
        flow: Flow of the month.
        period: Month, as yyyymm.

    Returns:
        data/interim/<flow>/<year>/<flow>_<yyyymm>.parquet.
    """
    return utils.data_interim_dir(
        flow.value, str(period // 100), f"{flow.value}_{period}.parquet"
    )


def convert_month_to_parquet(flow: Flow, period: int, zip_path: Path) -> Path:
    """Convert one monthly zip into a parquet file, every column as text.

    Every column is kept as the text DIAN published, because column names,
    count and contents change across the years; typing and unifying them is
    a later step. Column names are stripped of surrounding spaces. A month
    already converted is skipped, unless its zip is newer than the parquet (a
    new version downloaded from the server).

    Args:
        flow: Flow of the month.
        period: Month of the zip, as yyyymm.
        zip_path: Path to the monthly zip archive.

    Returns:
        Path to the month's parquet.
    """
    output_path = interim_path(flow, period)
    if output_path.exists() and output_path.stat().st_mtime >= zip_path.stat().st_mtime:
        return output_path

    with zipfile.ZipFile(zip_path) as zf:
        xlsx_bytes = zf.read(_single_xlsx_member(zf))

    df_month = (
        fastexcel.read_excel(xlsx_bytes).load_sheet(0, dtypes="string").to_polars()
    )
    df_month = df_month.rename({column: column.strip() for column in df_month.columns})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(f"{output_path.name}.tmp")
    df_month.write_parquet(tmp_path, compression="zstd", compression_level=9)
    tmp_path.replace(output_path)
    return output_path


def _normalize_header(value: object) -> str:
    """Normalize a control totals header for matching (e.g. "CIF US$" -> "CIFUS").

    Args:
        value: Header cell value.

    Returns:
        The header uppercased, without spaces or symbols.
    """
    return re.sub(r"[^A-Z]", "", str(value).upper())


def read_control_totals(zip_path: Path) -> pl.DataFrame:
    """Read DIAN's monthly control totals for every year.

    Each year is a sheet with a title, a header row and one row per month.
    Imports identify the month by its number ("MES") and exports by
    yyyymm ("FECHA"); both are returned as yyyymm. Months not published yet
    have empty rows and are left out, as is the yearly total row.

    Args:
        zip_path: Control totals archive of one flow.

    Returns:
        One row per month: PERIODO (yyyymm), REGISTROS and the flow's measures
        (CIF_USD, FOB_USD, PESO_NETO_KG).

    Raises:
        ValueError: If a sheet has no recognizable header row.
    """
    with zipfile.ZipFile(zip_path) as zf:
        reader = fastexcel.read_excel(zf.read(_single_xlsx_member(zf)))

    rows = []
    for sheet_name in reader.sheet_names:
        year_match = re.search(r"\d{4}", sheet_name)
        if year_match is None:
            continue
        year = int(year_match.group())
        cells = reader.load_sheet(
            sheet_name, header_row=None, dtypes="string"
        ).to_polars()

        header_index = None
        for index, row in enumerate(cells.iter_rows()):
            headers = [_normalize_header(value) for value in row]
            if "REGISTROS" in headers:
                header_index = index
                columns = {
                    position: CONTROL_HEADERS[header]
                    for position, header in enumerate(headers)
                    if header in CONTROL_HEADERS
                }
                break
        if header_index is None:
            raise ValueError(
                f"{zip_path.name}: la hoja {sheet_name!r} no tiene encabezado."
            )

        for row in cells.iter_rows():
            record = {name: row[position] for position, name in columns.items()}
            month = record.get("PERIODO")
            if month is None or not re.fullmatch(r"\d+(\.0+)?", month):
                continue
            if record.get("REGISTROS") is None:
                continue
            month_number = int(float(month))
            # Exports already give yyyymm; imports give the month number.
            period = month_number if month_number > 12 else year * 100 + month_number
            rows.append({**record, "PERIODO": period})

    return pl.DataFrame(rows).with_columns(
        pl.col("PERIODO").cast(pl.Int32),
        pl.col("REGISTROS").cast(pl.Float64).cast(pl.Int64),
        pl.exclude("PERIODO", "REGISTROS").cast(pl.Float64),
    )


@dataclass(frozen=True)
class ControlCheck:
    """Comparación de un mes con su total de control.

    Attributes:
        measure: Medida comparada (REGISTROS, CIF_USD, FOB_USD o PESO_NETO_KG).
        data: Valor calculado a partir de los datos del mes.
        control: Valor que publica la DIAN en sus totales de control.
    """

    measure: str
    data: float
    control: float

    @property
    def ok(self) -> bool:
        """Whether the data matches the control total within tolerance."""
        if self.measure == "REGISTROS":
            return self.data == self.control
        return abs(self.data - self.control) <= CONTROL_RELATIVE_TOLERANCE * max(
            abs(self.control), 1.0
        )


def validate_month(
    flow: Flow,
    period: int,
    df_totals: pl.DataFrame,
    lf_month: pl.LazyFrame | None = None,
) -> list[ControlCheck]:
    """Compare one month with DIAN's control totals.

    Args:
        flow: Flow of the month.
        period: Month, as yyyymm.
        df_totals: The flow's control totals, from `read_control_totals`.
        lf_month: The month's rows to check. If None, the month's converted
            parquet in data/interim/ is read; the final tables pass their own
            rows to check that building them kept every row and amount.

    Returns:
        One check per measure (rows plus the flow's summed values).

    Raises:
        ValueError: If the control totals don't include the month.
    """
    df_control = df_totals.filter(pl.col("PERIODO") == period)
    if df_control.height != 1:
        raise ValueError(f"Los totales de control de {flow} no incluyen {period}.")
    control = df_control.row(0, named=True)

    measures = CONTROL_MEASURES[flow.value]
    if lf_month is None:
        lf_month = pl.scan_parquet(interim_path(flow, period))
    columns = lf_month.collect_schema().names()
    df_sums = lf_month.select(
        pl.len().alias("REGISTROS"),
        *[
            # A month missing a measure's column can't be checked on it: NaN
            # never matches its control total, so the check fails visibly.
            (
                pl.col(column).cast(pl.Float64).sum()
                if column in columns
                else pl.lit(float("nan"))
            ).alias(measure)
            for measure, column in measures.items()
        ],
    ).collect()
    sums = df_sums.row(0, named=True)
    return [
        ControlCheck(
            measure=measure, data=float(sums[measure]), control=float(control[measure])
        )
        for measure in ["REGISTROS", *measures]
    ]


def validation_report(flow: Flow, periods: list[int]) -> pl.DataFrame:
    """Compare every given converted month with DIAN's control totals.

    Args:
        flow: Flow of the months.
        periods: Months to check, as yyyymm; each must be converted already.

    Returns:
        One row per month and measure: FLUJO, PERIODO, MEDIDA, DATOS (value
        computed from the data), CONTROL (DIAN's control total) and OK.
    """
    df_totals = read_control_totals(local_control_totals(flow))
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
        for check in validate_month(flow, period, df_totals)
    ]
    return pl.DataFrame(
        rows,
        schema={
            "FLUJO": pl.String,
            "PERIODO": pl.Int32,
            "MEDIDA": pl.String,
            "DATOS": pl.Float64,
            "CONTROL": pl.Float64,
            "OK": pl.Boolean,
        },
    )
