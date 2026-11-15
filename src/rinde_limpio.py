"""Frente 1 (tarea 1.2): rinde limpio con código único por departamento.

Lee los extractos crudos del MAGyP (data/raw/magyp_<region>_soja_maiz.csv) y los une, por nombre normalizado,
con los códigos INDEC oficiales de data/processed/cruce_departamentos.csv (API Georef de datos.gob.ar).
Escribe data/processed/<region>/rinde_limpio_<region>.csv: una fila por departamento x campaña x cultivo.

Uso:  python src/rinde_limpio.py            # todas las regiones
      python src/rinde_limpio.py santa_fe   # una región
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
REGIONES = {"santa_fe": "Santa Fe", "entre_rios": "Entre Ríos"}
CULTIVOS = {"Soja total": "soja", "Maíz": "maiz"}


def normalizar(s: str) -> str:
    """Mayúsculas y sin acentos, para cruzar nombres entre fuentes."""
    s = unicodedata.normalize("NFD", str(s).upper().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def construir(region: str) -> pd.DataFrame:
    prov = REGIONES[region]
    crudo = pd.read_csv(RAIZ / f"data/raw/magyp_{region}_soja_maiz.csv", sep=";", encoding="latin-1", dtype=str)
    crudo.columns = ["prov_id", "provincia", "magyp_id", "departamento", "cultivo_id", "cultivo",
                     "camp_id", "campania", "sembrada_ha", "cosechada_ha", "produccion_tn", "rinde_kg_ha"]
    cruce = pd.read_csv(RAIZ / "data/processed/cruce_departamentos.csv", dtype=str)
    cruce = cruce[cruce.provincia == prov]

    crudo["nombre_norm"] = crudo.departamento.map(normalizar)
    df = crudo.merge(cruce[["nombre_norm", "indec_id", "nombre_oficial"]], on="nombre_norm", how="left", validate="m:1")
    sin_codigo = df[df.indec_id.isna()].departamento.unique()
    assert len(sin_codigo) == 0, f"Departamentos sin código INDEC en {prov}: {list(sin_codigo)}"

    df["provincia"] = prov
    df["cultivo"] = df.cultivo.map(CULTIVOS)
    assert df.cultivo.notna().all(), "Cultivo inesperado en el extracto"
    for c in ["sembrada_ha", "cosechada_ha", "produccion_tn", "rinde_kg_ha"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["anio_siembra"] = df.campania.str[:4].astype(int)
    df["perdida_total"] = (df.sembrada_ha > 0) & (df.cosechada_ha == 0) & (df.rinde_kg_ha == 0)

    out = df.rename(columns={"indec_id": "depto_id", "nombre_oficial": "departamento_oficial"})
    out = out[["depto_id", "departamento_oficial", "provincia", "campania", "anio_siembra", "cultivo",
               "sembrada_ha", "cosechada_ha", "produccion_tn", "rinde_kg_ha", "perdida_total"]]
    out = out.rename(columns={"departamento_oficial": "departamento"})
    out = out.sort_values(["depto_id", "cultivo", "anio_siembra"]).reset_index(drop=True)
    assert not out.duplicated(["depto_id", "campania", "cultivo"]).any(), "Filas duplicadas"
    return out


def main(regiones: list[str]) -> None:
    for r in regiones:
        out = construir(r)
        destino = RAIZ / f"data/processed/{r}"
        destino.mkdir(parents=True, exist_ok=True)
        archivo = destino / f"rinde_limpio_{r}.csv"
        out.to_csv(archivo, index=False, encoding="utf-8")
        print(f"{r}: {len(out)} filas, {out.depto_id.nunique()} departamentos -> {archivo}")


if __name__ == "__main__":
    main(sys.argv[1:] or list(REGIONES))
