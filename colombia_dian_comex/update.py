"""Actualización de las tablas con los meses nuevos o corregidos por la DIAN.

Se corre con `python -m colombia_dian_comex.update`, pensado para GitHub
Actions (ver `.github/workflows/update-data.yml`), aunque también funciona en
local. Compara el tamaño y la fecha de cada archivo mensual de la DIAN con los
ya procesados en `data/manifest.json` y solo procesa los nuevos o cambiados:

1. Descarga los totales de control y los meses que cambiaron.
2. Convierte cada mes a parquet y lo valida contra los totales de control. Si
   un mes no coincide, se detiene sin publicar nada.
3. Rehace las tablas de los años afectados: parte de la tabla publicada del
   año (o la local), le quita los meses que cambiaron y les agrega su versión
   nueva. Así no hace falta volver a bajar de la DIAN el año entero.
4. Valida las tablas rehechas contra los totales de control y actualiza la
   tabla de cobertura de columnas.

Una corrida procesa como mucho `--max-gb` de archivos de la DIAN (que entrega
alrededor de 0,5 MB/s); si la DIAN volvió a subir más, el resto queda para la
corrida siguiente. Publicar los archivos y commitear el manifest quedan a
cargo del workflow; este módulo le informa qué cambió a través de
`GITHUB_OUTPUT` cuando corre en Actions.
"""

import argparse
import json
import logging
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import polars as pl
import requests

from colombia_dian_comex import utils
from colombia_dian_comex.build import (
    COVERAGE_FILENAME,
    final_path,
    typing_losses,
    unify_month,
    update_coverage,
    validate_year,
    year_coverage,
)
from colombia_dian_comex.pipeline import (
    Flow,
    RemoteFile,
    convert_month_to_parquet,
    download_file,
    interim_path,
    list_remote_files,
    local_monthly_zips,
    read_control_totals,
    validate_month,
)
from colombia_dian_comex.query import download_release_asset

logger = logging.getLogger(__name__)

MANIFEST_PATH = utils.data_dir("manifest.json")

# Hora de Colombia (UTC-5, sin horario de verano), para fechar el procesamiento.
COLOMBIA_TZ = timezone(timedelta(hours=-5))

# GB de archivos de la DIAN que procesa una corrida, por defecto. A ~0,5 MB/s,
# 6 GB son unas 3,5 horas de descarga, dentro de las 6 horas de un job de
# GitHub Actions.
DEFAULT_MAX_GB = 6.0


@dataclass
class PreviousVersion:
    """Versión de un mes que la DIAN reemplazó al volver a subir el archivo.

    Attributes:
        size: Tamaño del zip en el servidor, en bytes.
        modified: Fecha de modificación en el servidor (UTC), como aaaammddhhmmss.
        rows: Filas del mes en esa versión.
        processed_at: Fecha en que se procesó esa versión (AAAA-MM-DD).
        replaced_at: Fecha en que se reemplazó por la siguiente (AAAA-MM-DD).
    """

    size: int
    modified: str
    rows: int
    processed_at: str
    replaced_at: str


@dataclass
class MonthRecord:
    """Registro de un mes ya procesado, tal como se guarda en el manifest.

    Attributes:
        name: Nombre del archivo en la DIAN.
        size: Tamaño del zip en el servidor, en bytes.
        modified: Fecha de modificación en el servidor (UTC), como aaaammddhhmmss.
        rows: Filas del mes.
        processed_at: Fecha de procesamiento (AAAA-MM-DD).
        previous: Versiones anteriores del mes, de la más vieja a la más
            nueva; vacía si la DIAN nunca lo volvió a subir.
    """

    name: str
    size: int
    modified: str
    rows: int
    processed_at: str
    previous: list[PreviousVersion] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> MonthRecord:
        """Build a record from its JSON form in the manifest.

        Args:
            raw: One month's entry, as written by `save_manifest`.

        Returns:
            The record, with its previous versions.
        """
        return cls(
            **{
                **raw,
                "previous": [PreviousVersion(**version) for version in raw["previous"]],
            }
        )

    def matches(self, remote: RemoteFile) -> bool:
        """Tell whether this record is the same version as the file on the server.

        Args:
            remote: File on the server.

        Returns:
            True if size and modification time are the same.
        """
        return self.size == remote.size and self.modified == remote.version


# Manifest: flow -> yyyymm (as text, for JSON) -> record.
Manifest = dict[str, dict[str, MonthRecord]]


def load_manifest() -> Manifest:
    """Read the processed months from data/manifest.json.

    Returns:
        Mapping of flow and yyyymm to MonthRecord; empty if there's no manifest.
    """
    if not MANIFEST_PATH.exists():
        return {flow.value: {} for flow in Flow}
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        flow.value: {
            period: MonthRecord.from_dict(record)
            for period, record in raw.get(flow.value, {}).items()
        }
        for flow in Flow
    }


