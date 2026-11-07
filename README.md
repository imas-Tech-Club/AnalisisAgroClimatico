# Predictor de rinde · El Niño 2026-27

Proyecto del Club de Informática (UADE). Estima el **rinde de soja y maíz por departamento durante la
campaña**, a partir del verdor visto desde satélite (NDVI de MODIS), el clima y la fase ENSO, y mide
cuánto error tiene el modelo, en especial en años Niño. Entrega final: 20/12/2026.

**Región piloto propuesta:** Santa Fe (19 departamentos). La comparación con las otras candidatas está
en [`docs/region_piloto.md`](docs/region_piloto.md).

## Estructura

```
src/          pipeline de datos y modelo (se corre en orden)
  config.py             rutas, regiones candidatas, meses de la campaña
  01_descargas.py       límites IGN, rinde MAGyP, ONI de NOAA
  02_rinde_enso.py      rinde limpio por departamento, fase ENSO por campaña, comparación de regiones
  03_clima.py           lluvia CHIRPS (por polígono) + temperatura y humedad del suelo (NASA POWER)
  04_modis.py           NDVI de MODIS en tierras de cultivo, por departamento (Planetary Computer)
  05_tabla_maestra.py   une todo: una fila por departamento × campaña × cultivo
  06_exploracion.py     figuras del análisis histórico
  modelo.py             frente 4: líneas base, validación por campaña, XGBoost, métricas
notebooks/
  01_ndvi_modis_departamento.ipynb               NDVI de un departamento y una campaña (tarea 3.1)
  02_frente4_validacion_lineas_base_xgboost.ipynb  tareas 4.1 a 4.4
tests/        pruebas del módulo del modelo con datos sintéticos (uv run pytest tests)
docs/         fuentes de datos, diccionario de la tabla maestra, región piloto, notas del modelo
data/raw/        descargas originales (no se versiona)
data/processed/  tablas generadas; por región en data/processed/<region>/
outputs/figures/ figuras por región
web/          demo web (semana 5)
```

## Cómo correrlo

Requiere [uv](https://docs.astral.sh/uv/). No hace falta ninguna cuenta: todas las fuentes del v1 son
abiertas.

```bash
uv sync
export AGRO_REGION=santa_fe          # o norte_ba_sur_sf, entre_rios

uv run python src/01_descargas.py    # ~1 min
uv run python src/02_rinde_enso.py   # segundos
uv run python src/03_clima.py        # ~5 min
uv run python src/04_modis.py        # ~30 min la primera vez (2000-hoy); después solo el año en curso
uv run python src/05_tabla_maestra.py
uv run python src/06_exploracion.py
uv run python src/modelo.py          # métricas de líneas base y XGBoost
```

Para abrir los notebooks: `uv run --with jupyterlab jupyter lab`. Las pruebas del modelo:
`uv run pytest tests`.

Si solo vas a trabajar en el modelo, alcanza con `data/processed/<region>/tabla_maestra.csv` y
`src/modelo.py`. El diccionario de columnas está en [`docs/tabla_maestra.md`](docs/tabla_maestra.md).

## Estado (7/11/2026)

| Tarea | Estado |
| --- | --- |
| 1.1-1.3 Rinde por departamento, limpieza, cobertura y región | Hecho para las tres candidatas. **El MAGyP tiene datos hasta 2024/25**, no hasta 2019 |
| 1.4 Tabla maestra v1 | Hecha para Santa Fe (`tabla_maestra.csv`) |
| 2.1 ONI y fase por campaña | Hecho (`data/processed/enso_campanas.csv`) |
| 2.2 Lluvia mensual | Hecho con CHIRPS v3 |
| 2.3 Temperatura y humedad del suelo | Provisorio con NASA POWER; falta ERA5-Land |
| 3.1 Notebook NDVI de un departamento | Hecho (Planetary Computer, con el equivalente en Earth Engine) |
| 3.2 Máscara de soja y maíz | Pendiente: hoy se usa "cultivo" de ESA WorldCover para los dos |
| 3.3 NDVI mensual de todos los departamentos | Hecho para Santa Fe |
| 4.1-4.4 Validación, líneas base, XGBoost, métricas | Primera versión en `src/modelo.py` y el notebook 02. El XGBoost tiene entre 14 y 25 % menos error que la mejor línea base ([resultados](docs/frente4_modelo.md)) |

## Qué es de otros y qué aportamos

Los datos son de terceros: MAGyP (rinde), NOAA (ONI), IGN (límites), NASA (MODIS, POWER),
ESA (WorldCover), Climate Hazards Center (CHIRPS) y Microsoft Planetary Computer (acceso a MODIS y
WorldCover). Licencias en [`docs/fuentes_de_datos.md`](docs/fuentes_de_datos.md). El aporte del
proyecto es el procesamiento por departamento, la tabla maestra, los modelos y su validación por
campaña y por fase ENSO.
