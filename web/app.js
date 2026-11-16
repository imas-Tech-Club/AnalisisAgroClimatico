/* Predictor de rinde · demo web. Sin dependencias: lee window.DATOS (web/datos.js, de src/exportar_web.py). */
"use strict";

const D = window.DATOS;
const $ = (sel) => document.querySelector(sel);
const SVG = "http://www.w3.org/2000/svg";

const NOMBRE_CULTIVO = { soja: "soja", maiz: "maíz" };
const NOMBRE_FASE = { nino: "Niño", nina: "Niña", neutro: "Neutro" };
const ULTIMA = D.campanias[D.campanias.length - 1];
const fmtEntero = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });
const fmtDecimal = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const kg = (v) => (v == null ? "sin dato" : `${fmtEntero.format(v)} kg/ha`);
const pct = (v) => (v == null ? "sin dato" : `${fmtDecimal.format(v)} %`);

const deptos = new Map(D.mapa.departamentos.map((d) => [d.id, d]));
const estado = { cultivo: "soja", metrica: "rinde", depto: null };

function el(tag, attrs = {}, texto) {
  const ns = ["svg", "g", "path", "rect", "line", "circle", "text"].includes(tag) ? SVG : null;
  const e = ns ? document.createElementNS(ns, tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (texto != null) e.textContent = texto;
  return e;
}

const clave = (id, cultivo = estado.cultivo) => `${id}|${cultivo}`;
const tieneDatos = (id) => Boolean(D.series[clave(id)]);

// ------------------------------------------------------------------ métricas del mapa
const METRICAS = {
  rinde: {
    opcion: `Rinde ${ULTIMA}`,
    titulo: () => `Rinde ${ULTIMA} de ${NOMBRE_CULTIVO[estado.cultivo]}, en kg/ha`,
    valor: (id) => { const s = D.series[clave(id)]; return s ? s.real[s.real.length - 1] : null; },
    formato: kg,
  },
  error: {
    opcion: "Error del modelo",
    titulo: () => `Error del modelo con ${NOMBRE_CULTIVO[estado.cultivo]}: más oscuro, más error`,
    valor: (id) => D.resumen[clave(id)]?.error_modelo_pct ?? null,
    formato: pct,
  },
  estimacion: {
    opcion: D.prediccion ? `Estimación ${D.en_curso}` : `Estimación ${D.en_curso} (sale en diciembre)`,
    titulo: () => `Estimación ${D.en_curso} de ${NOMBRE_CULTIVO[estado.cultivo]}, en kg/ha`,
    valor: (id) => D.prediccion?.valores[clave(id)]?.modelo ?? null,
    formato: kg,
    deshabilitada: !D.prediccion,
  },
};
const CLASES = ["--r1", "--r2", "--r3", "--r4", "--r5", "--r6"];

// ------------------------------------------------------------------ mapa
const mapaSvg = $("#mapa-svg");
const mapaTooltip = $("#mapa-tooltip");
const paths = new Map();

function armarMapa() {
  mapaSvg.setAttribute("viewBox", `0 0 ${D.mapa.ancho} ${D.mapa.alto}`);
  const gDeptos = el("g");
  for (const d of D.mapa.departamentos) {
    const p = el("path", { d: d.d, class: "depto-path", "data-id": d.id, tabindex: "0", role: "button" });
    p.addEventListener("click", () => elegir(d.id));
    p.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); elegir(d.id); } });
    p.addEventListener("pointermove", (e) => mostrarTooltipMapa(d.id, e));
    p.addEventListener("pointerleave", () => { mapaTooltip.hidden = true; });
    p.addEventListener("focus", () => mostrarTooltipMapa(d.id));
    p.addEventListener("blur", () => { mapaTooltip.hidden = true; });
    paths.set(d.id, p);
    gDeptos.append(p);
  }
  const gProv = el("g");
  for (const p of D.mapa.provincias) {
    gProv.append(el("path", { d: p.d, class: "provincia-borde" }));
  }
  for (const p of D.mapa.provincias) {
    gProv.append(el("text", { x: p.x, y: p.y, class: "provincia-nombre", "text-anchor": "middle" }, p.nombre));
  }
  mapaSvg.append(gDeptos, gProv);
}

