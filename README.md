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

En Santa Fe, el XGBoost tiene entre 14 y 25 % menos error que la mejor línea base, tanto dejando una
campaña afuera como entrenando solo con el pasado. Resultados y decisiones en
[`docs/frente4_modelo.md`](docs/frente4_modelo.md).

## Estructura

```
src/modelo.py              líneas base, validación por campaña, XGBoost y métricas
notebooks/frente4_validacion_lineas_base_xgboost.ipynb   tareas 4.1 a 4.4 con resultados
tests/test_modelo.py       pruebas con datos sintéticos (incluye la regla de oro)
docs/frente4_modelo.md     método, decisiones, resultados y próximos pasos
data/processed/santa_fe/
  tabla_maestra.csv        entrada del modelo (provisoria, ver abajo)
  predicciones_loco.csv, predicciones_temporal.csv, metricas_modelos.csv   salidas
```

## Cómo correrlo

Requiere [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python src/modelo.py              # predicciones y métricas en data/processed/santa_fe/
uv run --with jupyterlab jupyter lab     # para abrir el notebook
uv run pytest tests
```

Para otra región: dejar su tabla en `data/processed/<region>/tabla_maestra.csv` y correr con
`AGRO_REGION=<region>`.

## Entrada

El modelo lee la tabla maestra con el formato del plan: una fila por departamento × campaña × cultivo.
Las columnas que usa están en [`docs/frente4_modelo.md`](docs/frente4_modelo.md#entrada-la-tabla-maestra).

La tabla que está en el repo es una **versión provisoria de Santa Fe** para poder avanzar con el frente 4.
Cuando el equipo tenga la tabla maestra v1, se reemplaza el archivo y se vuelve a correr todo.

Esa tabla usa datos de terceros: rinde del MAGyP (CC BY 4.0), ONI de NOAA, NDVI de MODIS (NASA), máscara
de cultivo de ESA WorldCover, lluvia de CHIRPS (Climate Hazards Center) y temperatura y humedad del suelo
de NASA POWER.
