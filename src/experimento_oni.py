"""Experimento: cómo entra el ONI al XGBoost (16/11/2026).

Prueba cinco formas de meter el ENSO, con las dos bases (tendencia y promedio), prediciendo en
diciembre y en abril, en Santa Fe y Entre Ríos, con los esquemas loco y temporal. Más un placebo:
el ONI de otra campaña al azar (si el placebo "ayuda" igual que el ONI, la ayuda no es señal).

  oni               ONI continuo (el modelo hasta el 15/11)
  sin_oni           sin variable ENSO (el modelo por defecto desde el 16/11)
  fase              Niño y Niña como dos indicadores
  oni_fuerte        ONI solo si |ONI| >= 1, si no 0
  solo_nino_fuerte  indicador de Niño fuerte (ONI >= 1,5)

Salida: data/processed/experimento_oni.csv, una fila por región × cultivo × base × corte × esquema ×
variante × campaña con el error medio absoluto (kg/ha), el error porcentual y el sesgo. La sección 9 del
notebook la resume. Las predicciones de cada combinación quedan en data/processed/experimento_oni/
(no se versionan) y no se recalculan si ya están: el experimento retoma si se corta.

Uso:  uv run python src/experimento_oni.py [--procesos 3]      (unos 15 minutos con 3 procesos)
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

import modelo

CACHE = modelo.ROOT / "data" / "processed" / "experimento_oni"
SALIDA = modelo.ROOT / "data" / "processed" / "experimento_oni.csv"
REGIONES = ("santa_fe", "entre_rios")
VARIANTES = {"oni": ["oni"], "sin_oni": [], "fase": ["fase_nino", "fase_nina"],
             "oni_fuerte": ["oni_fuerte"], "solo_nino_fuerte": ["nino_fuerte_f"]}
CORTES = {"dic": 4, "abr": 8}
SEMILLAS_PLACEBO = range(3)


def preparar(region: str) -> pd.DataFrame:
    df = modelo.cargar_tabla(region)
    df["fase_nino"] = (df.fase_enso == "nino").astype(float)
    df["fase_nina"] = (df.fase_enso == "nina").astype(float)
    df["oni_fuerte"] = df.oni.where(df.oni.abs() >= 1, 0.0)
    df["nino_fuerte_f"] = df.nino_fuerte.astype(float)
    camp = np.sort(df.campania.unique())
    oni_c = df.drop_duplicates("campania").set_index("campania").oni.reindex(camp).to_numpy()
    for s in SEMILLAS_PLACEBO:
        perm = dict(zip(camp, np.random.default_rng(s).permutation(oni_c)))
        df[f"placebo_{s}"] = df.campania.map(perm)
    return df


def correr(cfg: tuple) -> Path:
    region, variante, extra, base, corte = cfg
    dest = CACHE / f"{region}__{variante}__{base}__{corte}.csv"
    if dest.exists():
        return dest
    df = preparar(region)
    f = modelo.xgboost_sobre_tendencia(modelo.columnas_clima_satelite(CORTES[corte]) + extra, base=base)
    p = pd.concat([modelo.validar(df, {variante: f}, esquema=e) for e in ("loco", "temporal")])
    tmp = dest.with_suffix(".tmp")
    p.assign(region=region, base=base, corte=corte).to_csv(tmp, index=False)
    tmp.rename(dest)  # escritura atómica: un corte no deja archivos a medias
    return dest


def configuraciones() -> list[tuple]:
    cfgs = [(r, v, x, b, c) for r in REGIONES for v, x in VARIANTES.items()
            for b in ("tendencia", "promedio") for c in CORTES]
    cfgs += [(r, f"placebo_{s}", [f"placebo_{s}"], "tendencia", "abr") for r in REGIONES for s in SEMILLAS_PLACEBO]
    return cfgs


def resumir(archivos: list[Path]) -> pd.DataFrame:
    p = pd.concat(pd.read_csv(a, dtype={"depto_id": str}) for a in archivos)
    p["error_abs"] = p.error.abs()
    p["error_pct"] = p.error_abs / p[modelo.OBJETIVO] * 100
    claves = ["region", "cultivo", "base", "corte", "esquema", "modelo", "campania", "fase_enso", "nino_fuerte"]
    r = p.groupby(claves).agg(mae_kg_ha=("error_abs", "mean"), error_pct=("error_pct", "mean"),
                              sesgo_kg_ha=("error", "mean"), n=("error", "size")).reset_index()
    return r.rename(columns={"modelo": "variante"}).round(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procesos", type=int, default=3)
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    cfgs = configuraciones()
    with ProcessPoolExecutor(a.procesos) as ex:
        archivos = []
        for i, dest in enumerate(ex.map(correr, cfgs), 1):
            archivos.append(dest)
            print(f"{i}/{len(cfgs)} {dest.name}", flush=True)
    r = resumir(archivos)
    r.to_csv(SALIDA, index=False)
    print(f"{SALIDA.name}: {len(r)} filas")


if __name__ == "__main__":
    main()
