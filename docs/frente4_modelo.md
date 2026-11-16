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
| Modelos que se comparan siempre (incluye `xgboost_con_oni`) | `modelos_estandar(hasta_mes)` |
| Experimento de cómo entra el ONI | `src/experimento_oni.py` |

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

Desde el 15/11/2026 también hay tabla de **Entre Ríos** (`AGRO_REGION=entre_rios`), con las mismas
fuentes. Las dos tablas se generan con `src/01_descargas.py` a `src/05_tabla_maestra.py`, que toman el
rinde del frente 1; detalle en [`docs/tabla_maestra.md`](tabla_maestra.md).

## Decisiones

- **Regla de oro.** `validar` separa por `campania` y lo verifica con un `assert` en cada pliegue.
  Todo lo que se aprende (promedios, rectas por departamento, el XGBoost) se ajusta dentro del pliegue.
- **Dos esquemas.** `loco` es el del plan. `temporal` entrena solo con campañas anteriores (desde
  2008/09) y simula el uso real. `loco` favorece a la tendencia lineal porque le deja interpolar con
  campañas futuras: un modelo tiene que ganar en los dos esquemas.
- **El XGBoost predice el desvío, no el rinde.** Cada departamento tiene su nivel y su tendencia por
  tecnología, y con 26 campañas eso lo resuelve mejor una recta que un árbol. El XGBoost aprende lo que
  la base no explica (el año climático) y la predicción es base + desvío. Un modelo por cultivo.
- **Variables:** NDVI, lluvia, temperatura y humedad del suelo de septiembre a abril (32 columnas).
  Sin identificador de departamento, porque eso ya entra por la base. **Sin ONI desde el 16/11/2026**
  (sección "Cómo entra el ONI"): el ENSO entra por lo que se observa en la campaña. El modelo anterior,
  con ONI, queda como `xgboost_con_oni` para comparar.
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

## Resultados (Santa Fe, 16/11/2026)

19 departamentos, campañas 2000/01 a 2025/26: 494 filas de soja y 489 de maíz. Variables de septiembre
a abril. Tabla completa en `data/processed/santa_fe/metricas_modelos.csv`. Las versiones anteriores (7/11
sin 2025/26, 14/11 con ONI) quedan en el historial de git.

**Error medio absoluto (kg/ha) y error porcentual**

| Modelo | Soja · loco | Soja · temporal | Maíz · loco | Maíz · temporal |
| --- | --- | --- | --- | --- |
| Promedio histórico | 493 (25,0 %) | 584 (29,0 %) | 1182 (23,9 %) | 1273 (25,6 %) |
| Tendencia lineal | 491 (25,2 %) | 616 (31,7 %) | 1195 (24,4 %) | 1382 (29,3 %) |
| **XGBoost sobre la tendencia (por defecto)** | **360 (16,7 %)** | **466 (23,1 %)** | **1072 (21,0 %)** | **1179 (23,0 %)** |
| XGBoost sobre el promedio | 378 (17,0 %) | 459 (21,7 %) | 1119 (21,9 %) | 1187 (21,9 %) |
| XGBoost con ONI (escenario; el modelo hasta el 15/11) | 363 (16,7 %) | 476 (23,4 %) | 950 (18,6 %) | 1144 (22,1 %) |

R² del XGBoost (loco): 0,67 en soja y 0,63 en maíz, contra 0,41 y 0,53 del promedio histórico.

**Lo que dicen estos números**

1. **El XGBoost supera a las dos líneas base en los dos esquemas.** En soja tiene entre 20 y 27 % menos
   error que la mejor base. En maíz la ventaja es chica: entre 7 y 9 %. El costo de sacar el ONI está
   ahí: en maíz con `loco` el modelo con ONI le sacaba 20 % a la mejor base.
2. **La tendencia lineal no le gana al promedio histórico** en Santa Fe: empatan en `loco` y el promedio
   gana claro en `temporal`. El rinde medio casi no tiene tendencia en 2000-2025 (+11 kg/ha por año en
   soja y +19 en maíz, menos de 0,5 % anual), y la recta por departamento se deja arrastrar por los años
   extremos (2008/09, 2022/23).
3. **Las bases se equivocan con sesgo según la fase.** El promedio histórico sobreestima en años Niña
   (+927 kg/ha en maíz) y subestima en años Niño (−846). El XGBoost lo reduce a +521 y −208 (con ONI
   llegaba a +159 y −127: en maíz el ONI sí ayuda a corregir la fase en la historia).
4. **Subpregunta 2, primera respuesta:** el modelo **no** se equivoca más en años Niño. Error en soja:
   12,5 % en Niño, 11,6 % en neutro y **23,0 % en Niña**. El año difícil es el seco, no el lluvioso.
   Con 9 campañas Niño (2 fuertes) hay que tomarlo con cuidado.
5. **Subpregunta 1, cómo baja el error en la campaña.** En soja baja de 447 kg/ha (20 %) prediciendo
   en diciembre a 348 kg/ha (16 %) en marzo. **En maíz no baja** (1055 en diciembre, 1072 en abril): el
   NDVI de la máscara genérica de cultivo refleja sobre todo a la soja, que ocupa más superficie. La
   máscara propia de maíz (tarea 3.2) es lo que más puede mejorar este cultivo.
