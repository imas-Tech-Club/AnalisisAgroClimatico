# Frente 4 · Modelo de machine learning

Código: `src/modelo.py`. Notebook con resultados: `notebooks/frente4_validacion_lineas_base_xgboost.ipynb`.
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

## Entrada: la tabla maestra

`data/processed/<region>/tabla_maestra.csv`, una fila por departamento × campaña × cultivo. El modelo usa
estas columnas:

| Columna | Contenido |
| --- | --- |
| `depto_id` | Código INDEC del departamento. Se lee como texto para no perder el 0 inicial |
| `departamento` | Nombre, solo para mostrar |
| `campania`, `anio_siembra` | `2015/16` y `2015`. La campaña es el grupo de la validación; el año ordena la tendencia |
| `cultivo` | `soja` o `maiz`. Se entrena un modelo por cultivo |
| `fase_enso`, `oni`, `nino_fuerte` | Fase de la campaña (`nino`, `nina`, `neutro`), ONI promedio y si es ≥ 1,5 |
| `ndvi_mes_N`, `lluvia_mes_N`, `temp_mes_N`, `humedad_suelo_mes_N` | N = 1 a 8, de septiembre (1) a abril (8) |
| `rinde_real` | kg/ha. Vacío en las campañas que hay que predecir |

Las celdas vacías en las variables mensuales no rompen nada: el XGBoost las maneja y las líneas base no
las usan. Si cambian los nombres o los meses en la v1 del equipo, alcanza con ajustar
`VARIABLES_MENSUALES` y `MESES_CORTE` en `modelo.py`.

La tabla provisoria de Santa Fe tiene NDVI de MODIS promediado en tierras de cultivo (ESA WorldCover),
lluvia de CHIRPS v3, temperatura y humedad del suelo de NASA POWER y rinde del MAGyP. El rinde de 2025/26
se cargó el 14/11/2026 desde `data/processed/santa_fe/rinde_limpio_santa_fe.csv` (frente 1, MAGyP
actualizado el 30/10/2026). Ese archivo coincide con la tabla en las 945 filas que ya tenían rinde.

### Entre Ríos

El modelo corre sin cambios con `AGRO_REGION=entre_rios` en cuanto exista
`data/processed/entre_rios/tabla_maestra.csv`. Lo que falta es el NDVI y el clima de sus departamentos.

El pipeline que armó la tabla provisoria de Santa Fe (`src/01_descargas.py` a `src/05_tabla_maestra.py`)
ya tiene la región `entre_rios` configurada con los polígonos del IGN, y sus 17 códigos coinciden con
`data/processed/cruce_departamentos.csv`. Ese código se sacó del repo porque es de los frentes 2 y 3, y
está en el commit `517f766`. Todavía no se corrió para Entre Ríos. Si se corre:

- El rinde conviene tomarlo de `data/processed/entre_rios/rinde_limpio_entre_rios.csv`: el dataset del
  MAGyP que baja `01_descargas.py` termina en 2024/25.
- Islas del Ibicuy queda sin filas para entrenar, porque el MAGyP no tiene rinde de soja ni maíz ahí.

## Decisiones

- **Regla de oro.** `validar` separa por `campania` y lo verifica con un `assert` en cada pliegue.
  Todo lo que se aprende (promedios, rectas por departamento, el XGBoost) se ajusta dentro del pliegue.
- **Dos esquemas.** `loco` es el del plan. `temporal` entrena solo con campañas anteriores (desde
  2008/09) y simula el uso real. `loco` favorece a la tendencia lineal porque le deja interpolar con
  campañas futuras: un modelo tiene que ganar en los dos esquemas.
- **El XGBoost predice el desvío, no el rinde.** Cada departamento tiene su nivel y su tendencia por
  tecnología, y con 26 campañas eso lo resuelve mejor una recta que un árbol. El XGBoost aprende lo que
  la base no explica (el año climático) y la predicción es base + desvío. Un modelo por cultivo.
- **Variables v1:** NDVI, lluvia, temperatura y humedad del suelo de septiembre a abril (32 columnas)
  más el ONI. Sin identificador de departamento, porque eso ya entra por la base.
