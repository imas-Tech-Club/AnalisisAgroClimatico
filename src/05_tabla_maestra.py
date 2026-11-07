"""Tabla maestra v1 (tarea 1.4): una fila por departamento × campaña × cultivo.

Formato del documento "Predictor de rinde" (diccionario completo en docs/tabla_maestra.md):
  depto_id, departamento, provincia, campania (2015/16), anio_siembra, cultivo (soja | maiz),
  fase_enso (nino | nina | neutro), oni, nino_fuerte,
  ndvi_mes_1..N, lluvia_mes_1..N, temp_mes_1..N, humedad_suelo_mes_1..N,
  sembrada_ha, rinde_real (kg/ha)

mes_1 = primer mes de config.MESES_CAMPANA (septiembre por defecto) ... mes_8 = abril.
Incluye las campañas sin rinde publicado (2025/26 y la 2026/27 en curso) con rinde_real vacío:
son las que el modelo tiene que predecir.

Uso:  AGRO_REGION=santa_fe uv run python src/05_tabla_maestra.py
"""
import json

import numpy as np
import pandas as pd

import config

MODIS = config.PROC / "modis"
MIN_VALIDO = 0.5  # fracción mínima de píxeles de cultivo válidos (sin nube) para usar un compuesto


def anio_siembra(fecha: pd.Series) -> np.ndarray:
    """Julio a junio = una campaña; julio-diciembre pertenecen al año de siembra."""
    return np.where(fecha.dt.month >= 7, fecha.dt.year, fecha.dt.year - 1)


def ndvi_mensual() -> pd.DataFrame:
    """NDVI medio en tierras de cultivo por departamento y mes (MODIS Terra, máscara WorldCover)."""
    z = pd.concat(pd.read_parquet(p) for p in sorted((MODIS / "zonal").glob("*.parquet")))
    z = z.drop_duplicates(subset=["fecha", "tile", "zona"])  # compuesto de fin de año repetido
    zonas = json.loads((MODIS / "zonas.json").read_text())
    z["depto_id"] = z["zona"].astype(str).map(lambda k: zonas[k]["id"])
    c = z.groupby(["fecha", "depto_id"], as_index=False)[
        ["n_px_cult", "n_valid_cult", "n_ndvi_cult", "ndvi_sum_cult"]].sum()  # suma de tiles
    c["valido"] = c["n_valid_cult"] / c["n_px_cult"].where(c["n_px_cult"] > 0)
    c = c[c["valido"] >= MIN_VALIDO]
    c["ndvi"] = c["ndvi_sum_cult"] / c["n_ndvi_cult"].where(c["n_ndvi_cult"] > 0)
    c["mes"] = c["fecha"].dt.to_period("M").dt.to_timestamp()
    m = c.groupby(["depto_id", "mes"], as_index=False).agg(ndvi=("ndvi", "mean"), compuestos=("ndvi", "count"),
                                                           valido=("valido", "mean"))
    m.round({"ndvi": 4, "valido": 3}).to_csv(config.PROC / "ndvi_mensual_departamento.csv", index=False)
    return m


def a_columnas(m: pd.DataFrame, var: str, nombre: str) -> pd.DataFrame:
    """Serie mensual (depto_id, mes, var) -> columnas nombre_mes_1..N por campaña."""
    m = m[m["mes"].dt.month.isin(config.MESES_CAMPANA)].copy()
    m["anio_siembra"] = anio_siembra(m["mes"])
    m["k"] = m["mes"].dt.month.map({mes: i + 1 for i, mes in enumerate(config.MESES_CAMPANA)})
    w = m.pivot_table(index=["depto_id", "anio_siembra"], columns="k", values=var)
    w = w.reindex(columns=range(1, len(config.MESES_CAMPANA) + 1))
    w.columns = [f"{nombre}_mes_{k}" for k in w.columns]
    return w.reset_index()


def main():
    deps = config.departamentos().rename(columns={"id": "depto_id"})[["depto_id", "departamento", "provincia"]]
    enso = config.enso()
    ultima = int(enso["anio_siembra"].max())
    base = deps.merge(pd.DataFrame({"anio_siembra": range(2000, ultima + 1)}), how="cross")
    base = base.merge(pd.DataFrame({"cultivo": list(config.CULTIVOS.values())}), how="cross")
    base = base.merge(enso[["anio_siembra", "campania", "fase_enso", "oni", "nino_fuerte"]], on="anio_siembra")

    r = pd.read_csv(config.PROC / "rinde_departamento.csv", dtype={"depto_id": str})
    r = r[["depto_id", "anio_siembra", "cultivo", "sembrada_ha", "rinde_kg_ha"]].rename(
        columns={"rinde_kg_ha": "rinde_real"})
    base = base.merge(r, on=["depto_id", "anio_siembra", "cultivo"], how="left")

    ndvi = ndvi_mensual()
    clima = pd.read_csv(config.PROC / "clima_mensual_departamento.csv", parse_dates=["mes"], dtype={"depto_id": str})
    for serie, var, nombre in [(ndvi, "ndvi", "ndvi"), (clima, "lluvia_mm", "lluvia"),
                               (clima, "temp_c", "temp"), (clima, "humedad_suelo", "humedad_suelo")]:
        base = base.merge(a_columnas(serie, var, nombre), on=["depto_id", "anio_siembra"], how="left")

    claves = ["depto_id", "departamento", "provincia", "campania", "anio_siembra", "cultivo",
              "fase_enso", "oni", "nino_fuerte"]
    resto = [c for c in base.columns if c not in claves + ["sembrada_ha", "rinde_real"]]
    base = base[claves + resto + ["sembrada_ha", "rinde_real"]]
    base = base.sort_values(["cultivo", "depto_id", "anio_siembra"]).reset_index(drop=True)
    base.round(4).to_csv(config.PROC / "tabla_maestra.csv", index=False)

    meses = ", ".join(f"mes_{i + 1}={config.NOMBRE_MES[m]}" for i, m in enumerate(config.MESES_CAMPANA))
    entrenables = base["rinde_real"].notna()
    print(f"tabla_maestra: {len(base)} filas x {base.shape[1]} columnas · {base.depto_id.nunique()} deptos · "
          f"{base.campania.min()} a {base.campania.max()} · con rinde: {int(entrenables.sum())}")
    print(f"meses: {meses}")
    huecos = base[entrenables][resto].isna().mean().mul(100).round(1)
    print("huecos en filas con rinde (%):", huecos[huecos > 0].to_dict() or "ninguno")


if __name__ == "__main__":
    main()
