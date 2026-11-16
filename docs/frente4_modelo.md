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
| Experimento de la base del XGBoost (tendencia o promedio) | `src/experimento_base.py` |
| Predicción de una campaña sin rinde publicado (p. ej. 2026/27) | `predecir(df, campania, modelos, hasta_mes)`, o `src/modelo.py --predecir 2026/27 --corte nov` |

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
- **El XGBoost predice el desvío, no el rinde.** Cada departamento tiene su nivel, y con 26 campañas eso
  lo resuelve mejor una línea base que un árbol. El XGBoost aprende lo que la base no explica (el año
  climático) y la predicción es base + desvío. Un modelo por cultivo. **Desde el 16/11/2026 la base es el
  promedio histórico del departamento** (antes, la tendencia lineal): ver "Sobre qué base aprende el
  XGBoost".
- **Variables:** NDVI, lluvia, temperatura y humedad del suelo de septiembre a abril (32 columnas).
  Sin identificador de departamento, porque eso ya entra por la base. **Sin ONI desde el 16/11/2026**
  (sección "Cómo entra el ONI"): el ENSO entra por lo que se observa en la campaña. El modelo anterior,
  con ONI, queda como `xgboost_con_oni` para comparar.
- **Hiperparámetros conservadores** (400 árboles, profundidad 3, tasa 0,03, submuestreo 0,8), sin
  ajustar todavía. Ajustarlos con los mismos pliegues que se usan para medir el error infla los
  resultados: para buscarlos hace falta validación anidada.
- **Métricas:** MAE en kg/ha, error porcentual absoluto medio, R² y sesgo (error medio con signo:
  positivo = sobreestima). `mejora_vs_base_pct` compara el MAE contra el promedio histórico, la línea
  base más difícil de superar en las dos provincias.
- **Cortes:** `MESES_CORTE` va de noviembre (`mes_1` a `mes_3`) a abril. Noviembre es el corte de la
  entrega del 20/12/2026, porque los datos de diciembre recién están en enero.
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
sin 2025/26; 14/11 sobre la tendencia y con ONI) quedan en el historial de git.

**Error medio absoluto (kg/ha) y error porcentual**

| Modelo | Soja · loco | Soja · temporal | Maíz · loco | Maíz · temporal |
| --- | --- | --- | --- | --- |
| Promedio histórico | 493 (25,0 %) | 584 (29,0 %) | 1182 (23,9 %) | 1273 (25,6 %) |
| Tendencia lineal | 491 (25,2 %) | 616 (31,7 %) | 1195 (24,4 %) | 1382 (29,3 %) |
| **XGBoost (por defecto: sobre el promedio, sin ONI)** | **378 (17,0 %)** | **459 (21,7 %)** | **1119 (21,9 %)** | **1187 (21,9 %)** |
| XGBoost sobre la tendencia | 360 (16,7 %) | 466 (23,1 %) | 1072 (21,0 %) | 1179 (23,0 %) |
| XGBoost con ONI (escenario) | 376 (16,9 %) | 479 (22,7 %) | 995 (19,4 %) | 1253 (22,9 %) |

R² del XGBoost (loco): 0,66 en soja y 0,60 en maíz, contra 0,41 y 0,53 del promedio histórico.

**Lo que dicen estos números**

