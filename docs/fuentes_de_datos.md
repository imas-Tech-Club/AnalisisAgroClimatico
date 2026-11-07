# Fuentes de datos

Estado al 7/11/2026. Todo lo que usa la tabla maestra v1 se descarga **sin cuentas** con los scripts de `src/`.

## Usadas en la tabla maestra v1

| Fuente | Qué aporta | Período y resolución | Acceso | Licencia |
| --- | --- | --- | --- | --- |
| **MAGyP – Estimaciones agrícolas** | Siembra, cosecha, producción y rinde por departamento y campaña | 1969/70 a **2024/25**, por departamento | CSV en [datos.magyp.gob.ar](https://datos.magyp.gob.ar/dataset/estimaciones-agricolas) (versión 2026-03). `src/01_descargas.py` toma la URL vigente desde la API del portal | CC BY 4.0 |
| **ONI (NOAA CPC)** | Fase ENSO de cada campaña | 1950 a hoy (último: ASO 2026 = +2,46) | [oni.ascii.txt](https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt) | Dominio público |
| **IGN – Departamentos** | Polígonos oficiales; el código `in1` es el mismo `departamento_id` del MAGyP | Vigente | WFS `ign:departamento` en [wms.ign.gob.ar](https://wms.ign.gob.ar/geoserver/ows) | Datos abiertos del IGN (confirmar condiciones) |
| **MODIS MOD13Q1 v6.1 (Terra)** | NDVI cada 16 días | Feb 2000 a hoy, 250 m | [Planetary Computer](https://planetarycomputer.microsoft.com/dataset/modis-13Q1-061), sin cuenta. En Earth Engine: `MODIS/061/MOD13Q1` | Sin restricciones (NASA LP DAAC) |
| **ESA WorldCover 2021 v200** | Máscara de "tierras de cultivo" (clase 40) para promediar el NDVI solo en lotes | 2021, 10 m | [Planetary Computer](https://planetarycomputer.microsoft.com/dataset/esa-worldcover). En Earth Engine: `ESA/WorldCover/v200` | CC BY 4.0 |
| **CHIRPS v3 mensual** | Lluvia mensual promediada sobre el polígono | 1981 a hoy (atraso de ~1 mes), 0,05° ≈ 5 km | GeoTIFF en [data.chc.ucsb.edu](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/tifs/), lectura por ventana | CC BY 4.0 (Climate Hazards Center) |
| **NASA POWER** (provisorio) | Temperatura media a 2 m y humedad del suelo de la zona de raíces (0-1) | 1981 a hoy (atraso de ~3 días), ~50 km, un punto por departamento | [API diaria](https://power.larc.nasa.gov/docs/services/api/temporal/daily/), sin cuenta | Uso libre con cita (NASA) |

## Hallazgo sobre el rinde (cambia el supuesto del plan)

El plan dice que las series por departamento llegan hasta 2019 y que la página de datos.gob.ar da 404.
**El MAGyP publica el dataset completo en su propio portal, actualizado a marzo de 2026, hasta la campaña 2024/25.**

- Para Santa Fe están los 19 departamentos con soja (475 filas) y maíz (470 filas) entre 2000/01 y 2024/25.
  Solo faltan 5 campañas de maíz sueltas en departamentos del norte. Detalle en
  `data/processed/santa_fe/cobertura_rinde.csv`.
- Eso da **25 campañas para entrenar, no 19**, e incluye la sequía 2022/23 y el Niño 2023/24.
- La campaña 2025/26 todavía no figura por departamento: va a salir en el próximo CSV del MAGyP.
- Unidad: el MAGyP publica en **kg/ha**; la tabla maestra la mantiene (qq/ha = kg/ha ÷ 100).

## Pendientes

| Fuente | Para qué | Dónde está |
| --- | --- | --- |
| ERA5-Land | Reemplazar a NASA POWER en temperatura y humedad del suelo (9 km, tarea 2.3) | Earth Engine `ECMWF/ERA5_LAND/DAILY_AGGR`; Open-Meteo `models=era5_land` |
| SMAP | Humedad del suelo observada (desde 2015) | Earth Engine `NASA/SMAP/SPL4SMGP/007` |
| Mapa Nacional de Cultivos (INTA) / MapBiomas Argentina | Máscara de soja y maíz por separado en lugar de "cultivo" genérico (tarea 3.2) | INTA (campañas 2018/19 en adelante) y MapBiomas (colecciones anuales). Revisar cobertura y licencia |
| Landsat 8/9 y Sentinel-2 | Verdor a 10-30 m como apoyo de MODIS | Planetary Computer `landsat-c2-l2`, `sentinel-2-l2a`; Earth Engine equivalentes |

## Planetary Computer y Earth Engine

El v1 corre sin cuentas para que cualquiera lo reproduzca clonando el repo. Earth Engine sigue siendo
el camino para ERA5-Land, SMAP y MapBiomas. Los IDs equivalentes están arriba, y el notebook
`notebooks/01_ndvi_modis_departamento.ipynb` trae el mismo cálculo de NDVI en las dos versiones.
