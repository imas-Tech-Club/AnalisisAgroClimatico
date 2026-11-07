"""Clima mensual por departamento (frente 2), sin cuentas:

  * Lluvia: CHIRPS v3 mensual (0,05° ≈ 5 km), promedio sobre el polígono del departamento.
  * Temperatura media del aire a 2 m y humedad del suelo de la zona de raíces (0-1):
    NASA POWER (reanálisis MERRA-2, ~50 km) en un punto interior del departamento.

NASA POWER es provisorio: el plan es reemplazarlo por ERA5-Land (tarea 2.3), que tiene
más resolución. El formato de salida no cambia.

Salida: data/processed/<region>/clima_mensual_departamento.csv
  depto_id, depto, mes (AAAA-MM-01), lluvia_mm, temp_c, humedad_suelo

Uso:  AGRO_REGION=santa_fe uv run python src/03_clima.py [--desde 2000]
"""
import argparse
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.features import rasterize
from rasterio.windows import from_bounds

import config

CHIRPS = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/tifs/chirps-v3.0.{y}.{m:02d}.tif"
POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
CACHE = config.RAW / "clima"
CACHE.mkdir(exist_ok=True)


# ------------------------------------------------------------------ CHIRPS
def chirps_mes(y: int, m: int, deps, zonas_cache: dict) -> pd.DataFrame | None:
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="3"):
        try:
            src = rasterio.open("/vsicurl/" + CHIRPS.format(y=y, m=m))
        except rasterio.errors.RasterioIOError:
            return None  # mes todavía no publicado
        with src:
            win = from_bounds(*config.region_bbox(0.1), src.transform).round_offsets().round_lengths()
            arr = src.read(1, window=win)
            tf = src.window_transform(win)
    key = (arr.shape, tuple(tf)[:6])
    if key not in zonas_cache:
        zonas_cache[key] = rasterize([(g, i + 1) for i, g in enumerate(deps.geometry)],
                                     out_shape=arr.shape, transform=tf, fill=0, dtype="uint8")
    z = zonas_cache[key]
    ok = (z > 0) & (arr >= 0)
    suma = np.bincount(z[ok], weights=arr[ok], minlength=len(deps) + 1)
    n = np.bincount(z[ok], minlength=len(deps) + 1)
    return pd.DataFrame({"depto_id": deps["id"].values, "mes": pd.Timestamp(y, m, 1),
                         "lluvia_mm": suma[1:] / np.maximum(n[1:], 1), "celdas": n[1:]})


def chirps(deps, desde: int) -> pd.DataFrame:
    dest = config.PROC / "chirps_mensual.csv"
    previo = pd.read_csv(dest, parse_dates=["mes"], dtype={"depto_id": str}) if dest.exists() else None
    hoy = pd.Timestamp.today()
    meses = [(y, m) for y in range(desde, hoy.year + 1) for m in range(1, 13) if pd.Timestamp(y, m, 1) < hoy]
    if previo is not None:
        hechos = set(previo["mes"].dt.strftime("%Y-%m"))
        meses = [(y, m) for y, m in meses if f"{y}-{m:02d}" not in hechos]
    zonas_cache: dict = {}
    with ThreadPoolExecutor(8) as ex:
        res = [r for r in ex.map(lambda ym: chirps_mes(*ym, deps, zonas_cache), meses) if r is not None]
    df = pd.concat(([previo] if previo is not None else []) + res).sort_values(["depto_id", "mes"])
    df.to_csv(dest, index=False)
    print(f"CHIRPS: {df.mes.min():%Y-%m} a {df.mes.max():%Y-%m}, mínimo {df.celdas.min()} celdas por departamento")
    return df


# ------------------------------------------------------------------ NASA POWER
def power_depto(depto_id: str, lat: float, lon: float, desde: int) -> pd.DataFrame:
    dest = CACHE / f"power_{depto_id}.csv"
    if dest.exists() and pd.Timestamp(dest.stat().st_mtime, unit="s") > pd.Timestamp.today() - pd.Timedelta(days=7):
        return pd.read_csv(dest, parse_dates=["fecha"])
    params = dict(parameters="T2M,GWETROOT", community="AG", longitude=round(lon, 4), latitude=round(lat, 4),
                  start=f"{desde}0101", end=pd.Timestamp.today().strftime("%Y%m%d"), format="JSON")
    for intento in range(5):
        r = requests.get(POWER, params=params, timeout=300)
        if r.ok:
            break
        time.sleep(20 * (intento + 1))
    r.raise_for_status()
    p = r.json()["properties"]["parameter"]
    df = pd.DataFrame({"fecha": pd.to_datetime(list(p["T2M"]), format="%Y%m%d"),
                       "temp_c": list(p["T2M"].values()), "humedad_suelo": list(p["GWETROOT"].values())})
    df = df.replace(-999.0, np.nan)
    df.to_csv(dest, index=False)
    return df


def power(deps, desde: int) -> pd.DataFrame:
    pts = deps.to_crs(32720).representative_point().to_crs(4326)
    frames = []
    for (_, row), pt in zip(deps.iterrows(), pts):
        d = power_depto(row.id, pt.y, pt.x, desde)
        d["depto_id"] = row.id
        frames.append(d)
    d = pd.concat(frames)
    d["mes"] = d["fecha"].dt.to_period("M").dt.to_timestamp()
    g = d.groupby(["depto_id", "mes"])
    m = g[["temp_c", "humedad_suelo"]].mean()
    m = m[g["temp_c"].count() >= 25].reset_index()  # mes completo (o casi)
    print(f"NASA POWER: {m.mes.min():%Y-%m} a {m.mes.max():%Y-%m}")
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=int, default=2000)
    a = ap.parse_args()
    deps = config.departamentos()
    ch = chirps(deps, a.desde)
    pw = power(deps, a.desde)
    out = ch.drop(columns="celdas").merge(pw, on=["depto_id", "mes"], how="outer")
    out = out.merge(deps[["id", "departamento"]].rename(columns={"id": "depto_id", "departamento": "depto"}),
                    on="depto_id")
    out = out[["depto_id", "depto", "mes", "lluvia_mm", "temp_c", "humedad_suelo"]].sort_values(["depto_id", "mes"])
    out.round({"lluvia_mm": 1, "temp_c": 2, "humedad_suelo": 3}).to_csv(
        config.PROC / "clima_mensual_departamento.csv", index=False)
    print(f"clima mensual: {len(out)} filas, {out.depto_id.nunique()} departamentos")


if __name__ == "__main__":
    main()
