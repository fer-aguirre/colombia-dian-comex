# Diccionario de datos

Columnas de las tablas finales (`data/processed/<flujo>_<año>.parquet`), en el orden en que aparecen. Este archivo se genera a partir de [`colombia_dian_comex/esquema_final.csv`](colombia_dian_comex/esquema_final.csv) (tipos), [`colombia_dian_comex/mapeo_columnas.csv`](colombia_dian_comex/mapeo_columnas.csv) (de qué columnas originales sale cada una) y la tabla de cobertura (en qué años tiene datos).

- **Años con datos**: años en los que la columna tiene al menos un valor. Las consultas no muestran las columnas sin datos en ninguno de los años consultados.
- **Columnas originales**: nombre o nombres con que la DIAN publicó la columna, si alguna vez fue distinto del final. El detalle y la evidencia de cada correspondencia están en `mapeo_columnas.csv`.
- **Tipos**: los códigos, NIT y números de documento son texto, para no perder ceros iniciales; los montos están en la moneda o unidad que indica su nombre (USD, pesos, kg).
- La DIAN no publica descripciones de cada columna más allá de su nombre; la estructura oficial está en la [ficha técnica](docs/Ficha-Tecnica-bases-estadisticas-de-Comercio-Exterior.pdf).

## Importaciones

