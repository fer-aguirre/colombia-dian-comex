"""Rutas a las carpetas del proyecto.

Las rutas se arman a partir de la ubicación de este paquete, no de la carpeta
desde la que se corre el código, así que las consultas y comandos encuentran
`data/` y `outputs/` aunque se ejecuten desde cualquier otra carpeta.
"""

from collections.abc import Callable
from pathlib import Path

# The package lives in <project>/colombia_dian_comex/, installed in editable
# mode by `uv sync`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_dir_function(*parts: str) -> Callable[..., Path]:
    """Build a function returning a path under the project root.

    Args:
        *parts: Folders under the project root (e.g. "data", "raw").

    Returns:
        A function that extends that folder with any given parts.
    """

    def dir_path(*args: str) -> Path:
        """Return the folder extended with the given parts."""
        return PROJECT_ROOT.joinpath(*parts, *args)

    return dir_path


project_dir = make_dir_function()
data_dir = make_dir_function("data")
data_raw_dir = make_dir_function("data", "raw")
data_processed_dir = make_dir_function("data", "processed")
data_interim_dir = make_dir_function("data", "interim")
outputs_dir = make_dir_function("outputs")
outputs_figures_dir = make_dir_function("outputs", "figures")
outputs_tables_dir = make_dir_function("outputs", "tables")
assets_dir = make_dir_function("assets")
