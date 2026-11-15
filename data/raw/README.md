# data/raw — datos originales sin modificar

Extractos del dataset de Estimaciones Agrícolas del MAGyP. Son las filas originales, con el mismo encabezado,
separador (`;`) y codificación (ISO-8859-1, abrir con `encoding="latin-1"`). Solo se filtró por provincia y cultivo.

| Archivo | Provincia | Cultivos | Departamentos | Filas | SHA-256 |
|---|---|---|---|---|---|
| `magyp_santa_fe_soja_maiz.csv` | Santa Fe | Soja total, Maíz | 19 | 2136 | `ac8f400a9790a33cc87263ccd21b75c7a05f2e975c098d08a7369d8b2cf2c863` |
| `magyp_entre_rios_soja_maiz.csv` | Entre Ríos | Soja total, Maíz | 16 | 1643 | `59d97d0678558646f873e26e2cbaf9dc6913d2ae45418f3b4c0af74a2715f872` |

Campañas: 1969/70 a 2025/26 (Entre Ríos: soja desde 1973/74).

## Fuente y cómo repetirlo
- Ministerio de Agricultura (MAGyP), Dirección de Estimaciones Agrícolas.
  Portal: https://datosestimaciones.magyp.gob.ar/reportes.php?reporte=Estimaciones
- Descargado el 14/11/2026. El portal informa actualización del 30/10/2026.
- Archivo completo del país (11,7 MB, 163.760 filas, SHA-256
  `d1ef8fa2e21a7cbb266b4783d4d417b9abbb17cded1754982d77e677ddfa74d3`), que no se versiona:
  `curl -L -X POST -d "Dataset=Dataset" "https://datosestimaciones.magyp.gob.ar/reportes.php?reporte=Estimaciones" -o Estimaciones.csv`
- Unidades: superficies en ha, producción en tn, rendimiento en kg/ha.
- Licencia: el README del frente 4 cita CC BY 4.0; el portal no la muestra. Confirmar antes de publicar.

## Notas
- Los `ID Departamento` del MAGyP no son códigos INDEC (ej.: 77 contra 82007). El cruce se hace por nombre
  normalizado (sin acentos, en mayúsculas). En Santa Fe coinciden los 19 departamentos con la tabla maestra.
- Soja = `Soja total` (1ra + 2da). Maíz = `Maíz`.
- Santa Fe, maíz 2008/09: 5 departamentos (9 de Julio, Garay, General Obligado, San Javier, Vera) tienen superficie
  sembrada pero cosechada = 0 y rinde = 0. Es pérdida total reportada, no un dato faltante.
- Entre Ríos tiene 16 departamentos en el MAGyP (no figura Islas del Ibicuy). San Salvador tiene 23 campañas
  desde 2000/01; el resto, 26. Los códigos INDEC se cruzan por nombre con `data/processed/cruce_departamentos.csv`.
- La campaña 2025/26 ya trae rinde por departamento; puede ser preliminar.