| # | Columna | Tipo | Años con datos | Columnas originales | Nota |
|---|---|---|---|---|---|
| 1 | `PERIODO` | entero | 2001-2026 |  | Mes del archivo de la DIAN (aaaamm). Columna agregada. |
| 2 | `BANC_CODIGO_BANCO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 3 | `COD_ADUANA_PRESENTADA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 4 | `ADUANA_PRESENTADA` | texto | 2001-2026 |  |  |
| 5 | `CODIGO_SUCURSAL` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 6 | `CODIGO_CAJERO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 7 | `CONSECUTIVO_CAJERO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 8 | `DIGITO_VERIFICACION_DOC` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 9 | `CODIGO_MODALIDAD_DECLARAC` | texto | 2001-2026 |  |  |
| 10 | `COD_TIPO_DECLARACION` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 11 | `TIPO_DECLARACION` | texto | 2001-2026 |  |  |
| 12 | `NUM_DECLARACION_ANT` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 13 | `FECHA_DECLARACION_ANT` | fecha | 2001-2026 |  | aaaammdd convertido a fecha; vacío si no es una fecha completa. Un 0 ("no aplica") se deja vacío. |
| 14 | `MANIFIESTO_DE_CARGA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 15 | `FECHA_MANIFIESTO` | fecha | 2001-2026 |  | aaaammdd convertido a fecha; vacío si no es una fecha completa. |
| 16 | `DOCUMENTO_TRANSPORTE` | texto | 2001-2026 |  |  |
| 17 | `MODA_CODIGO_MODALIDAD` | código (texto) | 2001-2026 | `CODIGO_ADMON_ADUANA` | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 18 | `CODIGO_DEPOSITO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 19 | `RAZON_SOCIAL_DECLARANTE` | texto | 2001-2026 | `DECLARANTE AUTORIZADO` |  |
| 20 | `TIPO_IDENTIFICAC_DECLARAN` | texto | 2001-2026 |  |  |
| 21 | `NIT_DECLARANTE` | código (texto) | 2001-2026 | `NUME_IDENTIFICAC_DECLAR` | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 22 | `DIGITO_VERIFI_NIT_DECLARA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 23 | `NOMBRE_IMPORTADOR` | texto | 2001-2026 | `IMPORTADOR` |  |
| 24 | `TIPO_IDENTIFICAC_IMPORTAD` | texto | 2001-2026 |  |  |
| 25 | `NIT_IMPORTADOR` | código (texto) | 2001-2026 | `NUMERO_IDENTIFICAC_IMPORT` | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 26 | `DIGITO_VERIFI_NIT_IMPORTA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 27 | `CIUDAD_PAIS_IMPORTADOR` | texto | 2001-2004 |  |  |
| 28 | `DIRECCION_IMPORTADOR` | texto | 2001-2026 |  |  |
| 29 | `NOMBRE_EXPORTADOR` | texto | 2001-2026 | `EXPORTADOR` |  |
| 30 | `TIPO_IDENTIFICAC_EXPORTAD` | texto | 2001-2026 |  |  |
| 31 | `NUMERO_IDENTIFICAC_EXPORT` | texto | 2007 |  |  |
| 32 | `DIGITO_VERIFI_NIT_EXPORTA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 33 | `DIRECCION_EXPORTADOR` | texto | 2001-2026 |  |  |
| 34 | `CIUDAD_PAIS_EXPORTADOR` | texto | 2001-2026 |  |  |
| 35 | `ACTIVIDAD_ECONOMICA_SEC` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 36 | `CODIGO_PAIS_PROCEDENCIA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 37 | `CODIGO_PAIS_PROCEDENCIA_M49` | código (texto) | 2001-2026 |  | Código M49 de CODIGO_PAIS_PROCEDENCIA: el original desde 2025; hasta 2024, convertido desde ALADI con la correlativa oficial (vacío si no tiene equivalente). Columna agregada. |
| 38 | `PAIS_PROCEDENCIA` | texto | 2001-2026 |  |  |
| 39 | `COD_MODO_TRANSPORTE` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 40 | `MODO_TRANSPORTE` | texto | 2001-2026 |  |  |
| 41 | `COD_BANDERA_TRANSPORTE` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 42 | `COD_BANDERA_TRANSPORTE_M49` | código (texto) | 2001-2026 |  | Código M49 de COD_BANDERA_TRANSPORTE: el original desde 2025; hasta 2024, convertido desde ALADI con la correlativa oficial (vacío si no tiene equivalente). Columna agregada. |
| 43 | `BANDERA_TRANSPORTE` | texto | 2001-2026 |  |  |
| 44 | `EMPRESA_TRANSPORTADORA` | texto | 2001-2026 |  |  |
| 45 | `CODIGO_ENTIDAD_INTERMEDIA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 46 | `TASA_CAMBIO` | número | 2001-2026 |  |  |
| 47 | `COD_DEPARTAMENTO_DESTINO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 48 | `DEPARTAMENTO_DESTINO` | texto | 2001-2026 |  |  |
| 49 | `COD_MODALIDAD_IMPORTACION` | texto | 2001-2026 |  |  |
| 50 | `NUM_CUOTAS_O_MESES` | número | 2001-2026 |  |  |
| 51 | `SUBPARTIDA_ARANCELARIA` | código (texto) | 2001-2026 |  | Completada a 10 dígitos con ceros a la izquierda (la DIAN publica algunas sin el cero inicial). |
| 52 | `PESO_NETO` | número | 2001-2026 |  |  |
| 53 | `VALOR_FOB_USD` | número | 2001-2026 |  |  |
| 54 | `CODIGO_PAIS_ORIGEN` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 55 | `CODIGO_PAIS_ORIGEN_M49` | código (texto) | 2001-2026 |  | Código M49 de CODIGO_PAIS_ORIGEN: el original desde 2025; hasta 2024, convertido desde ALADI con la correlativa oficial (vacío si no tiene equivalente). Columna agregada. |
| 56 | `PAIS_ORIGEN` | texto | 2001-2026 |  |  |
| 57 | `CODIGO_ACUERDO` | texto | 2001-2026 |  |  |
| 58 | `PESO_BRUTO` | número | 2001-2026 |  |  |
| 59 | `FLETES_SEGUROS1` | número | 2001-2026 |  |  |
| 60 | `VALOR_AJUSTE_USD` | número | 2001-2026 |  |  |
| 61 | `VALOR_ADUANA_USD` | número | 2001-2026 |  |  |
| 62 | `CODIGO_EMBALAJE` | texto | 2001-2026 |  |  |
| 63 | `CLASE_DE_EMBALAJE` | texto | 2001-2026 |  |  |
| 64 | `NUMERO_BULTOS` | número | 2001-2026 |  |  |
| 65 | `CANTIDAD_SUBPARTIDAS` | número | 2001-2026 |  |  |
| 66 | `CANTIDAD` | número | 2001-2026 |  |  |
| 67 | `COD_UNIDAD_COMERCIAL` | texto | 2003-2026 |  |  |
| 68 | `UNIDAD_COMERCIAL` | texto | 2001-2026 |  |  |
| 69 | `NUM_REGISTRO_LICENCIA` | texto | 2001-2026 |  | Un 0 ("no aplica") se deja vacío. |
| 70 | `CODIGO_OFICINA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 71 | `AÑO_REGISTRO_LICENCIA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 72 | `DESCRIPCION_MERCANCIA` | texto | 2001-2026 |  |  |
| 73 | `PORCENTAJE_ARANCEL` | número | 2001-2026 |  |  |
| 74 | `BASE_ARANCEL` | número | 2001-2026 |  |  |
| 75 | `TOTAL_LIQUIDADO_ARANCEL` | número | 2001-2026 |  |  |
| 76 | `PORCENTAJE_IVA` | número | 2001-2026 |  |  |
| 77 | `BASE_IVA` | número | 2001-2026 |  |  |
| 78 | `TOTAL_LIQUIDADO_IVA` | número | 2001-2026 |  |  |
| 79 | `PORCENTAJE_OTROS1` | número | 2001-2026 |  |  |
| 80 | `BASE_OTROS1` | número | 2001-2026 |  |  |
| 81 | `SUBTOTAL_OTROS1` | número | 2001-2026 |  |  |
| 82 | `TOTAL_ITEM1` | número | 2001-2026 |  |  |
| 83 | `VALOR_TOTAL_ARANCEL` | número | 2001-2026 |  |  |
| 84 | `VALOR_TOTAL_IVA` | número | 2001-2026 |  |  |
| 85 | `VALOR_TOTAL_OTROS` | número | 2001-2026 |  |  |
| 86 | `TOTAL_LIQUIDADO_SANCION` | número | 2001-2026 |  |  |
| 87 | `TOTAL_LIQUIDADO` | número | 2001-2026 |  |  |
| 88 | `PAGO_TOTAL` | número | 2001-2026 |  |  |
| 89 | `FECHA_PRESENTACION` | fecha | 2001-2026 |  | aaaammdd convertido a fecha; vacío si no es una fecha completa. |
| 90 | `NUMERO_FORMULARIO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 91 | `VALOR_PAGOS_ANTERIORES` | número | 2001-2026 | `TP_EFECTUADOS` |  |
| 92 | `COD_ADUANA_ANTERIOR` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 93 | `NUM_DECLARACION_EXPORT` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 94 | `FECHA_DECLARACION_EXPORT` | fecha | 2001-2026 |  | aaaammdd convertido a fecha; vacío si no es una fecha completa. Un 0 ("no aplica") se deja vacío. |
| 95 | `COD_ADUANA_EXPORT` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 96 | `COD_CLASE_IMPORTADOR` | texto | 2001-2026 |  |  |
| 97 | `CLASE IMPORTADOR` | texto | 2001-2026 |  |  |
| 98 | `CODIGO_DEPTO_IMPORTADOR` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 99 | `DEPARTAMENTO_IMPORTADOR` | texto | 2001-2026 |  |  |
| 100 | `CODIGO_PAIS_EXPORTADOR` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 101 | `CODIGO_PAIS_EXPORTADOR_M49` | código (texto) | 2001-2026 |  | Código M49 de CODIGO_PAIS_EXPORTADOR: el original desde 2025; hasta 2024, convertido desde ALADI con la correlativa oficial (vacío si no tiene equivalente). Columna agregada. |
| 102 | `PAIS_EXPORTADOR` | texto | 2001-2026 |  |  |
| 103 | `NUME_DECLARA_CAMBIO` | texto | 2001-2002 |  | Un 0 ("no aplica") se deja vacío. |
| 104 | `FECHA_DECLARA_CAMBIO` | fecha | 2001 |  | aaaammdd convertido a fecha; vacío si no es una fecha completa. Un 0 ("no aplica") se deja vacío. |
| 105 | `COD_FORMA_PAGO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 106 | `FORMA_PAGO` | texto | 2001-2026 |  |  |
| 107 | `COD_TIPO_IMPORTACION` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 108 | `TIPO_IMPORTACION` | texto | 2001-2026 |  |  |
| 109 | `CODIGO_PAIS_COMPRA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 110 | `CODIGO_PAIS_COMPRA_M49` | código (texto) | 2001-2026 |  | Código M49 de CODIGO_PAIS_COMPRA: el original desde 2025; hasta 2024, convertido desde ALADI con la correlativa oficial (vacío si no tiene equivalente). Columna agregada. |
| 111 | `PAIS_COMPRA` | texto | 2001-2026 |  |  |
| 112 | `TIPO_DOCUMENTO1` | texto | 2001-2026 |  |  |
| 113 | `USUARIO_DIAN1` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 114 | `CODIGO_USUARIO_DIAN1` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 115 | `NUM_RECIBO_PAGO_ANTERIOR` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 116 | `FECHA_RECIBO_PAGO_ANTERIOR` | fecha | 2001-2004, 2008 |  | aaaammdd convertido a fecha; vacío si no es una fecha completa. Un 0 ("no aplica") se deja vacío. |
| 117 | `NRO_CERTIFICADO_INSPECCION` | código (texto) | 2003-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 118 | `FECHA_DOCUMENTO_TRANSP` | fecha | 2001-2026 |  | aaaammdd convertido a fecha; vacío si no es una fecha completa. |
| 119 | `TOTAL_A_PAGAR_ARANCEL` | número | 2001-2026 |  |  |
| 120 | `TOTAL_A_PAGAR_IVA` | número | 2001-2026 |  |  |
| 121 | `OTROS_PAGADOS` | número | 2001-2026 |  |  |
| 122 | `TOTAL_A_PAGAR_SANCION` | número | 2001-2026 |  |  |
| 123 | `TELEFONO_IMPORTADOR` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 124 | `NUM_ACEPTACION_DECLARACION` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 125 | `FECHA_ACEPTACION_DECLARACION` | fecha | 2001-2026 |  | aaaammdd convertido a fecha; vacío si no es una fecha completa. |
| 126 | `VALOR_CUOTA_USD` | número | 2003-2026 |  |  |
| 127 | `PER_PAGO_CUOTA_1` | número | 2004-2026 |  |  |
| 128 | `VALOR_SEGUROS_USD` | número | 2003-2026 |  |  |
| 129 | `VALOR_FLETES_USD` | número | 2003-2026 |  |  |
| 130 | `VALOR_OTROS_GASTOS_USD` | número | 2003-2026 |  |  |
| 131 | `LUGAR_INGRESO_MCIA` | texto | 2003-2026 |  |  |
| 132 | `COD_LUGAR_INGRESO_MCIA` | texto | 2003-2026 |  |  |
| 133 | `IDENTIFICADOR_DOCUMENTO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 134 | `IDENTIFICACION_FORMULARIO` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 135 | `CODIGO_MUNICIPIO` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 136 | `DOCTO_IDENTIF_DECLAR` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 137 | `NOMBRE_DECLARANTE` | texto | 2004-2026 |  |  |
| 138 | `EMAIL_EXPORTADOR` | texto | 2004-2026 |  |  |
| 139 | `NUMERO_FACTURA` | texto | 2004-2026 |  |  |
| 140 | `FECHA_FACTURA` | fecha | 2004-2026 |  | aaaammdd convertido a fecha; vacío si no es una fecha completa. |
| 141 | `PROGRAMA_NUMERO` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 142 | `PORCENTAJE_SANCION` | número | 2004-2026 |  |  |
| 143 | `BASE_SANCION` | número | 2004-2026 |  |  |
| 144 | `VALOR_CIF_USD` | número | 2001-2026 |  |  |
| 145 | `CODIGO_COMPLEMENTARIO` | código (texto) | 2007-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 146 | `CODIGO_SUPLEMENTARIO` | código (texto) | 2007-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 147 | `TOTAL_LIQUIDADO_ARANCEL_USD` | número | 2007-2026 |  |  |
| 148 | `TOTAL_LIQUIDADO_IVA_USD` | número | 2007-2026 |  |  |
| 149 | `PORCENTAJE_SALVAGUARDIA` | número | 2007-2026 |  |  |
| 150 | `BASE_SALVAGUARDIA` | número | 2007-2026 |  |  |
| 151 | `TOTAL_LIQUIDADO_SALVAGUARDIA` | número | 2007-2026 |  |  |
| 152 | `TOTAL_A_PAGAR_SALVAGUARDIA` | número | 2007-2026 |  |  |
| 153 | `TOTAL_LIQUIDADO_SALVAGUARDIA_USD` | número | 2007-2026 |  |  |
| 154 | `PORCENTAJE_DERECHOS_COMP` | número | 2007-2026 |  |  |
| 155 | `BASE_DERECHOS_COMP` | número | 2007-2026 |  |  |
| 156 | `TOTAL_LIQUIDADO_DERECHOS_COMP` | número | 2007-2026 |  |  |
| 157 | `TOTAL_A_PAGAR_DERECHOS_COMP` | número | 2007-2026 |  |  |
| 158 | `TOTAL_LIQUID_DERECHOS_COMP_USD` | número | 2007-2026 |  |  |
| 159 | `PORCENTAJE_ANTIDUMPING` | número | 2007-2026 |  |  |
| 160 | `BASE_ANTIDUMPING` | número | 2007-2026 |  |  |
| 161 | `TOTAL_LIQUIDADO_ANTIDUMPING` | número | 2007-2026 |  |  |
| 162 | `TOTAL_A_PAGAR_ANTIDUMPING` | número | 2007-2026 |  |  |
| 163 | `TOTAL_LIQUIDADO_ANTIDUMPING_USD` | número | 2007-2026 |  |  |
| 164 | `PORCENTAJE_RESCATE` | número | 2007-2026 |  |  |
| 165 | `BASE_RESCATE` | número | 2007-2026 |  |  |
| 166 | `TOTAL_LIQUIDADO_RESCATE` | número | 2007-2026 |  |  |
| 167 | `TOTAL_A_PAGAR_RESCATE` | número | 2007-2026 |  |  |
| 168 | `TOTAL_LIQUIDADO_USD` | número | 2007-2026 |  |  |
| 169 | `PERIODICIDAD_PAGO_CUOTA` | texto | 2003 |  |  |
| 170 | `COD_UNIDAD_COMERCIAL_2001_2002` | texto | 2001-2002 | `COD_UNIDAD_COMERCIAL` |  |

