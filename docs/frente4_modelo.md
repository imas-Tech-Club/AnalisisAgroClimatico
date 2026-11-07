# Frente 4 · Modelo de machine learning

Código: `src/modelo.py`. Notebook con resultados: `notebooks/02_frente4_validacion_lineas_base_xgboost.ipynb`.
Pruebas: `uv run pytest tests`.

## Qué hay

| Tarea | Función en `modelo.py` |
| --- | --- |
| 4.1 Validación dejando una campaña afuera | `validar(df, modelos, esquema="loco")` |
| 4.2 Líneas base | `promedio_historico`, `tendencia_lineal` |
| 4.3 Primer XGBoost | `xgboost_sobre_tendencia(features, base="tendencia" \| "promedio")` |
| 4.4 Métricas y comparación | `metricas(pred, por=...)`, `comparar_con_base(...)` |
| Error mes a mes (insumo del frente 5) | `columnas_clima_satelite(hasta_mes)` + `MESES_CORTE` |

Un "modelo" es cualquier función `f(train, test) -> np.ndarray` con una predicción por fila de `test`.
Para probar otro algoritmo (Random Forest, regresión lineal, LSTM), alcanza con escribir esa función y
pasarla en el diccionario de `validar`. Las métricas y la comparación salen igual.

## Decisiones

- **Regla de oro.** `validar` separa por `campania` y lo verifica con un `assert` en cada pliegue.
  Todo lo que se aprende (promedios, rectas por departamento, el XGBoost) se ajusta dentro del pliegue.
- **Dos esquemas.** `loco` es el del plan. `temporal` entrena solo con campañas anteriores (desde
  2008/09) y simula el uso real. `loco` favorece a la tendencia lineal porque le deja interpolar con
  campañas futuras: un modelo tiene que ganar en los dos esquemas.
- **El XGBoost predice el desvío, no el rinde.** Cada departamento tiene su nivel y su tendencia por
  tecnología, y con 25 campañas eso lo resuelve mejor una recta que un árbol. El XGBoost aprende lo que
  la base no explica (el año climático) y la predicción es base + desvío. Un modelo por cultivo.
- **Variables v1:** NDVI, lluvia, temperatura y humedad del suelo de septiembre a abril (32 columnas)
  más el ONI. Sin identificador de departamento, porque eso ya entra por la base.
- **Hiperparámetros conservadores** (400 árboles, profundidad 3, tasa 0,03, submuestreo 0,8), sin
  ajustar todavía. Ajustarlos con los mismos pliegues que se usan para medir el error infla los
  resultados: para buscarlos hace falta validación anidada.
- **Métricas:** MAE en kg/ha, error porcentual absoluto medio, R² y sesgo (error medio con signo:
  positivo = sobreestima). `mejora_vs_base_pct` compara el MAE contra la tendencia lineal.

## Resultados v1 (Santa Fe, 7/11/2026)

19 departamentos, campañas 2000/01 a 2024/25: 475 filas de soja y 470 de maíz. Variables de septiembre
a abril. Tabla completa en `data/processed/santa_fe/metricas_modelos.csv`.

**Error medio absoluto (kg/ha) y error porcentual**

| Modelo | Soja · loco | Soja · temporal | Maíz · loco | Maíz · temporal |
| --- | --- | --- | --- | --- |
| Promedio histórico | 500 (25,5 %) | 596 (30,0 %) | 1180 (24,1 %) | 1270 (26,1 %) |
| Tendencia lineal | 506 (26,1 %) | 638 (33,1 %) | 1210 (24,9 %) | 1392 (30,2 %) |
| **XGBoost sobre la tendencia** | **375 (17,3 %)** | **487 (24,3 %)** | **976 (19,4 %)** | **1096 (21,9 %)** |
| XGBoost sobre el promedio | 378 (17,1 %) | 476 (23,0 %) | 974 (19,5 %) | 1200 (22,6 %) |

R² del XGBoost (loco): 0,65 en soja y 0,70 en maíz, contra 0,40 y 0,53 del promedio histórico.

**Lo que dicen estos números**

1. **El XGBoost supera a las dos líneas base en los dos esquemas.** Tiene entre 14 y 25 % menos error
   que la mejor base (el promedio histórico) y entre 19 y 26 % menos que la tendencia lineal. La mejora
   se sostiene en la validación temporal, que es la que simula el uso real.
2. **El promedio histórico le gana a la tendencia lineal** en Santa Fe. El rinde medio casi no tiene
   tendencia en 2000-2024 (+10 kg/ha por año en soja y en maíz, menos de 0,4 % anual), y la recta por
   departamento se deja arrastrar por los años extremos (2008/09, 2022/23).
3. **Las bases se equivocan con sesgo según la fase.** Sobreestiman en años Niña (+1094 kg/ha en
   maíz) y subestiman en años Niño (−894 kg/ha). El XGBoost reduce ese sesgo a +346 y −145.
4. **Subpregunta 2, primera respuesta:** el modelo **no** se equivoca más en años Niño. Error en soja:
   13,7 % en Niño, 11,6 % en neutro y **23,9 % en Niña**. El año difícil es el seco, no el lluvioso.
   Con 9 campañas Niño (2 fuertes) hay que tomarlo con cuidado.
5. **Subpregunta 1, cómo baja el error en la campaña.** En soja baja de 477 kg/ha (21 %) prediciendo
   en diciembre a 368 kg/ha (17 %) en marzo. **En maíz casi no baja** (986 → 976): el NDVI de la
   máscara genérica de cultivo refleja sobre todo a la soja, que ocupa más superficie. La máscara
   propia de maíz (tarea 3.2) es lo que más puede mejorar este cultivo.
6. **El ONI es la variable más importante en maíz** (28 % de la ganancia) y **empata con el NDVI de
   diciembre en soja** (13 % cada una). Les siguen la lluvia y la temperatura de diciembre y la humedad
   del suelo de febrero.

**Predicción 2025/26.** El notebook deja la estimación por departamento de la campaña 2025/26, que el
MAGyP todavía no publicó por departamento. Al compararla con el próximo CSV del MAGyP queda la primera
validación en vivo. A esa campaña le falta el NDVI de septiembre y octubre de 2025, porque Planetary
Computer no tiene esos compuestos.

## Próximos pasos sugeridos

- Hiperparámetros con validación anidada (búsqueda dentro de cada pliegue de entrenamiento).
- Variables derivadas: NDVI máximo, integral de NDVI dic-mar, lluvia acumulada, días de calor.
- Probar sin el ONI, para medir cuánto aporta el satélite solo.
- Rinde ponderado por superficie en las métricas regionales (hoy cada departamento pesa igual).
- Repetir con `AGRO_REGION=norte_ba_sur_sf` para ver si los resultados se sostienen en otra región.