1. **El XGBoost supera a las dos líneas base en los dos esquemas.** En soja tiene entre 21 y 23 % menos
   error que el promedio histórico, la mejor base. En maíz la ventaja es chica: entre 5 y 7 %. En Santa Fe
   las dos bases del XGBoost dan parecido; la del promedio se eligió con las dos provincias (ver "Sobre qué
   base aprende el XGBoost"). Ojo con el sesgo: en `temporal` el modelo subestima el maíz en 423 kg/ha en
   promedio, porque el promedio histórico va detrás de la mejora del rinde.
2. **La tendencia lineal no le gana al promedio histórico** en Santa Fe: empatan en `loco` y el promedio
   gana claro en `temporal`. El rinde medio casi no tiene tendencia en 2000-2025 (+11 kg/ha por año en
   soja y +19 en maíz, menos de 0,5 % anual), y la recta por departamento se deja arrastrar por los años
   extremos (2008/09, 2022/23).
3. **Las bases se equivocan con sesgo según la fase.** El promedio histórico sobreestima en años Niña
   (+927 kg/ha en maíz) y subestima en años Niño (−846). El XGBoost lo reduce a +507 y −201.
4. **Subpregunta 2, primera respuesta:** el modelo **no** se equivoca más en años Niño. Error en soja:
   13,6 % en Niño, 11,6 % en neutro y **22,7 % en Niña**. El año difícil es el seco, no el lluvioso.
   Con 9 campañas Niño (2 fuertes) hay que tomarlo con cuidado.
5. **Subpregunta 1, cómo baja el error en la campaña** (insumo para el frente 5). Con `loco`, en soja baja
   de 520 kg/ha (25 %) prediciendo en noviembre a 459 (20 %) en diciembre y 365 (16 %) en marzo. En maíz
   baja de 1249 (25 %) en noviembre a 1057 (21 %) en diciembre, y **después ya no baja**: el NDVI de la
   máscara genérica de cultivo refleja sobre todo a la soja, que ocupa más superficie. La máscara propia de
   maíz (tarea 3.2) es lo que más puede mejorar este cultivo. Con datos hasta noviembre, el modelo todavía
   no le gana al promedio histórico (ver "Sobre qué base aprende el XGBoost").
6. **El NDVI y la lluvia de diciembre son las variables más importantes.** En soja: NDVI de diciembre
   (13 % de la ganancia), humedad del suelo de febrero (10 %) y lluvia de diciembre (9 %). En maíz: lluvia
   de diciembre (12 %), NDVI de diciembre (11 %) y temperatura de diciembre y de marzo.

## Validación en vivo: campaña 2025/26

El 7/11/2026 el notebook dejó registrada la predicción de 2025/26 por departamento, entrenada con
2000/01 a 2024/25. La tabla no tenía el rinde de esa campaña: el dataset del MAGyP que usaba el
pipeline terminaba en 2024/25. El rinde real llegó el 14/11 con el frente 1. La predicción registrada es
la del modelo de ese momento (XGBoost sobre la tendencia y con ONI), y se verificó que coincide
departamento por departamento. Detalle en la sección 8 del notebook.

2025/26 fue Niña débil (ONI −0,54) con muy buena cosecha: maíz 7700 kg/ha de media, el segundo mejor
año desde 2000 (después de 2009/10), y soja 2961 kg/ha, arriba del promedio de 2720.

| 2025/26 · 19 departamentos | Maíz | Soja |
| --- | --- | --- |
| Promedio histórico | 1319 (16,8 %) | 374 (12,0 %) |
| Tendencia lineal | **1213 (15,2 %)** | 235 (7,9 %) |
| **XGBoost registrado el 7/11 (tendencia, con ONI)** | 1948 (24,9 %) | 286 (9,3 %) |
| XGBoost de hoy (promedio, sin ONI) | 1483 (18,5 %) | 413 (13,1 %) |
| XGBoost sobre la tendencia, sin ONI | 1376 (17,1 %) | **207 (6,9 %)** |

**En la primera prueba real, el XGBoost perdió contra la tendencia lineal en los dos cultivos.** En maíz
subestimó 18 de los 19 departamentos, por 1915 kg/ha en promedio.

**Causa probable: el ONI.** 9 de las 10 Niñas anteriores dieron maíz por debajo del promedio, y el ONI era
la variable que más pesaba: el modelo bajó la predicción por ser Niña. Sin el ONI el error baja, pero el
maíz sigue subestimado en 17 de los 19 departamentos: fue un año muy bueno y todos los modelos se
quedaron cortos. Las dos últimas filas son modelos elegidos el 16/11, después de ver este resultado, así
que no cuentan como prueba en vivo: la próxima es 2026/27. En Santa Fe, 2025/26 le fue peor a la base del
promedio que a la de la tendencia, porque fue un año muy por encima del promedio.

**Descartado: el hueco de NDVI.** A 2025/26 le falta el NDVI de septiembre y octubre, y en el
entrenamiento ese dato nunca falta, así que el árbol podría mandar los vacíos por la rama equivocada.
Entrenando sin esos dos meses, el error en vivo del modelo registrado casi no cambia (maíz 24,9 → 23,7 %
en Santa Fe y 20,3 → 21,4 % en Entre Ríos).

## Entre Ríos (16/11/2026)

16 departamentos con rinde (Islas del Ibicuy no tiene rinde ni NDVI: es delta y WorldCover no marca
cultivo), campañas 2000/01 a 2025/26: 413 filas de soja y 413 de maíz. San Salvador empieza en 2003/04.
No hay pérdidas totales en la ventana. Tabla completa en `data/processed/entre_rios/metricas_modelos.csv`.

| Modelo | Soja · loco | Soja · temporal | Maíz · loco | Maíz · temporal |
| --- | --- | --- | --- | --- |
| Promedio histórico | 426 (26,3 %) | 469 (31,6 %) | 1199 (27,7 %) | 1294 (32,1 %) |
| Tendencia lineal | 441 (27,0 %) | 560 (34,5 %) | 1233 (28,5 %) | 1433 (34,9 %) |
| **XGBoost (por defecto: sobre el promedio, sin ONI)** | **297 (17,8 %)** | **382 (23,8 %)** | **858 (18,8 %)** | **984 (22,9 %)** |
| XGBoost sobre la tendencia | 314 (18,5 %) | 453 (26,1 %) | 881 (19,2 %) | 1106 (24,8 %) |
| XGBoost con ONI (escenario) | 303 (18,0 %) | 375 (23,3 %) | 882 (18,8 %) | 1001 (22,9 %) |

1. **El XGBoost vuelve a ganarles a las dos líneas base en los dos esquemas**, así que el resultado de
   Santa Fe se sostiene en otra provincia: entre 18 y 30 % menos error que el promedio histórico.
2. **Acá la base del promedio es claramente mejor.** El XGBoost sobre la tendencia casi no le gana al
   promedio histórico en soja con validación temporal (453 contra 469 kg/ha).
3. **El ONI no aporta en Entre Ríos**: con o sin él, el error histórico es casi igual.

**Validación en vivo 2025/26.** También fue un buen año (maíz 6519 kg/ha contra 5734 de media, soja
2454 contra 2257).

| 2025/26 · 16 departamentos | Maíz | Soja |
| --- | --- | --- |
| **Promedio histórico** | 846 (12,7 %) | **216 (8,7 %)** |
| Tendencia lineal | 1065 (16,0 %) | 337 (13,6 %) |
| XGBoost del 7/11 (tendencia, con ONI) | 1338 (20,3 %) | 350 (14,1 %) |
| XGBoost de hoy (promedio, sin ONI) | **806 (12,2 %)** | 283 (11,5 %) |
| XGBoost sobre la tendencia, sin ONI | 1044 (15,9 %) | 361 (14,6 %) |

Igual que en Santa Fe, el modelo del 7/11 perdió en vivo y subestimó el maíz en los 16 departamentos. Las
dos últimas filas son modelos elegidos después de ver 2025/26, así que no cuentan como prueba en vivo.

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

## Sobre qué base aprende el XGBoost, y el corte de noviembre (16/11/2026)

Con Santa Fe se había elegido la tendencia como base del XGBoost, pero en Entre Ríos anduvo mejor el
promedio. Se compararon las dos bases con el modelo sin ONI, en las dos provincias y en todos los cortes,
de noviembre a abril. Código: `src/experimento_base.py`; resultados: `data/processed/experimento_base.csv`
y sección 10 del notebook.

**Criterio, fijado antes de correr:** el error en `temporal`, promediando provincias, cultivos y cortes;
una sola base para todas las provincias. Si la elegida pierde por más de 5 % en alguna provincia y
cultivo, se discute antes de cambiar.

| Temporal: cambio del error con el promedio en vez de la tendencia | Nov | Dic | Ene | Feb | Mar | Abr | Media |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Santa Fe · maíz | −8,9 % | +2,8 % | +1,7 % | +4,5 % | +4,5 % | +0,6 % | +0,9 % |
| Santa Fe · soja | −4,0 % | +2,8 % | +1,0 % | −0,6 % | −2,5 % | −1,6 % | −0,8 % |
| Entre Ríos · maíz | −5,5 % | −14,1 % | −15,5 % | −12,8 % | −14,9 % | −11,0 % | −12,3 % |
| Entre Ríos · soja | −15,3 % | −12,7 % | −17,2 % | −18,9 % | −17,9 % | −15,6 % | −16,3 % |

**Decisión: la base es el promedio histórico.** Baja el error 7,1 % en promedio y gana en 17 de las 24
combinaciones. En Santa Fe empatan (en ninguna provincia y cultivo pierde por más de 0,9 %), en Entre
Ríos gana por 12 a 16 %, y en el corte de noviembre gana en los cuatro casos. En `loco` empatan (−0,9 %),
como era de esperar: ese esquema favorece a la tendencia porque la deja interpolar.

**Hallazgo: con datos hasta noviembre, el modelo todavía no le gana al promedio histórico.**

| Temporal: error del XGBoost contra el promedio histórico solo | Nov | Dic | Ene | Abr |
| --- | --- | --- | --- | --- |
| Santa Fe · maíz | +5,3 % | −7,1 % | −3,9 % | −6,8 % |
| Santa Fe · soja | +3,0 % | −3,5 % | −13,3 % | −21,5 % |
| Entre Ríos · maíz | +1,0 % | −28,0 % | −27,3 % | −23,9 % |
| Entre Ríos · soja | +3,4 % | +9,3 % | −9,2 % | −18,4 % |

Con datos de septiembre a noviembre, el XGBoost tiene entre 1 y 5 % más error que el promedio histórico
solo, en las dos provincias y los dos cultivos (con `loco`, entre 2 y 11 % más). Empieza a aportar en
diciembre; la soja de Entre Ríos, recién en enero. Es lo esperable: en noviembre la soja se está
sembrando y el NDVI todavía no muestra el cultivo.

**Consecuencia para la entrega del 20/12/2026.** La predicción de 2026/27 que se puede hacer para la
entrega es con el corte de noviembre, y con ese corte el modelo no supera al promedio histórico: hay que
presentarla así. La primera predicción en la que el modelo aporta es con los datos de diciembre, que
llegan en enero, en la etapa posterior del proyecto.

## Próximos pasos sugeridos

- **Predicción 2026/27 con el corte de noviembre**, cuando la tabla tenga los datos de noviembre
  (primera semana de diciembre; hoy le falta entre 42 y 50 % de los datos del corte):
  `AGRO_REGION=<region> uv run python src/modelo.py --predecir 2026/27 --corte nov`. Deja
  `prediccion_2026-27_nov.csv` con todos los modelos y avisa si faltan datos. Presentarla junto con el
  promedio histórico, que con ese corte es igual o mejor. Reportar también `xgboost_con_oni`: la
  diferencia con `xgboost` es cuánto empuja la fase.
- **Predicción con el corte de diciembre** en enero, si el proyecto sigue.
- Hiperparámetros con validación anidada (búsqueda dentro de cada pliegue de entrenamiento).
- Variables derivadas: NDVI máximo, integral de NDVI dic-mar, lluvia acumulada, días de calor.
- Rinde ponderado por superficie en las métricas regionales (hoy cada departamento pesa igual).
- Sumar más provincias cuando el frente 1 tenga su rinde limpio (cómo, en `docs/tabla_maestra.md`).
