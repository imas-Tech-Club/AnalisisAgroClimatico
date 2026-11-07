# Región piloto: comparación de candidatas (tarea 1.3)

Datos: MAGyP, campañas 2000/01 a 2024/25 (las que tienen MODIS y rinde publicado). Tabla completa en
`data/processed/comparacion_regiones.csv`, generada por `src/02_rinde_enso.py`.

| | Santa Fe completa | Norte de BA + sur de SF | Entre Ríos |
| --- | --- | --- | --- |
| Departamentos con rinde | 19 de 19 | 22 de 22 | 16 de 17 (falta Islas del Ibicuy) |
| Filas para entrenar (soja / maíz) | 475 / 470 | **550 / 550** | 397 / 397 |
| Soja sembrada por campaña (promedio) | **3,2 M ha** | 2,9 M ha | 1,2 M ha |
| Departamentos con menos de 10.000 ha (soja / maíz) | 1 / 3 | 0 / 6 | 0 / 6 |
| Variabilidad del rinde respecto de la tendencia (soja / maíz) | 21 % / 22 % | 21 % / 19 % | 24 % / 26 % |
| Soja en años Niño vs tendencia | +10,9 % | +11,7 % | +10,5 % |
| Soja en años Niña vs tendencia | −14,0 % | −12,7 % | −14,2 % |
| Soja en 2022/23 (sequía) vs tendencia | −49 % | −53 % | −53 % |
| Soja perdida en 2015/16 (Niño fuerte, inundaciones) | **10,0 %** | 4,9 % | 10,4 % |

## Lectura

- En las tres regiones **los años Niño rinden en promedio 10-12 % arriba de la tendencia y los Niña
  12-14 % abajo**. La fase ENSO es una señal fuerte para el modelo, no solo una categoría para
  analizar el error.
- El daño de un Niño fuerte aparece como **superficie que no se cosecha** (2015/16), y el MAGyP lo
  calcula sobre la superficie cosechada. Por eso un Niño con inundaciones puede tener buen rinde
  oficial y aun así perder producción. Conviene que el informe lo aclare.
- **Santa Fe completa** combina el mayor volumen de soja con un Niño 2015/16 que sí dejó pérdidas.
  Tiene la zona núcleo al sur y departamentos más variables al norte. Es la que mejor permite
  responder si el modelo se equivoca más en años Niño.
- **Norte de BA + sur de SF** da más filas y es más homogénea, pero ahí el Niño casi no generó
  pérdidas. Es la mejor opción si el objetivo es solo el menor error posible.
- **Entre Ríos** tiene menos filas y más variabilidad.

**Propuesta: Santa Fe completa.** Es la región que usa el repo por defecto. Cambiarla es correr el
pipeline con `AGRO_REGION=norte_ba_sur_sf` o `AGRO_REGION=entre_rios`.
