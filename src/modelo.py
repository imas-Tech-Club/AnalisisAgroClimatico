"""Frente 4 · Modelo de machine learning: líneas base, validación por campaña, XGBoost y métricas.

Se usa como librería desde los notebooks (`import modelo`) o por línea de comandos:

    AGRO_REGION=santa_fe uv run python src/modelo.py

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

import warnings
from typing import Callable

import numpy as np
import pandas as pd

import config

warnings.filterwarnings("ignore", category=np.exceptions.RankWarning)

OBJETIVO = "rinde_real"
GRUPO = "campania"
VARIABLES_MENSUALES = ("ndvi", "lluvia", "temp", "humedad_suelo")
MESES_CORTE = {"dic": 4, "ene": 5, "feb": 6, "mar": 7, "abr": 8}  # hasta qué mes_N hay datos al predecir


# ------------------------------------------------------------------ datos
def cargar_tabla(region: str = config.REGION) -> pd.DataFrame:
    ruta = config.ROOT / "data" / "processed" / region / "tabla_maestra.csv"
    return pd.read_csv(ruta, dtype={"depto_id": str})


def entrenables(df: pd.DataFrame) -> pd.DataFrame:
    """Filas con rinde publicado (las de 2025/26 y 2026/27 quedan para predecir)."""
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
    lluvia, temperatura, humedad del suelo, ONI). Predicción final = base + desvío predicho.
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


def comparar_con_base(m: pd.DataFrame, base: str = "tendencia_lineal") -> pd.DataFrame:
    """Agrega cuánto mejora cada modelo el MAE de la línea base (% positivo = mejor)."""
    m = m.copy()
    ref = m.xs(base, level="modelo")["mae_kg_ha"]
    niveles = [n for n in m.index.names if n != "modelo"]
    claves = m.index.droplevel("modelo") if niveles else None
    m["mejora_vs_base_pct"] = ((1 - m["mae_kg_ha"].to_numpy() / ref.reindex(claves).to_numpy()) * 100).round(1)
    return m


def modelos_estandar(hasta_mes: int = 8) -> dict[str, Callable]:
    feats = columnas_clima_satelite(hasta_mes) + ["oni"]
    return {
        "promedio_historico": promedio_historico,
        "tendencia_lineal": tendencia_lineal,
        "xgboost": xgboost_sobre_tendencia(feats, base="tendencia"),
        "xgboost_sobre_promedio": xgboost_sobre_tendencia(feats, base="promedio"),
    }


def main():
    df = cargar_tabla()
    tablas = []
    for esquema in ("loco", "temporal"):
        pred = validar(df, modelos_estandar(), esquema)
        pred.to_csv(config.PROC / f"predicciones_{esquema}.csv", index=False)
        for por in [("modelo", "cultivo"), ("modelo", "cultivo", "fase_enso")]:
            m = comparar_con_base(metricas(pred, por)).reset_index()
            m.insert(0, "esquema", esquema)
            tablas.append(m)
    res = pd.concat(tablas, ignore_index=True)
    res.to_csv(config.PROC / "metricas_modelos.csv", index=False)
    print(res[res["fase_enso"].isna()].drop(columns="fase_enso").to_string(index=False))


if __name__ == "__main__":
    main()
