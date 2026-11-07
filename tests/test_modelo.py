"""Pruebas del frente 4 con una tabla sintética chica (no necesitan descargar nada)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import modelo  # noqa: E402


@pytest.fixture
def tabla():
    rng = np.random.default_rng(0)
    filas = []
    for d in ["82001", "82002", "82003"]:
        for a in range(2000, 2020):
            for c, nivel in [("soja", 3000), ("maiz", 7000)]:
                ndvi = rng.uniform(.4, .8)
                filas.append({"depto_id": d, "departamento": d, "campania": f"{a}/{(a + 1) % 100:02d}",
                              "anio_siembra": a, "cultivo": c, "fase_enso": "neutro", "nino_fuerte": False,
                              "oni": 0.0, **{f"ndvi_mes_{k}": ndvi for k in range(1, 9)},
                              "rinde_real": nivel + 20 * (a - 2000) + 4000 * (ndvi - .6)})
    return pd.DataFrame(filas)


def test_tendencia_exacta_en_datos_lineales(tabla):
    t = tabla.assign(rinde_real=lambda x: 1000 + 50 * (x.anio_siembra - 2000))
    pred = modelo.validar(t, {"tendencia_lineal": modelo.tendencia_lineal}, esquema="loco")
    assert pred["error"].abs().max() < 1e-6


def test_promedio_historico_no_usa_la_campania_de_prueba(tabla):
    pred = modelo.validar(tabla, {"promedio_historico": modelo.promedio_historico}, esquema="loco")
    fila = pred.iloc[0]
    esperado = tabla[(tabla.depto_id == fila.depto_id) & (tabla.cultivo == fila.cultivo)
                     & (tabla.campania != fila.campania)]["rinde_real"].mean()
    assert fila["pred"] == pytest.approx(esperado)


def test_temporal_solo_entrena_con_el_pasado(tabla):
    vistos = []

    def espia(train, test):
        vistos.append((train.anio_siembra.max(), test.anio_siembra.min()))
        return np.zeros(len(test))

    modelo.validar(tabla, {"espia": espia}, esquema="temporal", primera_temporal=2010)
    assert vistos and all(max_train < anio_test for max_train, anio_test in vistos)


def test_xgboost_aprende_la_senal_del_ndvi(tabla):
    feats = [f"ndvi_mes_{k}" for k in range(1, 9)]
    pred = modelo.validar(tabla, {"tendencia_lineal": modelo.tendencia_lineal,
                                  "xgboost": modelo.xgboost_sobre_tendencia(feats)}, esquema="loco")
    m = modelo.metricas(pred)["mae_kg_ha"]
    assert m[("xgboost", "soja")] < m[("tendencia_lineal", "soja")]
