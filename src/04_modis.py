"""NDVI de MODIS Terra (MOD13Q1 v6.1, 250 m, compuestos de 16 días, 2000-hoy) por departamento.

De cada compuesto saca, por departamento, la suma y la cantidad de píxeles válidos de NDVI en
tierras de cultivo (ESA WorldCover 2021, clase 40, llevada a 250 m por moda). Con eso
05_tabla_maestra.py arma el NDVI mensual.

Se descartan los píxeles con confiabilidad 2-3 (nieve, nube) y los que tienen agua en superficie
(NIR < 0,12 y MIR 2,1 µm < 0,05). Esos píxeles de agua se cuentan aparte (`n_agua_*`): no entran en
la tabla v1, pero quedan como variable candidata (anegamiento en años Niño).

Lee los COG de Microsoft Planetary Computer (sin cuenta) en la grilla sinusoidal nativa de cada
tile: no se remuestrea y no se mezclan valores de relleno entre tiles. Los años ya procesados no se
vuelven a bajar, salvo el año en curso.

Uso:  AGRO_REGION=santa_fe uv run python src/04_modis.py [--desde 2000] [--hasta 2026]
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds

import config

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
B_NDVI = "250m_16_days_NDVI"
B_NIR = "250m_16_days_NIR_reflectance"
B_MIR = "250m_16_days_MIR_reflectance"
B_REL = "250m_16_days_pixel_reliability"
WATER_NIR_MAX = 1200  # 0,12 (reflectancia x 1e4)
WATER_MIR_MAX = 500  # 0,05
WC_CULTIVO, WC_PASTIZAL = 40, 30

OUT = config.PROC / "modis"
OUT_MASKS = OUT / "grillas"
OUT_MASKS.mkdir(parents=True, exist_ok=True)
GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    GDAL_HTTP_MAX_RETRY="6",
    GDAL_HTTP_RETRY_DELAY="3",
    VSI_CACHE="TRUE",
)


def tile_of(item) -> str:
    return item.id.split(".")[2]


def build_grids(cat) -> dict:
    """Por tile: ventana que cubre la región, zonas (departamentos) y cobertura WorldCover."""
    deps = config.departamentos()
    sample = {}
    for it in cat.search(collections=["modis-13Q1-061"], bbox=config.region_bbox(),
                         datetime="2020-01-01/2020-01-20").items():
        if it.id.startswith("MOD13Q1"):
            sample.setdefault(tile_of(it), it)
    wc_items = list(cat.search(collections=["esa-worldcover"], bbox=config.region_bbox(),
                               query={"esa_worldcover:product_version": {"eq": "2.0.0"}}).items())
    grids = {}
    with rasterio.Env(**GDAL_ENV):
        for tile, item in sorted(sample.items()):
            with rasterio.open(pc.sign(item.assets[B_NDVI].href)) as src:
                crs, tf_full, W, H = src.crs, src.transform, src.width, src.height
            p = deps.to_crs(crs)
            win = from_bounds(*p.total_bounds, tf_full)
            col0, row0 = max(0, int(np.floor(win.col_off))), max(0, int(np.floor(win.row_off)))
            col1 = min(W, int(np.ceil(win.col_off + win.width)))
            row1 = min(H, int(np.ceil(win.row_off + win.height)))
            if col1 <= col0 or row1 <= row0:
                continue
            win = Window(col0, row0, col1 - col0, row1 - row0)
            tf = rasterio.windows.transform(win, tf_full)
            shape = (int(win.height), int(win.width))
            zones = rasterize([(g, i + 1) for i, g in enumerate(p.geometry)],
                              out_shape=shape, transform=tf, fill=0, dtype="uint8")
            if not zones.any():
                continue
            cover = np.zeros(shape, dtype=np.uint8)
            for wi in wc_items:
                with rasterio.open(pc.sign(wi.assets["map"].href)) as wsrc:
                    with WarpedVRT(wsrc, crs=crs, transform=tf, width=shape[1], height=shape[0],
                                   resampling=Resampling.mode, nodata=0) as vrt:
                        arr = vrt.read(1)
                cover = np.where(cover == 0, arr, cover)
            grids[tile] = dict(window=win, transform=tf, crs=crs, shape=shape, zones=zones, cover=cover)
            np.savez_compressed(OUT_MASKS / f"grilla_{tile}.npz", zones=zones, cover=cover,
                                transform=np.array(tf)[:6], crs_wkt=np.array(crs.to_wkt()))
            enreg = zones > 0
            print(f"[grilla] {tile}: ventana {shape}, píxeles en región {int(enreg.sum())}, "
                  f"cultivo {int((enreg & (cover == WC_CULTIVO)).sum())}, "
                  f"pastizal {int((enreg & (cover == WC_PASTIZAL)).sum())}", flush=True)
    zonas = {i + 1: {"id": r.id, "departamento": r.departamento} for i, r in deps.iterrows()}
    (OUT / "zonas.json").write_text(json.dumps(zonas, ensure_ascii=False, indent=1))
    return grids


def read_band(item, band, win):
    with rasterio.open(pc.sign(item.assets[band].href)) as src:
        return src.read(1, window=win).astype(np.int16)


def process_item(item, grid):
    win, zones, cover = grid["window"], grid["zones"], grid["cover"]
    with rasterio.Env(**GDAL_ENV):
        ndvi = read_band(item, B_NDVI, win)
        nir = read_band(item, B_NIR, win)
        mir = read_band(item, B_MIR, win)
        rel = read_band(item, B_REL, win)
    valid = ((rel == 0) | (rel == 1)) & (ndvi > -2000) & (nir >= 0) & (mir >= 0)
    water = valid & (nir < WATER_NIR_MAX) & (mir < WATER_MIR_MAX)
    crop, grass = cover == WC_CULTIVO, cover == WC_PASTIZAL
    nz = int(zones.max()) + 1
    z = zones.ravel()

    def zsum(mask, weights=None):
        m = mask.ravel()
        w = None if weights is None else weights.ravel()[m].astype(np.float64)
        return np.bincount(z[m], weights=w, minlength=nz)

    crop_land = valid & ~water & crop
    stats = pd.DataFrame({
        "zona": np.arange(nz),
        "n_px": np.bincount(z, minlength=nz),
        "n_valid": zsum(valid), "n_agua": zsum(water),
        "n_px_cult": zsum(crop), "n_valid_cult": zsum(valid & crop), "n_agua_cult": zsum(water & crop),
        "n_px_past": zsum(grass), "n_valid_past": zsum(valid & grass), "n_agua_past": zsum(water & grass),
        "n_ndvi_cult": zsum(crop_land), "ndvi_sum_cult": zsum(crop_land, ndvi) * 1e-4,
    }).iloc[1:]
    stats["fecha"] = pd.Timestamp(item.properties["start_datetime"][:10])
    stats["tile"] = tile_of(item)
    return stats


def run_year(cat, grids, year, workers):
    out = OUT / "zonal" / f"{year}.parquet"
    out.parent.mkdir(exist_ok=True)
    if out.exists() and year < pd.Timestamp.today().year:
        print(f"[{year}] ya procesado", flush=True)
        return
    items = [it for it in cat.search(collections=["modis-13Q1-061"], bbox=config.region_bbox(),
                                     datetime=f"{year}-01-01/{year}-12-31").items()
             if it.id.startswith("MOD13Q1") and tile_of(it) in grids
             and it.properties["start_datetime"][:4] == str(year)]  # el compuesto de fin de año aparece en dos búsquedas
    if not items:
        return
    t0 = time.time()
    rows = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(process_item, it, grids[tile_of(it)]): it for it in items}
        for f in as_completed(futs):
            it = futs[f]
            try:
                stats = f.result()
            except Exception as e:  # noqa: BLE001 — un compuesto caído no frena la serie
                print(f"   ! {it.id}: {type(e).__name__}: {e}", flush=True)
                continue
            rows.append(stats)
    pd.concat(rows).sort_values(["fecha", "tile", "zona"]).to_parquet(out, index=False)
    print(f"[{year}] {len(items)} compuestos-tile en {time.time() - t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=int, default=2000)
    ap.add_argument("--hasta", type=int, default=pd.Timestamp.today().year)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    cat = pystac_client.Client.open(STAC, modifier=pc.sign_inplace)
    print(f"Región: {config.REGIONES[config.REGION]['nombre']}", flush=True)
    grids = build_grids(cat)
    for year in range(a.desde, a.hasta + 1):
        run_year(cat, grids, year, a.workers)


if __name__ == "__main__":
    main()
