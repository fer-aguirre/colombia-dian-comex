"""Tabla de correspondencia de columnas (`mapeo_columnas.csv`).

La DIAN cambió los nombres, la cantidad y a veces el contenido de las columnas
entre 2001 y 2026. `mapeo_columnas.csv` registra, para cada flujo, columna
original y rango de meses, cuál es la columna final, qué tratamiento recibe y
la evidencia que lo respalda (ver README y notebook 0.1). La usa `build` para
unificar los meses en las tablas finales.
"""

from functools import cache
from pathlib import Path

import polars as pl

MAPPING_PATH = Path(__file__).with_name("mapeo_columnas.csv")

MAPPING_SCHEMA = {
    "FLUJO": pl.String,
    "COLUMNA_ORIGINAL": pl.String,
    "DESDE": pl.Int32,
    "HASTA": pl.Int32,
    "COLUMNA_FINAL": pl.String,
    "TRATAMIENTO": pl.String,
    "ESTADO": pl.String,
    "EVIDENCIA": pl.String,
}


@cache
def load_column_mapping() -> pl.DataFrame:
    """Read the column mapping table.

    Returns:
        One row per flow, original column and range of months (DESDE/HASTA
        as yyyymm; an empty HASTA means the column is still current), with its final column (null if the column is dropped),
        treatment, approval status and evidence.
    """
    return pl.read_csv(MAPPING_PATH, schema=MAPPING_SCHEMA)
