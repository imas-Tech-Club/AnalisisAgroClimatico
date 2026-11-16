"""Frente 4 · Modelo de machine learning: líneas base, validación por campaña, XGBoost y métricas.

Se usa como librería desde los notebooks (`import modelo`) o por línea de comandos:

    uv run python src/modelo.py

Lee `data/processed/<region>/tabla_maestra.csv` (región por la variable AGRO_REGION, por defecto
santa_fe) y deja ahí mismo las predicciones y las métricas.

Regla de oro: nunca mezclar filas de la misma campaña entre entrenamiento y prueba.
Todo lo que se "aprende" (promedios, tendencias, el XGBoost) se ajusta dentro de cada
pliegue, solo con las campañas de entrenamiento.

Esquemas de validación:
  * "loco"     (leave-one-campaign-out, el del plan): se esconde una campaña y se entrena con
               todas las demás, también las posteriores.
  * "temporal" (origen móvil): para predecir la campaña t se entrena solo con campañas < t.
               Es lo que pasa de verdad al predecir 2026/27; sirve de control porque la
               validación "loco" le da ventaja a la tendencia (interpola en vez de extrapolar).
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=np.exceptions.RankWarning)

OBJETIVO = "rinde_real"
GRUPO = "campania"
VARIABLES_MENSUALES = ("ndvi", "lluvia", "temp", "humedad_suelo")
# Hasta qué mes_N hay datos al predecir. "nov" es el corte de la entrega del 20/12/2026: los datos de
# noviembre están a principios de diciembre, y los de diciembre recién en enero.
MESES_CORTE = {"nov": 3, "dic": 4, "ene": 5, "feb": 6, "mar": 7, "abr": 8}
BASE_XGBOOST = "promedio"  # base sobre la que aprende el XGBoost por defecto (src/experimento_base.py)

ROOT = Path(__file__).resolve().parents[1]
REGION = os.environ.get("AGRO_REGION", "santa_fe")


def carpeta(region: str = REGION) -> Path:
    """Carpeta con la tabla maestra de la región y los resultados del modelo."""
    return ROOT / "data" / "processed" / region


# ------------------------------------------------------------------ datos
def cargar_tabla(region: str = REGION) -> pd.DataFrame:
    return pd.read_csv(carpeta(region) / "tabla_maestra.csv", dtype={"depto_id": str})


def entrenables(df: pd.DataFrame) -> pd.DataFrame:
    """Filas con rinde publicado (la campaña en curso, 2026/27, queda para predecir).

    El maíz 2008/09 de cinco departamentos con pérdida total (cosechada = 0) también queda afuera:
    el rinde es producción / superficie cosechada y con cosechada 0 no está definido.
    """
    return df[df[OBJETIVO].notna()].copy()


def columnas_clima_satelite(hasta_mes: int = 8, variables=VARIABLES_MENSUALES) -> list[str]:
    """Columnas mensuales disponibles si se predice con datos hasta mes_{hasta_mes}."""
    return [f"{v}_mes_{k}" for v in variables for k in range(1, hasta_mes + 1)]


# ------------------------------------------------------------------ líneas base (tarea 4.2)
def promedio_historico(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Promedio del rinde del departamento en las campañas de entrenamiento."""
    prom = train.groupby(["depto_id", "cultivo"])[OBJETIVO].mean()
    general = train.groupby("cultivo")[OBJETIVO].mean()
    idx = pd.MultiIndex.from_frame(test[["depto_id", "cultivo"]])
    return prom.reindex(idx).fillna(test["cultivo"].map(general).set_axis(idx)).to_numpy()


def _tendencias(train: pd.DataFrame, min_puntos: int = 5) -> dict:
    coef = {}
    for clave, g in train.groupby(["depto_id", "cultivo"]):
        if len(g) >= min_puntos:
            coef[clave] = np.polyfit(g["anio_siembra"], g[OBJETIVO], 1)
    return coef


