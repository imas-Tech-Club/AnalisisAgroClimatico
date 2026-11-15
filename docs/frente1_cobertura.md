# Frente 1 · Cobertura de datos de rinde y región piloto (tarea 1.3)

Fuente: dataset de Estimaciones Agrícolas del MAGyP, descargado el 14/11/2026 (actualizado por el MAGyP el
30/10/2026). Cultivos: `Soja total` y `Maíz`. Ventana de trabajo: campañas 2000/01 a 2025/26 (desde el inicio de
MODIS). Detalle de la fuente y de los archivos en `data/raw/README.md`.

## Resumen

- **Santa Fe y Entre Ríos tienen cobertura completa y sin huecos relevantes** de rinde para soja y maíz.
  Juntas son 35 departamentos.
- **Recomendación:** Santa Fe como región piloto confirmada; Entre Ríos como ampliación si NDVI y clima se pueden
  extraer para sus 16 departamentos a tiempo. Corrientes, Misiones y Formosa no se recomiendan para soja y maíz.
- **La campaña 2025/26 ya tiene rinde por departamento** en las dos provincias (puede ser preliminar), lo que
  permite validar en vivo la predicción del modelo.

## Comparación de regiones candidatas (2000/01 a 2024/25)

Superficie sembrada = promedio anual de soja + maíz de la provincia. Porcentaje calculado sobre estas seis
provincias del Litoral y el NEA.

| Provincia | Deptos soja / maíz | Filas con rinde > 0 (soja / maíz) | Superficie sembrada media | % del total de las seis |
|---|---|---|---|---|
| Santa Fe | 19 / 19 | 475 de 475 / 470 de 475 | 3,92 M ha | 61,6 % |
| Entre Ríos | 16 / 16 | 397 de 397 / 397 de 397 | 1,54 M ha | 24,2 % |
| Chaco | 23 / 25 | 522 de 522 / 560 de 562 | 0,80 M ha | 12,6 % |
| Corrientes | 20 / 26 | 171 de 175 / 385 de 386 | 0,03 M ha | 0,4 % |
| Misiones | 12 / 17 | 172 de 173 / 398 de 425 | 0,03 M ha | 0,5 % |
| Formosa | 8 / 8 | 71 de 71 / 71 de 72 | 0,04 M ha | 0,7 % |

Lectura: Santa Fe y Entre Ríos concentran el 86 % de la superficie de soja y maíz de estas provincias y no tienen
huecos. Corrientes, Misiones y Formosa tienen series cortas, incompletas y con superficies casi nulas: el modelo
no tendría señal para aprender. Su cultivo dominante es otro (arroz, yerba, té, forestales), por lo que quedan
para una segunda etapa con cultivos propios. Chaco es viable pero queda fuera del Litoral estricto y suma 25
departamentos más de extracción.

No se evaluó la opción "norte de Buenos Aires + sur de Santa Fe" del plan, porque requiere elegir qué
departamentos bonaerenses incluir (la provincia tiene 103) y esa lista no está definida.

## Santa Fe (región base)

- 19 departamentos, 26 campañas completas (2000/01 a 2025/26) en soja y en maíz.
- Rinde medio 2000/01 a 2024/25: soja 2710 kg/ha, maíz 6584 kg/ha.
- **Maíz 2008/09:** 9 de Julio, Garay, General Obligado, San Javier y Vera figuran con superficie sembrada pero
  superficie cosechada = 0 y rinde = 0. Es pérdida total reportada (campaña de sequía), no un dato faltante.
  La tabla maestra provisoria los deja vacíos. **Decisión pendiente:** tratarlos como 0 o excluirlos.
- 2025/26: rinde publicado para los 19 departamentos en soja y en maíz.
- Los 945 valores de rinde de la tabla maestra provisoria coinciden con el MAGyP.

## Entre Ríos (ampliación)

- 16 departamentos. Islas del Ibicuy no figura en el MAGyP para estos cultivos.
- 26 campañas completas en 15 departamentos. **San Salvador** tiene 23 (empieza en 2003/04).
- Sin ceros ni huecos de rinde en la ventana. Rinde medio 2000/01 a 2024/25: soja 2257 kg/ha, maíz 5734 kg/ha.
- La soja de la provincia empieza en 1973/74; no afecta a la ventana de trabajo.
- 2025/26: rinde publicado para los 16 departamentos en soja y en maíz.
- Los códigos INDEC no vienen en el MAGyP: se cruzan por nombre con los oficiales de la API Georef (datos.gob.ar); ver `data/processed/cruce_departamentos.csv`.

## Para tener en cuenta en todas las regiones

- Los `ID Departamento` del MAGyP no son códigos INDEC (ej.: 77 contra 82007). El cruce se hace por nombre
  normalizado, sin acentos y en mayúsculas. En Santa Fe coinciden los 19.
- La soja es `Soja total` (1ra + 2da).
- El rinde es por departamento, no por lote.
- 2025/26 puede ser una estimación preliminar y ser revisada por el MAGyP.

## Decisiones y pendientes

- [ ] Confirmar región: Santa Fe, o Santa Fe + Entre Ríos.
- [ ] Tratamiento del maíz 2008/09 de los cinco departamentos con pérdida total.
- [ ] Confirmar con Juan si su pipeline de NDVI y clima corre para los 16 departamentos de Entre Ríos.
- [x] Códigos INDEC de Entre Ríos (cruce hecho, tarea 1.2).
- [ ] Verificar la licencia del dataset (el README del frente 4 cita CC BY 4.0; el portal no la muestra).