- **Hiperparámetros conservadores** (400 árboles, profundidad 3, tasa 0,03, submuestreo 0,8), sin
  ajustar todavía. Ajustarlos con los mismos pliegues que se usan para medir el error infla los
  resultados: para buscarlos hace falta validación anidada.
- **Métricas:** MAE en kg/ha, error porcentual absoluto medio, R² y sesgo (error medio con signo:
  positivo = sobreestima). `mejora_vs_base_pct` compara el MAE contra la tendencia lineal.
- **Maíz 2008/09 con pérdida total.** 9 de Julio, Garay, General Obligado, San Javier y Vera tienen
  superficie sembrada pero cosechada = 0 y rinde = 0 en el MAGyP. Quedan afuera del entrenamiento y de
  las métricas: el rinde es producción / superficie cosechada, y con cosechada 0 no está definido.
  Cargarlos como 0 mezclaría cuánto rinde lo que se cosecha con cuánto se pierde. Si más adelante se
  quieren predecir pérdidas, el objetivo es otro: producción / superficie sembrada, que ahí sí vale 0.
- **Rinde 2025/26 preliminar.** Puede ser una estimación que el MAGyP revise. Si cambia, se actualiza
  la tabla y se vuelve a correr.

## Resultados (Santa Fe, 14/11/2026)

19 departamentos, campañas 2000/01 a 2025/26: 494 filas de soja y 489 de maíz. Variables de septiembre
a abril. Tabla completa en `data/processed/santa_fe/metricas_modelos.csv`. La primera versión (7/11, sin
2025/26) queda en el historial de git. Las conclusiones generales se mantienen; la ventaja en maíz con
validación temporal se achicó por la campaña 2025/26 (ver la sección siguiente).

**Error medio absoluto (kg/ha) y error porcentual**

| Modelo | Soja · loco | Soja · temporal | Maíz · loco | Maíz · temporal |
| --- | --- | --- | --- | --- |
| Promedio histórico | 493 (25,0 %) | 584 (29,0 %) | 1182 (23,9 %) | 1273 (25,6 %) |
| Tendencia lineal | 491 (25,2 %) | 616 (31,7 %) | 1195 (24,4 %) | 1382 (29,3 %) |
| **XGBoost sobre la tendencia** | **363 (16,7 %)** | **476 (23,4 %)** | **950 (18,6 %)** | **1144 (22,1 %)** |
| XGBoost sobre el promedio | 376 (16,9 %) | 479 (22,7 %) | 995 (19,4 %) | 1253 (22,9 %) |

R² del XGBoost (loco): 0,67 en soja y 0,69 en maíz, contra 0,41 y 0,53 del promedio histórico.

**Lo que dicen estos números**

1. **El XGBoost supera a las dos líneas base en los dos esquemas.** Tiene entre 10 y 26 % menos error
   que la mejor base y entre 17 y 26 % menos que la tendencia lineal. La ventaja más chica es en maíz con
   validación temporal (10 % sobre el promedio histórico; era 14 % sin 2025/26).
2. **La tendencia lineal no le gana al promedio histórico** en Santa Fe: empatan en `loco` y el promedio
   gana claro en `temporal`. El rinde medio casi no tiene tendencia en 2000-2025 (+11 kg/ha por año en
   soja y +19 en maíz, menos de 0,5 % anual), y la recta por departamento se deja arrastrar por los años
   extremos (2008/09, 2022/23).
3. **Las bases se equivocan con sesgo según la fase.** El promedio histórico sobreestima en años Niña
   (+927 kg/ha en maíz) y subestima en años Niño (−846). El XGBoost reduce ese sesgo a +159 y −127.
4. **Subpregunta 2, primera respuesta:** el modelo **no** se equivoca más en años Niño. Error en soja:
   13,5 % en Niño, 11,0 % en neutro y **22,4 % en Niña**. El año difícil es el seco, no el lluvioso.
   Con 9 campañas Niño (2 fuertes) hay que tomarlo con cuidado.
