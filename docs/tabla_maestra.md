# Tabla maestra v1: cómo se genera y diccionario de columnas

Archivo: `data/processed/<region>/tabla_maestra.csv`, generado por `src/05_tabla_maestra.py`.

**Una fila por departamento × campaña × cultivo**, de 2000/01 (inicio de MODIS) a la campaña en curso.
La campaña en curso (2026/27) no tiene `rinde_real`: es la que el modelo tiene que predecir.

| Región | Departamentos | Filas | Filas con rinde |
| --- | --- | --- | --- |
| Santa Fe (`santa_fe`) | 19 | 1026 | 983 |
| Entre Ríos (`entre_rios`) | 17 (Islas del Ibicuy sin rinde) | 918 | 826 |

Sigue la propuesta del documento "Predictor de rinde". Donde hubo que decidir algo, está marcado como
**decisión v1**. Se puede cambiar en equipo.

## Cómo generarla

Las dependencias del pipeline están en el grupo `datos` de `pyproject.toml` (el modelo no las necesita).
Ninguna fuente pide cuenta.

```bash
uv run --group datos python src/01_descargas.py                          # polígonos del IGN y ONI de NOAA
uv run --group datos python src/02_enso.py                               # fase ENSO por campaña
AGRO_REGION=entre_rios uv run --group datos python src/03_clima.py        # lluvia, temperatura, humedad
AGRO_REGION=entre_rios uv run --group datos python src/04_modis.py        # NDVI (el paso largo)
AGRO_REGION=entre_rios uv run --group datos python src/05_tabla_maestra.py
```

El rinde lo pone el frente 1: `05_tabla_maestra.py` lee `data/processed/<region>/rinde_limpio_<region>.csv`
(de `src/rinde_limpio.py`). Los años de MODIS ya procesados no se vuelven a bajar, salvo el año en curso;
para actualizar la campaña en curso alcanza con volver a correr 03, 04 y 05.

Con las mismas entradas, el pipeline reproduce byte por byte la tabla de Santa Fe que está en el repo.

**Agregar otra provincia:** sumar su código INDEC a `config.PROVINCIAS` y la región a `config.REGIONES`;
volver a correr `01_descargas.py --forzar` para bajar sus polígonos; que el frente 1 genere su
`rinde_limpio_<region>.csv`; y correr 03 a 05 con esa `AGRO_REGION`.

## Columnas

| Columna | Tipo | Contenido |
| --- | --- | --- |
| `depto_id` | texto (5 dígitos) | Código INDEC del departamento (el `in1` del IGN). El MAGyP usa otros ID; el frente 1 los cruza por nombre (`data/processed/cruce_departamentos.csv`). **Leerlo como texto** (`dtype={"depto_id": str}`) para no perder el 0 inicial en Buenos Aires (`06…`) |
| `departamento` | texto | Nombre según el IGN |
| `provincia` | texto | Provincia |
| `campania` | texto | Formato `2015/16` |
| `anio_siembra` | entero | Año en que empieza la campaña (2015 para 2015/16). Cómodo para ordenar y para la tendencia |
| `cultivo` | texto | `soja` o `maiz`. En soja es "soja total" del MAGyP (1ra + 2da) |
| `fase_enso` | texto | `nino`, `nina` o `neutro`, según el ONI promedio de SON, OND, NDJ y DJF de la campaña (±0,5) |
| `oni` | número | Ese ONI promedio. Variable continua, más informativa que la fase. En la campaña en curso es parcial |
| `nino_fuerte` | booleano | ONI ≥ 1,5 (en el período: 2015/16, 2023/24 y 2026/27) |
| `ndvi_mes_1` … `ndvi_mes_8` | número (0-1) | NDVI medio en tierras de cultivo del departamento, por mes |
| `lluvia_mes_1` … `lluvia_mes_8` | mm | Lluvia acumulada del mes, promedio sobre el polígono (CHIRPS v3) |
| `temp_mes_1` … `temp_mes_8` | °C | Temperatura media del aire a 2 m (NASA POWER, provisorio) |
| `humedad_suelo_mes_1` … `humedad_suelo_mes_8` | 0-1 | Humedad de la zona de raíces, 0 = seco y 1 = saturado (NASA POWER, provisorio) |
| `sembrada_ha` | ha | Superficie sembrada del cultivo (MAGyP). Sirve para ponderar promedios regionales |
| `rinde_real` | kg/ha | Rinde oficial del MAGyP (producción / superficie cosechada). Vacío si no está publicado o si hubo pérdida total (cosechada = 0) |

## Meses (decisión v1)

`mes_1` = septiembre, `mes_2` = octubre, `mes_3` = noviembre, `mes_4` = diciembre, `mes_5` = enero,
`mes_6` = febrero, `mes_7` = marzo, `mes_8` = abril.

Arranca en septiembre para incluir la humedad con la que se siembra (clave en años Niño) y el maíz
temprano, y termina en abril para cubrir la soja de segunda. Se define en `config.MESES_CAMPANA`.

Para medir **cómo baja el error mes a mes**, una predicción "en diciembre" usa solo `*_mes_1` a
`*_mes_4`; "en febrero", hasta `*_mes_6`. La función `modelo.columnas_clima_satelite(hasta_mes)` arma
esa lista.

## Cómo se calcula el NDVI

1. Compuestos MOD13Q1 de Terra (16 días, 250 m), en la grilla nativa de MODIS, sin remuestrear.
2. Se descartan los píxeles con confiabilidad 2 (nieve) o 3 (nube) y los de agua.
3. Se promedian solo los píxeles que ESA WorldCover marca como cultivo, dentro del polígono del IGN.
4. Se descarta el compuesto si menos del 50 % de los píxeles de cultivo del departamento quedan válidos.
5. El valor mensual es el promedio de los compuestos que empiezan en ese mes (uno o dos).

**Limitación:** la máscara es "cultivo" en general, así que soja y maíz comparten el mismo NDVI.
Separarlos con el mapa del INTA o de MapBiomas es la tarea 3.2.

## Calidad (para la tarea 3.4)

- `data/processed/<region>/ndvi_mensual_departamento.csv` trae, por mes, cuántos compuestos entraron
  (`compuestos`) y qué fracción de píxeles de cultivo fue válida (`valido`). No se versiona: lo genera
  `05_tabla_maestra.py`.
- Cuando falta un mes, la celda queda vacía. XGBoost maneja los vacíos; para otros modelos hay que
  imputarlos.
- **Hueco conocido:** Planetary Computer no tiene compuestos MOD13Q1 de Terra entre el 12/7 y el 1/11
  de 2025. A la campaña 2025/26 le faltan `ndvi_mes_1` y `ndvi_mes_2` en las dos regiones. Se puede
  completar con Earth Engine o con Aqua (MYD13Q1).
- Fuera de ese hueco, las filas con rinde de las dos regiones están completas.
- **Islas del Ibicuy** (Entre Ríos) no tiene NDVI: es delta y WorldCover no marca píxeles de cultivo.
  Tampoco tiene rinde de soja ni maíz, así que no entra al modelo.
- **Campaña en curso:** al 15/11/2026, 2026/27 tiene NDVI de septiembre y clima de septiembre y
  octubre. Para actualizarla, volver a correr 03, 04 y 05.
