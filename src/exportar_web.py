"""Arma los datos de la demo web (web/datos.js) a partir de las salidas del modelo.

La página es estática: no hay servidor. Todo lo que muestra sale de este archivo, que define
`window.DATOS`. Se vuelve a correr cada vez que cambia el modelo o la tabla maestra:

    uv run --group datos python src/exportar_web.py

Lee, por región: la tabla maestra (rinde real, fase ENSO), las predicciones de la validación temporal
(cada campaña predicha solo con las anteriores), las métricas, y la predicción de 2026/27 si ya existe
(data/processed/<region>/prediccion_2026-27_<corte>.csv, de `src/modelo.py --predecir`). Los polígonos
salen del IGN (data/raw/ign_departamentos.geojson, de src/01_descargas.py): se simplifican y se
proyectan acá a coordenadas de SVG, así la página no necesita ninguna librería de mapas.
"""
from __future__ import annotations

import json
import math
from datetime import date

import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon

import config
import modelo

REGIONES = {"santa_fe": "Santa Fe", "entre_rios": "Entre Ríos"}
CULTIVOS = ("soja", "maiz")
CAMPANIA_EN_CURSO = "2026/27"
DESTINO = modelo.ROOT / "web" / "datos.js"
ANCHO_SVG = 520  # ancho del viewBox del mapa
TOLERANCIA = 0.004  # simplificación de los polígonos, en grados (~400 m)


# ------------------------------------------------------------------ mapa
def _proyectar(deps):
    minx, miny, maxx, maxy = deps.total_bounds
    k = math.cos(math.radians((miny + maxy) / 2))
    escala = ANCHO_SVG / ((maxx - minx) * k)
    alto = (maxy - miny) * escala

    def xy(lon, lat):
        return (lon - minx) * k * escala, (maxy - lat) * escala

    return xy, round(alto, 1)


def _path(geom, xy) -> str:
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    partes = []
    for p in polys:
        for anillo in [p.exterior, *p.interiors]:
            pts = [xy(x, y) for x, y in anillo.coords]
            partes.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    return "".join(partes)


def mapa() -> dict:
    deps = pd.concat([config.departamentos(r) for r in REGIONES], ignore_index=True)
    xy, alto = _proyectar(deps)
    deptos = [{"id": r.id, "nombre": r.departamento, "provincia": r.provincia,
               "d": _path(r.geometry.simplify(TOLERANCIA, preserve_topology=True), xy)}
              for r in deps.itertuples()]
    provs = deps.dissolve(by="provincia")
    provincias = []
    for nombre, r in provs.iterrows():
        g = r.geometry.simplify(TOLERANCIA, preserve_topology=True)
        c = g.representative_point()
        x, y = xy(c.x, c.y)
        provincias.append({"nombre": nombre, "d": _path(g, xy), "x": round(x, 1), "y": round(y, 1)})
    return {"ancho": ANCHO_SVG, "alto": alto, "departamentos": deptos, "provincias": provincias}


# ------------------------------------------------------------------ datos del modelo
def _num(v, nd=0):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), nd)


def series(region: str, campanias: list[str]) -> tuple[dict, dict]:
    tabla = modelo.cargar_tabla(region)
    pred = pd.read_csv(modelo.carpeta(region) / "predicciones_temporal.csv", dtype={"depto_id": str})
    pred = pred[pred.modelo.isin(["xgboost", "promedio_historico"])]
    pv = pred.pivot_table(index=["depto_id", "cultivo", "campania"], columns="modelo", values="pred")
    salida, resumen = {}, {}
    for (depto, cult), g in tabla.groupby(["depto_id", "cultivo"]):
        g = g.set_index("campania").reindex(campanias)
        if g["rinde_real"].notna().sum() == 0:
            continue  # sin rinde (Islas del Ibicuy)
        try:
            p = pv.loc[(depto, cult)].reindex(campanias)
        except KeyError:  # departamento sin predicciones
            p = pd.DataFrame(np.nan, index=campanias, columns=["xgboost", "promedio_historico"])
        modelo_, prom = p["xgboost"], p["promedio_historico"]
        clave = f"{depto}|{cult}"
        salida[clave] = {"real": [_num(v) for v in g["rinde_real"]],
                         "modelo": [_num(v) for v in modelo_],
                         "promedio": [_num(v) for v in prom]}
        ok = g["rinde_real"].notna() & modelo_.notna()
        real = g["rinde_real"][ok]
        resumen[clave] = {
            "error_modelo_pct": _num(((modelo_[ok] - real).abs() / real).mean() * 100, 1),
            "error_promedio_pct": _num(((prom[ok] - real).abs() / real).mean() * 100, 1),
            "campanias_probadas": int(ok.sum()),
            "rinde_medio": _num(g["rinde_real"].mean()),
        }
    return salida, resumen


