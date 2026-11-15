"""Fase ENSO por campaña a partir del ONI de NOAA (tarea 2.1).

Salida: data/processed/enso_campanas.csv  (campaña -> ONI y fase; no depende de la región)

Fase ENSO de la campaña Y/Y+1: promedio del ONI de SON, OND y NDJ (año Y) y DJF (año Y+1),
los trimestres de siembra y período crítico de soja y maíz.
  ONI >= 0,5 -> nino · ONI <= -0,5 -> nina · resto -> neutro · nino_fuerte si ONI >= 1,5
En la campaña en curso, si todavía no hay ningún trimestre de esos publicado, se usa el último
disponible (`oni_parcial` = True).

El rinde ya no sale de acá: lo arma el frente 1 en data/processed/<region>/rinde_limpio_<region>.csv
(src/rinde_limpio.py).

Uso:  uv run --group datos python src/02_enso.py
"""
import numpy as np
import pandas as pd

import config

TRIMESTRES = ["SON", "OND", "NDJ"]


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


if __name__ == "__main__":
    c = enso_campanas()
    ult = c.iloc[-1]
    print(f"enso_campanas: {c.campania.min()} a {c.campania.max()} · última: ONI {ult.oni} ({ult.fase_enso}"
          f"{', parcial' if ult.oni_parcial else ''})")
