# Predictor de rinde · Frente 4: modelo

Proyecto del Club de Informática (UADE) sobre El Niño 2026-27. Este repo tiene el **frente 4, el modelo
de machine learning**: estima el rinde de soja y maíz por departamento durante la campaña y mide cuánto
se equivoca, en especial en años Niño. Entrega final: 20/12/2026.

## Tareas

| Tarea | Fecha | Estado | Dónde |
| --- | --- | --- | --- |
| 4.1 Notebook de validación dejando una campaña afuera | 15/11 | Hecho | `modelo.validar`, sección 2 del notebook |
| 4.2 Líneas base: promedio histórico y tendencia lineal | 15/11 | Hecho | `modelo.promedio_historico`, `modelo.tendencia_lineal` |
| 4.3 Primer XGBoost sobre la tabla maestra v1 | 22/11 | Hecho | `modelo.xgboost_sobre_tendencia` |
| 4.4 Métricas (MAE, % de error, R²) por cultivo contra las líneas base | 22/11 | Hecho | `modelo.metricas`, `metricas_modelos.csv` |

En Santa Fe y Entre Ríos (2000/01 a 2025/26), el XGBoost les gana a las dos líneas base, tanto dejando
una campaña afuera como entrenando solo con el pasado: en soja por 18 a 30 %, en maíz de Entre Ríos por
24 a 28 % y en maíz de Santa Fe solo por 5 a 7 %. En la primera validación en vivo (la campaña 2025/26,
predicha antes de que el MAGyP publicara el rinde) el modelo de ese momento perdió contra las líneas base
en las dos provincias, sobre todo en maíz, por el peso del ONI. Desde el 16/11/2026 el modelo por defecto
aprende sobre el promedio histórico y no usa el ONI. **Con datos solo hasta noviembre, que es lo que habrá
para la entrega del 20/12, el modelo todavía no le gana al promedio histórico**; empieza a aportar con los
datos de diciembre (la soja de Entre Ríos, con los de enero).

Resultados y decisiones en [`docs/frente4_modelo.md`](docs/frente4_modelo.md).

## Estructura

```
src/modelo.py              líneas base, validación por campaña, XGBoost y métricas
src/experimento_oni.py     experimento de cómo entra el ONI -> data/processed/experimento_oni.csv
src/experimento_base.py    experimento de la base del XGBoost -> data/processed/experimento_base.csv
notebooks/frente4_validacion_lineas_base_xgboost.ipynb   tareas 4.1 a 4.4 con resultados
tests/test_modelo.py       pruebas con datos sintéticos (incluye la regla de oro)
docs/frente4_modelo.md     método, decisiones, resultados y próximos pasos
data/processed/<region>/   santa_fe y entre_rios
  tabla_maestra.csv        entrada del modelo
  predicciones_loco.csv, predicciones_temporal.csv, metricas_modelos.csv   salidas

Tabla maestra (ver docs/tabla_maestra.md):
src/config.py, src/01_descargas.py ... src/05_tabla_maestra.py   ENSO, clima, NDVI y armado de la tabla

Frente 1 (datos de rinde, ver docs/frente1_cobertura.md):
data/raw/                  extractos del MAGyP sin modificar
src/rinde_limpio.py        rinde limpio con código INDEC -> data/processed/<region>/rinde_limpio_<region>.csv
```

## Cómo correrlo

Requiere [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python src/modelo.py              # predicciones y métricas en data/processed/santa_fe/
uv run python src/modelo.py --predecir 2026/27 --corte nov   # predicción de una campaña sin rinde
uv run --with jupyterlab jupyter lab     # para abrir el notebook
uv run pytest tests
```

Para otra región: dejar su tabla en `data/processed/<region>/tabla_maestra.csv` y correr con
`AGRO_REGION=<region>`.

## Entrada

El modelo lee la tabla maestra con el formato del plan: una fila por departamento × campaña × cultivo.
Las columnas que usa están en [`docs/frente4_modelo.md`](docs/frente4_modelo.md#entrada-la-tabla-maestra).

Hay tablas de **Santa Fe y Entre Ríos**. Se generan con el pipeline de `src/01_descargas.py` a
`src/05_tabla_maestra.py`, que toma el rinde del frente 1; los comandos y cómo sumar otra provincia
están en [`docs/tabla_maestra.md`](docs/tabla_maestra.md).

Esa tabla usa datos de terceros: rinde del MAGyP (CC BY 4.0), ONI de NOAA, NDVI de MODIS (NASA), máscara
de cultivo de ESA WorldCover, lluvia de CHIRPS (Climate Hazards Center) y temperatura y humedad del suelo
de NASA POWER.
