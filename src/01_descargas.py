"""Descarga las fuentes base (no requieren cuenta):

  * Límites de departamentos del IGN (WFS) para Buenos Aires, Entre Ríos y Santa Fe.
  * Índice ONI de NOAA (fase ENSO trimestral desde 1950).

El rinde del MAGyP ya no se baja acá: los extractos están en data/raw/ (frente 1, ver data/raw/README.md).

Uso:  uv run --group datos python src/01_descargas.py [--forzar]
"""
import argparse
import json

import requests

import config

IGN_WFS = (
    "https://wms.ign.gob.ar/geoserver/ign/ows?service=WFS&version=1.0.0&request=GetFeature"
    "&typeName=ign:departamento&outputFormat=application/json&CQL_FILTER=in1%20LIKE%20%27{prov}%25%27"
)
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

    dest = config.RAW / "oni.ascii.txt"
    if a.forzar or not dest.exists():
        dest.write_bytes(get(ONI_URL))
        print("ONI descargado")


if __name__ == "__main__":
    main()
