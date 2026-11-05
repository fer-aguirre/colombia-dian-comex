"""Descarga de las bases de la DIAN desde la terminal.

Se corre con `uv run python -m colombia_dian_comex.download`. Hace lo mismo
que el notebook `0.0-collect-data.ipynb`: descarga en `data/raw/` los zips
mensuales que falten o hayan cambiado, más los totales de control. Se puede
interrumpir con Ctrl+C y retomar corriendo el mismo comando: lo ya descargado
se saltea y un archivo a medio bajar sigue desde donde quedó (ver
`pipeline.download_file`).
"""

import argparse
import logging
from collections.abc import Sequence

from colombia_dian_comex.pipeline import (
    Flow,
    RemoteFile,
    download_all,
    list_remote_files,
)

logger = logging.getLogger(__name__)


def remotes_to_download(flow: Flow, years: Sequence[int] | None) -> list[RemoteFile]:
    """List a flow's files to download: its control totals plus the chosen months.

    Args:
        flow: Flow whose library is listed.
        years: Years whose monthly files are included, or None for every year.
            The control totals are always included, since they cover every
            year and validate the months.

    Returns:
        Files to download, sorted by name.
    """
    return [
        remote
        for remote in list_remote_files(flow)
        if remote.is_control_totals
        or (
            remote.period is not None
            and (years is None or remote.period // 100 in years)
        )
    ]


def download(
    flows: Sequence[Flow], years: Sequence[int] | None
) -> dict[Flow, list[str]]:
    """Download the chosen flows and years, skipping what is already downloaded.

    Args:
        flows: Flows to download, in order.
        years: Years to download, or None for every year.

    Returns:
        Mapping of flow to the names of the files that failed (empty lists if
        everything was downloaded).
    """
    failed_by_flow = {}
    for flow in flows:
        remotes = remotes_to_download(flow, years)
        logger.info(
            "%s: %d archivos, %.1f GB en el servidor.",
            flow,
            len(remotes),
            sum(remote.size for remote in remotes) / 1e9,
        )
        _, failed_by_flow[flow] = download_all(remotes)
    return failed_by_flow


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada de `python -m colombia_dian_comex.download`.

    Args:
        argv: Argumentos de línea de comandos a parsear. Si es `None`, se
            usan los de `sys.argv`.

    Returns:
        Código de salida del proceso: 0 si se descargó todo, 1 si algún
        archivo falló (volver a correr el comando para reintentarlo).
    """
    parser = argparse.ArgumentParser(
        prog="colombia-dian-download",
        description=(
            "Descarga de la DIAN, en data/raw/, los zips mensuales de "
            "importaciones y exportaciones que falten o hayan cambiado, y los "
            "totales de control. Se puede interrumpir con Ctrl+C y retomar "
            "corriendo el mismo comando."
        ),
    )
    parser.add_argument(
        "-y",
        "--years",
        type=int,
        nargs="+",
        default=None,
        metavar="AÑO",
        help="Años a descargar, separados por espacios (ej. --years 2024 2025). Por defecto, todos desde 2001.",
    )
    parser.add_argument(
        "-f",
        "--flujo",
        type=str.lower,
        nargs="+",
        default=[flow.value for flow in Flow],
        choices=[flow.value for flow in Flow],
        metavar="FLUJO",
        help="importaciones y/o exportaciones. Por defecto, los dos.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    failed_by_flow = download([Flow(flow) for flow in args.flujo], args.years)
    if any(failed_by_flow.values()):
        return 1
    logger.info("Descarga completa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
