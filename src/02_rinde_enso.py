"""Rinde por departamento (MAGyP), fase ENSO por campaña (ONI) y comparación de regiones candidatas.

Tareas 1.1-1.3 y 2.1 del plan del Predictor de rinde.

Salidas:
  data/processed/enso_campanas.csv                campaña -> ONI y fase (tarea 2.1)
  data/processed/comparacion_regiones.csv         datos disponibles y efecto ENSO por región candidata (1.3)
  data/processed/<region>/rinde_departamento.csv  soja y maíz por departamento y campaña, limpio (1.2)
  data/processed/<region>/cobertura_rinde.csv     campañas con dato por departamento y cultivo (1.3)

Fase ENSO de la campaña Y/Y+1: promedio del ONI de SON, OND y NDJ (año Y) y DJF (año Y+1),
los trimestres de siembra y período crítico de soja y maíz.
  ONI >= 0,5 -> nino · ONI <= -0,5 -> nina · resto -> neutro · nino_fuerte si ONI >= 1,5

Uso:  AGRO_REGION=santa_fe uv run python src/02_rinde_enso.py
"""
import numpy as np
import pandas as pd

import config

TRIMESTRES = ["SON", "OND", "NDJ"]
DESDE, HASTA = 2000, 2024  # campañas con MODIS y rinde publicado (2000/01 a 2024/25)


def enso_campanas() -> pd.DataFrame:
    oni = pd.read_csv(config.RAW / "oni.ascii.txt", sep=r"\s+")
    rows = []
    for y in range(oni["YR"].min(), oni["YR"].max() + 1):
        s = pd.concat([oni[(oni.YR == y) & oni.SEAS.isin(TRIMESTRES)]["ANOM"],
                       oni[(oni.YR == y + 1) & (oni.SEAS == "DJF")]["ANOM"]])
        parcial = len(s) < 4
        if len(s) == 0:
            # Campaña en curso sin SON publicado todavía: se usa el último trimestre disponible.
            ult = oni[oni.YR == y].tail(1)["ANOM"]
            if y != oni["YR"].max() or ult.empty:
                continue
            s = ult
        rows.append({"campania": config.campania(y), "anio_siembra": y, "oni": round(s.mean(), 2),
                     "oni_parcial": parcial})
    c = pd.DataFrame(rows)
    c["fase_enso"] = np.select([c.oni >= 0.5, c.oni <= -0.5], ["nino", "nina"], "neutro")
    c["nino_fuerte"] = c["oni"] >= 1.5
    c.to_csv(config.SHARED / "enso_campanas.csv", index=False)
    return c


def magyp() -> pd.DataFrame:
    df = pd.read_csv(config.RAW / "estimaciones-agricolas.csv", dtype={"departamento_id": str})
    df = df[df["cultivo"].isin(config.CULTIVOS) & (df["departamento"] != "sin definir")].copy()
    df["cultivo"] = df["cultivo"].map(config.CULTIVOS)
    return df.rename(columns={
        "anio": "anio_siembra", "departamento_id": "depto_id", "superficie_sembrada_ha": "sembrada_ha",
        "superficie_cosechada_ha": "cosechada_ha", "produccion_tm": "produccion_t",
        "rendimiento_kgxha": "rinde_kg_ha",
    }).drop(columns=["campania", "provincia", "provincia_id", "departamento"])


def anomalia_tendencia(g: pd.DataFrame) -> pd.Series:
    """Rinde vs la tendencia lineal del propio departamento (%)."""
    k = np.polyfit(g["anio_siembra"], g["rinde_kg_ha"], 1)
    return (g["rinde_kg_ha"] / np.polyval(k, g["anio_siembra"]) - 1) * 100