def tendencia_lineal(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Recta rinde ~ año ajustada por departamento con las campañas de entrenamiento."""
    coef = _tendencias(train)
    prom = promedio_historico(train, test)
    pred = [np.polyval(coef[(d, c)], a) if (d, c) in coef else p
            for d, c, a, p in zip(test["depto_id"], test["cultivo"], test["anio_siembra"], prom)]
    return np.asarray(pred, dtype=float)


# ------------------------------------------------------------------ XGBoost (tarea 4.3)
def xgboost_sobre_tendencia(features: list[str], base: str = "tendencia", **params) -> Callable:
    """XGBoost que aprende el desvío respecto de una línea base del departamento.

    Cada departamento tiene su nivel de rinde (y una tendencia por tecnología); eso ya lo captura
    la línea base. El árbol se concentra en lo que la base no explica: el año climático (NDVI,
    lluvia, temperatura, humedad del suelo y, si va en `features`, el ONI). Predicción final = base + desvío.
    `base`: "tendencia" (recta por departamento) o "promedio" (promedio histórico del departamento).
    Un modelo por cultivo.
    """
    from xgboost import XGBRegressor

    p = dict(n_estimators=400, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
             min_child_weight=5, reg_lambda=1.0, n_jobs=4, random_state=0)
    p.update(params)

    def ajustar_y_predecir(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
        pred = np.full(len(test), np.nan)
        for cult in test["cultivo"].unique():
            tr, te = train[train["cultivo"] == cult], test["cultivo"] == cult
            f_base = tendencia_lineal if base == "tendencia" else promedio_historico
            base_tr = f_base(tr, tr)
            base_te = f_base(tr, test[te])
            m = XGBRegressor(**p)
            m.fit(tr[features], tr[OBJETIVO] - base_tr)
            pred[te.to_numpy()] = base_te + m.predict(test.loc[te, features])
        return pred

    ajustar_y_predecir.__name__ = f"xgboost_{base}"
    return ajustar_y_predecir


# ------------------------------------------------------------------ validación (tarea 4.1)
def validar(df: pd.DataFrame, modelos: dict[str, Callable], esquema: str = "loco",
            primera_temporal: int = 2008) -> pd.DataFrame:
    """Devuelve una fila por (modelo, departamento, campaña, cultivo) con la predicción fuera de muestra."""
    df = entrenables(df)
    salidas = []
    for camp in sorted(df[GRUPO].unique()):
        test = df[df[GRUPO] == camp]
        anio = int(test["anio_siembra"].iloc[0])
        if esquema == "loco":
            train = df[df[GRUPO] != camp]
        elif esquema == "temporal":
            if anio < primera_temporal:
                continue
            train = df[df["anio_siembra"] < anio]
        else:
            raise ValueError(esquema)
        assert not set(train[GRUPO]) & set(test[GRUPO]), "regla de oro: campaña en train y test"
        for nombre, f in modelos.items():
            out = test[["depto_id", "departamento", "campania", "anio_siembra", "cultivo", "fase_enso",
                        "nino_fuerte", OBJETIVO]].copy()
            out["modelo"], out["pred"] = nombre, f(train, test)
            salidas.append(out)
    res = pd.concat(salidas, ignore_index=True)
    res["error"] = res["pred"] - res[OBJETIVO]
    res["esquema"] = esquema
    return res


# ------------------------------------------------------------------ métricas (tarea 4.4)
def metricas(pred: pd.DataFrame, por=("modelo", "cultivo")) -> pd.DataFrame:
    """MAE (kg/ha), error porcentual medio absoluto (%), R² y sesgo, por grupo."""
    def calc(g):
        y, e = g[OBJETIVO], g["error"]
        ss_res, ss_tot = (e ** 2).sum(), ((y - y.mean()) ** 2).sum()
        return pd.Series({
            "mae_kg_ha": e.abs().mean(),
            "error_pct": (e.abs() / y).mean() * 100,
            "r2": 1 - ss_res / ss_tot if ss_tot > 0 else np.nan,
            "sesgo_kg_ha": e.mean(),
            "n": len(g),
        })
    return pred.groupby(list(por)).apply(calc, include_groups=False).round(3)


def comparar_con_base(m: pd.DataFrame, base: str = "promedio_historico") -> pd.DataFrame:
    """Agrega cuánto mejora cada modelo el MAE de la línea base (% positivo = mejor).

    Por defecto contra el promedio histórico, que es la línea base más difícil de superar en Santa Fe y
    Entre Ríos (la tendencia lineal es peor en la validación temporal).
    """
    m = m.copy()
    ref = m.xs(base, level="modelo")["mae_kg_ha"]
    niveles = [n for n in m.index.names if n != "modelo"]
    claves = m.index.droplevel("modelo") if niveles else None
    m["mejora_vs_base_pct"] = ((1 - m["mae_kg_ha"].to_numpy() / ref.reindex(claves).to_numpy()) * 100).round(1)
    return m


def modelos_estandar(hasta_mes: int = 8) -> dict[str, Callable]:
    """Líneas base, XGBoost por defecto y dos variantes de comparación.

    Desde el 16/11/2026 el XGBoost por defecto aprende sobre el promedio histórico (src/experimento_base.py)
    y no usa el ONI: en la validación temporal no mejora el error, y en 2025/26 (Niña débil con buena
    cosecha) y en los Niños fuertes empujó la predicción en la dirección equivocada (src/experimento_oni.py).
    El ENSO sigue entrando por lo que se observa en la campaña: lluvia, humedad del suelo y NDVI.
    `xgboost_sobre_tendencia` y `xgboost_con_oni` quedan para comparar.
    """
    feats = columnas_clima_satelite(hasta_mes)
    return {
        "promedio_historico": promedio_historico,
        "tendencia_lineal": tendencia_lineal,
        "xgboost": xgboost_sobre_tendencia(feats, base=BASE_XGBOOST),
        "xgboost_sobre_tendencia": xgboost_sobre_tendencia(feats, base="tendencia"),
        "xgboost_con_oni": xgboost_sobre_tendencia(feats + ["oni"], base=BASE_XGBOOST),
    }


# ------------------------------------------------------------------ predicción de una campaña
def predecir(df: pd.DataFrame, campania: str, modelos: dict[str, Callable], hasta_mes: int = 8) -> pd.DataFrame:
    """Predice una campaña (por ejemplo, la campaña en curso) entrenando con todas las anteriores.

    Es lo mismo que el pliegue de esa campaña en la validación `temporal`: solo entra lo publicado antes.
    `hasta_mes` no filtra nada por sí solo (las columnas las eligen los modelos, ver `modelos_estandar`):
    se usa para medir cuántos datos del corte le faltan a la campaña y dejarlo en la salida.
    """
    test = df[df[GRUPO] == campania]
    assert len(test), f"no hay filas de la campaña {campania}"
    anio = int(test["anio_siembra"].iloc[0])
    train = entrenables(df)
    train = train[train["anio_siembra"] < anio]
    assert not set(train[GRUPO]) & set(test[GRUPO]), "regla de oro: campaña en train y test"
    cols_corte = [c for c in columnas_clima_satelite(hasta_mes) if c in test.columns]
    faltan = test[cols_corte].isna().mean(axis=1).mul(100).round(1)
    info = [c for c in ["depto_id", "departamento", "campania", "anio_siembra", "cultivo", "fase_enso", "oni",
                        "sembrada_ha"] if c in test.columns]
    salidas = []
    for nombre, f in modelos.items():
        out = test[info].copy()
        out["modelo"], out["pred"] = nombre, f(train, test)
        out["hasta_mes"], out["faltan_datos_pct"] = hasta_mes, faltan
        salidas.append(out)
    return pd.concat(salidas, ignore_index=True)


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Validación de los modelos o predicción de una campaña.")
    ap.add_argument("--predecir", metavar="CAMPAÑA", help='campaña a predecir, p. ej. "2026/27"')
    ap.add_argument("--corte", default="abr", choices=list(MESES_CORTE),
                    help="último mes con datos al predecir (por defecto abr)")
    a = ap.parse_args()
    df = cargar_tabla()

    if a.predecir:
        k = MESES_CORTE[a.corte]
        p = predecir(df, a.predecir, modelos_estandar(k), hasta_mes=k)
        destino = carpeta() / f"prediccion_{a.predecir.replace('/', '-')}_{a.corte}.csv"
        p.to_csv(destino, index=False)
        faltan = p.drop_duplicates(["depto_id", "cultivo"])["faltan_datos_pct"].mean()
        if faltan > 0:
            print(f"OJO: a la campaña {a.predecir} le falta el {faltan:.0f} % de los datos hasta {a.corte}. "
                  "La predicción no vale hasta completar la tabla maestra (src/03 a 05).")
        resumen = p.pivot_table(index="modelo", columns="cultivo", values="pred").round(0)
        print(f"{a.predecir}, corte {a.corte}: rinde medio predicho por modelo (kg/ha)\n{resumen}\n-> {destino}")
        return

    tablas = []
    for esquema in ("loco", "temporal"):
        pred = validar(df, modelos_estandar(), esquema)
        pred.to_csv(carpeta() / f"predicciones_{esquema}.csv", index=False)
        for por in [("modelo", "cultivo"), ("modelo", "cultivo", "fase_enso")]:
            m = comparar_con_base(metricas(pred, por)).reset_index()
            m.insert(0, "esquema", esquema)
            tablas.append(m)
    res = pd.concat(tablas, ignore_index=True)
    res.to_csv(carpeta() / "metricas_modelos.csv", index=False)
    print(res[res["fase_enso"].isna()].drop(columns="fase_enso").to_string(index=False))


if __name__ == "__main__":
    main()