function mostrarTooltipMapa(id, evento) {
  const d = deptos.get(id);
  const m = METRICAS[estado.metrica];
  const v = tieneDatos(id) ? m.valor(id) : null;
  mapaTooltip.replaceChildren(
    el("div", { class: "tooltip__titulo" }, `${d.nombre}, ${d.provincia}`),
    el("b", {}, tieneDatos(id) ? m.formato(v) : "Sin datos de rinde"),
  );
  mapaTooltip.hidden = false;
  const caja = mapaSvg.parentElement.getBoundingClientRect();
  let x, y;
  if (evento) { x = evento.clientX - caja.left; y = evento.clientY - caja.top; }
  else { const b = paths.get(id).getBoundingClientRect(); x = b.left + b.width / 2 - caja.left; y = b.top + b.height / 2 - caja.top; }
  const ancho = mapaTooltip.offsetWidth;
  mapaTooltip.style.left = `${Math.min(Math.max(0, x + 14), caja.width - ancho)}px`;
  mapaTooltip.style.top = `${Math.max(0, y - mapaTooltip.offsetHeight - 10)}px`;
}

function pintarMapa() {
  const m = METRICAS[estado.metrica];
  $("#mapa-titulo").textContent = m.titulo();
  const valores = [...deptos.keys()].filter(tieneDatos).map(m.valor).filter((v) => v != null);
  const min = Math.min(...valores), max = Math.max(...valores);
  const clase = (v) => Math.min(CLASES.length - 1, Math.floor(((v - min) / (max - min || 1)) * CLASES.length));
  for (const [id, p] of paths) {
    const d = deptos.get(id);
    const v = tieneDatos(id) ? m.valor(id) : null;
    p.classList.toggle("sin-datos", v == null);
    p.style.fill = v == null ? "var(--sin-datos)" : `var(${CLASES[clase(v)]})`;
    p.setAttribute("aria-label", `${d.nombre}, ${d.provincia}: ${v == null ? "sin datos" : m.formato(v)}`);
    p.classList.toggle("elegido", id === estado.depto);
  }
  const elegido = paths.get(estado.depto);
  if (elegido) elegido.parentNode.append(elegido); // arriba de los vecinos, para que se vea el borde

  const leyenda = $("#leyenda-mapa");
  const escala = el("div", { class: "leyenda-mapa__escala", "aria-hidden": "true" });
  for (const c of CLASES) { const s = el("span"); s.style.background = `var(${c})`; escala.append(s); }
  const extremos = el("div", { class: "leyenda-mapa__extremos" });
  extremos.append(el("span", {}, m.formato(min)), el("span", {}, m.formato(max)));
  const sin = el("div", { class: "leyenda-mapa__sin" });
  sin.append(el("i"), el("span", {}, "Sin datos de rinde (Islas del Ibicuy)"));
  leyenda.replaceChildren(escala, extremos, sin);
}

// ------------------------------------------------------------------ panel del departamento
function cifra(titulo, valor, detalle) {
  const div = el("div");
  const dd = el("dd", {}, valor);
  if (detalle) dd.append(el("small", {}, detalle));
  div.append(el("dt", {}, titulo), dd);
  return div;
}

function pintarDepto() {
  const id = estado.depto;
  const d = deptos.get(id);
  const k = clave(id);
  const s = D.series[k];
  const r = D.resumen[k];
  $("#depto-provincia").textContent = d.provincia;
  $("#depto-nombre").textContent = d.nombre;
  $("#departamento").value = id;
  document.title = `${d.nombre}: Predictor de rinde`;

  const cifras = $("#cifras");
  if (!s) {
    cifras.replaceChildren(cifra("Rinde", "Sin datos", "El Ministerio de Agricultura no publica rinde de soja ni maíz para este departamento."));
    $("#grafico").replaceChildren();
    $("#leyenda-grafico").replaceChildren();
    $("#grafico-titulo").textContent = "";
    $("#tabla-campanias").replaceChildren();
    pintarEnCurso(null);
    return;
  }
  const ultimo = s.real[s.real.length - 1];
  const diferencia = r.error_promedio_pct - r.error_modelo_pct;
  cifras.replaceChildren(
    cifra(`Rinde ${ULTIMA}`, kg(ultimo),
      `${fmtDecimal.format(ultimo / 100)} qq/ha. El promedio desde ${D.campanias[0]} es de ${kg(r.rinde_medio)}.`),
    cifra("Error del modelo acá", pct(r.error_modelo_pct),
      `Promedio de las ${r.campanias_probadas} campañas que se probaron.`),
    cifra("Error sin modelo", pct(r.error_promedio_pct),
      diferencia >= 0
        ? `Usando el promedio de las campañas anteriores. El modelo mejora ${fmtDecimal.format(diferencia)} puntos.`
        : `Usando el promedio de las campañas anteriores. Acá el modelo empeora ${fmtDecimal.format(-diferencia)} puntos.`),
  );
  $("#grafico-titulo").textContent = `Rinde de ${NOMBRE_CULTIVO[estado.cultivo]} por campaña, en kg/ha`;
  pintarLeyendaGrafico();
  dibujarGrafico(s);
  pintarTabla(s);
  pintarEnCurso(k);
}

