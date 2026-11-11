"""Parámetros de una consulta y nombre del archivo exportado.

`Consulta` guarda la búsqueda una sola vez: la usan tanto `query_data` (para
filtrar) como `export_query_result` (para nombrar el archivo), así el nombre
siempre describe los datos que contiene. Valida y normaliza los valores al
crearse.

Formato del nombre exportado (las partes vacías se omiten):

    <país>_<régimen>_<nombre>_<códigos>_nit<nits>_<años>_<AAAAMMDDTHHMMSS>.<formato>
    ej. co_importacion_acme_2701-8420_2019-2021+2024_20261111T153012.csv

Este módulo tiene la misma estructura en argentina_afip_comex,
uruguay_dua_comex y colombia_dian_comex. Solo cambia lo propio de cada país:
`COUNTRY_PREFIX` y el régimen (fijo en Argentina; elegible en Uruguay). En
Colombia el régimen es obligatorio, porque la DIAN publica importaciones y
exportaciones como bases separadas, con columnas distintas. Colombia agrega
además el filtro por NIT.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from colombia_dian_comex.pipeline import Flow

# --- Propio de cada país ---
# Prefijo al inicio de cada archivo exportado.
COUNTRY_PREFIX = "co"
# Códigos cortos aceptados para tipo_regimen, mapeados a la base de la DIAN
# que se consulta.
TIPO_REGIMEN_MAP = {
    "i": Flow.IMPORTACIONES,
    "e": Flow.EXPORTACIONES,
}
# Régimen tal como se escribe en el nombre del archivo (en singular, igual
# que en los otros dos proyectos).
REGIMEN_LABELS = {
    Flow.IMPORTACIONES: "importacion",
    Flow.EXPORTACIONES: "exportacion",
}

# --- Común a los tres proyectos ---
# Largo máximo de la parte del nombre de importador en el archivo.
MAX_NOMBRE_CHARS = 40
# Cantidad máxima de códigos (subpartidas o NIT) que se escriben en el
# archivo; el resto se resume como "-y<N>mas".
MAX_CODES_IN_NAME = 3
# Fecha y hora de exportación en formato básico ISO 8601 (ej. 20261111T153012).
# No usa "_" ni "-", que ya separan las partes del nombre y los rangos de años.
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%S"

# Matches any character that isn't a digit, to strip separators from a code.
NON_DIGIT_PATTERN = re.compile(r"\D+")
# Runs of characters that aren't safe in a filename on every OS.
UNSAFE_CHARS_PATTERN = re.compile(r"[^a-z0-9.-]+")


def normalize_code(code: str) -> str:
    """Strip separators from a NANDINA subpartida, prefix or NIT.

    People write codes with dots (e.g. "27.01" or "900.585.965") or without
    (e.g. "2701"). Stripping non-digit characters makes all forms equivalent.

    Args:
        code: Subpartida, prefix or NIT, with or without separators.

    Returns:
        The code with any non-digit characters removed.
    """
    return NON_DIGIT_PATTERN.sub("", code)


def _normalize_codes(codes: str | Sequence[str], label: str) -> tuple[str, ...]:
    """Validate codes and return them digit-only, sorted and unique.

    Args:
        codes: One code or a list of codes, as written by the user.
        label: Name of the parameter, used in error messages ("codigo", "nit").

    Returns:
        The digit-only codes, sorted and without duplicates.

    Raises:
        ValueError: If the list is empty or a code has no digits.
    """
    raw_codes = [codes] if isinstance(codes, str) else codes
    if not raw_codes:
        raise ValueError(f"`{label}` está vacío.")
    for code in raw_codes:
        # Un código sin dígitos coincidiría con todas las filas.
        if not normalize_code(code):
            raise ValueError(
                f"`{label}` inválido: {code!r}. Debe tener al menos un dígito."
            )
    return tuple(sorted({normalize_code(code) for code in raw_codes}))


def _slug(text: str) -> str:
    """Turn free text into a filename-safe part.

    Removes accents, lowercases, replaces every run of unsafe characters
    (spaces, "/", ":", tabs, etc.) with a single "_" and trims "_" and "."
    from the ends, so the part can't create folders or hidden files.

    Args:
        text: Text to convert, e.g. an importer name.

    Returns:
        The filename-safe text, e.g. "Café del Sur S.A." -> "cafe_del_sur_s.a".
    """
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return UNSAFE_CHARS_PATTERN.sub("_", ascii_text.lower()).strip("_.")


def _years_label(years: tuple[int, ...]) -> str:
    """Describe sorted years, collapsing consecutive ones into ranges.

    Args:
        years: Sorted, unique years.

    Returns:
        E.g. (2024,) -> "2024"; (2019, 2020, 2021, 2024) -> "2019-2021+2024".
    """
    groups: list[list[int]] = []
    for year in years:
        # Extend the current group if this year follows it, else start a new one.
        if groups and year == groups[-1][-1] + 1:
            groups[-1].append(year)
        else:
            groups.append([year])
    return "+".join(
        str(group[0]) if len(group) == 1 else f"{group[0]}-{group[-1]}"
        for group in groups
    )


def _codes_label(codes: tuple[str, ...]) -> str:
    """Describe codes, listing at most MAX_CODES_IN_NAME of them.

    Args:
        codes: Sorted, unique, digit-only codes.

    Returns:
        E.g. ("2701", "2702") -> "2701-2702";
        ("01", "02", "03", "04", "05") -> "01-02-03-y2mas".
    """
    label = "-".join(codes[:MAX_CODES_IN_NAME])
    extra = len(codes) - MAX_CODES_IN_NAME
    return f"{label}-y{extra}mas" if extra > 0 else label


@dataclass(frozen=True)
class Consulta:
    """Parámetros de una búsqueda en las bases de la DIAN.

    Se pasan los valores tal como los escribe el usuario (`years`,
    `tipo_regimen`, `nombre`, `codigo`, `nit`) y al crearse se validan y
    normalizan en los campos `*_value(s)`, que son los que usan la consulta y
    el nombre del archivo.

    Attributes:
        years: Año o lista de años a consultar.
        tipo_regimen: "i" (importaciones) o "e" (exportaciones). No distingue
            mayúsculas/minúsculas.
        nombre: Nombre (o parte del nombre) del importador o exportador. Se
            busca como texto literal y no distingue mayúsculas/minúsculas.
            En exportaciones solo existe desde 2007, y a veces figura como
            "PERSONA NATURAL": para no perder filas, conviene buscar por NIT.
        codigo: Subpartida arancelaria NANDINA (10 dígitos) o lista de
            subpartidas/prefijos. Los puntos u otros separadores son
            opcionales (ej. "27.01" equivale a "2701").
        nit: NIT o lista de NIT del importador o exportador, sin dígito de
            verificación. Los puntos o guiones se ignoran.
        year_values: Años ordenados y sin duplicados.
        regimen_value: Base que se consulta (importaciones o exportaciones).
        nombre_value: `nombre` sin espacios al inicio ni al final.
        codigo_values: Subpartidas solo con dígitos, ordenadas y sin
            duplicados (vacío si no se indicó `codigo`).
        nit_values: NIT solo con dígitos, ordenados y sin duplicados (vacío
            si no se indicó `nit`).

    Raises:
        ValueError: Si no hay años, si `tipo_regimen` no es "i" ni "e", si
            `nombre` está vacío, si algún código o NIT no tiene dígitos, o si
            no se indica `nombre`, `codigo` ni `nit`.
    """

    years: int | Sequence[int]
    tipo_regimen: str
    nombre: str | None = None
    codigo: str | Sequence[str] | None = None
    nit: str | Sequence[str] | None = None
    year_values: tuple[int, ...] = field(init=False, repr=False, compare=False)
    regimen_value: Flow = field(init=False, repr=False, compare=False)
    nombre_value: str | None = field(init=False, repr=False, compare=False)
    codigo_values: tuple[str, ...] = field(init=False, repr=False, compare=False)
    nit_values: tuple[str, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate the inputs and fill the normalized `*_value(s)` fields."""
        year_values = tuple(
            sorted({self.years} if isinstance(self.years, int) else set(self.years))
        )
        if not year_values:
            raise ValueError("Debe indicar al menos un año.")

        regimen_code = self.tipo_regimen.lower()
        if regimen_code not in TIPO_REGIMEN_MAP:
            valid = ", ".join(
                f"{code} ({flow.value})" for code, flow in TIPO_REGIMEN_MAP.items()
            )
            raise ValueError(
                f"tipo_regimen inválido: {self.tipo_regimen!r}. Valores válidos: {valid}."
            )

        nombre_value = None
        if self.nombre is not None:
            nombre_value = self.nombre.strip()
            # Un nombre vacío coincidiría con todas las filas.
            if not nombre_value:
                raise ValueError("`nombre` está vacío.")

        codigo_values = (
            _normalize_codes(self.codigo, "codigo") if self.codigo is not None else ()
        )
        nit_values = _normalize_codes(self.nit, "nit") if self.nit is not None else ()

        if nombre_value is None and not codigo_values and not nit_values:
            raise ValueError("Debe indicar al menos `nombre`, `codigo` o `nit`.")

        # Frozen dataclass: los campos derivados se asignan con object.__setattr__.
        object.__setattr__(self, "year_values", year_values)
        object.__setattr__(self, "regimen_value", TIPO_REGIMEN_MAP[regimen_code])
        object.__setattr__(self, "nombre_value", nombre_value)
        object.__setattr__(self, "codigo_values", codigo_values)
        object.__setattr__(self, "nit_values", nit_values)

    def export_filename(self, formato: str) -> str:
        """Arma el nombre del archivo exportado para esta consulta.

        Incluye la fecha y hora actual (hasta segundos) para que exports
        repetidos no se pisen. Ver el formato en la docstring del módulo.

        Args:
            formato: Extensión del archivo ("csv", "xlsx" o "parquet").

        Returns:
            Nombre de archivo sin carpeta, seguro en cualquier sistema.
        """
        parts = [COUNTRY_PREFIX, REGIMEN_LABELS[self.regimen_value]]
        if self.nombre_value is not None:
            # Si el nombre queda vacío al limpiarlo (ej. "???"), se omite.
            nombre_part = _slug(self.nombre_value)[:MAX_NOMBRE_CHARS].rstrip("_.-")
            if nombre_part:
                parts.append(nombre_part)
        if self.codigo_values:
            parts.append(_codes_label(self.codigo_values))
        if self.nit_values:
            # Prefijo "nit" para distinguirlos de las subpartidas.
            parts.append(f"nit{_codes_label(self.nit_values)}")
        parts.append(_years_label(self.year_values))
        # Hora local de quien exporta.
        parts.append(datetime.now().astimezone().strftime(TIMESTAMP_FORMAT))
        return f"{'_'.join(parts)}.{formato}"