def metricas() -> list[dict]:
    filas = []
    for region, nombre in REGIONES.items():
        m = pd.read_csv(modelo.carpeta(region) / "metricas_modelos.csv")
        m = m[m.fase_enso.isna() & m.modelo.isin(["promedio_historico", "tendencia_lineal", "xgboost"])]
        for r in m.itertuples():
            filas.append({"provincia": nombre, "cultivo": r.cultivo, "esquema": r.esquema, "modelo": r.modelo,
                          "error_pct": _num(r.error_pct, 1), "mae_kg_ha": _num(r.mae_kg_ha)})
    return filas


def corte_noviembre() -> list[dict]:
    """Error del modelo con datos hasta noviembre contra el promedio histórico (validación temporal)."""
    eb = pd.read_csv(modelo.ROOT / "data" / "processed" / "experimento_base.csv")
    eb = eb[(eb.variante == modelo.BASE_XGBOOST) & (eb.esquema == "temporal") & (eb.corte == "nov")]
    filas = []
    for region, nombre in REGIONES.items():
        m = pd.read_csv(modelo.carpeta(region) / "metricas_modelos.csv")
        base = m[(m.esquema == "temporal") & (m.modelo == "promedio_historico") & m.fase_enso.isna()]
        for cult in CULTIVOS:
            e = eb[(eb.region == region) & (eb.cultivo == cult)]
            mae_nov = (e.mae_kg_ha * e.n).sum() / e.n.sum()
            mae_base = base[base.cultivo == cult].mae_kg_ha.iloc[0]
            filas.append({"provincia": nombre, "cultivo": cult, "cambio_pct": _num((mae_nov / mae_base - 1) * 100, 1)})
    return filas


def prediccion_en_curso() -> dict | None:
    """La predicción de 2026/27 si ya se corrió `src/modelo.py --predecir` (se usa el corte más tardío)."""
    orden = list(modelo.MESES_CORTE)
    encontrada = None
    for corte in reversed(orden):
        archivos = {r: modelo.carpeta(r) / f"prediccion_{CAMPANIA_EN_CURSO.replace('/', '-')}_{corte}.csv"
                    for r in REGIONES}
        if all(a.exists() for a in archivos.values()):
            encontrada = (corte, archivos)
            break
    if encontrada is None:
        return None
    corte, archivos = encontrada
    p = pd.concat([pd.read_csv(a, dtype={"depto_id": str}) for a in archivos.values()])
    if p["faltan_datos_pct"].max() > 0:
        return None  # todavía faltan datos del corte: no se publica
    pv = p.pivot_table(index=["depto_id", "cultivo"], columns="modelo", values="pred")
    return {"corte": corte, "valores": {f"{d}|{c}": {"modelo": _num(r["xgboost"]),
                                                       "promedio": _num(r["promedio_historico"]),
                                                       "con_oni": _num(r.get("xgboost_con_oni"))}
                                         for (d, c), r in pv.iterrows()}}


def main():
    tabla_sf = modelo.cargar_tabla("santa_fe")
    campanias = sorted(c for c in tabla_sf.campania.unique() if c != CAMPANIA_EN_CURSO)
    fases = tabla_sf.drop_duplicates("campania").set_index("campania")
    datos = {
        "generado": date.today().isoformat(),
        "campanias": campanias,
        "en_curso": CAMPANIA_EN_CURSO,
        "fase": {c: fases.loc[c, "fase_enso"] for c in campanias + [CAMPANIA_EN_CURSO]},
        "oni": {c: _num(fases.loc[c, "oni"], 2) for c in campanias + [CAMPANIA_EN_CURSO]},
        "mapa": mapa(),
        "series": {},
        "resumen": {},
        "metricas": metricas(),
        "corte_noviembre": corte_noviembre(),
        "prediccion": prediccion_en_curso(),
    }
    for region in REGIONES:
        s, r = series(region, campanias)
        datos["series"].update(s)
        datos["resumen"].update(r)
    # departamento que se muestra al abrir: el de más soja sembrada en la última campaña
    ult = pd.concat([modelo.cargar_tabla(r) for r in REGIONES])
    ult = ult[(ult.campania == campanias[-1]) & (ult.cultivo == "soja")]
    datos["inicial"] = ult.sort_values("sembrada_ha", ascending=False).depto_id.iloc[0]

    DESTINO.parent.mkdir(exist_ok=True)
    js = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    DESTINO.write_text(f"// Generado por src/exportar_web.py el {datos['generado']}. No editar a mano.\n"
                       f"window.DATOS = {js};\n", encoding="utf-8")
    print(f"{DESTINO.relative_to(modelo.ROOT)}: {DESTINO.stat().st_size / 1024:.0f} KB · "
          f"{len(datos['mapa']['departamentos'])} departamentos · {len(datos['series'])} series · "
          f"predicción 2026/27: {'sí, corte ' + datos['prediccion']['corte'] if datos['prediccion'] else 'todavía no'}")


if __name__ == "__main__":
    main()