6. **La lluvia de diciembre es la variable más importante en los dos cultivos** (12 % de la ganancia en
   soja y 14 % en maíz). En soja le siguen la humedad del suelo de febrero y el NDVI de diciembre; en
   maíz, el NDVI y la temperatura de diciembre y la temperatura de marzo.

## Validación en vivo: campaña 2025/26

El 7/11/2026 el notebook dejó registrada la predicción de 2025/26 por departamento, entrenada con
2000/01 a 2024/25. La tabla no tenía el rinde de esa campaña: el dataset del MAGyP que usaba el
pipeline terminaba en 2024/25. El rinde real llegó el 14/11 con el frente 1. La predicción registrada es
la del modelo con ONI (hoy `xgboost_con_oni`): es el pliegue 2025/26 del esquema `temporal`, y se
verificó que coincide departamento por departamento. Detalle en la sección 8 del notebook.

2025/26 fue Niña débil (ONI −0,54) con muy buena cosecha: maíz 7700 kg/ha de media, el segundo mejor
año desde 2000 (después de 2009/10), y soja 2961 kg/ha, arriba del promedio de 2720.

| 2025/26 · 19 departamentos | Maíz | Soja |
| --- | --- | --- |
| Promedio histórico | 1319 (16,8 %) | 374 (12,0 %) |
| Tendencia lineal | **1213 (15,2 %)** | 235 (7,9 %) |
| **XGBoost con ONI (la predicción registrada)** | 1948 (24,9 %) | 286 (9,3 %) |
| XGBoost sin ONI (el de hoy; no cuenta como prueba en vivo) | 1376 (17,1 %) | **207 (6,9 %)** |

**En la primera prueba real, el XGBoost perdió contra la tendencia lineal en los dos cultivos.** En maíz
subestimó 18 de los 19 departamentos, por 1915 kg/ha en promedio.

**Causa probable: el ONI.** 9 de las 10 Niñas anteriores dieron maíz por debajo del promedio, y el ONI era
la variable que más pesaba: el modelo bajó la predicción por ser Niña. Sin el ONI el error baja, pero el
maíz sigue subestimado en 17 de los 19 departamentos: fue un año muy bueno y todos los modelos se
quedaron cortos. El modelo sin ONI se eligió el 16/11, después de ver este resultado, así que su error
en 2025/26 no es una prueba en vivo: la próxima es 2026/27.

**Descartado: el hueco de NDVI.** A 2025/26 le falta el NDVI de septiembre y octubre, y en el
entrenamiento ese dato nunca falta, así que el árbol podría mandar los vacíos por la rama equivocada.
Entrenando sin esos dos meses, el error en vivo casi no cambia (maíz 24,9 → 23,7 % en Santa Fe y
20,3 → 21,4 % en Entre Ríos).

## Entre Ríos (15/11/2026)

16 departamentos con rinde (Islas del Ibicuy no tiene rinde ni NDVI: es delta y WorldCover no marca
cultivo), campañas 2000/01 a 2025/26: 413 filas de soja y 413 de maíz. San Salvador empieza en 2003/04.
No hay pérdidas totales en la ventana. Tabla completa en `data/processed/entre_rios/metricas_modelos.csv`.

| Modelo | Soja · loco | Soja · temporal | Maíz · loco | Maíz · temporal |
| --- | --- | --- | --- | --- |
| Promedio histórico | 426 (26,3 %) | 469 (31,6 %) | 1199 (27,7 %) | 1294 (32,1 %) |
| Tendencia lineal | 441 (27,0 %) | 560 (34,5 %) | 1233 (28,5 %) | 1433 (34,9 %) |
| XGBoost sobre la tendencia (por defecto) | 314 (18,5 %) | 453 (26,1 %) | 881 (19,2 %) | 1106 (24,8 %) |
| **XGBoost sobre el promedio** | **297 (17,8 %)** | **382 (23,8 %)** | **858 (18,8 %)** | **984 (22,9 %)** |
| XGBoost con ONI (escenario) | 320 (18,8 %) | 462 (26,8 %) | 918 (19,5 %) | 1107 (24,5 %) |

1. **El XGBoost vuelve a ganarles a las dos líneas base en los dos esquemas**, así que el resultado de
   Santa Fe se sostiene en otra provincia.
2. **Pero acá conviene la otra base.** En Entre Ríos la tendencia lineal es peor que el promedio, y el
   XGBoost sobre el promedio tiene entre 18 y 30 % menos error que la mejor línea base. El XGBoost sobre
   la tendencia, el que se eligió con Santa Fe, casi no le gana al promedio en soja con validación
   temporal (453 contra 469 kg/ha).
3. **El ONI no aporta en Entre Ríos**: con o sin él, el error histórico es casi igual.

**Validación en vivo 2025/26.** También fue un buen año (maíz 6519 kg/ha contra 5734 de media, soja
2454 contra 2257).

