# Colombia DIAN Comex

Importaciones y exportaciones de Colombia desde 2001, a partir de las bases estadísticas de comercio exterior que publica la Dirección de Impuestos y Aduanas Nacionales (DIAN), en tablas limpias y fáciles de consultar.

Creado por: Fernanda Aguirre Ruiz

---

## ¿Qué es esto?

La DIAN publica cada mes las bases estadísticas de comercio exterior de Colombia: una fila por cada producto (subpartida arancelaria) de cada declaración de importación o exportación, con importador o exportador, valores, pesos, países, aduana, modalidad, transporte e impuestos. Esos archivos son difíciles de usar tal como vienen:

- Se publican en un zip por mes y por flujo, con un Excel adentro: más de 600 archivos y unos 63 GB comprimidos desde 2001.
- Las columnas cambian con los años: cambian de nombre, aparecen y desaparecen, y en algunos años vienen corridas o con otro contenido bajo el mismo nombre.
- La DIAN corrige y vuelve a subir meses ya publicados.
- Desde 2025 los países usan otra codificación (M49 en vez de ALADI).

Este proyecto toma esos archivos y arma **una tabla por flujo y año**:

- **Desde enero de 2001**: unos 69 millones de filas de importaciones y 24 millones de exportaciones (a noviembre de 2026).
- **Una fila por ítem de declaración** (una subpartida dentro de una declaración).
- **Con las columnas unificadas entre 2001 y hoy**, con los nombres actuales de la DIAN, y el código de país M49 para todos los años.
- **Validada mes por mes contra los totales de control que publica la DIAN** (registros, valor FOB y CIF, peso).
- **Actualizada todas las semanas** de forma automática (ver [Actualización automática](#actualización-automática)).

---

## Por dónde empezar

**Si quieres buscar datos sin escribir código:** abre [`notebooks/0.3-query-data.ipynb`](notebooks/0.3-query-data.ipynb) en Jupyter o VS Code, cambia los valores de la celda de configuración y ejecuta todas las celdas.

**Si prefieres la terminal:**
```bash
uv run colombia-dian-query importaciones --years 2024 --codigo 2701
```

**Si vas a analizar los datos:** lee primero [Qué tener en cuenta al analizar](#qué-tener-en-cuenta-al-analizar) y el [diccionario de datos](DICCIONARIO.md).

**Si quieres entender o revisar cómo se arma:** consulta [Cómo se arman las tablas](#cómo-se-arman-las-tablas). Todas las decisiones están en tablas versionadas en el repositorio, con la evidencia de cada una.

---

## Instalación

El proyecto usa [`uv`](https://docs.astral.sh/uv/), una herramienta que instala Python y todas las librerías necesarias en las versiones exactas del proyecto (definidas en `pyproject.toml` y `uv.lock`). Si todavía no la tienes, sigue su [guía de instalación](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/fer-aguirre/colombia-dian-comex.git
cd colombia-dian-comex
uv sync
```

`uv sync` crea una carpeta `.venv` con todo lo necesario, incluidos los comandos `colombia-dian-query`, `colombia-dian-download` y `colombia-dian-update`. Los comandos y las consultas encuentran las carpetas `data/` y `outputs/` del proyecto aunque se corran desde otra carpeta.

> **En Windows**, si un comando `uv run colombia-dian-...` falla con un error de que una directiva bloqueó el archivo, usa la forma equivalente con `python -m`: por ejemplo `uv run python -m colombia_dian_comex` en vez de `uv run colombia-dian-query`, y `uv run python -m colombia_dian_comex.download` o `.update` para los otros dos.

---

## Conseguir los datos

Las tablas son archivos parquet, uno por flujo y año: `importaciones_2024.parquet` (unos 550 MB), `exportaciones_2024.parquet` (unos 45 MB), etc. Parquet es un formato de tabla comprimido, mucho más liviano y rápido que un CSV; se abre con Python (polars, pandas), R o DuckDB. En total son unos 9,3 GB de importaciones y 1,1 GB de exportaciones.

**No hace falta descargarlas a mano.** Cuando haces una consulta, los años que no están en `data/processed/` se descargan solos desde el [release `datos`](https://github.com/fer-aguirre/colombia-dian-comex/releases/tag/datos) del repositorio en GitHub. Para tener los meses más recientes, borra el archivo del año y vuelve a consultar.

Si prefieres armar todo desde cero con los archivos originales de la DIAN, sigue los pasos de [Cómo se arman las tablas](#cómo-se-arman-las-tablas). Hacen falta unos 75 GB libres y la descarga tarda alrededor de 30 horas, pero se puede interrumpir y retomar.

---

## Consultar los datos

Las consultas funcionan igual desde un notebook o desde la terminal. Hay que indicar el flujo, los años y al menos un **nombre**, un **código** (subpartida) o un **NIT**, para no recorrer millones de filas sin acotar.

| Filtro | Qué es | Ejemplo |
|---|---|---|
| `flujo` | `importaciones` o `exportaciones` | `"importaciones"` |
| `years` | Año o lista de años (no hace falta que sean consecutivos) | `2024` / `[2023, 2024, 2025]` |
| `nombre` *(opcional)* | Nombre de la empresa colombiana que importa o exporta. Busca coincidencias parciales, sin distinguir mayúsculas. En exportaciones solo existe desde 2007. | `"acme"` |
| `codigo` *(opcional)* | Subpartida arancelaria (código NCM), completa (10 dígitos) o solo el comienzo; los puntos son opcionales. Uno o varios | `"2701"` / `"27.01"` / `["2701", "2704"]` |
| `nit` *(opcional)* | NIT de la empresa, sin dígito de verificación. Uno o varios | `"890900608"` |

**Desde un notebook:**
```python
from colombia_dian_comex import utils
from colombia_dian_comex.query import export_query_result, query_comex

resultado = query_comex("importaciones", [2024, 2025], codigo="2701")
export_query_result(resultado, "importaciones", [2024, 2025], query_codigo="2701",
                    output_dir=utils.outputs_tables_dir(), formato="xlsx")
```

**Desde la terminal:**
```bash
uv run colombia-dian-query importaciones --years 2024 2025 -c 2701 -f xlsx
uv run colombia-dian-query exportaciones --years 2023 --nombre "acme" -o outputs/tables
```
Por defecto guarda un CSV en la carpeta desde la que corres el comando. Con `-o` eliges otra carpeta y con `-f` el formato: `csv`, `xlsx` o `parquet`. Todas las opciones aparecen con `--help`.

**El resultado solo trae las columnas que tienen datos en los años consultados.** Una consulta de 2020 a 2026 no muestra las columnas de los formatos viejos de la DIAN (por ejemplo `NUMERO_SERIE_2001_2004`) ni las que la DIAN dejó siempre vacías en esos años; una de 2001 no muestra las columnas que todavía no existían. Las columnas con datos se mantienen aunque todos sus valores sean 0: un 0 es un valor (por ejemplo, "no se cobró antidumping"), no un dato faltante.

> **¿CSV o Excel?** Excel admite como máximo 1.048.576 filas por hoja; para búsquedas amplias usa CSV o parquet.

### Analizar las tablas completas

Para análisis que van más allá de un filtro, puedes leer las tablas directamente. Con [polars](https://docs.pola.rs/) y `scan_parquet`, solo se leen las columnas y filas necesarias:

```python
import polars as pl

from colombia_dian_comex import utils

# Valor CIF importado en 2024 por país de origen (código M49).
df_por_pais = (
    pl.scan_parquet(utils.data_processed_dir("importaciones_2024.parquet"))
    .group_by("CODIGO_PAIS_ORIGEN_M49")
    .agg(pl.col("VALOR_CIF_USD").sum())
    .sort("VALOR_CIF_USD", descending=True)
    .collect()
)
```

---

## Qué tener en cuenta al analizar

**Sobre lo que publica la DIAN** (de su página y su ficha técnica, copias en [`docs/`](docs/)):

- **Una fila es un ítem, no una declaración.** Una declaración con cinco subpartidas distintas aparece en cinco filas.
- **No es la totalidad de las operaciones.** Por metodología estadística, la DIAN excluye ciertas modalidades: en importaciones, por ejemplo, las temporales de corto plazo, las de transformación y ensamble y las reimportaciones en el mismo estado; en exportaciones, el tráfico postal, las temporales, las reexportaciones y los reembarques, entre otras (lista completa en la ficha técnica). Además, algunos valores se ajustan según el Manual de Compiladores de Naciones Unidas. La DIAN aclara que la información no es apta para fines probatorios, sancionatorios, de trámite o de control: su finalidad es estadística.
- **Las cifras desde 2009 son provisionales** y la DIAN las sigue corrigiendo; las de 2001 a 2008 son definitivas.
- **Los datos tardan en publicarse**: unos 35 días después del mes para exportaciones y 45 para importaciones.
- **Personas naturales.** Su nombre se reemplaza por "PERSONA NATURAL" y sus datos de identificación y ubicación no se publican. Para las personas jurídicas, la DIAN publica razón social, NIT, dirección, teléfono y correo, en cumplimiento de un fallo del Tribunal Administrativo de Cundinamarca (19 de septiembre de 2022, expediente 25000-23-41-000-2022-00994-00). Este proyecto los mantiene tal como vienen.
- **Uso responsable.** La DIAN pide que las bases no se comercialicen, adulteren ni usen con fines contrarios a la ley (Ley 1712 de 2014).

**Sobre las columnas a lo largo del tiempo** (detalle en el [diccionario](DICCIONARIO.md) y en [`mapeo_columnas.csv`](colombia_dian_comex/mapeo_columnas.csv)):

- **Muchas columnas no existen en todos los años.** Por ejemplo, fletes, seguros, factura y derechos antidumping de importaciones aparecen en 2003-2007; el nombre del exportador y del destinatario en exportaciones, en 2007. El diccionario indica en qué años tiene datos cada columna.
- **Países: ALADI hasta 2024, M49 desde 2025.** Las columnas de código de país (`CODIGO_PAIS_ORIGEN`, `COD_PAIS_DESTINO_NUM`, etc.) están tal como las publicó la DIAN: hasta 2024 con códigos ALADI y desde 2025 con M49, así que el mismo número puede ser otro país antes y después. **Para series largas usa las columnas `_M49`**, que tienen el código M49 en todos los años (convertido con la correlativa oficial de la DIAN). Quedan vacías donde no hay equivalente: "no declarados" (`999`), países que ya no existen (Antillas Holandesas, Yugoslavia, Serbia y Montenegro) y zonas francas colombianas; en total, entre 0,02% y 1% de las filas según la columna. Los nombres de país también cambian de formato en 2025 (`ESTADOS UNIDOS DE AMÉRICA` → `Estados Unidos de América`).
- **Los códigos de aduana y de lugar de salida se renumeraron** alrededor de 2008-2010 (por ejemplo, Bogotá pasó de 47 a 3 en exportaciones). Para comparar entre años, usa los nombres (`ADUANA_PRESENTADA`, `ADUANA_DESPACHO`, `COD_LUG_SALIDA_ALF`).
- **`MODA_CODIGO_MODALIDAD` no es la modalidad**: pese al nombre, es el código de la aduana (coincide con `COD_ADUANA_PRESENTADA` en 99,6-100% de las filas). La modalidad está en `COD_MODALIDAD_IMPORTACION`.
- **Moneda de las exportaciones.** `COD_MONEDA_TRANSACCION` usa códigos ISO (`USD`) desde 2005. En 2001-2003 la DIAN usaba códigos numéricos propios y en 2004 códigos de país; están aparte, en `COD_MONEDA_TRANSACCION_2001_2003` y `COD_MONEDA_TRANSACCION_2004`, porque no hay una tabla oficial para convertirlos.
- **Unidades de importación 2001-2002** en códigos UN/ECE (`NAR`, `KGM`), aparte en `COD_UNIDAD_COMERCIAL_2001_2002`; desde 2003, `COD_UNIDAD_COMERCIAL` (`U`, `KG`). El nombre de la unidad (`UNIDAD_COMERCIAL`) está en todos los años.
- **`COD_CLASE_IMPORTADOR` en 2004 y 2008** usa letras (`P`, `R`, `M`) que no están en la tabla oficial (01, 02, 03); en esos años `CLASE IMPORTADOR` dice "no declarado o fuera de lista".
- **Fecha de la declaración de exportación**: hasta 2004 la DIAN solo publica año y mes, así que `FECHA_DECLARACION_EXPORTACION` está vacía en 2001-2004; el mes está en `FECHA_PROCESO`. No se inventa un día.
- **Valores redondeados en los primeros años**: los valores y pesos son enteros hasta 2003 en exportaciones y hasta 2002 en importaciones.
- **Descripción de la mercancía recortada**: la DIAN publica `DESCRIPCION_MERCANCIA` cortada en 90 a 120 caracteres.
- **`ACTIVIDAD_ECONOMICA_SEC`** vale 0 desde fines de 2012 (la DIAN dejó de publicarla).

---

## Cómo se arman las tablas

El proceso está dividido en notebooks numerados que se corren en orden; cada uno usa los archivos que deja el anterior y explica en su primera celda qué hace y por qué. El código está en [`colombia_dian_comex/`](colombia_dian_comex/), comentado y documentado.

| Notebook | Qué hace | Entrada | Salida |
|---|---|---|---|
| [`0.0-collect-data.ipynb`](notebooks/0.0-collect-data.ipynb) | Descarga de la DIAN los zips mensuales y los totales de control que falten o hayan cambiado. También desde la terminal (ver [Si la descarga se interrumpe](#si-la-descarga-se-interrumpe)). | Sitio de la DIAN | `data/raw/<flujo>/<año>/*.zip`, `data/raw/<flujo>/totales/*.zip` |
| [`0.1-convert-parquet.ipynb`](notebooks/0.1-convert-parquet.ipynb) | Convierte cada mes a parquet (todas las columnas como texto, tal como vienen), lo valida contra los totales de control y registra qué columnas tiene. | `data/raw/` | `data/interim/<flujo>/<año>/<flujo>_<aaaamm>.parquet` |
| [`0.2-build-tables.ipynb`](notebooks/0.2-build-tables.ipynb) | Unifica las columnas, corrige y tipa los valores, agrega `PERIODO` y M49, y arma una tabla por flujo y año. Vuelve a validar contra los totales de control. | `data/interim/` | `data/processed/<flujo>_<año>.parquet`, `cobertura_columnas.parquet` |
| [`0.3-query-data.ipynb`](notebooks/0.3-query-data.ipynb) | Consulta las tablas y exporta el resultado. | `data/processed/` | CSV, Excel o parquet en `outputs/tables/` |

### 1. Descarga

La DIAN publica los archivos en dos bibliotecas de documentos de su sitio (SharePoint), una por flujo. Los enlaces de la página piden login, pero el contenido se puede listar sin iniciar sesión con la API pública de SharePoint del sitio, que devuelve el nombre, el tamaño y la fecha de modificación de cada archivo.

- **Solo se baja lo que falta o cambió.** Un archivo local con el mismo tamaño y la misma fecha que en el servidor no se vuelve a bajar.
- **Las versiones corregidas no pisan a las anteriores.** Si la DIAN vuelve a subir un mes, la versión nueva se guarda al lado de la vieja como `<nombre>_<fecha del servidor>.zip`. `data/raw/` nunca se modifica.
- **Se le pide poco al servidor**: se espera 2 segundos entre archivos.

#### Si la descarga se interrumpe

La descarga completa son unos 63 GB y tarda alrededor de 30 horas. Conviene correrla desde la terminal, porque un notebook se detiene si se cierra el editor:

```bash
uv run colombia-dian-download
uv run colombia-dian-download --years 2024 2025 --flujo exportaciones
```

Se interrumpe con `Ctrl+C` y se retoma corriendo el mismo comando: los archivos completos se saltean y el que quedó a medias sigue desde el último byte recibido (se guarda en `data/interim/descargas_parciales/` hasta estar completo y verificado). Los cortes de conexión se reintentan solos hasta 5 veces, y un archivo que falla no frena el resto.

### 2. Conversión y validación

Cada Excel se convierte a parquet **con todas las columnas como texto, exactamente como las publica la DIAN**: muchos códigos están guardados como números y leerlos como números les borraría los ceros iniciales. Cada mes se compara con los totales de control de la DIAN: la cantidad de filas tiene que coincidir exactamente y las sumas de valor FOB, CIF y peso neto, salvo redondeo (hasta una millonésima). **Todos los meses publicados coinciden**: al armar el proyecto, en noviembre de 2026, 617 meses y 2.159 comparaciones. Las actualizaciones validan cada mes nuevo o corregido antes de publicarlo.

### 3. Unificación de columnas

Revisando las columnas de todos los meses aparecieron 35 tramos de estructuras distintas, columnas renombradas, columnas que van y vienen, columnas corridas respecto de sus datos y columnas con el mismo nombre pero otro contenido. Cada caso se resolvió con evidencia de los datos (misma posición en el archivo, mismos NIT y nombres en los meses vecinos, mismos valores), y la decisión y su evidencia quedaron en [`colombia_dian_comex/mapeo_columnas.csv`](colombia_dian_comex/mapeo_columnas.csv), una fila por columna original y rango de meses (`DESDE` y `HASTA`, en aaaamm; un `HASTA` vacío indica que la columna sigue vigente):

| Tratamiento | Qué se hizo | Ejemplo |
|---|---|---|
| `igual` | Mismo nombre y contenido; no cambia nada | La mayoría de las columnas |
| `renombrada` | El mismo dato con otro nombre se une bajo el nombre actual de la DIAN | `IMPORTADOR` → `NOMBRE_IMPORTADOR` (alterna de nombre mes a mes en 2008, en la misma posición) |
| `desalineada` | Columnas con el nombre corrido respecto de los datos se mueven a la columna que corresponde a su contenido | Exportaciones 2004-2006: `TIPO_DESPACHO` trae el lugar de salida → `COD_LUGAR_SALIDA_NUM` |
| `colision` | Mismo nombre, contenido incompatible: los años viejos van a una columna aparte, con el período en el nombre | `NUMERO_SERIE` de 2001-2004 → `NUMERO_SERIE_2001_2004` |
| `solo_estructura_vieja` | Columnas sin equivalente en la estructura actual; se mantienen con su nombre original | `NUM_MANIFIESTO`, `PERIODICIDAD_PAGO_CUOTA` |
| `eliminada` | Columnas que solo valen "1" en todos los meses en que aparecen; no tienen información | `NOMBRE_ADUANA (1)`, `ACTIVO1` |

Si la DIAN publica una columna que esta tabla no contempla, la construcción se detiene: una estructura nueva hay que revisarla antes de unificarla.

### 4. Limpieza y tipos

| Corrección | Por qué |
|---|---|
| Se quitan los espacios sobrantes y el `.0` que Excel agrega a los códigos (`3.0` → `3`) | Formato de Excel, no del dato |
| La subpartida se completa a 10 dígitos con ceros a la izquierda | La DIAN publica algunas sin el cero inicial (capítulos 01 a 09) |
| En las columnas de números y fechas de referencia donde la DIAN escribe `0` para decir "no aplica", el `0` pasa a vacío. Los montos en `0` quedan en `0` | Desde febrero de 2017 la DIAN escribe `0` donde antes dejaba vacío; así "sin dato" significa lo mismo en todos los años. Las columnas afectadas están marcadas en [`esquema_final.csv`](colombia_dian_comex/esquema_final.csv) (`CERO_ES_VACIO`) |
| `IDENTIFICACION_FORMULARIO` queda vacía donde la DIAN la publicó en notación científica (2004-10 a 2004-12 y 2008) | Esa notación perdió dígitos; el número completo está en `NUMERO_FORMULARIO` |
| Donde la DIAN escribió "no declarado o fuera de lista" pero el código es válido, se recupera el nombre del código: `TIPO_IMPORTACION` y `FORMA_PAGO` (2004 y 2008) y `TIPO_DESPACHO` (exportaciones 2004-2006, desde `TIPO_DECLARACION`) | El dato está en el código. Las tablas usadas, con su fuente, están en [`colombia_dian_comex/tablas/`](colombia_dian_comex/tablas/); solo se reemplaza el texto "no declarado", nunca un nombre válido |
| Se agrega `PERIODO` (mes del archivo, aaaamm) y una columna `_M49` al lado de cada código de país | Para filtrar por mes y para series de países que no se corten en 2025 |

Los tipos de cada columna están en [`esquema_final.csv`](colombia_dian_comex/esquema_final.csv): los códigos, NIT y números de documento son texto (para no perder ceros iniciales), los montos, pesos y cantidades son números y las fechas aaaammdd son fechas. **Los valores que no se pueden convertir quedan vacíos y se cuentan** en el notebook 0.2: son fechas inválidas que publica la DIAN (`20010229`, `20050300`, `2008513`), menos de 1.000 por columna en 69 millones de filas de importaciones; el texto original sigue en `data/interim/`.

Después de armar cada año se vuelve a comparar con los totales de control de la DIAN: **todas las comparaciones siguen coincidiendo**, así que unificar y tipar no perdió ni duplicó filas ni montos.

---

## Actualización automática

Un proceso automático en GitHub (un *workflow* de GitHub Actions, definido en [`.github/workflows/update-data.yml`](.github/workflows/update-data.yml)) revisa **todos los lunes** el tamaño y la fecha de cada archivo mensual en la DIAN, porque la DIAN no publica en una fecha fija y además vuelve a subir meses corregidos. Si algún mes es nuevo o cambió:

1. Descarga y convierte **solo esos meses**, y los valida contra los totales de control. Si no coinciden, se detiene sin publicar nada.
2. Rehace las tablas de los **años afectados**: parte de la tabla publicada del año, le quita los meses que cambiaron y les agrega su versión nueva, y la vuelve a validar.
3. Reemplaza esos archivos en el release `datos` del repositorio y anota los meses en [`data/manifest.json`](data/manifest.json): para cada mes guarda el tamaño y la fecha del archivo en la DIAN, cuántas filas tiene y cuándo se procesó. Si la DIAN volvió a subir un mes, la versión anterior queda anotada en `previous`.

Una corrida procesa como mucho 6 GB de archivos de la DIAN (unas 3,5 horas de descarga); si hay más, el resto queda para la semana siguiente. También se puede correr a mano desde la pestaña **Actions** (botón *Run workflow*) o, en tu computadora, con `uv run colombia-dian-update`.

---

## Estructura del proyecto

```
colombia_dian_comex/
├─ colombia_dian_comex/       # Código del proyecto
│  ├─ __init__.py             # Expone query_comex y export_query_result
│  ├─ __main__.py             # Permite `python -m colombia_dian_comex` (consultas)
│  ├─ pipeline.py             # Descarga, conversión y validación
│  ├─ download.py             # Descarga desde la terminal
│  ├─ build.py                # Tablas finales: unificación, limpieza, tipos, M49
│  ├─ mapping.py              # Lectura de mapeo_columnas.csv
│  ├─ query.py                # Consultas y exportación
│  ├─ update.py               # Actualización con los meses nuevos o corregidos
│  ├─ utils.py                # Rutas a las carpetas del proyecto
│  ├─ mapeo_columnas.csv      # Columna original → columna final, con evidencia
│  ├─ esquema_final.csv       # Columnas finales: orden, tipo y tratamiento
│  └─ tablas/                 # Códigos → nombres para los textos "no declarado"
│
├─ notebooks/                 # Los pasos del proceso, numerados
├─ data/
│  ├─ raw/                    # Zips originales de la DIAN (nunca se modifican)
│  ├─ interim/                # Parquet por mes, controles e inventario de columnas
│  ├─ processed/              # Tablas finales por flujo y año, y cobertura de columnas
│  └─ manifest.json           # Registro de meses procesados
│
├─ docs/                      # Documentos oficiales de la DIAN (ver docs/FUENTES.md)
├─ DICCIONARIO.md             # Diccionario de datos
├─ .github/workflows/         # Actualización automática semanal
├─ outputs/tables/            # Resultados de las consultas
├─ pyproject.toml             # Librerías del proyecto
└─ README.md
```

---

## Fuentes

- Bases estadísticas de comercio exterior, importaciones y exportaciones, DIAN: https://www.dian.gov.co/dian/cifras/Paginas/Bases-Estadisticas-de-Comercio-Exterior-Importaciones-y-Exportaciones.aspx. Consultado el 2026-10-10.
- Ficha técnica, ficha metodológica, correlativa M49-ALADI, totales de control y copia de la página: [`docs/`](docs/). El detalle de cada archivo, con su URL, fecha de descarga y hash, está en [`docs/FUENTES.md`](docs/FUENTES.md).

---

## Licencia

Este proyecto se distribuye bajo licencia [MIT](LICENSE).

---

Este repositorio fue generado con [cookiecutter](https://github.com/fer-aguirre/cookiecutter-data-analysis-lite).