def comparar_regiones(df: pd.DataFrame, enso: pd.DataFrame) -> pd.DataFrame:
    fase = enso.set_index("anio_siembra")["fase_enso"]
    out = []
    for reg in ["santa_fe", "entre_rios", "norte_ba_sur_sf"]:
        deps = config.departamentos(reg)
        d = df[df["depto_id"].isin(deps["id"]) & df["anio_siembra"].between(DESDE, HASTA)]
        for cult, x in d.groupby("cultivo"):
            x = x[x["rinde_kg_ha"] > 0].copy()
            x["anom"] = x.groupby("depto_id", group_keys=False).apply(anomalia_tendencia, include_groups=False)
            x["fase"] = x["anio_siembra"].map(fase)
            resid_cv = x.groupby("depto_id")["anom"].std()  # desvío típico respecto de la tendencia, en %
            sem = x.groupby("depto_id")["sembrada_ha"].mean()
            s15 = d[(d["cultivo"] == cult) & (d["anio_siembra"] == 2015)]
            out.append({
                "region": config.REGIONES[reg]["nombre"], "region_id": reg, "cultivo": cult,
                "departamentos_ign": len(deps), "departamentos_con_rinde": x["depto_id"].nunique(),
                "filas_entrenamiento": len(x),
                "sembrada_media_kha": round(x.groupby("anio_siembra")["sembrada_ha"].sum().mean() / 1e3),
                "deptos_menos_10000_ha": int((sem < 10000).sum()),
                "variabilidad_rinde_pct": round(resid_cv.median(), 1),
                "rinde_nino_vs_tendencia_pct": round(x.loc[x["fase"] == "nino", "anom"].mean(), 1),
                "rinde_nina_vs_tendencia_pct": round(x.loc[x["fase"] == "nina", "anom"].mean(), 1),
                "rinde_2022_23_vs_tendencia_pct": round(x.loc[x["anio_siembra"] == 2022, "anom"].mean(), 1),
                "superficie_perdida_2015_16_pct": round((1 - s15["cosechada_ha"].sum() / s15["sembrada_ha"].sum()) * 100, 1),
            })
    res = pd.DataFrame(out)
    res.to_csv(config.SHARED / "comparacion_regiones.csv", index=False)
    return res


def main():
    enso = enso_campanas()
    df = magyp()
    comparar_regiones(df, enso)

    deps = config.departamentos().rename(columns={"id": "depto_id"})
    r = df[df["depto_id"].isin(deps["depto_id"])].merge(deps[["depto_id", "departamento", "provincia"]], on="depto_id")
    r["campania"] = r["anio_siembra"].map(config.campania)
    r.loc[r["rinde_kg_ha"] <= 0, "rinde_kg_ha"] = np.nan
    r["perdida_pct"] = ((1 - r["cosechada_ha"] / r["sembrada_ha"]) * 100).clip(lower=0).round(1)
    cols = ["depto_id", "departamento", "provincia", "campania", "anio_siembra", "cultivo",
            "sembrada_ha", "cosechada_ha", "produccion_t", "rinde_kg_ha", "perdida_pct"]
    r = r[cols].sort_values(["cultivo", "depto_id", "anio_siembra"])
    r.to_csv(config.PROC / "rinde_departamento.csv", index=False)

    v = r[r["anio_siembra"].between(DESDE, HASTA)]
    cov = v.groupby(["depto_id", "departamento", "cultivo"]).agg(
        primera=("campania", "min"), ultima=("campania", "max"),
        campanias_con_rinde=("rinde_kg_ha", "count"),
        sembrada_media_ha=("sembrada_ha", "mean")).reset_index().round(0)
    cov["faltan"] = (HASTA - DESDE + 1) - cov["campanias_con_rinde"]
    cov.to_csv(config.PROC / "cobertura_rinde.csv", index=False)
    print(f"{config.REGIONES[config.REGION]['nombre']}: {v.depto_id.nunique()} de {len(deps)} departamentos; "
          f"filas con rinde 2000/01-2024/25: " + ", ".join(f"{c} {n}" for c, n in v.groupby('cultivo')['rinde_kg_ha'].count().items()))


if __name__ == "__main__":
    main()