| 2025/26 · 16 departamentos | Maíz | Soja |
| --- | --- | --- |
| **Promedio histórico** | 846 (12,7 %) | **216 (8,7 %)** |
| Tendencia lineal | 1065 (16,0 %) | 337 (13,6 %) |
| XGBoost con ONI (el modelo de ese momento) | 1338 (20,3 %) | 350 (14,1 %) |
| XGBoost sin ONI (el de hoy) | 1044 (15,9 %) | 361 (14,6 %) |
| XGBoost sobre el promedio, sin ONI | **806 (12,2 %)** | 283 (11,5 %) |

Igual que en Santa Fe, el XGBoost con ONI perdió en vivo y subestimó el maíz en los 16 departamentos. Sin
el ONI el maíz baja a 15,9 %; la soja no cambia. Las dos últimas filas son modelos elegidos después de ver
2025/26, así que no cuentan como prueba en vivo.

## Cómo entra el ONI (16/11/2026)

Después de 2025/26 se probaron cinco formas de meter el ENSO, con las dos bases, prediciendo en
diciembre (el primer corte para 2026/27) y en abril, en las dos provincias: ONI continuo (el modelo
anterior), sin ONI, fase Niño/Niña, ONI solo si |ONI| ≥ 1, y solo el indicador de Niño fuerte. Más un
**placebo**: el ONI de otra campaña al azar, para ver si el ONI ayuda por señal o porque, con un solo
valor por campaña, le sirve al árbol para memorizar años. Código: `src/experimento_oni.py`; resultados:
`data/processed/experimento_oni.csv` y sección 9 del notebook.

**Criterio, fijado antes de ver los resultados:** el error en validación `temporal` (el uso real),
promediando provincias y cultivos; `loco`, los años Niño y 2025/26 como control. Ante un empate, la
variante más simple.

| Variante | Temporal: cambio del error contra el ONI continuo | Pliegues en que le gana al ONI | Loco: cambio del error |
| --- | --- | --- | --- |
| Sin ONI | entre −2,8 y −0,2 % | 47 a 54 % | entre +1,5 y +2,9 % |
| Fase Niño/Niña | entre −3,4 y −1,1 % | 46 a 60 % | entre +1,6 y +3,6 % |
| ONI solo si \|ONI\| ≥ 1 | entre −3,5 y −0,8 % | 51 a 56 % | entre +1,8 y +2,9 % |
| Solo Niño fuerte | entre −3,3 y 0 % | 46 a 60 % | entre +1,7 y +3,9 % |

1. **Ninguna variante gana con claridad.** En `temporal` las diferencias son de 0 a 3,5 % y cada variante
   le gana al ONI en la mitad de los pliegues, más o menos: nivel de ruido.
2. **El ONI no memoriza años: tiene señal, pero solo en el maíz de Santa Fe.** Ahí, con `loco`, el error
   es de 950 kg/ha con ONI, 1072 sin ONI y unos 1090 con el placebo. En Entre Ríos y en soja, el ONI,
   el placebo y nada dan parecido.
3. **Las tres peores campañas de cada provincia y cultivo fueron Niñas moderadas**, con ONI entre −0,63
   y −0,82 (2022/23, 2008/09, 2017/18, 2000/01, 2021/22). Por eso cortar el ONI en ±1 borra justo la
   señal de sequía.
4. **En los dos Niños fuertes (2015/16 y 2023/24), el ONI empujó la predicción para arriba de más.** Sin
   ONI el error es menor en 7 de las 8 combinaciones de provincia, cultivo y corte; la mayor diferencia,
   en soja de Santa Fe prediciendo en diciembre (29,1 % sin ONI contra 33,4 % con ONI).

**Decisión:** el XGBoost por defecto va **sin ONI**, por la regla del empate y porque en los Niños
fuertes, que es el caso de 2026/27, el ONI empeoró la predicción. El costo es el maíz de Santa Fe, donde
el ONI sí ayudaba en la historia. El modelo con ONI queda como `xgboost_con_oni`, y para 2026/27 se
reportan los dos: si difieren mucho, la diferencia es lo que empuja la fase.

## Próximos pasos sugeridos

- **Elegir la base del XGBoost (tendencia o promedio)** con las dos provincias juntas: en Santa Fe gana
  sobre la tendencia y en Entre Ríos sobre el promedio. Una opción es entrenar con las dos tablas juntas.
- **Predicción 2026/27** con el corte de diciembre, cuando la tabla tenga los datos de diciembre de 2026
  (hoy solo tiene septiembre y parte de octubre). Reportar `xgboost` y `xgboost_con_oni`: la diferencia
  entre los dos es cuánto empuja la fase.
- Hiperparámetros con validación anidada (búsqueda dentro de cada pliegue de entrenamiento).
- Variables derivadas: NDVI máximo, integral de NDVI dic-mar, lluvia acumulada, días de calor.
- Rinde ponderado por superficie en las métricas regionales (hoy cada departamento pesa igual).
- Sumar más provincias cuando el frente 1 tenga su rinde limpio (cómo, en `docs/tabla_maestra.md`).