function pintarLeyendaGrafico() {
  const items = [
    ["var(--serie-real)", "Rinde oficial", ""],
    ["var(--serie-modelo)", "Predicción del modelo", ""],
    ["var(--serie-promedio)", "Promedio de las campañas anteriores", ""],
    ["var(--nino)", "Año Niño", "banda"],
  ];
  $("#leyenda-grafico").replaceChildren(...items.map(([color, texto, tipo]) => {
    const li = el("li");
    const i = el("i", tipo ? { class: tipo } : {});
    i.style.background = color;
    li.append(i, el("span", {}, texto));
    return li;
  }));
}

function pintarTabla(s) {
  const t = $("#tabla-campanias");
  const thead = el("thead");
  const fila = el("tr");
  for (const h of ["Campaña", "Fase", "Rinde oficial (kg/ha)", "Predicción del modelo", "Promedio de campañas anteriores"]) {
    fila.append(el("th", { scope: "col" }, h));
  }
  thead.append(fila);
  const tbody = el("tbody");
  for (let i = D.campanias.length - 1; i >= 0; i--) {
    const c = D.campanias[i];
    const tr = el("tr");
    tr.append(el("th", { scope: "row" }, c), el("td", {}, NOMBRE_FASE[D.fase[c]]));
    for (const v of [s.real[i], s.modelo[i], s.promedio[i]]) tr.append(el("td", {}, v == null ? "–" : fmtEntero.format(v)));
    tbody.append(tr);
  }
  t.replaceChildren(thead, tbody);
}

function rangoNoviembre() {
  const v = D.corte_noviembre.map((f) => f.cambio_pct);
  return [Math.min(...v), Math.max(...v)];
}

function pintarEnCurso(k) {
  const caja = $("#en-curso");
  const h = el("h3", {}, `Estimación ${D.en_curso}`);
  const p = D.prediccion?.valores[k];
  if (!k) { caja.replaceChildren(); return; }
  if (!p) {
    const [a, b] = rangoNoviembre();
    caja.replaceChildren(h, el("p", {},
      `Todavía no está. Sale a principios de diciembre, cuando estén los datos de noviembre. Con datos solo hasta ` +
      `noviembre el modelo todavía no le gana al promedio de las campañas anteriores (en las pruebas se equivocó ` +
      `entre ${fmtDecimal.format(a)} % y ${fmtDecimal.format(b)} % más), así que se va a mostrar junto a ese promedio.`));
    return;
  }
  const valores = el("div", { class: "valores" });
  const v1 = el("div", {}, kg(p.modelo)); v1.append(el("small", {}, "Modelo"));
  const v2 = el("div", {}, kg(p.promedio)); v2.append(el("small", {}, "Promedio de las campañas anteriores"));
  valores.append(v1, v2);
  const nota = D.prediccion.corte === "nov"
    ? "Con datos hasta noviembre el modelo todavía no le gana al promedio de las campañas anteriores: tomá las dos cifras juntas."
    : `Con datos hasta ${D.prediccion.corte}.`;
  caja.replaceChildren(h, valores, el("p", {}, nota));
}

// ------------------------------------------------------------------ gráfico
function pasoLindo(rango) {
  const bruto = rango / 4;
  const mag = 10 ** Math.floor(Math.log10(bruto));
  return [1, 2, 2.5, 5, 10].map((f) => f * mag).find((p) => p >= bruto);
}

let grafico = null;