def save_manifest(manifest: Manifest) -> None:
    """Write the processed months to data/manifest.json, sorted by flow and month.

    Args:
        manifest: Mapping of flow and yyyymm to MonthRecord.
    """
    raw = {
        flow: {period: asdict(records[period]) for period in sorted(records)}
        for flow, records in manifest.items()
    }
    MANIFEST_PATH.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _month_rows(flow: Flow, period: int) -> int:
    """Count the rows of a converted month.

    Args:
        flow: Flow of the month.
        period: Month, as yyyymm.

    Returns:
        Number of rows in its parquet in data/interim/.
    """
    return pl.scan_parquet(interim_path(flow, period)).select(pl.len()).collect().item()


def _today() -> str:
    """Today's date in Colombia, as AAAA-MM-DD."""
    return datetime.now(COLOMBIA_TZ).date().isoformat()


def initialize_manifest() -> Manifest:
    """Create the manifest from the months already downloaded and converted locally.

    Meant for the first run, after building every table locally with the
    notebooks: records the version of each month in data/raw/ (whose
    modification time is the server's) so later updates only process what
    changed afterwards.

    Returns:
        The manifest, also written to data/manifest.json.
    """
    manifest: Manifest = {}
    for flow in Flow:
        manifest[flow.value] = {}
        for period, zip_path in local_monthly_zips(flow).items():
            modified = datetime.fromtimestamp(zip_path.stat().st_mtime, tz=UTC)
            # The original name, without the version suffix of corrected files.
            name = (
                zip_path.name
                if zip_path.stem.count("_") == 3
                else f"{zip_path.stem.rsplit('_', 1)[0]}.zip"
            )
            manifest[flow.value][str(period)] = MonthRecord(
                name=name,
                size=zip_path.stat().st_size,
                modified=modified.strftime("%Y%m%d%H%M%S"),
                rows=_month_rows(flow, period),
                processed_at=_today(),
            )
    save_manifest(manifest)
    return manifest


def pending_files(manifest: Manifest, max_bytes: float) -> list[RemoteFile]:
    """List the monthly files that are new or changed on DIAN's site.

    Args:
        manifest: Processed months, from `load_manifest`.
        max_bytes: Most bytes to process in this run; the oldest months go
            first and the rest wait for the next run. At least one file is
            always included.

    Returns:
        Files to process, oldest month first.
    """
    changed = []
    for flow in Flow:
        records = manifest[flow.value]
        for remote in list_remote_files(flow):
            if remote.period is None:
                continue
            record = records.get(str(remote.period))
            if record is None or not record.matches(remote):
                changed.append(remote)
    changed.sort(key=lambda remote: (remote.period or 0, remote.flow.value))

    selected: list[RemoteFile] = []
    total = 0
    for remote in changed:
        if selected and total + remote.size > max_bytes:
            logger.info(
                "Quedan %d archivo(s) para la corrida siguiente.",
                len(changed) - len(selected),
            )
            break
        selected.append(remote)
        total += remote.size
    return selected


def rebuild_year(flow: Flow, year: int, periods: list[int]) -> Path:
    """Replace some months of a year's final table with their new version.

    Starts from the year's table (local, or downloaded from the latest
    release), drops its rows for the given months and adds those months
    unified again from data/interim/. Months of the year that aren't in the
    table yet are added the same way.

    Args:
        flow: Flow of the table.
        year: Year of the table.
        periods: Months (yyyymm) to replace or add.

    Returns:
        Path to the rebuilt table.
    """
    path = final_path(flow, year)
    frames = [unify_month(flow, period) for period in sorted(periods)]
    if not path.exists():
        try:
            download_release_asset(path.name)
        except requests.HTTPError as error:
            logger.info(
                "%s no está publicado (%s); se arma solo con los meses locales.",
                path.name,
                error,
            )
    if path.exists():
        kept = pl.scan_parquet(path).filter(~pl.col("PERIODO").is_in(periods))
        frames.insert(0, kept)
    tmp_path = path.with_name(f"{path.name}.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.concat(frames).sort("PERIODO", maintain_order=True).sink_parquet(
        tmp_path, compression="zstd", compression_level=9
    )
    tmp_path.replace(path)
    return path