## Exportaciones

| # | Columna | Tipo | Años con datos | Columnas originales | Nota |
|---|---|---|---|---|---|
| 1 | `PERIODO` | entero | 2001-2026 |  | Mes del archivo de la DIAN (aaaamm). Columna agregada. |
| 2 | `FECHA_PROCESO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 3 | `NUMERO_SERIE` | código (texto) | 2001-2026 | `NUM_ARTICULO` | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 4 | `OFICINA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 5 | `COD_ADUANA_DESPACHO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 6 | `ADUANA_DESPACHO` | texto | 2001-2026 |  |  |
| 7 | `TIPO_IDENT` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 8 | `NIT_EXPORTADOR` | código (texto) | 2001-2026 | `NIT_EXPORTADOR_` | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 9 | `TIPO_USUARIO` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 10 | `COD_USUARIO` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 11 | `CLASE_EXPORTADOR` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 12 | `COD_DPTO_EXPORTADOR` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 13 | `COD_PAIS_DESTINO_NUM` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 14 | `COD_PAIS_DESTINO_NUM_M49` | código (texto) | 2001-2026 |  | Código M49 de COD_PAIS_DESTINO_NUM: el original desde 2025; hasta 2024, convertido desde ALADI con la correlativa oficial (vacío si no tiene equivalente). Columna agregada. |
| 15 | `COD_PAIS_DESTINO_ALF` | texto | 2007-2026 |  |  |
| 16 | `COD_PAIS_DESTINO` | texto | 2001-2026 | `COD_PAIS_DESTINO_ALF` |  |
| 17 | `PAIS_DESTINO_FINAL` | texto | 2001-2026 |  |  |
| 18 | `CIUDAD_DESTINATARIO` | texto | 2007-2026 |  |  |
| 19 | `NUM_SOLICITUD_AUTO_EMBARQUE` | texto | 2007-2026 |  |  |
| 20 | `TIPO_DECLARACION` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 21 | `TIPO_DESPACHO` | texto | 2004-2026 |  |  |
| 22 | `COD_LUGAR_SALIDA_NUM` | código (texto) | 2004-2026 | `TIPO_DESPACHO` | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 23 | `COD_LUG_SALIDA_ALF` | texto | 2004-2026 | `COD_LUGAR_SALIDA_NUM` |  |
| 24 | `COD_REGION_PROCEDENCIA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 25 | `REGION_PROCEDENCIA` | texto | 2001-2026 |  |  |
| 26 | `NUM__DECLA_EXPORTACION_ANT` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 27 | `FECH_DECLA_EXPORTACION_ANT` | código (texto) | 2007-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 28 | `NUM_DECLARACION_PRECEDENTE` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 29 | `FECH_DECLA_PRECEDENTE` | código (texto) | 2007-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. Un 0 ("no aplica") se deja vacío. |
| 30 | `COD_MODALIDAD_PRECEDENTE` | texto | 2004-2026 |  |  |
| 31 | `COD_MONEDA_TRANSACCION` | texto | 2005-2026 |  |  |
| 32 | `COD_MODO_TRANSPORTE` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 33 | `MODO_TRANSPORTE` | texto | 2001-2026 |  |  |
| 34 | `BANDERA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 35 | `BANDERA_M49` | código (texto) | 2001-2026 |  | Código M49 de BANDERA: el original desde 2025; hasta 2024, convertido desde ALADI con la correlativa oficial (vacío si no tiene equivalente). Columna agregada. |
| 36 | `COD_NACIONALIDAD_BANDERA` | texto | 2001-2026 |  |  |
| 37 | `NACIONALIDAD_BANDERA` | texto | 2001-2026 |  |  |
| 38 | `COD_REGIMEN_CAN` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 39 | `COD_MODALIDAD_EXPORTACION` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 40 | `MODALIDAD_EXPORTACION` | texto | 2001-2026 |  |  |
| 41 | `FORMA_PAGO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 42 | `COD_TIPO_EMBARQUE` | código (texto) | 2007-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 43 | `TIPO_DE_EMBARQUE` | texto | 2007-2026 |  |  |
| 44 | `COD_TIPO_DATOS` | código (texto) | 2007-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 45 | `TIPO_DE_DATOS` | texto | 2007-2026 |  |  |
| 46 | `TIPO_CERTIFICADO_ORIGEN` | código (texto) | 2004-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 47 | `SISTEMAS_ESPECIALES` | texto | 2001-2026 |  |  |
| 48 | `COD_EXPORTACION_TRANSITO` | texto | 2007-2026 |  |  |
| 49 | `EXPORTACION_EN_TRANSITO` | texto | 2007-2026 |  |  |
| 50 | `SUBPARTIDA` | código (texto) | 2001-2026 |  | Completada a 10 dígitos con ceros a la izquierda (la DIAN publica algunas sin el cero inicial). |
| 51 | `COD_REGION_ORIGEN` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 52 | `REGION_DE_ORIGEN` | texto | 2001-2026 |  |  |
| 53 | `COD_UNIDAD_FISICA_NUM` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 54 | `COD_UNIDAD_FISICA_ALF` | texto | 2004-2026 | `COD_UNIDAD_FISICA` |  |
| 55 | `UNIDAD_FISICA` | texto | 2001-2026 |  |  |
| 56 | `CANTIDAD_UNIDADES_FISICAS` | número | 2001-2026 |  |  |
| 57 | `PESO_BRUTO_KGS` | número | 2001-2026 |  |  |
| 58 | `PESO_NETO_KGS` | número | 2001-2026 |  |  |
| 59 | `VALOR_FOB_USD` | número | 2001-2026 |  |  |
| 60 | `VALOR_FOB_PESOS` | número | 2001-2026 |  |  |
| 61 | `VLR_SERIE_AGREGADO_NAL_USD` | número | 2001-2026 |  |  |
| 62 | `VALOR_SERIE_FLETES_USD` | número | 2001-2026 |  |  |
| 63 | `VALOR_SERIE_SEGUROS_USD` | número | 2001-2026 |  |  |
| 64 | `VLR_SERIE_OTROS_GASTOS_USD` | número | 2001-2026 |  |  |
| 65 | `COD_ADUANA_SALIDA` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 66 | `ADUANA_SALIDA` | texto | 2001-2026 |  |  |
| 67 | `FECHA_SOLICITUD_AUTO_EMBARQUE` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 68 | `NUMERO_FORMULARIO` | código (texto) | 2001-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 69 | `FECHA_DECLARACION_EXPORTACION` | fecha | 2005-2026 |  | aaaammdd convertido a fecha; vacío si no es una fecha completa. |
| 70 | `RAZON_SOCIAL_EXPORTADOR` | texto | 2007-2026 |  |  |
| 71 | `DIREC_EXPORTADOR` | texto | 2007-2026 |  |  |
| 72 | `NIT_DECLARANTE` | código (texto) | 2007-2026 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 73 | `RAZON_SOCIAL_DECLARANTE` | texto | 2007-2026 |  |  |
| 74 | `RAZON_SOCIAL_DESTINATARIO` | texto | 2007-2026 |  |  |
| 75 | `DOMICILIO_DESTINATARIO` | texto | 2007-2026 |  |  |
| 76 | `NUMERO_SERIE_2001_2004` | texto | 2001-2004 | `NUMERO_SERIE` |  |
| 77 | `NUM_MANIFIESTO` | código (texto) | 2001-2004 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 78 | `COD_MONEDA_TRANSACCION_2004` | texto | 2004 | `COD_MONEDA_TRANSACCION` |  |
| 79 | `NUM_DOC_EXPO_ADUANA` | código (texto) | 2001-2003 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 80 | `COD_OFICINA_REINTEGRO` | código (texto) | 2001-2003 |  | Código o número guardado como texto; se quita el '.0' que agrega Excel. |
| 81 | `COD_MONEDA_TRANSACCION_2001_2003` | texto | 2001-2003 | `COD_MONEDA_TRANSACCION` |  |

## Columnas originales eliminadas

Valen "1" (o vacío) en todas las filas de todos los meses en que aparecen; no tienen información. Siguen en `data/raw/` y `data/interim/`.

- importaciones: `ACTIVO (1)`
- importaciones: `ACTIVO1`
- importaciones: `CODIGO_DEPARTAMENTO (1)`
- importaciones: `COD_ADMINISTRACION_PRESENTADA (1)`
- importaciones: `NOMBRE_ADUANA (1)`