function dibujarGrafico(s) {
  const cont = $("#grafico");
  const W = Math.max(300, cont.clientWidth);
  const H = W < 520 ? 240 : 300;
  const m = { t: 12, r: W < 520 ? 44 : 56, b: 30, l: 50 };
  const n = D.campanias.length;
  const banda = (W - m.l - m.r) / n;
  const x = (i) => m.l + (i + 0.5) * banda;
  const todos = [...s.real, ...s.modelo, ...s.promedio].filter((v) => v != null);
  const paso = pasoLindo(Math.max(...todos));
  const ymax = Math.ceil((Math.max(...todos) * 1.04) / paso) * paso;
  const y = (v) => m.t + (H - m.t - m.b) * (1 - v / ymax);

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
    "aria-label": `Rinde de ${NOMBRE_CULTIVO[estado.cultivo]} por campaña en ${deptos.get(estado.depto).nombre}. Los números están en la tabla de abajo.` });

  const gNino = el("g");
  D.campanias.forEach((c, i) => {
    if (D.fase[c] === "nino") gNino.append(el("rect", { x: x(i) - banda / 2, y: m.t, width: banda, height: H - m.t - m.b, fill: "var(--nino)" }));
  });

  const gGrilla = el("g", { class: "grilla" });
  for (let v = paso; v <= ymax; v += paso) {
    gGrilla.append(el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }));
  }
  const gEjes = el("g", { class: "eje" });
  gEjes.append(el("line", { x1: m.l, x2: W - m.r, y1: y(0), y2: y(0) }));
  for (let v = 0; v <= ymax; v += paso) {
    gEjes.append(el("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end" }, fmtEntero.format(v)));
  }
  const cada = W < 520 ? 8 : 5;
  D.campanias.forEach((c, i) => {
    if (i % cada === 0) gEjes.append(el("text", { x: x(i), y: H - m.b + 18, "text-anchor": "middle" }, c));
  });

  const linea = (vals) => {
    let d = "", abierto = false;
    vals.forEach((v, i) => {
      if (v == null) { abierto = false; return; }
      d += `${abierto ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      abierto = true;
    });
    return d;
  };
  const gSeries = el("g");
  const series = [
    ["promedio", s.promedio, "var(--serie-promedio)"],
    ["modelo", s.modelo, "var(--serie-modelo)"],
    ["real", s.real, "var(--serie-real)"],
  ];
  for (const [nombre, vals, color] of series) {
    gSeries.append(el("path", { d: linea(vals), class: `serie serie--${nombre}`, stroke: color }));
  }
  const iu = n - 1, vu = s.real[iu];
  gSeries.append(el("circle", { cx: x(iu), cy: y(vu), r: 4.5, fill: "var(--serie-real)", class: "punto" }));
  gSeries.append(el("text", { x: x(iu) + 9, y: y(vu) + 4, class: "etiqueta-final" }, fmtEntero.format(vu)));

  const cursor = el("g", { visibility: "hidden" });
  const cursorLinea = el("line", { class: "cursor", y1: m.t, y2: H - m.b });
  cursor.append(cursorLinea);
  const puntos = series.map(([, , color]) => {
    const c = el("circle", { r: 4.5, fill: color, class: "punto" });
    cursor.append(c);
    return c;
  });

  const captura = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent" });
  svg.append(gNino, gGrilla, gEjes, gSeries, cursor, captura);

  const tooltip = el("div", { class: "tooltip", hidden: "" });
  cont.replaceChildren(svg, tooltip);

  grafico = { s, x, y, banda, m, W, cursor, cursorLinea, puntos, series, tooltip, idx: null };
  captura.addEventListener("pointermove", (e) => {
    const caja = svg.getBoundingClientRect();
    const px = ((e.clientX - caja.left) / caja.width) * W;
    mover(Math.round((px - m.l) / banda - 0.5));
  });
  captura.addEventListener("pointerleave", ocultarCursor);
}

function mover(i) {
  const g = grafico;
  if (!g) return;
  const n = D.campanias.length;
  i = Math.max(0, Math.min(n - 1, i));
  g.idx = i;
  const cx = g.x(i);
  g.cursor.setAttribute("visibility", "visible");
  g.cursorLinea.setAttribute("x1", cx);
  g.cursorLinea.setAttribute("x2", cx);
  g.series.forEach(([, vals], j) => {
    const v = vals[i];
    g.puntos[j].setAttribute("visibility", v == null ? "hidden" : "visible");
    if (v != null) { g.puntos[j].setAttribute("cx", cx); g.puntos[j].setAttribute("cy", g.y(v)); }
  });

  const c = D.campanias[i];
  const t = g.tooltip;
  const oni = D.oni[c];
  const titulo = el("div", { class: "tooltip__titulo" },
    `${c}, ${NOMBRE_FASE[D.fase[c]]}${oni == null ? "" : ` (ONI ${fmtDecimal.format(oni)})`}`);
  const filas = [
    ["var(--serie-real)", g.s.real[i], "rinde oficial"],
    ["var(--serie-modelo)", g.s.modelo[i], "modelo"],
    ["var(--serie-promedio)", g.s.promedio[i], "promedio anterior"],
  ].map(([color, v, nombre]) => {
    const f = el("div", { class: "tooltip__fila" });
    const key = el("i"); key.style.background = color;
    f.append(key, el("b", {}, v == null ? "–" : fmtEntero.format(v)), el("span", {}, nombre));
    return f;
  });
  t.replaceChildren(titulo, ...filas);
  t.hidden = false;
  const escala = $("#grafico").clientWidth / g.W;
  const ancho = t.offsetWidth;
  let left = cx * escala + 14;
  if (left + ancho > $("#grafico").clientWidth) left = cx * escala - ancho - 14;
  t.style.left = `${Math.max(0, left)}px`;
  t.style.top = `${g.m.t}px`;
}

function ocultarCursor() {
  if (!grafico) return;
  grafico.cursor.setAttribute("visibility", "hidden");
  grafico.tooltip.hidden = true;
  grafico.idx = null;
}

$("#grafico").addEventListener("keydown", (e) => {
  if (!grafico) return;
  const n = D.campanias.length;
  const i = grafico.idx ?? n - 1;
  if (e.key === "ArrowLeft") { e.preventDefault(); mover(grafico.idx == null ? n - 1 : i - 1); }
  else if (e.key === "ArrowRight") { e.preventDefault(); mover(grafico.idx == null ? n - 1 : i + 1); }
  else if (e.key === "Home") { e.preventDefault(); mover(0); }
  else if (e.key === "End") { e.preventDefault(); mover(n - 1); }
  else if (e.key === "Escape") ocultarCursor();
});
$("#grafico").addEventListener("focus", () => mover(D.campanias.length - 1));
$("#grafico").addEventListener("blur", ocultarCursor);

// ------------------------------------------------------------------ precisión general
function pintarPrecision() {
  const t = $("#tabla-precision");
  const thead = el("thead");
  const fila = el("tr");
  for (const h of ["Provincia y cultivo", "Error del modelo", "Promedio de las campañas anteriores", "Tendencia lineal"]) {
    fila.append(el("th", { scope: "col" }, h));
  }
  thead.append(fila);
  const tbody = el("tbody");
  const temp = D.metricas.filter((r) => r.esquema === "temporal");
  for (const prov of ["Santa Fe", "Entre Ríos"]) {
    for (const cult of ["soja", "maiz"]) {
      const v = (mod) => temp.find((r) => r.provincia === prov && r.cultivo === cult && r.modelo === mod)?.error_pct;
      const tr = el("tr");
      tr.append(el("th", { scope: "row" }, `${prov}, ${NOMBRE_CULTIVO[cult]}`));
      for (const mod of ["xgboost", "promedio_historico", "tendencia_lineal"]) tr.append(el("td", {}, pct(v(mod))));
      tbody.append(tr);
    }
  }
  t.replaceChildren(thead, tbody);
  const [a, b] = rangoNoviembre();
  $("#nota-noviembre").textContent =
    `Durante la campaña, el modelo mejora a medida que hay más meses de datos. Con datos solo hasta noviembre ` +
    `todavía se equivoca más que el promedio de las campañas anteriores (entre ${fmtDecimal.format(a)} % y ` +
    `${fmtDecimal.format(b)} % más, según provincia y cultivo); empieza a aportar con los datos de diciembre, y en la ` +
    `soja de Entre Ríos, con los de enero.`;
}

// ------------------------------------------------------------------ controles
function armarControles() {
  const metrica = $("#metrica");
  for (const [k, m] of Object.entries(METRICAS)) {
    const o = el("option", { value: k }, m.opcion);
    if (m.deshabilitada) o.disabled = true;
    metrica.append(o);
  }
  metrica.addEventListener("change", () => { estado.metrica = metrica.value; pintarMapa(); });

  const sel = $("#departamento");
  for (const prov of ["Santa Fe", "Entre Ríos"]) {
    const g = el("optgroup", { label: prov });
    [...deptos.values()].filter((d) => d.provincia === prov)
      .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))
      .forEach((d) => g.append(el("option", { value: d.id }, d.nombre)));
    sel.append(g);
  }
  sel.addEventListener("change", () => elegir(sel.value));

  for (const r of document.querySelectorAll('input[name="cultivo"]')) {
    r.addEventListener("change", () => { estado.cultivo = r.value; pintarMapa(); pintarDepto(); });
  }
  $("#generado").textContent = `Datos actualizados el ${D.generado.split("-").reverse().join("/")}.`;
}

function elegir(id) {
  if (!deptos.has(id)) return;
  estado.depto = id;
  history.replaceState(null, "", `#${id}`);
  pintarMapa();
  pintarDepto();
}

let espera;
window.addEventListener("resize", () => {
  clearTimeout(espera);
  espera = setTimeout(() => { if (D.series[clave(estado.depto)]) dibujarGrafico(D.series[clave(estado.depto)]); }, 120);
});

armarMapa();
armarControles();
pintarPrecision();
elegir(deptos.has(location.hash.slice(1)) ? location.hash.slice(1) : D.inicial);
