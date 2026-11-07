"""Descarga las fuentes base (no requieren cuenta):

  * Límites de departamentos del IGN (WFS) para Buenos Aires, Entre Ríos y Santa Fe.
  * Estimaciones agrícolas por departamento del MAGyP (1969/70 en adelante).
  * Índice ONI de NOAA (fase ENSO trimestral desde 1950).

Uso:  uv run python src/01_descargas.py [--forzar]
"""
import argparse
import json

import requests

import config

IGN_WFS = (
    "https://wms.ign.gob.ar/geoserver/ign/ows?service=WFS&version=1.0.0&request=GetFeature"
    "&typeName=ign:departamento&outputFormat=application/json&CQL_FILTER=in1%20LIKE%20%27{prov}%25%27"
)
MAGYP_API = "https://datos.magyp.gob.ar/api/3/action/package_show?id=estimaciones-agricolas"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"


def get(url, timeout=180) -> bytes:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true", help="volver a descargar aunque exista")
    a = ap.parse_args()

    dest = config.RAW / "ign_departamentos.geojson"
    if a.forzar or not dest.exists():
        feats = []
        for prov in config.PROVINCIAS:
            feats += json.loads(get(IGN_WFS.format(prov=prov)))["features"]
        dest.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        print(f"IGN: {len(feats)} departamentos")

    dest = config.RAW / "estimaciones-agricolas.csv"
    if a.forzar or not dest.exists():
        res = requests.get(MAGYP_API, timeout=60).json()["result"]["resources"]
        url = next(r["url"] for r in res if r["format"] == "CSV" and r["name"] == "Estimaciones agrícolas")
        dest.write_bytes(get(url))
        print(f"MAGyP: {url.rsplit('/', 1)[-1]}")

    dest = config.RAW / "oni.ascii.txt"
    if a.forzar or not dest.exists():
        dest.write_bytes(get(ONI_URL))
        print("ONI descargado")


if __name__ == "__main__":
    main()
