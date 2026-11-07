"""Configuración compartida: rutas, regiones piloto y helpers geográficos.

La región activa se elige con la variable de entorno AGRO_REGION
(por defecto `santa_fe`):

    AGRO_REGION=entre_rios uv run python src/04_modis.py
"""
from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# Provincias que se descargan del IGN (código INDEC): Buenos Aires, Entre Ríos, Santa Fe.
PROVINCIAS = {"06": "Buenos Aires", "30": "Entre Ríos", "82": "Santa Fe"}

# Regiones candidatas. `ids` = códigos de departamento INDEC/IGN; None = toda la provincia.
REGIONES = {
    "santa_fe": {
        "nombre": "Santa Fe",
        "provincias": ["82"],
        "ids": None,
    },
    "entre_rios": {
        "nombre": "Entre Ríos",
        "provincias": ["30"],
        "ids": None,
    },
    "norte_ba_sur_sf": {
        "nombre": "Norte de Buenos Aires y sur de Santa Fe",
        "provincias": ["06", "82"],
        "ids": [
            "06070", "06077", "06140", "06161", "06175", "06210", "06294", "06413", "06623",
            "06665", "06686", "06714", "06735", "06763", "06770",
            "82007", "82014", "82028", "82042", "82056", "82084", "82119",
        ],
    },
    "noroeste_ba": {
        "nombre": "Noroeste de Buenos Aires",
        "provincias": ["06"],
        "ids": ["06392", "06679", "06154", "06826", "06609", "06147", "06588", "06469", "06351",
                "06277", "06462", "06406"],
    },
}

REGION = os.environ.get("AGRO_REGION", "santa_fe")
if REGION not in REGIONES:
    raise SystemExit(f"AGRO_REGION={REGION!r} no existe. Opciones: {', '.join(REGIONES)}")

PROC = ROOT / "data" / "processed" / REGION
FIG = ROOT / "outputs" / "figures" / REGION
SHARED = ROOT / "data" / "processed"  # tablas que no dependen de la región (ENSO, comparación)
for d in (PROC, FIG):
    d.mkdir(parents=True, exist_ok=True)

# Período de referencia para anomalías ("normal").
PERIODO_BASE = (2001, 2020)
# Cultivo en el CSV del MAGyP -> valor en la tabla maestra.
CULTIVOS = {"soja total": "soja", "maíz": "maiz"}
# Ventana de la campaña para las variables mensuales: mes_1 = septiembre ... mes_8 = abril.
# (Decisión pendiente del equipo; cambiar acá y volver a correr 05_tabla_maestra.py.)
MESES_CAMPANA = [9, 10, 11, 12, 1, 2, 3, 4]
NOMBRE_MES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun", 7: "jul", 8: "ago",
              9: "sep", 10: "oct", 11: "nov", 12: "dic"}


def campania(anio_siembra: int) -> str:
    """2015 -> '2015/16' (formato de la tabla maestra)."""
    return f"{anio_siembra}/{(anio_siembra + 1) % 100:02d}"


def departamentos(region: str = REGION) -> gpd.GeoDataFrame:
    """Polígonos IGN de los departamentos de la región, en WGS84."""
    cfg = REGIONES[region]
    g = gpd.read_file(RAW / "ign_departamentos.geojson")
    g = g[g["in1"].str[:2].isin(cfg["provincias"])]
    if cfg["ids"] is not None:
        g = g[g["in1"].isin(cfg["ids"])]
    g = g.drop(columns=["id"], errors="ignore").rename(columns={"in1": "id", "nam": "departamento"})
    g["provincia"] = g["id"].str[:2].map(PROVINCIAS)
    return g[["id", "departamento", "provincia", "geometry"]].sort_values("id").reset_index(drop=True)


def region_bbox(buffer_deg: float = 0.02) -> list[float]:
    minx, miny, maxx, maxy = departamentos().total_bounds
    return [minx - buffer_deg, miny - buffer_deg, maxx + buffer_deg, maxy + buffer_deg]


def enso() -> pd.DataFrame:
    """Fase ENSO por campaña (ver 02_rinde_enso.py)."""
    return pd.read_csv(SHARED / "enso_campanas.csv")
