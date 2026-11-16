"""Experimento: sobre qué base aprende el XGBoost, la tendencia lineal o el promedio histórico (16/11/2026).

El XGBoost aprende el desvío respecto de una línea base del departamento. En Santa Fe se había elegido la
tendencia; en Entre Ríos anduvo mejor el promedio. Acá se comparan las dos bases con el modelo por defecto
(sin ONI), en Santa Fe y Entre Ríos, en todos los cortes de `modelo.MESES_CORTE` (de noviembre a abril),
con los esquemas loco y temporal.

Criterio, fijado antes de correr: el error en `temporal`, promediando provincias, cultivos y cortes. Una
sola base para todas las provincias. Si la elegida pierde por más de 5 % en alguna provincia y cultivo,
se discute antes de cambiar.

Salida: data/processed/experimento_base.csv (mismo formato que experimento_oni.csv; la columna `variante`
dice la base). Las predicciones de cada combinación quedan en data/processed/experimento_base/ (no se
versionan) y no se recalculan si ya están.

Uso:  uv run python src/experimento_base.py [--procesos 3]      (unos 10 minutos con 3 procesos)
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

import modelo
from experimento_oni import resumir

CACHE = modelo.ROOT / "data" / "processed" / "experimento_base"
SALIDA = modelo.ROOT / "data" / "processed" / "experimento_base.csv"
REGIONES = ("santa_fe", "entre_rios")
BASES = ("tendencia", "promedio")


def correr(cfg: tuple) -> Path:
    region, base, corte = cfg
    dest = CACHE / f"{region}__{base}__{corte}.csv"
    if dest.exists():
        return dest
    df = modelo.cargar_tabla(region)
    f = modelo.xgboost_sobre_tendencia(modelo.columnas_clima_satelite(modelo.MESES_CORTE[corte]), base=base)
    p = pd.concat([modelo.validar(df, {base: f}, esquema=e) for e in ("loco", "temporal")])
    tmp = dest.with_suffix(".tmp")
    p.assign(region=region, base=base, corte=corte).to_csv(tmp, index=False)
    tmp.rename(dest)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procesos", type=int, default=3)
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    cfgs = [(r, b, c) for r in REGIONES for b in BASES for c in modelo.MESES_CORTE]
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
