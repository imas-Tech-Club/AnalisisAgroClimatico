"""Análisis histórico exploratorio sobre la tabla maestra (primera visualización).

Figuras en outputs/figures/<region>/:
  rinde_por_campania.png      rinde provincial de soja y maíz por campaña, coloreado por fase ENSO
  rinde_vs_tendencia_fase.png desvío del rinde respecto de la tendencia del departamento, por fase ENSO
  correlacion_mensual.png     correlación de cada variable mensual con ese desvío (qué mes informa más)
  ndvi_por_fase.png           curva media de NDVI en cultivos por fase ENSO

Uso:  AGRO_REGION=santa_fe uv run python src/06_exploracion.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
import modelo

COLOR = {"nino": "#c0392b", "neutro": "#8c8c8c", "nina": "#2e86c1"}
ETIQUETA = {"nino": "Niño", "neutro": "Neutro", "nina": "Niña"}
MESES = [config.NOMBRE_MES[m] for m in config.MESES_CAMPANA]
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def con_desvio(df: pd.DataFrame) -> pd.DataFrame:
    """Desvío % del rinde respecto de la tendencia lineal de su departamento (ajustada con todo)."""
    d = modelo.entrenables(df)
    d["tendencia"] = modelo.tendencia_lineal(d, d)
    d["desvio_pct"] = (d["rinde_real"] / d["tendencia"] - 1) * 100
    return d


def fig_rinde_campania(df, nombre):
    d = modelo.entrenables(df)
    d["prod"] = d["rinde_real"] * d["sembrada_ha"]  # ponderación aproximada por superficie
    g = d.groupby(["cultivo", "anio_siembra", "campania", "fase_enso"]).apply(
        lambda x: x["prod"].sum() / x["sembrada_ha"].sum(), include_groups=False).rename("rinde").reset_index()
    fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    for a, cult in zip(ax, ["soja", "maiz"]):
        x = g[g["cultivo"] == cult]
        a.bar(x["campania"], x["rinde"] / 1000, color=[COLOR[f] for f in x["fase_enso"]])
        a.set_ylabel("t/ha")
        a.set_title(f"{'Soja' if cult == 'soja' else 'Maíz'}: rinde medio de {nombre} por campaña (MAGyP)", loc="left")
    ax[1].tick_params(axis="x", rotation=60)
    ax[0].legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in COLOR.values()], ETIQUETA.values(),
                 frameon=False, ncol=3, loc="upper left")
    fig.tight_layout()
    fig.savefig(config.FIG / "rinde_por_campania.png", dpi=150)
    plt.close(fig)


def fig_desvio_fase(d):
    fig, ax = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    orden = ["nina", "neutro", "nino"]
    for a, cult in zip(ax, ["soja", "maiz"]):
        x = d[d["cultivo"] == cult]
        datos = [x[x["fase_enso"] == f]["desvio_pct"] for f in orden]
        bp = a.boxplot(datos, tick_labels=[ETIQUETA[f] for f in orden], showfliers=False, patch_artist=True, widths=.5)
        for caja, f in zip(bp["boxes"], orden):
            caja.set_facecolor(COLOR[f])
            caja.set_alpha(.45)
        rng = np.random.default_rng(0)
        for i, v in enumerate(datos):
            a.scatter(rng.normal(i + 1, .06, len(v)), v, s=4, color="#333", alpha=.25)
            a.annotate(f"mediana {v.median():+.0f}%\nn = {len(v)}", (i + 1, 58), ha="center", fontsize=8)
        a.axhline(0, color="#666", lw=.6)
        a.set_ylim(-95, 75)
        a.set_title(f"{'Soja' if cult == 'soja' else 'Maíz'}: rinde vs tendencia del depto, 2000/01-2024/25", loc="left")
    ax[0].set_ylabel("% sobre / bajo la tendencia")
    fig.tight_layout()
    fig.savefig(config.FIG / "rinde_vs_tendencia_fase.png", dpi=150)
    plt.close(fig)


def correlaciones(d) -> pd.DataFrame:
    filas = []
    for cult in ["soja", "maiz"]:
        x = d[d["cultivo"] == cult]
        for v in modelo.VARIABLES_MENSUALES:
            for k, mes in enumerate(MESES, start=1):
                col = f"{v}_mes_{k}"
                ok = x[[col, "desvio_pct"]].dropna()
                r = ok[col].corr(ok["desvio_pct"]) if len(ok) > 30 else np.nan
                filas.append({"cultivo": cult, "variable": v, "mes": mes, "k": k, "r": r, "n": len(ok)})
        ok = x[["oni", "desvio_pct"]].dropna()
        filas.append({"cultivo": cult, "variable": "oni", "mes": "campaña", "k": 0,
                      "r": ok["oni"].corr(ok["desvio_pct"]), "n": len(ok)})
    c = pd.DataFrame(filas)
    c.round(3).to_csv(config.PROC / "correlacion_variables_desvio.csv", index=False)
    return c


def fig_correlacion(c):
    fig, ax = plt.subplots(1, 2, figsize=(12, 3.4))
    for a, cult in zip(ax, ["soja", "maiz"]):
        m = c[(c["cultivo"] == cult) & (c["k"] > 0)].pivot(index="variable", columns="k", values="r")
        m = m.reindex(list(modelo.VARIABLES_MENSUALES))
        im = a.imshow(m.to_numpy(), cmap="RdBu", vmin=-.7, vmax=.7, aspect="auto")
        a.set_xticks(range(len(MESES)), MESES)
        a.set_yticks(range(len(m.index)), [s.replace("_", " ") for s in m.index] if a is ax[0] else [])
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                if not np.isnan(m.iat[i, j]):
                    a.text(j, i, f"{m.iat[i, j]:.2f}", ha="center", va="center", fontsize=7)
        r_oni = c[(c["cultivo"] == cult) & (c["variable"] == "oni")]["r"].iloc[0]
        a.set_title(f"{'Soja' if cult == 'soja' else 'Maíz'}: correlación con el desvío de rinde (ONI: r = {r_oni:.2f})",
                    loc="left", fontsize=9)
    fig.colorbar(im, ax=ax, shrink=.8, label="r de Pearson")
    fig.savefig(config.FIG / "correlacion_mensual.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_ndvi_fase(df):
    d = df[df["cultivo"] == "soja"]  # el NDVI es el mismo para ambos cultivos (máscara de cultivo genérica)
    d = d[d["anio_siembra"] <= 2024]
    cols = [f"ndvi_mes_{k}" for k in range(1, len(MESES) + 1)]
    fig, ax = plt.subplots(figsize=(7, 4))
    for f in ["nina", "neutro", "nino"]:
        x = d[d["fase_enso"] == f][cols]
        ax.plot(MESES, x.mean(), marker="o", ms=3, color=COLOR[f], label=f"{ETIQUETA[f]} ({x.dropna().shape[0]} filas)")
        ax.fill_between(MESES, x.quantile(.25), x.quantile(.75), color=COLOR[f], alpha=.12, lw=0)
    sequia = d[d["anio_siembra"] == 2022][cols].mean()
    ax.plot(MESES, sequia, ls="--", color="#7d5a00", label="2022/23 (sequía)")
    ax.set_ylabel("NDVI medio en tierras de cultivo")
    ax.set_title("NDVI de MODIS por fase ENSO (media y rango intercuartil)", loc="left")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(config.FIG / "ndvi_por_fase.png", dpi=150)
    plt.close(fig)


def main():
    nombre = config.REGIONES[config.REGION]["nombre"]
    df = modelo.cargar_tabla()
    d = con_desvio(df)
    fig_rinde_campania(df, nombre)
    fig_desvio_fase(d)
    c = correlaciones(d)
    fig_correlacion(c)
    fig_ndvi_fase(df)
    print(d.groupby(["cultivo", "fase_enso"])["desvio_pct"].agg(["median", "mean", "count"]).round(1).to_string())
    top = c[c["k"] > 0].assign(abs_r=lambda x: x["r"].abs()).sort_values("abs_r", ascending=False)
    print("Variables mensuales más correlacionadas con el desvío:\n",
          top.groupby("cultivo").head(5)[["cultivo", "variable", "mes", "r"]].to_string(index=False))


if __name__ == "__main__":
    main()