def update(max_bytes: float) -> list[RemoteFile]:
    """Process every monthly file that is new or changed on DIAN's site.

    Args:
        max_bytes: Most bytes of DIAN files to process in this run.

    Returns:
        The files processed, oldest month first; empty if nothing changed.

    Raises:
        ValueError: If a month doesn't match DIAN's control totals, or its
            columns aren't in mapeo_columnas.csv.
    """
    manifest = load_manifest()
    pending = pending_files(manifest, max_bytes)
    logger.info(
        "Archivos nuevos o corregidos en la DIAN: %s",
        [remote.name for remote in pending] or "ninguno",
    )
    if not pending:
        return []

    for flow in {remote.flow for remote in pending}:
        totals = download_file(
            next(r for r in list_remote_files(flow) if r.is_control_totals)
        )
        df_totals = read_control_totals(totals)
        for remote in [r for r in pending if r.flow == flow]:
            assert remote.period is not None
            convert_month_to_parquet(flow, remote.period, download_file(remote))
            failed = [
                check
                for check in validate_month(flow, remote.period, df_totals)
                if not check.ok
            ]
            if failed:
                raise ValueError(
                    f"{remote.name} no coincide con los totales de control de la DIAN: {failed}"
                )

    coverage_path = utils.data_processed_dir(COVERAGE_FILENAME)
    if not coverage_path.exists():
        download_release_asset(COVERAGE_FILENAME)
    years = sorted(
        {(remote.flow, remote.period // 100) for remote in pending if remote.period}
    )
    coverages = []
    for flow, year in years:
        periods = [
            remote.period
            for remote in pending
            if remote.flow == flow and remote.period and remote.period // 100 == year
        ]
        logger.info("Rehaciendo %s %d (meses %s)...", flow, year, periods)
        rebuild_year(flow, year, periods)
        df_validation = validate_year(flow, year)
        if not df_validation["OK"].all():
            raise ValueError(
                f"{flow} {year} no coincide con los totales de control: {df_validation.filter(~pl.col('OK'))}"
            )
        df_losses = typing_losses(flow, year)
        if df_losses.height:
            logger.info(
                "Valores que no se pudieron convertir en %s %d:\n%s",
                flow,
                year,
                df_losses,
            )
        coverages.append(year_coverage(flow, year))
    update_coverage(pl.concat(coverages))

    processed_at = _today()
    for remote in pending:
        assert remote.period is not None
        records = manifest[remote.flow.value]
        old = records.get(str(remote.period))
        previous = (
            []
            if old is None
            else [
                *old.previous,
                PreviousVersion(
                    size=old.size,
                    modified=old.modified,
                    rows=old.rows,
                    processed_at=old.processed_at,
                    replaced_at=processed_at,
                ),
            ]
        )
        records[str(remote.period)] = MonthRecord(
            name=remote.name,
            size=remote.size,
            modified=remote.version,
            rows=_month_rows(remote.flow, remote.period),
            processed_at=processed_at,
            previous=previous,
        )
    save_manifest(manifest)
    return pending


def _write_github_outputs(outputs: dict[str, str]) -> None:
    """Pass values to later workflow steps when running in GitHub Actions.

    Args:
        outputs: Output name -> value. Ignored outside GitHub Actions.
    """
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file is None:
        return
    with Path(output_file).open("a", encoding="utf-8") as file_:
        file_.writelines(f"{name}={value}\n" for name, value in outputs.items())


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada de `python -m colombia_dian_comex.update`.

    Args:
        argv: Argumentos de línea de comandos a parsear. Si es `None`, se
            usan los de `sys.argv`.

    Returns:
        Código de salida del proceso: 0 si la actualización terminó bien.
    """
    parser = argparse.ArgumentParser(
        prog="colombia-dian-update",
        description=(
            "Procesa los meses que la DIAN publicó o corrigió desde la última "
            "actualización (según data/manifest.json) y rehace las tablas de "
            "data/processed/ de los años afectados."
        ),
    )
    parser.add_argument(
        "--max-gb",
        type=float,
        default=DEFAULT_MAX_GB,
        help=f"GB de archivos de la DIAN a procesar como máximo en esta corrida (por defecto {DEFAULT_MAX_GB}).",
    )
    parser.add_argument(
        "--inicializar",
        action="store_true",
        help="Crea data/manifest.json con los meses ya procesados en local, sin descargar nada.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Mensajes detallados (nivel DEBUG).",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
    )

    if args.inicializar:
        manifest = initialize_manifest()
        logger.info(
            "Manifest creado con %s meses.",
            {flow: len(records) for flow, records in manifest.items()},
        )
        return 0

    processed = update(args.max_gb * 1e9)
    if not processed:
        logger.info("No hay meses nuevos ni corregidos. Las tablas ya están al día.")
        _write_github_outputs({"updated": "false"})
        return 0

    years = sorted(
        {
            f"{remote.flow.value}_{remote.period // 100}"
            for remote in processed
            if remote.period
        }
    )
    manifest = load_manifest()
    last = {flow: max(records) for flow, records in manifest.items() if records}
    _write_github_outputs(
        {
            "updated": "true",
            "processed_files": ", ".join(remote.name for remote in processed),
            "changed_assets": " ".join(
                f"data/processed/{name}.parquet" for name in years
            ),
            "last_months": ", ".join(
                f"{flow} {period[:4]}-{period[4:]}" for flow, period in last.items()
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