5. **Subpregunta 1, cómo baja el error en la campaña.** En soja baja de 456 kg/ha (20 %) prediciendo
   en diciembre a 355 kg/ha (16 %) en marzo. **En maíz casi no baja** (970 → 950): el NDVI de la
   máscara genérica de cultivo refleja sobre todo a la soja, que ocupa más superficie. La máscara
   propia de maíz (tarea 3.2) es lo que más puede mejorar este cultivo.
6. **El ONI es la variable más importante en los dos cultivos** (25 % de la ganancia en maíz y 12 % en
   soja). En soja le siguen la lluvia y el NDVI de diciembre y la humedad del suelo de febrero; en maíz,
   la temperatura de diciembre y de marzo y la lluvia de diciembre.

## Validación en vivo: campaña 2025/26

El 7/11/2026 el notebook dejó registrada la predicción de 2025/26 por departamento, entrenada con
2000/01 a 2024/25. La tabla no tenía el rinde de esa campaña: el dataset del MAGyP que usaba el
pipeline terminaba en 2024/25. El rinde real llegó el 14/11 con el frente 1. La predicción registrada es
el pliegue 2025/26 del esquema `temporal`, y se verificó que coincide departamento por departamento.
Detalle en la sección 8 del notebook.

2025/26 fue Niña débil (ONI −0,54) con muy buena cosecha: maíz 7700 kg/ha de media, el segundo mejor
año desde 2000 (después de 2009/10), y soja 2961 kg/ha, arriba del promedio de 2720.

| 2025/26 · 19 departamentos | Maíz | Soja |
| --- | --- | --- |
| Promedio histórico | 1319 (16,8 %) | 374 (12,0 %) |
| Tendencia lineal | **1213 (15,2 %)** | **235 (7,9 %)** |
| XGBoost sobre la tendencia | 1948 (24,9 %) | 286 (9,3 %) |
| XGBoost sobre el promedio | 2142 (27,6 %) | 531 (17,3 %) |

**En la primera prueba real, el XGBoost perdió contra la tendencia lineal en los dos cultivos.** En maíz
subestimó 18 de los 19 departamentos, por 1915 kg/ha en promedio.

**Causa probable: el ONI.** 9 de las 10 Niñas anteriores dieron maíz por debajo del promedio, y el ONI es
la variable que más pesa: el modelo bajó la predicción por ser Niña. El mismo XGBoost sin el ONI:

| Error del XGBoost | Con ONI | Sin ONI |
| --- | --- | --- |
| Maíz · 2025/26 en vivo | 24,9 % | 17,1 % |
| Maíz · loco, todas las campañas | 18,6 % | 21,0 % |
| Maíz · temporal, todas las campañas | 22,1 % | 23,0 % |
| Soja · 2025/26 en vivo | 9,3 % | 6,9 % |
| Soja · loco, todas las campañas | 16,7 % | 16,7 % |
| Soja · temporal, todas las campañas | 23,4 % | 23,1 % |

En soja el ONI no aporta en la historia y en 2025/26 restó. En maíz ayuda en la historia y falló fuerte
en vivo. Es un diagnóstico hecho mirando el resultado de un solo año, así que el modelo no se cambia
todavía: lo que hay que revisar es cómo entra el ONI. Para 2026/27, un Niño muy fuerte, el riesgo es el
mismo en espejo: que la fase empuje la predicción más de lo que muestran el NDVI y el clima del año.

## Próximos pasos sugeridos

- **Revisar cómo entra el ONI.** Probar sin el ONI en soja, donde no aporta. En maíz, probar alternativas
  (solo la intensidad, o que la fase entre a través del NDVI y el clima observados). Medir siempre en
  `temporal` y contra la validación en vivo, no solo en `loco`.
- **Predicción 2026/27** con el corte de diciembre, cuando la tabla tenga los datos de diciembre de 2026.
  Hoy solo tiene septiembre y parte de octubre.
- Hiperparámetros con validación anidada (búsqueda dentro de cada pliegue de entrenamiento).
- Variables derivadas: NDVI máximo, integral de NDVI dic-mar, lluvia acumulada, días de calor.
- Rinde ponderado por superficie en las métricas regionales (hoy cada departamento pesa igual).
- Repetir con la tabla de Entre Ríos para ver si los resultados se sostienen (ver arriba qué falta).
