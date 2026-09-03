"""Genera cumplimiento_vuelos.html a partir de cumplimiento_vuelos.json
(ver extraer_cumplimiento_vuelos.py para la metodologia completa). Dashboard
con tema oficial de marca 2ebox (tokens en Projects/2EBOX/Brand Book 2ebox/
assets/tokens/2ebox-brand-tokens.json). Tres pestañas -- "Vuelo exacto"
(estricto) y "Misma semana" (mas permisiva, ver docstring del extractor),
cada una con las mismas 4 secciones (KPIs, grafico semanal/mensual, top 5
semanas/meses, tabla de detalle ordenable con N° de semana), mas una
pestaña "Conclusiones" con el razonamiento de por que abril-junio son tan
altos (pedido de Jorge, 2026-09-01) -- capacidad de vuelos descartada,
retraso de asignacion a guia madre como causa real, y consolidacion probada
y descartada como explicacion del patron (aunque tiene tasa base mas alta)."""
import html
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone

with open("cumplimiento_vuelos.json", encoding="utf-8") as f:
    data = json.load(f)

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# Codigos de convenio por ejecutiva (confirmados con Jorge, 2026-09-01 --
# mismo mapeo que el subproyecto de comisiones, ver docs/SYSTEM_MAP.md T-0004:
# Kathy = KC2EBOX + CPLAZA2EBOX (su canal de referidos mas grande) + DiamanteK;
# Tiare = TB2EBOX + DiamanteT).
KATHY_CONVENIOS = ["KC2EBOX", "CPLAZA2EBOX", "DiamanteK"]
TIARE_CONVENIOS = ["TB2EBOX", "DiamanteT"]


def fmt_pct(n):
    return f"{n:.1f}%".replace(".", ",")


def fmt_n(n):
    return format(n, ",").replace(",", ".")


def fmt_kg(n):
    return fmt_n(round(n)) + " kg"


def fmt_clp(n):
    return "$" + fmt_n(round(n))


def color_por_pct(pct):
    if pct >= 40:
        return "var(--bad)"
    if pct >= 15:
        return "var(--warn)"
    return "var(--good)"


def mes_label(key):
    y, m = key.split("-")
    return f"{MESES_ES[int(m) - 1]} {y}"


def semana_label(key):
    y, m, d = key.split("-")
    return f"{d}-{MESES_ES[int(m) - 1]}"


def semana_numero(key):
    """N° de semana ISO del lunes de esa semana, formato 'W23'."""
    y, m, d = (int(x) for x in key.split("-"))
    return f"W{date(y, m, d).isocalendar()[1]}"


def barra_svg(items, label_fn, width=980, height=260, bar_gap=6):
    n = len(items)
    if n == 0:
        return "<p class='empty-note'>Sin datos.</p>"
    left_pad, right_pad, top_pad, bottom_pad = 40, 10, 18, 46
    plot_w = width - left_pad - right_pad
    plot_h = height - top_pad - bottom_pad
    bar_w = max((plot_w - bar_gap * (n - 1)) / n, 2)

    svg = [f'<svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="Porcentaje de guías afectadas">']
    for pct_guide in (0, 25, 50, 75, 100):
        y = top_pad + plot_h - (pct_guide / 100) * plot_h
        svg.append(f'<line x1="{left_pad}" y1="{y:.1f}" x2="{width - right_pad}" y2="{y:.1f}" class="grid-line" />')
        svg.append(f'<text x="{left_pad - 6}" y="{y + 3:.1f}" class="axis-label" text-anchor="end">{pct_guide}%</text>')

    for i, (key, v) in enumerate(items):
        x = left_pad + i * (bar_w + bar_gap)
        pct = v["pct"]
        bar_h = (pct / 100) * plot_h
        y = top_pad + plot_h - bar_h
        color = color_por_pct(pct)
        titulo = (
            f"{label_fn(key)}: {v['incidentes']} de {v['evaluables']} guías afectadas ({fmt_pct(pct)}) — "
            f"{fmt_kg(v['kilos'])}, {v['clientes']} clientes"
        )
        svg.append(
            f'<g class="bar-g"><title>{titulo}</title>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(bar_h, 1):.1f}" rx="2" fill="{color}" />'
            f'</g>'
        )
        step = max(1, n // 16)
        if i % step == 0 or i == n - 1:
            lx = x + bar_w / 2
            svg.append(f'<text x="{lx:.1f}" y="{height - bottom_pad + 16}" class="axis-label axis-x" text-anchor="end" transform="rotate(-55 {lx:.1f} {height - bottom_pad + 16})">{label_fn(key)}</text>')

    svg.append("</svg>")
    return "".join(svg)


def tabla_html(items, label_fn, semanal):
    rows = []
    for key, v in items:
        celda_semana = (
            f"<td data-v='{date(*(int(x) for x in key.split('-'))).isocalendar()[1]}'>{semana_numero(key)}</td>"
            if semanal else ""
        )
        rows.append(
            f"<tr>{celda_semana}"
            f"<td data-v='{key}'>{label_fn(key)}</td>"
            f"<td data-v='{v['evaluables']}'>{fmt_n(v['evaluables'])}</td>"
            f"<td data-v='{v['incidentes']}'>{fmt_n(v['incidentes'])}</td>"
            f"<td data-v='{v['pct']}' style='color:{color_por_pct(v['pct'])};font-weight:700'>{fmt_pct(v['pct'])}</td>"
            f"<td data-v='{v['kilos']}'>{fmt_kg(v['kilos'])}</td>"
            f"<td data-v='{v['pct_kilos']}' style='color:{color_por_pct(v['pct_kilos'])};font-weight:700'>{fmt_pct(v['pct_kilos'])}</td>"
            f"<td data-v='{v['clientes']}'>{fmt_n(v['clientes'])}</td></tr>"
        )
    return "\n".join(rows)


def ejecutivas_kpis_html(incidentes):
    """3 KPI tiles con el % de `incidentes` (detalle_incidentes de UN
    bloque/definición específico) que corresponde a cada ejecutiva, según
    código de convenio. Pedido de Jorge (2026-09-01): que vaya DENTRO de
    cada pestaña/definición (debajo de los KPIs generales), no como sección
    fija arriba de la página -- el valor tiene que cambiar según "vuelo
    exacto" / "misma semana" / "consolidadas", no quedarse fijo en un solo
    total mezclado."""
    total = len(incidentes)
    kathy = [r for r in incidentes if r["convenio"] in KATHY_CONVENIOS]
    tiare = [r for r in incidentes if r["convenio"] in TIARE_CONVENIOS]
    otros = total - len(kathy) - len(tiare)

    def pct(n):
        return round(n / total * 100, 1) if total else 0

    return f"""
  <section>
    <h2>Guías afectadas por ejecutiva</h2>
    <div class="kpis">
      <div class="kpi bad"><div class="v">{fmt_pct(pct(len(kathy)))}</div><div class="l">Katherine (Kathy) — {fmt_n(len(kathy))} guías · KC2EBOX, CPLAZA2EBOX, DiamanteK</div></div>
      <div class="kpi bad"><div class="v">{fmt_pct(pct(len(tiare)))}</div><div class="l">Tiare — {fmt_n(len(tiare))} guías · TB2EBOX, DiamanteT</div></div>
      <div class="kpi"><div class="v">{fmt_pct(pct(otros))}</div><div class="l">Otros convenios / sin convenio — {fmt_n(otros)} guías</div></div>
    </div>
  </section>
"""


def explica_panel(columnas):
    """Panel de explicación en 2-3 columnas, para reemplazar los párrafos
    largos de una sola columna que traía el reporte (pedido de Jorge,
    2026-09-02: "hazlo mucho más simple y usa todo el ancho... separando en
    2 o 3 columnas"). `columnas` es una lista de (icono_emoji, titulo,
    html_contenido) -- cada una se ve como una tarjeta corta con su propio
    tema, en vez de un bloque de texto corrido explicando 3 cosas
    distintas seguidas."""
    celdas = "".join(
        f'<div class="explica-col"><div class="ec-ico">{ico}</div>'
        f"<h4>{titulo}</h4><div class=\"ec-txt\">{contenido}</div></div>"
        for ico, titulo, contenido in columnas
    )
    return f'<div class="explica">{celdas}</div>'


def explica_diagrama(pasos):
    """Diagrama de flujo simple (cajas + flechas) para ilustrar un proceso
    de pocos pasos en vez de describirlo solo en texto -- ej. "guías
    originales -> bodega arma el bulto -> guía-bulto nueva". `pasos` es una
    lista de dicts: {"titulo", "sub" (opcional), "tag" (opcional, texto
    corto), "variante" ('off'|'proc'|'on', define el color del tag/borde)}.
    """
    color = {"off": "var(--bad)", "proc": "var(--ink-faint)", "on": "var(--good)"}
    partes = []
    for i, p in enumerate(pasos):
        if i > 0:
            partes.append('<div class="ed-arrow">&#8594;</div>')
        c = color.get(p.get("variante"), "var(--ink-faint)")
        tag_html = (
            f'<div class="ed-tag" style="color:{c};border-color:{c}">{p["tag"]}</div>'
            if p.get("tag") else ""
        )
        sub_html = f'<div class="ed-sub">{p["sub"]}</div>' if p.get("sub") else ""
        partes.append(
            f'<div class="ed-box"><div class="ed-label">{p["titulo"]}</div>{sub_html}{tag_html}</div>'
        )
    return f'<div class="explica-diagrama">{"".join(partes)}</div>'


def barra_capacidad_svg(items, label_fn, key_ingreso, key_podria, width=980, height=260, bar_gap=6):
    """Grafico de barras superpuestas: 'podria' (potencial, claro, atras)
    vs 'ingreso' (real, solido, adelante, mas angosta) -- ambas ancladas
    abajo, escaladas al mismo eje. La brecha visible entre el tope de la
    barra clara y la solida es capacidad sin usar."""
    n = len(items)
    if n == 0:
        return "<p class='empty-note'>Sin datos.</p>"
    left_pad, right_pad, top_pad, bottom_pad = 46, 10, 18, 46
    plot_w = width - left_pad - right_pad
    plot_h = height - top_pad - bottom_pad
    bar_w = max((plot_w - bar_gap * (n - 1)) / n, 2)
    y_max = max((v[key_podria] for _, v in items), default=1) or 1
    y_max = y_max * 1.08

    def escala(val):
        return (val / y_max) * plot_h if y_max else 0

    svg = [f'<svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="Capacidad ingresada vs potencial por vuelo">']
    pasos = 4
    for i in range(pasos + 1):
        val = round(y_max / pasos * i)
        y = top_pad + plot_h - escala(val)
        svg.append(f'<line x1="{left_pad}" y1="{y:.1f}" x2="{width - right_pad}" y2="{y:.1f}" class="grid-line" />')
        svg.append(f'<text x="{left_pad - 6}" y="{y + 3:.1f}" class="axis-label" text-anchor="end">{fmt_n(val)}</text>')

    for i, (key, v) in enumerate(items):
        x = left_pad + i * (bar_w + bar_gap)
        h_podria = escala(v[key_podria])
        h_ingreso = escala(v[key_ingreso])
        y_podria = top_pad + plot_h - h_podria
        y_ingreso = top_pad + plot_h - h_ingreso
        titulo = f"{label_fn(key)}: {fmt_n(v[key_ingreso])} ingresadas de {fmt_n(v[key_podria])} que podrían haber ingresado"
        svg.append(
            f'<g class="bar-g"><title>{titulo}</title>'
            f'<rect x="{x:.1f}" y="{y_podria:.1f}" width="{bar_w:.1f}" height="{max(h_podria, 1):.1f}" rx="2" fill="var(--2e-blue-claro)" fill-opacity="0.5" stroke="var(--2e-blue)" stroke-opacity="0.3" />'
            f'<rect x="{x + bar_w * 0.18:.1f}" y="{y_ingreso:.1f}" width="{bar_w * 0.64:.1f}" height="{max(h_ingreso, 1):.1f}" rx="2" fill="var(--2e-blue)" />'
            f'</g>'
        )
        step = max(1, n // 16)
        if i % step == 0 or i == n - 1:
            lx = x + bar_w / 2
            svg.append(f'<text x="{lx:.1f}" y="{height - bottom_pad + 16}" class="axis-label axis-x" text-anchor="end" transform="rotate(-55 {lx:.1f} {height - bottom_pad + 16})">{label_fn(key)}</text>')

    svg.append("</svg>")
    return "".join(svg)


def build_capacidad_vuelos():
    """Pestaña "Capacidad de Vuelos" (pedido de Jorge, 2026-09-01, 6ta y
    7ma iteración): capacidad real ingresada por vuelo (tope de lo que
    efectivamente voló) vs cuántas guías YA listas para volar (pago +
    factura) había disponibles justo antes de que ese vuelo saliera. Cálculo
    completo en `calcular_capacidad_vuelos()`/`calcular_capacidad_semanal()`
    del extractor -- ya excluye vuelos de 1 sola guía (carga).

    OJO con la semántica del %: corregido 2026-09-01 a pedido de Jorge --
    el 100% de la capacidad de un vuelo NO es "podría" (la cola de espera),
    es "ingreso" (lo que efectivamente voló), porque ESA es la restricción
    real que impone la aerolínea ese vuelo puntual. "Podría" es la DEMANDA
    (cuántas guías había listas); si demanda > capacidad, el sobrante es
    "excedente" (demanda que no alcanzó a subir, no "capacidad sin usar").
    Por eso `pct_capacidad = podria / ingreso * 100` -- 100% = la demanda
    calzó exacto con la capacidad del vuelo (sin excedente); más de 100% =
    hubo más guías listas que cupo. Puede darménos de 100% en semanas con
    varios clientes de crédito (ver docstring del extractor: esas guías
    cuentan en 'ingreso' pero no pasan por la cola de 'podria', asi que a
    veces el ingreso real supera a la demanda rastreada -- no es un error,
    es cobertura parcial de la cola de espera)."""
    cap = data.get("capacidad_por_vuelo", [])
    # capacidad_por_semana viene de una simulacion propia a nivel semanal
    # (calcular_capacidad_semanal en el extractor) -- NO es un rollup del
    # detalle por vuelo. 'podria' es un STOCK (tamano de cola en un
    # instante): sumarlo entre vuelos de la semana cuenta a la misma guia
    # esperando varias veces. La semana se mide como UN solo checkpoint
    # (justo antes del ultimo vuelo de esa semana).
    por_semana = {c["semana"]: c for c in data.get("capacidad_por_semana", [])}
    por_mes = {c["mes"]: c for c in data.get("capacidad_por_mes", [])}
    for b in list(por_semana.values()) + list(por_mes.values()):
        b["excedente"] = max(0, b["n_podria"] - b["n_ingreso"])
        b["kg_excedente"] = round(max(0, b["kg_podria"] - b["kg_ingreso"]), 1)
        b["pct_capacidad"] = round(b["n_podria"] / b["n_ingreso"] * 100, 1) if b["n_ingreso"] else 0

    for c in cap:
        c["excedente"] = max(0, c["n_podria"] - c["n_ingreso"])
        c["kg_excedente"] = round(max(0, c["kg_podria"] - c["kg_ingreso"]), 1)
        c["pct_capacidad"] = round(c["n_podria"] / c["n_ingreso"] * 100, 1) if c["n_ingreso"] else 0

    vuelo_items = [(c["ts"], c) for c in cap]
    semana_items = sorted(por_semana.items())
    mes_items = sorted(por_mes.items())

    def label_vuelo(ts):
        d = date.fromisoformat(ts[:10])
        return f"{d.day:02d}-{MESES_ES[d.month - 1]}"

    def color_exceso(pct_capacidad):
        return color_por_pct(max(0, pct_capacidad - 100))

    chart_vuelo = barra_capacidad_svg(vuelo_items, label_vuelo, "n_ingreso", "n_podria")
    chart_semana = barra_capacidad_svg(semana_items, semana_label, "n_ingreso", "n_podria", bar_gap=14)
    chart_mes = barra_capacidad_svg(mes_items, mes_label, "n_ingreso", "n_podria", bar_gap=18)

    def fila_vuelo(ts, c):
        fecha_txt = ts[:10]
        awb_txt = c.get("awb") or "s/d"
        aerolinea = c.get("aerolinea") or ""
        awb_html = html.escape(awb_txt) + (f" <span style='color:var(--ink-faint)'>({html.escape(aerolinea)})</span>" if aerolinea else "")
        return (
            f"<tr data-fecha='{fecha_txt}'><td data-v='{html.escape(awb_txt)}'>{awb_html}</td>"
            f"<td data-v='{ts}'>{fecha_txt}</td>"
            f"<td data-v='{c['n_ingreso']}'>{fmt_n(c['n_ingreso'])}</td>"
            f"<td data-v='{c['kg_ingreso']}'>{fmt_kg(c['kg_ingreso'])}</td>"
            f"<td data-v='{c['n_podria']}'>{fmt_n(c['n_podria'])}</td>"
            f"<td data-v='{c['kg_podria']}'>{fmt_kg(c['kg_podria'])}</td>"
            f"<td data-v='{c['kg_excedente']}' style='color:{color_exceso(c['pct_capacidad'])};font-weight:700'>{fmt_kg(c['kg_excedente'])}</td>"
            f"<td data-v='{c['excedente']}'>{fmt_n(c['excedente'])}</td>"
            f"<td data-v='{c['pct_capacidad']}' style='color:{color_exceso(c['pct_capacidad'])};font-weight:700'>{fmt_pct(c['pct_capacidad'])}</td></tr>"
        )

    def fila_semana(wk, b):
        return (
            f"<tr data-fecha='{wk}'><td data-v='{date.fromisoformat(wk).isocalendar()[1]}'>{semana_numero(wk)}</td>"
            f"<td data-v='{wk}'>{semana_label(wk)}</td>"
            f"<td data-v='{b['n_vuelos']}'>{fmt_n(b['n_vuelos'])}</td>"
            f"<td data-v='{b['n_ingreso']}'>{fmt_n(b['n_ingreso'])}</td>"
            f"<td data-v='{b['kg_ingreso']}'>{fmt_kg(b['kg_ingreso'])}</td>"
            f"<td data-v='{b['n_podria']}'>{fmt_n(b['n_podria'])}</td>"
            f"<td data-v='{b['kg_podria']}'>{fmt_kg(b['kg_podria'])}</td>"
            f"<td data-v='{b['kg_excedente']}' style='color:{color_exceso(b['pct_capacidad'])};font-weight:700'>{fmt_kg(b['kg_excedente'])}</td>"
            f"<td data-v='{b['excedente']}'>{fmt_n(b['excedente'])}</td>"
            f"<td data-v='{b['pct_capacidad']}' style='color:{color_exceso(b['pct_capacidad'])};font-weight:700'>{fmt_pct(b['pct_capacidad'])}</td></tr>"
        )

    def fila_mes(mo, b):
        return (
            f"<tr data-fecha='{mo}-01'><td data-v='{mo}'>{mes_label(mo)}</td>"
            f"<td data-v='{b['n_vuelos']}'>{fmt_n(b['n_vuelos'])}</td>"
            f"<td data-v='{b['n_ingreso']}'>{fmt_n(b['n_ingreso'])}</td>"
            f"<td data-v='{b['kg_ingreso']}'>{fmt_kg(b['kg_ingreso'])}</td>"
            f"<td data-v='{b['n_podria']}'>{fmt_n(b['n_podria'])}</td>"
            f"<td data-v='{b['kg_podria']}'>{fmt_kg(b['kg_podria'])}</td>"
            f"<td data-v='{b['kg_excedente']}' style='color:{color_exceso(b['pct_capacidad'])};font-weight:700'>{fmt_kg(b['kg_excedente'])}</td>"
            f"<td data-v='{b['excedente']}'>{fmt_n(b['excedente'])}</td>"
            f"<td data-v='{b['pct_capacidad']}' style='color:{color_exceso(b['pct_capacidad'])};font-weight:700'>{fmt_pct(b['pct_capacidad'])}</td></tr>"
        )

    tabla_vuelo = "\n".join(fila_vuelo(ts, c) for ts, c in vuelo_items)
    tabla_semana = "\n".join(fila_semana(wk, b) for wk, b in semana_items)
    tabla_mes = "\n".join(fila_mes(mo, b) for mo, b in mes_items)

    total_ingreso = sum(c["n_ingreso"] for c in cap)
    total_kg_ingreso = sum(c["kg_ingreso"] for c in cap)
    total_excedente = sum(c["excedente"] for c in cap)
    pct_capacidad_global = round(sum(b["n_podria"] for b in por_semana.values()) / sum(b["n_ingreso"] for b in por_semana.values()) * 100, 1) if por_semana else 0
    peor_vuelo = max(cap, key=lambda c: c["pct_capacidad"]) if cap else None
    kg_prom_vuelo = round(total_kg_ingreso / len(cap)) if cap else 0
    fecha_min = min((c["ts"][:10] for c in cap), default="")
    fecha_max = max((c["ts"][:10] for c in cap), default="")

    return f"""
  <div class="cap-filtro-fechas">
    <span class="cap-filtro-label">Filtrar por fecha:</span>
    <label>Desde <input type="date" id="cap-fecha-desde" value="{fecha_min}" min="{fecha_min}" max="{fecha_max}" onchange="capFiltrarFechas()"></label>
    <label>Hasta <input type="date" id="cap-fecha-hasta" value="{fecha_max}" min="{fecha_min}" max="{fecha_max}" onchange="capFiltrarFechas()"></label>
    <button onclick="capLimpiarFiltroFechas()">Limpiar</button>
  </div>

  {explica_panel([
      (
          "✈️", "\"Ingresó\" = 100% de capacidad",
          "Cuántas guías efectivamente subieron a ese vuelo. Es el tope real — la "
          "restricción que impuso la aerolínea ese día puntual.",
      ),
      (
          "⏳", "\"Podría\" = demanda real",
          "Cuántas guías YA listas para volar (pago + factura) había disponibles justo "
          "antes de que saliera el vuelo — incluye tanto a las que sí abordaron como a "
          "las que quedaron esperando uno posterior. A nivel semanal se mide 1 sola vez "
          "por semana (no se suma entre vuelos, para no contar dos veces a la misma guía "
          "esperando).",
      ),
      (
          "📈", "\"Excedente\" = demanda sin subir",
          "Todo lo que no alcanzó a subir. <b>No</b> es capacidad desperdiciada — es "
          "demanda que superó el cupo del vuelo. El filtro de fecha de arriba recalcula "
          "estos KPIs y las 3 tablas (no los gráficos, que quedan con el año completo).",
      ),
  ])}

  <div class="kpis">
    <div class="kpi"><div class="v" id="cap-kpi-ingreso">{fmt_n(total_ingreso)}</div><div class="l">Total guías ingresadas</div></div>
    <div class="kpi"><div class="v" id="cap-kpi-kgprom">{fmt_kg(kg_prom_vuelo)}</div><div class="l">Promedio de kilos por vuelo</div></div>
    <div class="kpi bad"><div class="v" id="cap-kpi-excedente">{fmt_n(total_excedente)}</div><div class="l">Guías-vuelo de excedente acumulado (suma por vuelo)</div></div>
    <div class="kpi"><div class="v" id="cap-kpi-peor">{peor_vuelo['ts'][:10] if peor_vuelo else 's/d'}</div><div class="l" id="cap-kpi-peor-l">Vuelo con mayor excedente ({fmt_pct(peor_vuelo['pct_capacidad']) if peor_vuelo else 's/d'} de su capacidad)</div></div>
  </div>

  <section>
    <h2>Guías ingresadas (capacidad) vs guías que podrían haber ingresado (demanda)</h2>
    <div class="toggle">
      <button id="btn-capacidad-semanal" class="active" onclick="verVistaCapacidad('semanal')">Semanal</button>
      <button id="btn-capacidad-mensual" onclick="verVistaCapacidad('mensual')">Mensual</button>
      <button id="btn-capacidad-porvuelo" onclick="verVistaCapacidad('porvuelo')">Por vuelo</button>
    </div>
    <div class="chart-wrap">
      <div id="view-capacidad-chart-semanal" class="view active">{chart_semana}</div>
      <div id="view-capacidad-chart-mensual" class="view">{chart_mes}</div>
      <div id="view-capacidad-chart-porvuelo" class="view">{chart_vuelo}</div>
    </div>
    <p class="empty-note" style="text-align:left;padding:10px 4px 0">
      Barra clara = podría haber ingresado (demanda). Barra sólida = efectivamente ingresó
      (capacidad real = 100%).
    </p>
  </section>

  <section>
    <h2>Detalle</h2>
    <div class="toggle">
      <button id="btn-capacidad-tabla-semanal" class="active" onclick="verTablaCapacidad('semanal')">Semanal</button>
      <button id="btn-capacidad-tabla-mensual" onclick="verTablaCapacidad('mensual')">Mensual</button>
      <button id="btn-capacidad-tabla-porvuelo" onclick="verTablaCapacidad('porvuelo')">Por vuelo</button>
    </div>
    <div class="table-wrap">
      <div id="view-capacidad-tabla-semanal" class="view active">
        <table id="tabla-capacidad-semanal" class="sortable"><thead><tr>
          <th onclick="ordenarTabla('tabla-capacidad-semanal',0,'num')">N° Semana</th>
          <th onclick="ordenarTabla('tabla-capacidad-semanal',1,'str')">Semana (lunes)</th>
          <th onclick="ordenarTabla('tabla-capacidad-semanal',2,'num')">Vuelos esa semana</th>
          <th onclick="ordenarTabla('tabla-capacidad-semanal',3,'num')">Guías ingresadas</th>
          <th onclick="ordenarTabla('tabla-capacidad-semanal',4,'num')">Kilos ingresados</th>
          <th onclick="ordenarTabla('tabla-capacidad-semanal',5,'num')">Podrían ingresar</th>
          <th onclick="ordenarTabla('tabla-capacidad-semanal',6,'num')">Kilos podrían</th>
          <th onclick="ordenarTabla('tabla-capacidad-semanal',7,'num')">Excedente (kg)</th>
          <th onclick="ordenarTabla('tabla-capacidad-semanal',8,'num')">Excedente (guías)</th>
          <th onclick="ordenarTabla('tabla-capacidad-semanal',9,'num')">% sobre capacidad</th>
        </tr></thead>
        <tbody>{tabla_semana}</tbody></table>
      </div>
      <div id="view-capacidad-tabla-mensual" class="view">
        <table id="tabla-capacidad-mes" class="sortable"><thead><tr>
          <th onclick="ordenarTabla('tabla-capacidad-mes',0,'str')">Mes</th>
          <th onclick="ordenarTabla('tabla-capacidad-mes',1,'num')">Vuelos ese mes</th>
          <th onclick="ordenarTabla('tabla-capacidad-mes',2,'num')">Guías ingresadas</th>
          <th onclick="ordenarTabla('tabla-capacidad-mes',3,'num')">Kilos ingresados (real)</th>
          <th onclick="ordenarTabla('tabla-capacidad-mes',4,'num')">Podrían ingresar</th>
          <th onclick="ordenarTabla('tabla-capacidad-mes',5,'num')">Kilos podrían</th>
          <th onclick="ordenarTabla('tabla-capacidad-mes',6,'num')">Excedente (kg)</th>
          <th onclick="ordenarTabla('tabla-capacidad-mes',7,'num')">Excedente (guías)</th>
          <th onclick="ordenarTabla('tabla-capacidad-mes',8,'num')">% sobre capacidad</th>
        </tr></thead>
        <tbody>{tabla_mes}</tbody></table>
      </div>
      <div id="view-capacidad-tabla-porvuelo" class="view">
        <table id="tabla-capacidad-vuelo" class="sortable"><thead><tr>
          <th onclick="ordenarTabla('tabla-capacidad-vuelo',0,'str')">N° vuelo / AWB</th>
          <th onclick="ordenarTabla('tabla-capacidad-vuelo',1,'str')">Fecha vuelo</th>
          <th onclick="ordenarTabla('tabla-capacidad-vuelo',2,'num')">Guías ingresadas</th>
          <th onclick="ordenarTabla('tabla-capacidad-vuelo',3,'num')">Kilos ingresados</th>
          <th onclick="ordenarTabla('tabla-capacidad-vuelo',4,'num')">Podrían ingresar</th>
          <th onclick="ordenarTabla('tabla-capacidad-vuelo',5,'num')">Kilos podrían</th>
          <th onclick="ordenarTabla('tabla-capacidad-vuelo',6,'num')">Excedente (kg)</th>
          <th onclick="ordenarTabla('tabla-capacidad-vuelo',7,'num')">Excedente (guías)</th>
          <th onclick="ordenarTabla('tabla-capacidad-vuelo',8,'num')">% sobre capacidad</th>
        </tr></thead>
        <tbody>{tabla_vuelo}</tbody></table>
      </div>
    </div>
  </section>

  <script>
    // Filtro de fechas de "Capacidad de Vuelos": esconde filas fuera de
    // rango en las 3 tablas (cada <tr> trae data-fecha='YYYY-MM-DD',
    // agregado en fila_vuelo/fila_semana/fila_mes) y recalcula los KPIs de
    // arriba a partir de las filas VISIBLES de la tabla "por vuelo" (la
    // granularidad mas fina -- coincide con como se calculan en Python).
    // Los graficos SVG no se filtran (quedan como contexto de año completo).
    (function () {{
      function capFechaOk(tr, desde, hasta) {{
        var f = tr.getAttribute('data-fecha');
        if (!f) return true;
        if (desde && f < desde) return false;
        if (hasta && f > hasta) return false;
        return true;
      }}

      window.capFiltrarFechas = function () {{
        var desde = document.getElementById('cap-fecha-desde').value;
        var hasta = document.getElementById('cap-fecha-hasta').value;
        ['tabla-capacidad-vuelo', 'tabla-capacidad-semanal', 'tabla-capacidad-mes'].forEach(function (tid) {{
          var tabla = document.getElementById(tid);
          if (!tabla) return;
          Array.prototype.slice.call(tabla.querySelectorAll('tbody tr')).forEach(function (tr) {{
            tr.style.display = capFechaOk(tr, desde, hasta) ? '' : 'none';
          }});
        }});
        capRecalcularKpisCapacidad();
      }};

      window.capLimpiarFiltroFechas = function () {{
        var desdeInput = document.getElementById('cap-fecha-desde');
        var hastaInput = document.getElementById('cap-fecha-hasta');
        desdeInput.value = desdeInput.min;
        hastaInput.value = hastaInput.max;
        capFiltrarFechas();
      }};

      function capRecalcularKpisCapacidad() {{
        var filas = Array.prototype.slice.call(document.querySelectorAll('#tabla-capacidad-vuelo tbody tr'))
          .filter(function (tr) {{ return tr.style.display !== 'none'; }});
        var totalIngreso = 0, totalKg = 0, totalExcedente = 0, peor = null;
        filas.forEach(function (tr) {{
          var tds = tr.children;
          var nIngreso = parseFloat(tds[2].getAttribute('data-v')) || 0;
          var kgIngreso = parseFloat(tds[3].getAttribute('data-v')) || 0;
          var excedenteN = parseFloat(tds[7].getAttribute('data-v')) || 0;
          var pct = parseFloat(tds[8].getAttribute('data-v')) || 0;
          var fecha = tds[1].getAttribute('data-v');
          totalIngreso += nIngreso;
          totalKg += kgIngreso;
          totalExcedente += excedenteN;
          if (!peor || pct > peor.pct) peor = {{ pct: pct, fecha: fecha }};
        }});
        var kgProm = filas.length ? Math.round(totalKg / filas.length) : 0;
        document.getElementById('cap-kpi-ingreso').textContent = totalIngreso.toLocaleString('es-CL');
        document.getElementById('cap-kpi-kgprom').textContent = kgProm.toLocaleString('es-CL') + ' kg';
        document.getElementById('cap-kpi-excedente').textContent = totalExcedente.toLocaleString('es-CL');
        document.getElementById('cap-kpi-peor').textContent = peor ? peor.fecha.slice(0, 10) : 's/d';
        document.getElementById('cap-kpi-peor-l').textContent =
          'Vuelo con mayor excedente (' + (peor ? peor.pct.toFixed(1) : '0') + '% de su capacidad)';
      }}
    }})();
  </script>
"""


def build_seccion(scope, titulo_bloque, subtitulo_bloque, poblacion=None, universo_evaluables=None, dom_id=None):
    """scope = 'estricto' | 'semana'. poblacion = None (todas, comportamiento
    original) | 'individuales' | 'consolidadas' -- selecciona
    data[poblacion][scope] en vez de data[scope]. universo_evaluables fija
    el denominador del KPI "% guías afectadas" (por defecto el total de la
    población elegida). dom_id identifica los ids/onclick generados en el
    HTML (por defecto = scope) -- OBLIGATORIO pasarlo distinto cuando se
    invoca build_seccion() más de una vez con el mismo scope (ej.
    individuales y consolidadas ambas usan scope='estricto'), o los ids
    quedan duplicados en la misma página. Devuelve el HTML completo de una
    pestaña (KPIs + gráfico + hallazgos + tabla)."""
    dom_id = dom_id or scope
    bloque = data[poblacion][scope] if poblacion else data[scope]
    semanas = list(bloque["por_semana"].items())
    meses = list(bloque["por_mes"].items())

    chart_semanal = barra_svg(semanas, semana_label)
    chart_mensual = barra_svg(meses, mes_label, bar_gap=14)
    tabla_semanal = tabla_html(semanas, semana_label, semanal=True)
    tabla_mensual = tabla_html(meses, mes_label, semanal=False)

    total_evaluables = universo_evaluables if universo_evaluables is not None else sum(v["evaluables"] for _, v in meses)
    pct_global = round(bloque["total_incidentes"] / total_evaluables * 100, 1) if total_evaluables else 0

    top_semanas = sorted(semanas, key=lambda kv: -kv[1]["pct"])[:5]
    top_meses = sorted(meses, key=lambda kv: -kv[1]["pct"])[:5]
    hallazgos_semanas = "".join(
        f"<li><b>{semana_label(k)}</b>: {fmt_pct(v['pct'])} ({v['incidentes']} de {v['evaluables']} guías, {fmt_kg(v['kilos'])}, {v['clientes']} clientes)</li>"
        for k, v in top_semanas
    )
    hallazgos_meses = "".join(
        f"<li><b>{mes_label(k)}</b>: {fmt_pct(v['pct'])} ({v['incidentes']} de {v['evaluables']} guías, {fmt_kg(v['kilos'])}, {v['clientes']} clientes)</li>"
        for k, v in top_meses
    )

    return f"""
  <p class="sub">{subtitulo_bloque}</p>

  <div class="kpis">
    <div class="kpi bad"><div class="v">{fmt_pct(pct_global)}</div><div class="l">% guías afectadas</div></div>
    <div class="kpi"><div class="v">{fmt_n(bloque['total_incidentes'])}</div><div class="l">Guías afectadas de {fmt_n(bloque['total_evaluables'])} evaluadas</div></div>
    <div class="kpi"><div class="v">{fmt_kg(bloque['total_kilos'])}</div><div class="l">Kilos afectados de {fmt_kg(bloque['total_kilos_evaluables'])} evaluados</div></div>
    <div class="kpi"><div class="v">{fmt_n(bloque['total_clientes'])}</div><div class="l">Clientes únicos afectados de {fmt_n(bloque['total_clientes_evaluables'])} evaluados</div></div>
  </div>

  {ejecutivas_kpis_html(bloque['detalle_incidentes'])}

  <section>
    <h2>% de guías afectadas — {titulo_bloque}</h2>
    <div class="toggle">
      <button id="btn-{dom_id}-semanal" class="active" onclick="verVista('{dom_id}','semanal')">Semanal</button>
      <button id="btn-{dom_id}-mensual" onclick="verVista('{dom_id}','mensual')">Mensual</button>
    </div>
    <div class="chart-wrap">
      <div id="view-{dom_id}-chart-semanal" class="view active">{chart_semanal}</div>
      <div id="view-{dom_id}-chart-mensual" class="view">{chart_mensual}</div>
    </div>
  </section>

  <section>
    <h2>Semanas y meses más críticos (2026)</h2>
    <div class="hallazgos">
      <div class="card">
        <h3>Top 5 semanas</h3>
        <ul>{hallazgos_semanas}</ul>
      </div>
      <div class="card">
        <h3>Top 5 meses</h3>
        <ul>{hallazgos_meses}</ul>
      </div>
    </div>
  </section>

  <section>
    <h2>Detalle</h2>
    <div class="toggle">
      <button id="btn-{dom_id}-tabla-semanal" class="active" onclick="verTabla('{dom_id}','semanal')">Semanal</button>
      <button id="btn-{dom_id}-tabla-mensual" onclick="verTabla('{dom_id}','mensual')">Mensual</button>
    </div>
    <div class="table-wrap">
      <div id="view-{dom_id}-tabla-semanal" class="view active">
        <table id="tabla-{dom_id}-semanal" class="sortable"><thead><tr>
          <th onclick="ordenarTabla('tabla-{dom_id}-semanal',0,'num')">N° Semana</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-semanal',1,'str')">Semana (lunes)</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-semanal',2,'num')">Guías evaluadas</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-semanal',3,'num')">Afectadas</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-semanal',4,'num')">%</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-semanal',5,'num')">Kilos</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-semanal',6,'num')">% Kilos</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-semanal',7,'num')">Clientes</th>
        </tr></thead>
        <tbody>{tabla_semanal}</tbody></table>
      </div>
      <div id="view-{dom_id}-tabla-mensual" class="view">
        <table id="tabla-{dom_id}-mensual" class="sortable"><thead><tr>
          <th onclick="ordenarTabla('tabla-{dom_id}-mensual',0,'str')">Mes</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-mensual',1,'num')">Guías evaluadas</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-mensual',2,'num')">Afectadas</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-mensual',3,'num')">%</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-mensual',4,'num')">Kilos</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-mensual',5,'num')">% Kilos</th>
          <th onclick="ordenarTabla('tabla-{dom_id}-mensual',6,'num')">Clientes</th>
        </tr></thead>
        <tbody>{tabla_mensual}</tbody></table>
      </div>
    </div>
  </section>
"""


def build_conclusiones():
    """Hoja de conclusiones: por que abril-junio son tan altos. Tres
    hallazgos, cada uno probado o descartado con datos (pedido de Jorge,
    2026-09-01) -- capacidad de vuelos, retraso de asignacion a guia madre,
    y guias consolidadas (separadas del resto y analizadas aparte)."""
    from datetime import datetime as dt, timedelta

    # --- Hallazgo 1: capacidad -- oferta vs demanda semanal (sobre 'estricto')
    def lunes(iso_ts):
        d = dt.fromisoformat(iso_ts).date()
        return d - timedelta(days=d.weekday())

    oferta_semana = {}
    for v in data["vuelos_calendario"]:
        wk = lunes(v["ts"]).isoformat()
        oferta_semana[wk] = oferta_semana.get(wk, 0) + v["n_guias"]

    semanas_estr = data["estricto"]["por_semana"]
    cum_dem = cum_sup = 0
    oferta_nunca_bajo_demanda = True
    for wk in sorted(set(list(semanas_estr.keys()) + list(oferta_semana.keys()))):
        cum_dem += semanas_estr.get(wk, {}).get("evaluables", 0)
        cum_sup += oferta_semana.get(wk, 0)
        if cum_sup < cum_dem:
            oferta_nunca_bajo_demanda = False

    semana_25may = "2026-05-25"
    oferta_25may = oferta_semana.get(semana_25may, 0)
    demanda_25may = semanas_estr.get(semana_25may, {}).get("evaluables", 0)
    otras = [oferta_semana.get(wk, 0) for wk in semanas_estr if wk != semana_25may]
    oferta_prom_otras = round(sum(otras) / len(otras)) if otras else 0

    # --- Hallazgo 2: lag de asignacion por mes
    lag = data.get("lag_asignacion_por_mes", {})
    filas_lag = "".join(
        f"<tr><td data-v='{mo}'>{mes_label(mo)}</td><td data-v='{v['mediana_horas']}'>{v['mediana_horas']:.1f} h</td>"
        f"<td data-v='{v['p90_horas']}'>{v['p90_horas']:.1f} h</td></tr>"
        for mo, v in sorted(lag.items()) if mo.startswith(str(data["anio_reporte"])) and v["n"] >= 50
    )

    # --- Hallazgo 3: individuales vs consolidadas por mes + friccion de consolidacion
    pobl = data["estricto"].get("por_mes_poblacion", {})
    filas_pobl = "".join(
        f"<tr><td data-v='{mo}'>{mes_label(mo)}</td>"
        f"<td data-v='{v['individuales']['pct']}' style='color:{color_por_pct(v['individuales']['pct'])};font-weight:700'>{fmt_pct(v['individuales']['pct'])}</td>"
        f"<td data-v='{v['individuales']['evaluables']}'>{fmt_n(v['individuales']['evaluables'])}</td>"
        f"<td data-v='{v['consolidadas']['pct']}' style='color:{color_por_pct(v['consolidadas']['pct'])};font-weight:700'>{fmt_pct(v['consolidadas']['pct'])}</td>"
        f"<td data-v='{v['consolidadas']['evaluables']}'>{fmt_n(v['consolidadas']['evaluables'])}</td></tr>"
        for mo, v in sorted(pobl.items())
    )

    fr = data.get("consolidadas_friccion", {})
    fr_cons = fr.get("tasa_consolidadas", {})
    fr_ind = fr.get("tasa_individuales", {})
    fr_neto = fr.get("tasa_consolidadas_neto", {})
    fr_af_fp = fr.get("afectadas_con_factura_pendiente", {})
    fr_ct_fp = fr.get("control_con_factura_pendiente", {})
    fr_af_al = fr.get("afectadas_con_armado_lento", {})
    fr_ct_al = fr.get("control_con_armado_lento", {})
    filas_fr_mes = "".join(
        f"<tr><td data-v='{mo}'>{mes_label(mo)}</td>"
        f"<td data-v='{v['total']}'>{fmt_n(v['total'])}</td>"
        f"<td data-v='{v['factura_pendiente']}'>{fmt_n(v['factura_pendiente'])}</td>"
        f"<td data-v='{v['armado_lento']}'>{fmt_n(v['armado_lento'])}</td></tr>"
        for mo, v in sorted(fr.get("por_mes", {}).items())
    )

    # --- Hallazgo 4: kilos excedentes por semana -- ¿hace falta un vuelo
    # extra? (pedido de Jorge, 2026-09-01, 7ma iteracion). Usa
    # capacidad_por_semana (kg_ingreso = lo que efectivamente voló esa
    # semana = la capacidad real; kg_podria = demanda). El "vuelo promedio"
    # (kg_ingreso / vuelo real, sobre TODOS los vuelos del año) es la vara
    # para estimar cuántos vuelos adicionales de tamaño típico se
    # necesitarían para absorber el excedente de cada semana -- no hay un
    # límite de kg "oficial" por vuelo en los datos, así que se usa el
    # tamaño real observado como proxy de la capacidad típica de un vuelo.
    cap_vuelos = data.get("capacidad_por_vuelo", [])
    cap_semanas = data.get("capacidad_por_semana", [])
    kg_vuelo_prom = (sum(c["kg_ingreso"] for c in cap_vuelos) / len(cap_vuelos)) if cap_vuelos else 0

    filas_kg = []
    for c in sorted(cap_semanas, key=lambda c: c["semana"]):
        kg_exced = round(max(0, c["kg_podria"] - c["kg_ingreso"]), 1)
        vuelos_extra = (kg_exced / kg_vuelo_prom) if kg_vuelo_prom else 0
        filas_kg.append({**c, "kg_exced": kg_exced, "vuelos_extra": vuelos_extra})

    filas_capacidad_kg = "".join(
        f"<tr><td data-v='{f['semana']}'>{semana_label(f['semana'])}</td>"
        f"<td data-v='{f['kg_ingreso']}'>{fmt_kg(f['kg_ingreso'])}</td>"
        f"<td data-v='{f['kg_podria']}'>{fmt_kg(f['kg_podria'])}</td>"
        f"<td data-v='{f['kg_exced']}' style='color:{color_por_pct(f['kg_exced'] / kg_vuelo_prom * 100 if kg_vuelo_prom else 0)};font-weight:700'>{fmt_kg(f['kg_exced'])}</td>"
        f"<td data-v='{f['vuelos_extra']}'>{f['vuelos_extra']:.1f}</td></tr>"
        for f in filas_kg
    )

    total_kg_exced = sum(f["kg_exced"] for f in filas_kg)
    prom_kg_exced_semana = round(total_kg_exced / len(filas_kg)) if filas_kg else 0
    semanas_necesitan_vuelo = sum(1 for f in filas_kg if f["vuelos_extra"] >= 1)
    peor_semana_kg = max(filas_kg, key=lambda f: f["kg_exced"]) if filas_kg else None

    return f"""
  <p class="sub">
    Por qué mayo y junio muestran una tasa de guías afectadas tan alta respecto al resto del
    año, y si hace falta un vuelo adicional a la semana. Se probaron tres hipótesis con los
    datos — pedido explícito de Jorge de separar las guías <b>consolidadas</b> (varias guías
    originales fundidas en una sola antes de volar) del resto para analizarlas aparte, en vez
    de mezclarlas — y se agregó un cuarto punto con los kilos excedentes semana a semana.
  </p>

  <section>
    <h2>1. No es un problema de capacidad total de vuelos (descartado)</h2>
    <p class="sub" style="margin-bottom:14px">
      Comparando semana a semana la demanda acumulada (guías evaluables) contra la oferta
      acumulada (suma de guías realmente transportadas por los vuelos del calendario), la
      oferta {"nunca" if oferta_nunca_bajo_demanda else "casi nunca"} queda por debajo de la
      demanda acumulada en {data['anio_reporte']} — no se arrastra un déficit estructural de
      asientos. La única excepción real es la semana del <b>25 de mayo</b> (Memorial Day en
      EE.UU.), donde los vuelos transportaron muy por debajo del promedio.
    </p>
    <div class="kpis">
      <div class="kpi"><div class="v">{"Sí" if oferta_nunca_bajo_demanda else "Casi"}</div><div class="l">Oferta acumulada ≥ demanda acumulada todo el año</div></div>
      <div class="kpi bad"><div class="v">{fmt_n(oferta_25may)}</div><div class="l">Guías transportadas semana 25-may (vs. {fmt_n(oferta_prom_otras)} promedio otras semanas)</div></div>
      <div class="kpi"><div class="v">{fmt_n(demanda_25may)}</div><div class="l">Guías que necesitaban volar esa semana</div></div>
    </div>
  </section>

  <section>
    <h2>2. Causa real y sistemática: se alargó el tiempo de asignación a guía madre</h2>
    <p class="sub" style="margin-bottom:14px">
      Tiempo entre que una guía queda "lista para volar" (pago + factura) y el momento en que
      el sistema la asigna a una guía madre. La mediana pasa de menos de 2 horas (dic-mar) a
      4-11,5 horas (may-jul). Consistente con esto: el <b>85% de los incidentes</b> (definición
      "vuelo exacto") se saltan exactamente UN vuelo — alcanzan el siguiente, no se quedan
      varados varias semanas — lo que apunta a que quedan listas justo después del corte de
      manifiesto del vuelo que les tocaba, no a una escasez de vuelos.
    </p>
    <div class="table-wrap" style="max-height:340px">
      <table id="tabla-lag" class="sortable"><thead><tr>
        <th onclick="ordenarTabla('tabla-lag',0,'str')">Mes</th>
        <th onclick="ordenarTabla('tabla-lag',1,'num')">Mediana espera asignación</th>
        <th onclick="ordenarTabla('tabla-lag',2,'num')">P90 espera asignación</th>
      </tr></thead><tbody>{filas_lag}</tbody></table>
    </div>
  </section>

  <section>
    <h2>3. Guías consolidadas: la fricción del proceso de consolidación existe, pero ya no genera brecha de cumplimiento</h2>
    <p class="sub" style="margin-bottom:14px">
      El correo (etiqueta Gmail <code>1. 2ebox/Consolidaciones</code>, 318 mensajes, 2021-2026)
      muestra que la consolidación se opera fuera del sistema: la ejecutiva lista las guías a
      mano en un mail con un tope FOB por bulto, Miami arma los bultos "al ojo", las facturas
      llegan goteando y a veces obligan a rearmar los bultos completos (caso CL29319000: 8
      correos en 2,5 h, 4 días parado hasta marcarlo "urgente"), y el registro en el módulo
      "Consolidaciones" se llena <b>después</b>, como acta. Esa fricción es real. La pregunta
      cuantitativa: ¿se traduce en que las guías-bulto no vuelan a tiempo más que las
      individuales? Con los datos 2026, y tras corregir el corte de manifiesto (un pago que
      llega pasado mediodía del día del vuelo ya no alcanza ese manifiesto), la respuesta es
      <b>no</b>.
    </p>
    <div class="kpis">
      <div class="kpi"><div class="v">{fmt_pct(fr_ind.get('pct', 0))}</div><div class="l">Individuales que no volaron en su vuelo exacto ({fmt_n(fr_ind.get('afectadas', 0))} de {fmt_n(fr_ind.get('evaluables', 0))})</div></div>
      <div class="kpi"><div class="v">{fmt_pct(fr_cons.get('pct', 0))}</div><div class="l">Consolidadas (guía-bulto) que no volaron en su vuelo exacto ({fmt_n(fr_cons.get('afectadas', 0))} de {fmt_n(fr_cons.get('evaluables', 0))})</div></div>
      <div class="kpi"><div class="v">{fmt_pct(fr_neto.get('pct', 0))}</div><div class="l">Consolidadas "neto" — descontando las {fmt_n(fr_af_fp.get('n', 0))} con factura pendiente al cerrar el bulto</div></div>
    </div>
    <p class="sub" style="margin-bottom:14px">
      Antes de este análisis las consolidadas se veían ~2x peor que las individuales; casi todo
      ese exceso era el artefacto del corte de manifiesto (las guías-bulto quedan "listas" en la
      tarde, cuando se arma el bulto, y se les asignaba por error el vuelo de ese mismo día). Con
      el cálculo corregido, individuales y consolidadas están prácticamente iguales
      ({fmt_pct(fr_ind.get('pct', 0))} vs {fmt_pct(fr_cons.get('pct', 0))}). Queda una brecha
      residual sólo en temporada baja (enero-febrero) — ver tabla por mes.
    </p>
    <div class="table-wrap" style="max-height:300px">
      <table id="tabla-poblacion" class="sortable"><thead><tr>
        <th onclick="ordenarTabla('tabla-poblacion',0,'str')">Mes</th>
        <th onclick="ordenarTabla('tabla-poblacion',1,'num')">% individuales</th>
        <th onclick="ordenarTabla('tabla-poblacion',2,'num')">Guías individuales</th>
        <th onclick="ordenarTabla('tabla-poblacion',3,'num')">% consolidadas</th>
        <th onclick="ordenarTabla('tabla-poblacion',4,'num')">Guías consolidadas</th>
      </tr></thead><tbody>{filas_pobl}</tbody></table>
    </div>

    <div class="card" style="margin-top:18px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px">
      <h3 style="font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--ink-faint);margin:0 0 10px">
        Señales de fricción de consolidación — ninguna predice el atraso
      </h3>
      <p class="sub" style="margin:0 0 12px">
        Se probó con datos si las dos señales medibles del cuello de botella del correo predicen
        que una guía-bulto no vuele a tiempo. Se comparan las guías-bulto afectadas contra el
        grupo de control (las que <b>sí</b> volaron en su vuelo exacto). Si el porcentaje es
        parecido en los dos grupos, la señal no discrimina.
      </p>
      <div class="table-wrap" style="max-height:none;margin-bottom:14px">
        <table><thead><tr>
          <th>Señal</th><th>En las afectadas</th><th>En las que volaron OK</th><th>¿Discrimina?</th>
        </tr></thead><tbody>
          <tr>
            <td>Consolidación cerrada con <b>factura pendiente</b> (FOB $0)</td>
            <td>{fmt_pct(fr_af_fp.get('pct', 0))} ({fmt_n(fr_af_fp.get('n', 0))})</td>
            <td>{fmt_pct(fr_ct_fp.get('pct', 0))} ({fmt_n(fr_ct_fp.get('n', 0))})</td>
            <td style="color:var(--warn)">Apenas</td>
          </tr>
          <tr>
            <td><b>Armado lento</b>: &gt;3 días entre crear el bulto y quedar lista</td>
            <td>{fmt_pct(fr_af_al.get('pct', 0))} ({fmt_n(fr_af_al.get('n', 0))})</td>
            <td>{fmt_pct(fr_ct_al.get('pct', 0))} ({fmt_n(fr_ct_al.get('n', 0))})</td>
            <td style="color:var(--ink-faint)">No</td>
          </tr>
        </tbody></table>
      </div>
      <p class="sub" style="margin:0 0 12px">
        Por eso <b>no se descuentan del reporte automáticamente</b>. El criterio
        <b>"neto de consolidación"</b> de la pestaña Consolidadas solo resta las guías con
        factura pendiente al cerrar el bulto (dato de sistema, inequívoco: la factura llegó
        tarde y con eso la fecha "lista" — que exige factura en Miami — quedó tironeada). Las
        demás señales quedan como <b>filtros</b> en la pestaña "Guías afectadas" (Población,
        Tamaño de consolidación, Señal de fricción) para explorarlas por segmento.
      </p>
      <p class="sub" style="margin:0 0 8px"><b>Guías-bulto afectadas con alguna señal de fricción, por mes:</b></p>
      <div class="table-wrap" style="max-height:280px">
        <table id="tabla-friccion-mes" class="sortable"><thead><tr>
          <th onclick="ordenarTabla('tabla-friccion-mes',0,'str')">Mes</th>
          <th onclick="ordenarTabla('tabla-friccion-mes',1,'num')">Afectadas (guía-bulto)</th>
          <th onclick="ordenarTabla('tabla-friccion-mes',2,'num')">…con factura pendiente</th>
          <th onclick="ordenarTabla('tabla-friccion-mes',3,'num')">…con armado lento</th>
        </tr></thead><tbody>{filas_fr_mes}</tbody></table>
      </div>
      <p class="sub" style="margin:12px 0 0">
        Diagnóstico completo del proceso de consolidación (cuellos de botella con evidencia
        datada, propuesta de flujo nuevo) en
        <code>Projects/2EBOX/Procesos-Logistica-Operacion/docs/FLUJO_CONSOLIDACIONES.md</code> y
        <code>analisis_vuelos_no_volados/CONSOLIDACIONES_CORREO.md</code>. Mover la decisión de
        consolidación adentro del sistema sigue teniendo sentido operativo (menos correos, menos
        errores de asignación), aunque el impacto medible sobre el cumplimiento de vuelos sea hoy
        marginal.
      </p>
    </div>
  </section>

  <section>
    <h2>4. Kilos excedentes por semana — ¿hace falta un vuelo extra?</h2>
    <p class="sub" style="margin-bottom:14px">
      Por semana: kilos que efectivamente volaron (capacidad real) vs. kilos que había
      disponibles para volar (demanda). El excedente es lo que se quedó esperando por falta de
      cupo. "Vuelos extra estimados" divide ese excedente por el tamaño promedio de un vuelo
      real este año ({fmt_kg(kg_vuelo_prom)}) — sirve como referencia de cuántos vuelos de
      tamaño típico harían falta para absorberlo, no un cálculo exacto de capacidad de bodega
      de ningún avión puntual. Ver pestaña <b>"Capacidad de Vuelos"</b> para el detalle a nivel
      de guías (no kilos) y por vuelo individual.
    </p>
    <p class="sub" style="margin-bottom:14px">
      <b>Ojo con los kilos específicamente:</b> a diferencia del conteo de guías, los kilos
      excedentes están muy concentrados en unos pocos paquetes atípicamente pesados (hasta
      1.638 kg — la mediana real es ~2 kg) que quedan varias semanas seguidas sin volar y se
      suman una y otra vez mientras siguen esperando — solo los 10 paquetes más pesados del año
      explican ~36% del total de kilos afectados. Para decidir si hace falta un vuelo extra
      <b>regular a la semana</b>, el conteo de guías (pestaña "Capacidad de Vuelos") es la señal
      más confiable; los kilos de abajo dan el orden de magnitud, pero un puñado de paquetes
      pesados puntuales pueden inflar el total sin que sea un problema de capacidad semanal
      recurrente.
    </p>
    <div class="kpis">
      <div class="kpi bad"><div class="v">{fmt_kg(total_kg_exced)}</div><div class="l">Kilos excedentes acumulados (2026)</div></div>
      <div class="kpi"><div class="v">{fmt_kg(prom_kg_exced_semana)}</div><div class="l">Promedio de excedente por semana</div></div>
      <div class="kpi"><div class="v">{semanas_necesitan_vuelo} de {len(filas_kg)}</div><div class="l">Semanas con excedente ≥ 1 vuelo completo</div></div>
      <div class="kpi bad"><div class="v">{semana_label(peor_semana_kg['semana']) if peor_semana_kg else 's/d'}</div><div class="l">Peor semana ({fmt_kg(peor_semana_kg['kg_exced']) if peor_semana_kg else 's/d'} de excedente)</div></div>
    </div>
    <div class="table-wrap" style="max-height:340px">
      <table id="tabla-kg-excedente" class="sortable"><thead><tr>
        <th onclick="ordenarTabla('tabla-kg-excedente',0,'str')">Semana (lunes)</th>
        <th onclick="ordenarTabla('tabla-kg-excedente',1,'num')">Kilos ingresados</th>
        <th onclick="ordenarTabla('tabla-kg-excedente',2,'num')">Kilos que podrían</th>
        <th onclick="ordenarTabla('tabla-kg-excedente',3,'num')">Kilos excedente</th>
        <th onclick="ordenarTabla('tabla-kg-excedente',4,'num')">Vuelos extra estimados</th>
      </tr></thead><tbody>{filas_capacidad_kg}</tbody></table>
    </div>
  </section>
"""


def build_wrapper_subtabs(dom_id_base, contenido_estricto, contenido_semana, nota_arriba,
                          contenido_neto=None, label_neto="Neto"):
    """Envuelve dos o tres build_seccion() (vuelo exacto / misma semana /
    opcionalmente 'neto') en un sub-toggle propio, para usar dentro de una
    pestaña principal que no es 'estricto'/'semana' directamente (ej. la
    pestaña Consolidadas). Si contenido_neto es None, solo 2 sub-toggles
    (comportamiento original, usado por la pestaña Individuales).

    nota_arriba va SIN envolver en <p class="sub"> (a diferencia de antes,
    2026-09-02) -- quien llama decide el envoltorio: texto plano corto sigue
    pasando su propio <p class="sub">...</p>, pero ahora también se puede
    pasar el HTML de explica_panel()/explica_diagrama() (columnas/diagrama),
    que rompería semánticamente metido dentro de un <p> (son <div>)."""
    btn_neto = (
        f'<button id="subtab-btn-{dom_id_base}-neto" onclick="verSubtab(\'{dom_id_base}\',\'neto\')">{label_neto}</button>'
        if contenido_neto is not None else ""
    )
    div_neto = (
        f'<div id="subtab-{dom_id_base}-neto" class="subtab">{contenido_neto}</div>'
        if contenido_neto is not None else ""
    )
    return f"""
  {nota_arriba}
  <div class="toggle" style="margin-bottom:18px">
    <button id="subtab-btn-{dom_id_base}-estricto" class="active" onclick="verSubtab('{dom_id_base}','estricto')">Vuelo exacto</button>
    <button id="subtab-btn-{dom_id_base}-semana" onclick="verSubtab('{dom_id_base}','semana')">Misma semana</button>
    {btn_neto}
  </div>
  <div id="subtab-{dom_id_base}-estricto" class="subtab active">{contenido_estricto}</div>
  <div id="subtab-{dom_id_base}-semana" class="subtab">{contenido_semana}</div>
  {div_neto}
"""


def build_guias_afectadas(scope="estricto", titulo_bloque="vuelo exacto", dom_id=None):
    """Pestaña "Guías afectadas": tabla completa guía a guía (todas las
    afectadas, individuales + consolidadas -- data[scope] ya es la suma
    exacta de individuales+consolidadas para ese criterio, ver
    bloque_definicion() en el extractor: es la misma poblacion sin filtrar,
    asi que el total SIEMPRE coincide con sumar las dos pestañas separadas),
    filtrable por mes, ejecutiva, convenio, población, tamaño de
    consolidación y señal de fricción, con KPIs resumen que se recalculan
    según los filtros activos. Renderizado 100% en el cliente (JS) a partir
    de un array embebido -- 1000+ filas, liviano de sobra para eso.

    scope = 'estricto' | 'semana' -- pedido de Jorge (2026-09-02): antes esta
    pestaña solo mostraba "vuelo exacto" (con una nota redirigiendo a
    Conclusiones para "misma semana", que no tenía el detalle completo).
    Ahora se llama dos veces (una por scope) y se envuelven con
    build_wrapper_subtabs(), igual que Individuales/Consolidadas. dom_id
    (por defecto = scope) sufija TODOS los ids y nombres de función/variable
    JS generados acá -- obligatorio pasarlo distinto en cada llamada o los
    dos <script> quedan pisándose variables globales del mismo nombre."""
    sfx = dom_id or scope
    # Universo COMPLETO evaluable 2026 (afectadas Y no afectadas) -- pedido
    # de Jorge (2026-09-03): quiere denominadores reales por filtro ("36
    # guías afectadas de 300 evaluadas", no solo "36"). Cada fila trae "af"
    # (bool, si es afectada bajo ESTE scope) -- el universo se usa para los
    # denominadores, la tabla y el numerador siguen mostrando solo las
    # afectadas.
    universo = data["universo_evaluable_2026"]

    def clasificar_ejecutiva(conv):
        if conv in KATHY_CONVENIOS:
            return "Kathy"
        if conv in TIARE_CONVENIOS:
            return "Tiare"
        return "Otros"

    def _parse_iso(s):
        if not s:
            return None
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    vuelos_dt = sorted(_parse_iso(v["ts"]) for v in data["vuelos_calendario"])
    generado_dt = _parse_iso(data["generado"])

    def _dato_blando(ve_dt, vr_dt):
        """Calcula, para una guía afectada, cuántos vuelos regulares salieron
        entre su vuelo esperado y el vuelo en que realmente voló (o hasta hoy
        si aún no vuela), y arma un texto en simple explicando el motivo.
        Se cuenta el propio vuelo esperado como "saltado" porque la guía no
        se subió a él -- por eso las afectadas parten siempre en >= 1."""
        limite_dt = vr_dt or generado_dt
        saltados = sum(1 for ts in vuelos_dt if ve_dt <= ts < limite_dt)
        dias = max(0, round((limite_dt - ve_dt).total_seconds() / 86400))
        if vr_dt:
            motivo = (
                f"Voló {dias} día{'s' if dias != 1 else ''} después de lo que le "
                f"correspondía -- se saltó {saltados} vuelo{'s' if saltados != 1 else ''} "
                f"antes de subirse."
            )
            if saltados == 1:
                categoria = "Saltó 1 vuelo"
            elif saltados == 2:
                categoria = "Saltó 2 vuelos"
            else:
                categoria = "Saltó 3+ vuelos"
        else:
            motivo = (
                f"Todavía no ha volado -- lleva {dias} día{'s' if dias != 1 else ''} "
                f"esperando desde que le tocaba, y {saltados} vuelo{'s' if saltados != 1 else ''} "
                f"salieron sin ella."
            )
            categoria = "Aún no vuela"
        return motivo, categoria, saltados, dias

    # Etiquetas de friccion de consolidacion (T-0006). Descriptivas: senalan si
    # el atraso de una guia-bulto pudo originarse aguas arriba, en el proceso
    # de consolidacion, en vez de en la operacion de vuelo. Ver Conclusiones
    # punto 3 -- en los datos ninguna de las dos senales predice el atraso
    # mejor que el azar, quedan como filtro exploratorio.
    FRICCION_LABEL = {
        "factura_pendiente": "Factura pendiente al cerrar",
        "armado_lento": "Armado lento (>3 días)",
        "": "Sin señal / individual",
    }

    def _tam_bucket(n):
        if not n:
            return "Individual"
        if n <= 3:
            return "2-3 guías"
        if n <= 6:
            return "4-6 guías"
        if n <= 10:
            return "7-10 guías"
        return "11+ guías"

    filas = []
    for r in universo:
        mo = r["vuelo_esperado"][:7]
        conv = r["convenio"] or ""
        afectada = bool(r["no_volo_" + scope])
        if afectada:
            ve_dt = _parse_iso(r["vuelo_esperado"])
            vr_dt = _parse_iso(r["vuelo_real"])
            motivo, categoria, saltados, dias = _dato_blando(ve_dt, vr_dt)
        else:
            # No afectada -- "motivo" no aplica (no se subieron KPIs de por
            # qué, porque no hay atraso que explicar). No cuesta calcular
            # _dato_blando() para las ~4.400 filas del universo cuando solo
            # ~700-900 son afectadas.
            motivo, categoria, saltados, dias = "", "", 0, 0
        # Campos que solo se usan para RENDERIZAR la fila en la tabla (que
        # solo muestra afectadas) -- se omiten (None) en las no afectadas
        # para no engordar el JSON embebido con ~3.700 filas de datos que
        # nunca se muestran (el universo completo por scope pasó de ~965 a
        # ~4.392 filas al agregar los denominadores, 2026-09-03).
        filas.append({
            "n": r["n_guia"] if afectada else None,
            "mo": mo,
            "eje": clasificar_ejecutiva(conv),
            "conv": conv,
            "cas": r["casilla"] or "",
            "pob": "Consolidada" if r["consolidada"] else "Individual",
            "consn": r.get("cons_n_guias") or 0,
            "consid": r.get("cons_id") if afectada else None,
            "tam": _tam_bucket(r.get("cons_n_guias") if r["consolidada"] else 0),
            "fri": r.get("cons_friccion") or "",
            "friL": FRICCION_LABEL.get(r.get("cons_friccion") or "", "Sin señal / individual"),
            "armado": r.get("armado_lag_dias") if afectada else None,
            "kg": round(r["peso"] or 0, 1),
            "awb": (r.get("awb") or "") if afectada else None,
            "aerolinea": (r.get("aerolinea") or "") if afectada else None,
            "ve": r["vuelo_esperado"][:10] if afectada else None,
            "vr": (r["vuelo_real"][:10] if r["vuelo_real"] else None) if afectada else None,
            "mot": categoria,
            "motivo": motivo,
            "saltados": saltados,
            "dias": dias,
            "af": afectada,
        })

    # Las opciones de cada filtro (qué meses/ejecutivas/convenios/etc.
    # aparecen como checkbox, y el numerito al lado) se siguen sacando SOLO
    # de las afectadas -- igual que antes de agregar el universo completo.
    # Esta pestaña es para acotar guías AFECTADAS; un convenio con 300
    # guías evaluables pero 0 afectadas no aporta como filtro acá.
    afectadas_todas = [r for r in filas if r["af"]]
    meses_presentes = sorted(set(r["mo"] for r in afectadas_todas))
    convenio_counts = Counter(r["conv"] for r in afectadas_todas)
    convenios_ordenados = sorted(convenio_counts.items(), key=lambda kv: -kv[1])
    ejecutiva_counts = Counter(r["eje"] for r in afectadas_todas)
    motivo_counts = Counter(r["mot"] for r in afectadas_todas)
    ORDEN_MOTIVOS = ["Saltó 1 vuelo", "Saltó 2 vuelos", "Saltó 3+ vuelos", "Aún no vuela"]
    motivos_presentes = [m for m in ORDEN_MOTIVOS if motivo_counts.get(m)]

    pob_counts = Counter(r["pob"] for r in afectadas_todas)
    tam_counts = Counter(r["tam"] for r in afectadas_todas)
    ORDEN_TAM = ["Individual", "2-3 guías", "4-6 guías", "7-10 guías", "11+ guías"]
    tam_presentes = [t for t in ORDEN_TAM if tam_counts.get(t)]
    fri_counts = Counter(r["friL"] for r in afectadas_todas)
    ORDEN_FRI = ["Factura pendiente al cerrar", "Armado lento (>3 días)", "Sin señal / individual"]
    fri_presentes = [f for f in ORDEN_FRI if fri_counts.get(f)]

    conteo_por_mes = Counter(r["mo"] for r in afectadas_todas)
    checkboxes_meses = "".join(
        f'<label class="chk"><input type="checkbox" class="filtro-mes" value="{mo}" checked>'
        f'{mes_label(mo)}<span class="chk-n">{conteo_por_mes[mo]}</span></label>'
        for mo in meses_presentes
    )
    checkboxes_ejecutivas = "".join(
        f'<label class="chk"><input type="checkbox" class="filtro-eje" value="{eje}" checked>'
        f'{eje}<span class="chk-n">{ejecutiva_counts.get(eje, 0)}</span></label>'
        for eje in ("Kathy", "Tiare", "Otros")
    )
    checkboxes_convenios = "".join(
        f'<label class="chk"><input type="checkbox" class="filtro-convenio" value="{html.escape(conv)}" checked>'
        f'{html.escape(conv) or "(sin convenio)"}<span class="chk-n">{cnt}</span></label>'
        for conv, cnt in convenios_ordenados
    )
    checkboxes_motivos = "".join(
        f'<label class="chk"><input type="checkbox" class="filtro-motivo" value="{html.escape(mot)}" checked>'
        f'{html.escape(mot)}<span class="chk-n">{motivo_counts[mot]}</span></label>'
        for mot in motivos_presentes
    )
    checkboxes_pob = "".join(
        f'<label class="chk"><input type="checkbox" class="filtro-pob" value="{p}" checked>'
        f'{p}<span class="chk-n">{pob_counts.get(p, 0)}</span></label>'
        for p in ("Individual", "Consolidada")
    )
    checkboxes_tam = "".join(
        f'<label class="chk"><input type="checkbox" class="filtro-tam" value="{html.escape(t)}" checked>'
        f'{html.escape(t)}<span class="chk-n">{tam_counts[t]}</span></label>'
        for t in tam_presentes
    )
    checkboxes_fri = "".join(
        f'<label class="chk"><input type="checkbox" class="filtro-fri" value="{html.escape(f)}" checked>'
        f'{html.escape(f)}<span class="chk-n">{fri_counts[f]}</span></label>'
        for f in fri_presentes
    )

    def filtro_card_head(titulo, grupo):
        return (
            '<div class="filtro-card-head">'
            f'<div class="filtro-card-title" onclick="gaToggleCard_{sfx}(this)">'
            '<span class="filtro-chevron">&#9662;</span>'
            f'<h3>{titulo}</h3></div>'
            '<div class="filtro-acciones">'
            f'<button onclick="gaSeleccionar_{sfx}(\'{grupo}\',\'todos\')">Todos</button>'
            f'<button onclick="gaSeleccionar_{sfx}(\'{grupo}\',\'ninguno\')">Ninguno</button>'
            "</div></div>"
        )

    datos_json = json.dumps(filas, ensure_ascii=False).replace("</", "<\\/")

    return f"""
  <p class="sub">
    Detalle guía a guía de las {fmt_n(len(afectadas_todas))} guías afectadas en 2026 bajo el
    criterio "{titulo_bloque}", de {fmt_n(len(universo))} guías evaluables en total. Filtra por
    fecha, ejecutiva, convenio, población, tamaño de consolidación o señal de fricción a la
    izquierda — los KPIs (con su denominador real para ese filtro) y la tabla se recalculan
    solos.
  </p>

  <div class="ga-layout" id="ga-wrap-{sfx}">
    <aside class="ga-sidebar">
      <div class="filtro-card">
        {filtro_card_head("Fechas", "mes")}
        <div class="chk-list chk-list-vert">{checkboxes_meses}</div>
      </div>
      <div class="filtro-card">
        {filtro_card_head("Ejecutivas", "eje")}
        <div class="chk-list chk-list-vert">{checkboxes_ejecutivas}</div>
      </div>
      <div class="filtro-card">
        {filtro_card_head("Población", "pob")}
        <div class="chk-list chk-list-vert">{checkboxes_pob}</div>
      </div>
      <div class="filtro-card">
        {filtro_card_head("Tamaño consolidación", "tam")}
        <div class="chk-list chk-list-vert">{checkboxes_tam}</div>
      </div>
      <div class="filtro-card">
        {filtro_card_head("Señal de fricción consolidación", "fri")}
        <div class="chk-list chk-list-vert">{checkboxes_fri}</div>
      </div>
      <div class="filtro-card">
        {filtro_card_head("Motivos", "motivo")}
        <div class="chk-list chk-list-vert">{checkboxes_motivos}</div>
      </div>
      <div class="filtro-card">
        {filtro_card_head("Códigos convenio", "convenio")}
        <div class="chk-list chk-list-vert chk-list-scroll">{checkboxes_convenios}</div>
      </div>
    </aside>

    <div class="ga-content">
      <div class="kpis" id="ga-kpis-{sfx}">
        <div class="kpi bad"><div class="v" id="ga-kpi-pct-{sfx}">—</div><div class="l">% afectadas sobre este filtro</div></div>
        <div class="kpi"><div class="v" id="ga-kpi-n-{sfx}">—</div><div class="l">Guías afectadas / evaluadas</div></div>
        <div class="kpi"><div class="v" id="ga-kpi-kg-{sfx}">—</div><div class="l">Kilos afectados / evaluados</div></div>
        <div class="kpi"><div class="v" id="ga-kpi-clientes-{sfx}">—</div><div class="l">Clientes afectados / evaluados</div></div>
      </div>

      <div class="table-wrap" style="max-height:520px">
        <table id="tabla-guias-afectadas-{sfx}" class="sortable">
          <thead><tr>
            <th onclick="gaOrdenar_{sfx}(0)">N° Guía</th>
            <th onclick="gaOrdenar_{sfx}(1)">Mes</th>
            <th onclick="gaOrdenar_{sfx}(2)">Convenio</th>
            <th onclick="gaOrdenar_{sfx}(3)">Casilla</th>
            <th onclick="gaOrdenar_{sfx}(4)">Población</th>
            <th onclick="gaOrdenar_{sfx}(5)">Consol. (n° guías)</th>
            <th onclick="gaOrdenar_{sfx}(6)">Señal fricción</th>
            <th onclick="gaOrdenar_{sfx}(7)">Kilos</th>
            <th onclick="gaOrdenar_{sfx}(8)">Vuelo esperado</th>
            <th onclick="gaOrdenar_{sfx}(9)">N° vuelo / AWB</th>
            <th onclick="gaOrdenar_{sfx}(10)">Vuelo real</th>
            <th onclick="gaOrdenar_{sfx}(11)">Motivo</th>
          </tr></thead>
          <tbody id="ga-tbody-{sfx}"></tbody>
        </table>
      </div>
      <p class="empty-note" id="ga-empty-{sfx}" style="display:none">Sin guías para este filtro.</p>
    </div>
  </div>

  <script>
  (function () {{
    var WRAP = '#ga-wrap-{sfx} ';
    // GA_DATOS = universo COMPLETO evaluable (afectadas Y no afectadas,
    // campo "af"). La tabla y el numerador de los KPIs solo muestran las
    // afectadas; el universo filtrado da el denominador real ("36 de 300").
    var GA_DATOS = {datos_json};
    var GA_MESES_LABEL = {json.dumps({mo: mes_label(mo) for mo in meses_presentes}, ensure_ascii=False)};
    var gaSort = {{ col: 0, asc: true }};

    function gaFmtN(n) {{ return n.toLocaleString('es-CL'); }}
    function gaFmtKg(n) {{ return Math.round(n).toLocaleString('es-CL') + ' kg'; }}
    function gaFmtDeN(n, total) {{ return gaFmtN(n) + ' de ' + gaFmtN(total); }}
    function gaFmtDeKg(kg, total) {{ return gaFmtN(Math.round(kg)) + ' de ' + gaFmtN(Math.round(total)) + ' kg'; }}
    function gaFmtFecha(iso) {{
      if (!iso) return '';
      var p = iso.split('-');
      return p[2] + '-' + p[1] + '-' + p[0];
    }}
    function gaUrlGuia(n) {{ return 'https://2020.2ebox.com/guias-hijas/ver/' + n; }}
    function gaFmtAwb(r) {{
      if (!r.awb) return '<span style="color:var(--ink-faint)">s/d</span>';
      return r.awb + (r.aerolinea ? ' <span style="color:var(--ink-faint)">(' + r.aerolinea + ')</span>' : '');
    }}

    function gaChecked(cls) {{
      var s = {{}};
      Array.prototype.slice.call(document.querySelectorAll(WRAP + cls + ':checked')).forEach(function (c) {{ s[c.value] = true; }});
      return s;
    }}
    function gaFiltrar() {{
      var mesesSet = gaChecked('.filtro-mes');
      var ejeSet = gaChecked('.filtro-eje');
      var convSet = gaChecked('.filtro-convenio');
      var motSet = gaChecked('.filtro-motivo');
      var pobSet = gaChecked('.filtro-pob');
      var tamSet = gaChecked('.filtro-tam');
      var friSet = gaChecked('.filtro-fri');
      // "universo": todas las guías evaluables (afectadas o no) que caen en
      // los filtros de atributo (fecha/ejecutiva/convenio/población/tamaño/
      // fricción) -- es el DENOMINADOR real de los KPIs. El filtro "Motivo"
      // no se aplica acá a propósito: no es un atributo de la guía en sí,
      // solo tiene sentido para las que SÍ están afectadas (ver más abajo).
      var universo = GA_DATOS.filter(function (r) {{
        return mesesSet[r.mo] && ejeSet[r.eje] && convSet[r.conv]
          && pobSet[r.pob] && tamSet[r.tam] && friSet[r.friL];
      }});
      // "afectadas": del universo de arriba, solo las que además están
      // afectadas bajo este criterio Y pasan el filtro de Motivo -- es lo
      // que se ve en la tabla y el NUMERADOR de los KPIs.
      var afectadas = universo.filter(function (r) {{ return r.af && motSet[r.mot]; }});
      return {{ universo: universo, afectadas: afectadas }};
    }}

    window.gaOrdenar_{sfx} = function (col) {{
      gaSort.asc = (gaSort.col === col) ? !gaSort.asc : true;
      gaSort.col = col;
      gaRender();
    }};

    var GA_COLS = ['n', 'mo', 'conv', 'cas', 'pob', 'consn', 'friL', 'kg', 've', 'awb', 'vr', 'saltados'];
    function gaFmtCons(r) {{
      if (!r.consn) return '<span style="color:var(--ink-faint)">—</span>';
      var t = r.consn + (r.armado != null ? ' <span style="color:var(--ink-faint)">· armado ' + r.armado + 'd</span>' : '');
      return r.consid ? '<a href="https://2020.2ebox.com/consolidaciones/ver/' + r.consid + '" target="_blank" rel="noopener">' + t + '</a>' : t;
    }}
    function gaFmtFri(r) {{
      if (r.fri === 'factura_pendiente') return '<span style="color:var(--bad);font-weight:600">Factura pendiente</span>';
      if (r.fri === 'armado_lento') return '<span style="color:var(--warn)">Armado lento</span>';
      return '<span style="color:var(--ink-faint)">—</span>';
    }}

    function gaRender() {{
      var res = gaFiltrar();
      var universo = res.universo, afectadas = res.afectadas;
      var col = GA_COLS[gaSort.col];
      afectadas.sort(function (a, b) {{
        var va = a[col], vb = b[col];
        if (va === null) va = '';
        if (vb === null) vb = '';
        if (typeof va === 'number') {{
          return gaSort.asc ? va - vb : vb - va;
        }}
        va = String(va); vb = String(vb);
        if (va < vb) return gaSort.asc ? -1 : 1;
        if (va > vb) return gaSort.asc ? 1 : -1;
        return 0;
      }});

      var kgAf = 0, clientesAf = {{}};
      afectadas.forEach(function (r) {{ kgAf += r.kg; clientesAf[r.cas] = true; }});
      var nClientesAf = Object.keys(clientesAf).length;

      var kgTot = 0, clientesTot = {{}};
      universo.forEach(function (r) {{ kgTot += r.kg; clientesTot[r.cas] = true; }});
      var nClientesTot = Object.keys(clientesTot).length;

      document.getElementById('ga-kpi-pct-{sfx}').textContent = (universo.length ? (afectadas.length / universo.length * 100).toFixed(1) : '0') + '%';
      document.getElementById('ga-kpi-n-{sfx}').textContent = gaFmtDeN(afectadas.length, universo.length);
      document.getElementById('ga-kpi-kg-{sfx}').textContent = gaFmtDeKg(kgAf, kgTot);
      document.getElementById('ga-kpi-clientes-{sfx}').textContent = gaFmtDeN(nClientesAf, nClientesTot);

      var filas = afectadas.map(function (r) {{
        return '<tr><td><a href="' + gaUrlGuia(r.n) + '" target="_blank" rel="noopener">' + r.n + '</a></td><td>' + (GA_MESES_LABEL[r.mo] || r.mo) + '</td><td>' +
          (r.conv || '<span style="color:var(--ink-faint)">(sin convenio)</span>') + '</td><td>' + r.cas + '</td><td>' + r.pob +
          '</td><td>' + gaFmtCons(r) + '</td><td>' + gaFmtFri(r) +
          '</td><td>' + gaFmtKg(r.kg) + '</td><td>' + gaFmtFecha(r.ve) + '</td><td>' + gaFmtAwb(r) + '</td><td>' +
          (r.vr ? gaFmtFecha(r.vr) : '<span style="color:var(--bad)">aún no vuela</span>') + '</td><td class="ga-motivo">' + r.motivo + '</td></tr>';
      }});
      document.getElementById('ga-tbody-{sfx}').innerHTML = filas.join('');
      document.getElementById('ga-empty-{sfx}').style.display = afectadas.length ? 'none' : 'block';

      var ths = document.querySelectorAll('#tabla-guias-afectadas-{sfx} thead th');
      ths.forEach(function (h, i) {{
        h.classList.toggle('sorted-asc', i === gaSort.col && gaSort.asc);
        h.classList.toggle('sorted-desc', i === gaSort.col && !gaSort.asc);
      }});
    }}

    var GA_SELECTORES = {{ mes: '.filtro-mes', eje: '.filtro-eje', convenio: '.filtro-convenio', motivo: '.filtro-motivo', pob: '.filtro-pob', tam: '.filtro-tam', fri: '.filtro-fri' }};
    window.gaSeleccionar_{sfx} = function (grupo, modo) {{
      var boxes = document.querySelectorAll(WRAP + GA_SELECTORES[grupo]);
      boxes.forEach(function (c) {{
        if (modo === 'todos') c.checked = true;
        else if (modo === 'ninguno') c.checked = false;
      }});
      gaRender();
    }};

    window.gaToggleCard_{sfx} = function (el) {{
      el.closest('.filtro-card').classList.toggle('colapsado');
    }};

    document.querySelectorAll(WRAP + '.filtro-mes, ' + WRAP + '.filtro-eje, ' + WRAP + '.filtro-convenio, ' + WRAP + '.filtro-motivo, ' + WRAP + '.filtro-pob, ' + WRAP + '.filtro-tam, ' + WRAP + '.filtro-fri').forEach(function (c) {{
      c.addEventListener('change', gaRender);
    }});
    gaRender();
  }})();
  </script>
"""


def build_modelo_aduana():
    """Pestaña "Modelo Aduana": metodología aparte que Jorge quiere poder
    CUESTIONAR (2026-09-03) -- 2ebox separa deliberadamente guías del mismo
    cliente en vuelos distintos cuando, sumadas, cruzarían un umbral de
    aduana chileno (USD 500 = ad valorem para cliente persona, USD 3.000 =
    agente de aduana obligatorio para cualquier cliente). Es más fácil de
    gestionar con el cliente (paga menos), pero puede ser un cuello de
    botella que infla la tasa de "afectadas" del reporte principal sin ser
    una falla operativa real. Detección y benchmarks en
    `_detectar_splits_umbral_aduana()`/`_calcular_benchmarks_aduana()` del
    extractor -- acá solo se presenta."""
    m = data["modelo_umbrales_aduana"]
    casos = list(m["casos"])
    bench = m["benchmarks"]
    umbral_ad_valorem = m["umbral_ad_valorem_usd"]
    umbral_agente = m["umbral_agente_aduana_usd"]

    def clasificar_ejecutiva(conv):
        if conv in KATHY_CONVENIOS:
            return "Kathy"
        if conv in TIARE_CONVENIOS:
            return "Tiare"
        return "Otros"

    for c in casos:
        c["eje"] = clasificar_ejecutiva(c["convenio"] or "")

    total_casos = len(casos)
    total_dias = sum(c["dias_extra_espera"] for c in casos)
    prom_dias = round(total_dias / total_casos, 1) if total_casos else 0
    total_costo_evitado = sum(c["costo_evitado_clp_estimado"] for c in casos)
    ya_afectadas = sum(1 for c in casos if c["afectada_estricto_segundo"])
    pct_ya_afectadas = round(ya_afectadas / total_casos * 100, 1) if total_casos else 0
    n_ad_valorem = sum(1 for c in casos if c["tipo"] == "ad_valorem")
    n_agente = sum(1 for c in casos if c["tipo"] == "agente_aduana")

    diagrama = explica_diagrama([
        {"titulo": "2 guías, mismo cliente", "sub": "listas para volar casi juntas"},
        {"titulo": "Se separan a propósito", "sub": "para que ninguna cruce el umbral sola", "tag": "cliente paga menos", "variante": "proc"},
        {"titulo": "Una de las 2 espera más", "sub": "hasta el vuelo siguiente disponible", "tag": "cuello de botella", "variante": "off"},
    ])
    panel = explica_panel([
        (
            "💰", "¿Por qué se hace?",
            f"Sobre USD {umbral_ad_valorem} de valor declarado, un cliente <b>persona</b> "
            f"paga ad valorem. Sobre USD {umbral_agente} (cualquier cliente) se "
            "necesita <b>agente de aduana</b>. Separar las guías del mismo cliente mantiene a "
            "cada una bajo el umbral — más fácil de gestionar, la mayoría prefiere pagar menos.",
        ),
        (
            "⏳", "¿Qué cuesta en tiempo?",
            f"{fmt_n(total_casos)} casos detectados en {data['anio_reporte']} (guías del mismo "
            f"cliente listas con ≤{m['ventana_dias']} días de diferencia, separadas en vuelos "
            f"distintos). <b>{fmt_n(total_dias)} días</b> de espera extra acumulados — y el "
            f"<b>{fmt_pct(pct_ya_afectadas)}</b> de estos casos YA cuentan como \"afectada\" en "
            "el reporte principal, sin ser una falla operativa real.",
        ),
        (
            "💵", "¿Qué evita en plata?",
            f"Estimado con guías reales que sí cruzaron el umbral: ~{fmt_pct(bench['tasa_ad_valorem_pct'])} "
            f"de ad valorem, ~USD {fmt_n(bench['costo_agente_usd'])} de agente de aduana "
            f"(mediana, n={bench['muestra_ad_valorem']} y n={bench['muestra_agente']} guías de "
            f"referencia). En total, separar evitó un estimado de <b>{fmt_clp(total_costo_evitado)}</b> "
            "en cargos de aduana durante el año.",
        ),
    ])

    comparacion = f"""
  <div class="explica" style="grid-template-columns:1fr 1fr">
    <div class="explica-col">
      <div class="ec-ico">🐌</div>
      <h4>Con el modelo actual (separar)</h4>
      <div class="ec-txt">
        <b>{fmt_n(total_dias)} días</b> extra de espera acumulados en {data['anio_reporte']}
        ({prom_dias} en promedio por caso).<br><br>
        <b>{fmt_pct(pct_ya_afectadas)}</b> de estos {fmt_n(total_casos)} casos ya cuentan como
        "afectada" en el reporte principal — inflando esa tasa sin que sea un problema operativo.<br><br>
        Costo de aduana evitado (no lo paga el cliente): <b>{fmt_clp(total_costo_evitado)}</b>.
      </div>
    </div>
    <div class="explica-col">
      <div class="ec-ico">⚡</div>
      <h4>Sin el modelo (agrupar igual)</h4>
      <div class="ec-txt">
        Las guías saldrían en el primer vuelo disponible, sin esperar por el corte de umbral —
        <b>{fmt_n(total_dias)} días</b> menos de espera acumulada en el año.<br><br>
        El cliente pagaría ad valorem o agente de aduana: costo adicional estimado
        <b>{fmt_clp(total_costo_evitado)}</b>, repartido en {fmt_n(total_casos)} casos
        (~{fmt_clp(round(total_costo_evitado / total_casos)) if total_casos else '$0'} por caso).<br><br>
        A cambio, {fmt_n(ya_afectadas)} guías dejarían de contar como "afectadas" sin cambiar
        nada en la operación de vuelos.
      </div>
    </div>
  </div>
"""

    def fila(c):
        tipo_txt = f"Ad valorem (USD {umbral_ad_valorem})" if c["tipo"] == "ad_valorem" else f"Agente aduana (USD {fmt_n(umbral_agente)})"
        afectada_txt = (
            "<span style='color:var(--bad);font-weight:700'>Sí</span>" if c["afectada_estricto_segundo"]
            else "<span style='color:var(--ink-faint)'>No</span>"
        )
        return (
            f"<tr data-tipo='{c['tipo']}'>"
            f"<td data-v='{html.escape(c['casilla'])}'>{html.escape(c['casilla'])}</td>"
            f"<td data-v='{c['eje']}'>{c['eje']}</td>"
            f"<td data-v='{c['tipo']}'>{tipo_txt}</td>"
            f"<td data-v='{c['n_guia_1']}'><a href='https://2020.2ebox.com/guias-hijas/ver/{c['n_guia_1']}' target='_blank' rel='noopener'>{c['n_guia_1']}</a></td>"
            f"<td data-v='{c['n_guia_2']}'><a href='https://2020.2ebox.com/guias-hijas/ver/{c['n_guia_2']}' target='_blank' rel='noopener'>{c['n_guia_2']}</a></td>"
            f"<td data-v='{c['valor_combinado_usd']}'>USD {fmt_n(round(c['valor_combinado_usd']))}</td>"
            f"<td data-v='{c['dias_extra_espera']}'>{c['dias_extra_espera']}</td>"
            f"<td data-v='{c['costo_evitado_clp_estimado']}'>{fmt_clp(c['costo_evitado_clp_estimado'])}</td>"
            f"<td data-v='{1 if c['afectada_estricto_segundo'] else 0}'>{afectada_txt}</td></tr>"
        )

    tabla = "\n".join(fila(c) for c in sorted(casos, key=lambda c: -c["dias_extra_espera"]))

    return f"""
  {diagrama}
  {panel}

  <div class="kpis">
    <div class="kpi bad"><div class="v">{fmt_n(total_casos)}</div><div class="l">Casos detectados ({fmt_n(n_ad_valorem)} ad valorem, {fmt_n(n_agente)} agente)</div></div>
    <div class="kpi"><div class="v">{fmt_n(total_dias)}</div><div class="l">Días extra de espera acumulados ({prom_dias} promedio)</div></div>
    <div class="kpi"><div class="v">{fmt_clp(total_costo_evitado)}</div><div class="l">Costo de aduana evitado (estimado)</div></div>
    <div class="kpi"><div class="v">{fmt_pct(pct_ya_afectadas)}</div><div class="l">Ya cuentan como "afectada" en el reporte</div></div>
  </div>

  {ejecutivas_kpis_html(casos)}

  <section>
    <h2>Comparación: con vs sin el modelo</h2>
    {comparacion}
  </section>

  <section>
    <h2>Detalle de casos</h2>
    <div class="toggle">
      <button id="btn-aduana-todos" class="active" onclick="filtrarAduana('todos')">Todos</button>
      <button id="btn-aduana-ad_valorem" onclick="filtrarAduana('ad_valorem')">Ad valorem</button>
      <button id="btn-aduana-agente_aduana" onclick="filtrarAduana('agente_aduana')">Agente aduana</button>
    </div>
    <div class="table-wrap" style="max-height:480px">
      <table id="tabla-aduana" class="sortable"><thead><tr>
        <th onclick="ordenarTabla('tabla-aduana',0,'str')">Casilla</th>
        <th onclick="ordenarTabla('tabla-aduana',1,'str')">Ejecutiva</th>
        <th onclick="ordenarTabla('tabla-aduana',2,'str')">Tipo de umbral</th>
        <th onclick="ordenarTabla('tabla-aduana',3,'num')">Guía 1</th>
        <th onclick="ordenarTabla('tabla-aduana',4,'num')">Guía 2 (la que espera)</th>
        <th onclick="ordenarTabla('tabla-aduana',5,'num')">Valor combinado</th>
        <th onclick="ordenarTabla('tabla-aduana',6,'num')">Días extra</th>
        <th onclick="ordenarTabla('tabla-aduana',7,'num')">Costo evitado</th>
        <th onclick="ordenarTabla('tabla-aduana',8,'num')">¿Ya "afectada"?</th>
      </tr></thead>
      <tbody>{tabla}</tbody></table>
    </div>
    <p class="empty-note" id="aduana-empty" style="display:none">Sin casos para este filtro.</p>
  </section>

  <script>
    function filtrarAduana(tipo) {{
      var visibles = 0;
      document.querySelectorAll('#tabla-aduana tbody tr').forEach(function (tr) {{
        var mostrar = (tipo === 'todos' || tr.getAttribute('data-tipo') === tipo);
        tr.style.display = mostrar ? '' : 'none';
        if (mostrar) visibles++;
      }});
      ['todos', 'ad_valorem', 'agente_aduana'].forEach(function (t) {{
        document.getElementById('btn-aduana-' + t).classList.toggle('active', t === tipo);
      }});
      document.getElementById('aduana-empty').style.display = visibles ? 'none' : 'block';
    }}
  </script>
"""


seccion_conclusiones = build_conclusiones()
seccion_capacidad = build_capacidad_vuelos()
seccion_modelo_aduana = build_modelo_aduana()

seccion_ga_estricto = build_guias_afectadas("estricto", "vuelo exacto", dom_id="ga_estricto")
seccion_ga_semana = build_guias_afectadas("semana", "misma semana", dom_id="ga_semana")
seccion_guias_afectadas = build_wrapper_subtabs(
    "guiasaf",
    seccion_ga_estricto,
    seccion_ga_semana,
    explica_panel([
        (
            "🎯", "Vuelo exacto",
            "No cuenta como afectada si subió exactamente al vuelo puntual que le "
            "correspondía. Cualquier otro vuelo posterior (aunque sea el siguiente) cuenta "
            "como afectada.",
        ),
        (
            "📅", "Misma semana",
            "Más permisivo: no cuenta como afectada si voló en OTRO vuelo dentro de la "
            "misma semana calendario. Solo cuenta si voló en una semana posterior, o si "
            "nunca voló.",
        ),
        (
            "➕", "Es la suma de las 2 pestañas",
            "Esta tabla junta individuales + consolidadas — el total siempre coincide con "
            "sumar Individuales y Consolidadas por separado (puedes comprobarlo con el "
            "filtro \"Población\").",
        ),
    ]),
)

seccion_estricto = build_seccion(
    "estricto",
    "vuelo exacto",
    "Criterio \"vuelo exacto\": no cuenta como afectada si brotó exactamente en el vuelo que "
    "le correspondía — brotó en cualquier vuelo posterior (aunque sea el siguiente, días "
    "después), o todavía no ha brotado y ese primer vuelo ya pasó, cuenta como afectada.",
    poblacion="individuales",
)
seccion_semana = build_seccion(
    "semana",
    "misma semana",
    "Criterio \"misma semana\" (más permisivo): no cuenta como afectada si brotó en OTRO vuelo "
    "dentro de la MISMA semana calendario (lunes a domingo) del que le correspondía — por "
    "ejemplo, le tocaba el miércoles y voló el viernes de esa misma semana. Solo cuenta como "
    "afectada si brotó en una semana posterior, o si nunca brotó.",
    poblacion="individuales",
)
seccion_individuales = build_wrapper_subtabs(
    "indiv",
    seccion_estricto,
    seccion_semana,
    explica_panel([
        (
            "📄", "¿Qué son?",
            "Guías que quedaron listas para volar (pago + factura en Miami) de forma "
            "independiente — no son producto de fundir varios paquetes en un bulto (eso son "
            "las guías <b>consolidadas</b>, con su propia pestaña).",
        ),
        (
            "🚫", "¿Qué se excluye?",
            "Guías de carga (vuelos dedicados a 1 sola guía) y guías que nunca completaron "
            "pago + factura — nunca llegaron a tener un vuelo que les correspondiera.",
        ),
        (
            "🎯", "Elige el criterio",
            "\"Vuelo exacto\" o \"misma semana\" — botones arriba. Mide qué tan estricto es "
            "el corte para considerar que una guía quedó afectada.",
        ),
    ]),
)
seccion_cons_estricto = build_seccion(
    "estricto",
    "vuelo exacto",
    "Criterio \"vuelo exacto\": no cuenta como afectada si brotó exactamente en el vuelo que "
    "le correspondía. Ver arriba qué es una guía consolidada.",
    poblacion="consolidadas",
    dom_id="cons-estricto",
)
seccion_cons_semana = build_seccion(
    "semana",
    "misma semana",
    "Criterio \"misma semana\" (más permisivo): no cuenta como afectada si brotó en OTRO vuelo "
    "dentro de la misma semana calendario del que le correspondía — solo si brotó en una "
    "semana posterior, o si nunca brotó. Ver pestaña \"Vuelo exacto\" para el detalle completo "
    "del criterio.",
    poblacion="consolidadas",
    dom_id="cons-semana",
)
seccion_cons_neto = build_seccion(
    "neto",
    "neto de consolidación",
    "Criterio \"neto de consolidación\": igual que \"vuelo exacto\", pero <b>descontando</b> "
    "las guías-bulto cuya consolidación se cerró con <b>factura pendiente</b> (FOB $0 en el "
    "registro): la fecha \"lista\" exige factura en Miami, así que si la factura llegó tarde "
    "el atraso se originó aguas arriba (goteo de facturas documentado en el correo), no en la "
    "operación de vuelo. Es el único ajuste que hacen los datos con confianza — el \"armado "
    "lento\" NO se descuenta porque no discrimina (ver Conclusiones punto 3). Para una guía "
    "individual este criterio es idéntico a \"vuelo exacto\".",
    poblacion="consolidadas",
    dom_id="cons-neto",
)
seccion_consolidadas = build_wrapper_subtabs(
    "cons",
    seccion_cons_estricto,
    seccion_cons_semana,
    explica_diagrama([
        {"titulo": "Guías originales", "sub": 'estado "Consolidado"', "tag": "NO se evalúan", "variante": "off"},
        {"titulo": "Bodega arma el bulto", "sub": "correo Chile ↔ Miami", "variante": "proc"},
        {"titulo": "Guía-bulto NUEVA", "sub": "guia_hijas.consolidacion > 0", "tag": "SÍ se evalúa", "variante": "on"},
    ]) + explica_panel([
        (
            "📦", "¿Qué es?",
            "Las guías originales que el cliente compró NUNCA entran a este análisis (no "
            "tienen su propio pago/factura). Lo que se evalúa es la guía-bulto NUEVA que "
            "arma bodega al fundir varios paquetes en 1 para ahorrar flete — esa sí pasa "
            "por pago, factura y vuelo, igual que cualquier otra guía.",
        ),
        (
            "✉️", "¿Cómo se arma?",
            "Por correo entre la ejecutiva (Chile) y bodega (Miami) — depende del pago, "
            "tipo de consolidación, cantidad de cajas, tope FOB y tiempos de espera de "
            "facturas (cadena de 4-8 personas). Detalle en "
            "<code>CONSOLIDACIONES_CORREO.md</code>.",
        ),
        (
            "✅", "¿Qué resta \"Neto\"?",
            "Esa fricción es real, pero tras corregir el corte de manifiesto <b>ya NO se "
            "traduce en que las guías-bulto vuelen peor que las individuales</b> (tasas "
            "casi iguales — ver Conclusiones punto 3). \"Neto\" resta el único efecto que "
            "los datos aíslan con confianza: bultos cerrados con factura pendiente.",
        ),
    ]),
    contenido_neto=seccion_cons_neto,
    label_neto="Neto de consolidación",
)

HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cumplimiento de Vuelos — Guías 2ebox 2026</title>
<script>
  // Se aplica ANTES de pintar la pagina para que no haya parpadeo de tema
  // al recargar (recuerda la eleccion en localStorage, por navegador).
  (function () {{
    try {{
      var t = localStorage.getItem('cumplimiento-vuelos-tema');
      if (t === 'light') document.documentElement.setAttribute('data-theme', 'light');
    }} catch (e) {{}}
  }})();
</script>
<link href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;600;700&family=Russo+One&display=swap" rel="stylesheet">
<style>
  :root {{
    --2e-red: #E3203E; --2e-red-claro: #E63551;
    --2e-blue: #5691DF; --2e-blue-claro: #A7C5E1; --2e-blue-dark: #152C4A; --2e-blue-darker: #0D1721;
    --2e-grey-dark: #7B92A4; --2e-white: #EFEFEF;
    --bg: var(--2e-blue-darker); --surface: #13233A; --surface-2: #182B45;
    --ink: var(--2e-white); --ink-faint: var(--2e-grey-dark);
    --line: rgba(167,197,225,0.14);
    --good: #34C77A; --warn: #E8A23D; --bad: var(--2e-red);
  }}
  /* Modo claro (pedido de Jorge, 2026-09-01: el oscuro no se ve bien
     compartiendo pantalla) -- solo se remapean fondo/superficie/texto, los
     colores de marca (rojo/azul/semáforo) se mantienen iguales en ambos
     temas. Se activa con data-theme="light" en <html> vía el botón. */
  :root[data-theme="light"] {{
    --bg: #F6FAFD; --surface: #FFFFFF; --surface-2: #EAF1F7;
    --ink: var(--2e-blue-dark); --ink-faint: #5B7691;
    --line: rgba(21,44,74,0.14);
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: 'Fira Sans', system-ui, sans-serif; background: var(--bg); color: var(--ink); -webkit-font-smoothing: antialiased; }}
  .app {{ max-width: 1480px; margin: 0 auto; padding: 28px 24px 60px; }}
  h1 {{ font-family: 'Russo One', system-ui, sans-serif; font-weight: 400; font-size: 20px; margin: 0 0 6px; }}
  h2 {{ font-family: 'Russo One', system-ui, sans-serif; font-weight: 400; font-size: 14px; margin: 0 0 12px; letter-spacing: .02em; }}
  p.sub {{ font-size: 12.5px; color: var(--ink-faint); line-height: 1.6; margin: 0 0 22px; max-width: 780px; }}
  .explica {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px 28px;
    background: var(--surface); border: 1px solid var(--line); border-radius: 16px;
    padding: 20px 26px; margin-bottom: 20px;
  }}
  .explica-col {{ display: flex; flex-direction: column; gap: 6px; }}
  .explica-col .ec-ico {{ font-size: 22px; line-height: 1; }}
  .explica-col h4 {{ font-size: 12.5px; margin: 0; color: var(--ink); font-family: 'Fira Sans', sans-serif; font-weight: 700; }}
  .explica-col .ec-txt {{ font-size: 12px; color: var(--ink-faint); line-height: 1.65; }}
  .explica-col .ec-txt code {{ font-size: 10.5px; }}
  .explica-diagrama {{ display: flex; align-items: stretch; flex-wrap: wrap; gap: 8px 4px; margin: 2px 0 18px; }}
  .ed-box {{
    background: var(--surface-2); border: 1px solid var(--line); border-radius: 12px;
    padding: 10px 16px; min-width: 150px; text-align: center; flex: 1 1 150px;
    display: flex; flex-direction: column; justify-content: center; gap: 3px;
  }}
  .ed-label {{ font-size: 12px; font-weight: 700; color: var(--ink); }}
  .ed-sub {{ font-size: 10px; color: var(--ink-faint); }}
  .ed-tag {{
    display: inline-block; margin: 3px auto 0; font-size: 9.5px; font-weight: 700;
    padding: 2px 9px; border-radius: 20px; border: 1px solid; width: fit-content;
  }}
  .ed-arrow {{ display: flex; align-items: center; justify-content: center; font-size: 18px; color: var(--ink-faint); flex: 0 0 auto; padding: 0 2px; }}
  @media (max-width: 640px) {{
    .explica-diagrama {{ flex-direction: column; }}
    .ed-box {{ width: 100%; }}
    .ed-arrow {{ transform: rotate(90deg); }}
  }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin-bottom: 26px; }}
  .kpi {{ background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; }}
  .kpi .v {{ font-family: 'Russo One', system-ui, sans-serif; font-size: 22px; }}
  .kpi .l {{ font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--ink-faint); margin-top: 4px; }}
  .kpi.bad .v {{ color: var(--bad); }}
  section {{ margin-bottom: 30px; }}
  .toggle {{ display: inline-flex; flex-wrap: wrap; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 3px; margin-bottom: 14px; max-width: 100%; }}
  .toggle button {{ font-family: 'Fira Sans', sans-serif; font-size: 12px; font-weight: 600; padding: 7px 16px; border: none; border-radius: 8px; background: transparent; color: var(--ink-faint); cursor: pointer; white-space: nowrap; }}
  .toggle button.active {{ background: var(--2e-red); color: white; }}
  .tabs-principal {{
    display: flex; gap: 8px; border-bottom: 1px solid var(--line); margin-bottom: 22px;
    overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: thin;
  }}
  .tabs-principal button {{
    font-family: 'Russo One', system-ui, sans-serif; font-size: 13px; font-weight: 400; letter-spacing: .02em;
    padding: 12px 4px; margin-right: 22px; border: none; border-bottom: 3px solid transparent;
    background: transparent; color: var(--ink-faint); cursor: pointer; white-space: nowrap; flex-shrink: 0;
  }}
  .tabs-principal button.active {{ color: var(--ink); border-bottom-color: var(--2e-red); }}
  .pestana {{ display: none; }}
  .pestana.active {{ display: block; }}
  .subtab {{ display: none; }}
  .subtab.active {{ display: block; }}
  .chart-wrap {{ background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 16px 12px 8px; }}
  .chart-svg {{ width: 100%; height: auto; overflow: visible; }}
  .grid-line {{ stroke: var(--line); stroke-width: 1; }}
  .axis-label {{ font-size: 9px; fill: var(--ink-faint); font-family: 'Fira Sans', sans-serif; }}
  .bar-g rect {{ transition: opacity .1s; }}
  .bar-g:hover rect {{ opacity: .78; }}
  .view {{ display: none; }}
  .view.active {{ display: block; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 14px; }}
  th, td {{ text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--line); font-variant-numeric: tabular-nums; }}
  th:first-child, td:first-child {{ text-align: left; }}
  thead th {{ font-size: 10px; text-transform: uppercase; letter-spacing: .04em; color: var(--ink-faint); border-bottom: 2px solid var(--line); position: sticky; top: 0; background: var(--surface); z-index: 1; }}
  td a {{ color: var(--2e-blue); text-decoration: none; font-weight: 600; }}
  td.ga-motivo {{ text-align: left; font-variant-numeric: normal; color: var(--ink-faint); font-size: 11.5px; min-width: 260px; white-space: normal; line-height: 1.4; }}
  td a:hover {{ text-decoration: underline; }}
  table.sortable thead th {{ cursor: pointer; user-select: none; white-space: nowrap; }}
  table.sortable thead th:hover {{ color: var(--ink); }}
  table.sortable thead th.sorted-asc::after {{ content: " ▲"; font-size: 8px; }}
  table.sortable thead th.sorted-desc::after {{ content: " ▼"; font-size: 8px; }}
  tbody tr:hover {{ background: var(--surface-2); }}
  .table-wrap {{ max-height: 420px; overflow-y: auto; overflow-x: auto; border: 1px solid var(--line); border-radius: 14px; padding: 0 4px; }}
  .hallazgos {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
  .hallazgos .card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; }}
  .hallazgos h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--ink-faint); margin: 0 0 10px; }}
  .hallazgos ul {{ margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.8; }}
  @media (max-width: 640px) {{ .hallazgos {{ grid-template-columns: 1fr; }} }}
  details.foot-note {{ font-size: 11.5px; color: var(--ink-faint); line-height: 1.7; }}
  details.foot-note summary {{ cursor: pointer; font-weight: 600; color: var(--ink); margin-bottom: 8px; }}
  code {{ background: var(--surface-2); padding: 1px 5px; border-radius: 4px; font-size: 11px; }}
  .empty-note {{ font-size: 12px; color: var(--ink-faint); padding: 18px 0; text-align: center; }}
  .ga-layout {{ display: grid; grid-template-columns: 176px 1fr; gap: 12px; align-items: start; }}
  .ga-sidebar {{ display: flex; flex-direction: column; gap: 10px; position: sticky; top: 12px; }}
  .ga-content {{ min-width: 0; }}
  @media (max-width: 860px) {{
    .ga-layout {{ grid-template-columns: 1fr; }}
    .ga-sidebar {{ position: static; }}
  }}
  .filtro-card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 10px 11px; }}
  .filtro-card-head {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 5px; margin-bottom: 7px; }}
  .filtro-card h3 {{ font-size: 10px; text-transform: uppercase; letter-spacing: .03em; color: var(--ink-faint); margin: 0; }}
  .filtro-card-title {{ display: flex; align-items: center; gap: 5px; cursor: pointer; user-select: none; }}
  .filtro-chevron {{ font-size: 9px; color: var(--ink-faint); transition: transform .15s; display: inline-block; }}
  .filtro-card.colapsado .filtro-chevron {{ transform: rotate(-90deg); }}
  .filtro-card.colapsado .chk-list, .filtro-card.colapsado .filtro-acciones {{ display: none; }}
  .filtro-acciones button {{
    font-family: 'Fira Sans', sans-serif; font-size: 9.5px; font-weight: 600; color: var(--ink-faint);
    background: var(--surface-2); border: 1px solid var(--line); border-radius: 6px; padding: 2px 6px; margin-left: 3px; cursor: pointer;
  }}
  .filtro-acciones button:hover {{ color: var(--ink); border-color: var(--2e-blue-claro); }}
  .chk-list {{ display: flex; flex-wrap: wrap; gap: 5px; }}
  .chk-list-vert {{ flex-direction: column; flex-wrap: nowrap; align-items: stretch; }}
  .chk-list-scroll {{ max-height: 320px; overflow-y: auto; }}
  .chk {{
    display: inline-flex; align-items: center; gap: 4px; font-size: 10.5px; color: var(--ink);
    background: var(--surface-2); border: 1px solid var(--line); border-radius: 7px; padding: 3px 7px; cursor: pointer;
  }}
  .chk-list-vert .chk {{ justify-content: space-between; }}
  .chk input {{ accent-color: var(--2e-red); cursor: pointer; }}
  .chk-n {{ color: var(--ink-faint); font-variant-numeric: tabular-nums; font-size: 10px; }}
  .cap-filtro-fechas {{
    display: flex; align-items: center; flex-wrap: wrap; gap: 10px;
    background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
    padding: 10px 14px; margin-bottom: 16px; font-size: 12px;
  }}
  .cap-filtro-label {{ font-weight: 600; color: var(--ink-faint); text-transform: uppercase; font-size: 10px; letter-spacing: .03em; }}
  .cap-filtro-fechas label {{ display: flex; align-items: center; gap: 6px; color: var(--ink-faint); }}
  .cap-filtro-fechas input[type="date"] {{
    font-family: 'Fira Sans', sans-serif; font-size: 12px; color: var(--ink); background: var(--surface-2);
    border: 1px solid var(--line); border-radius: 7px; padding: 4px 7px;
  }}
  .cap-filtro-fechas button {{
    font-family: 'Fira Sans', sans-serif; font-size: 11px; font-weight: 600; color: var(--ink-faint);
    background: var(--surface-2); border: 1px solid var(--line); border-radius: 7px; padding: 4px 10px; cursor: pointer;
  }}
  .cap-filtro-fechas button:hover {{ color: var(--ink); border-color: var(--2e-blue-claro); }}
  .header-row {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px 12px; margin-bottom: 6px; flex-wrap: wrap; }}
  .header-row h1 {{ min-width: 0; }}
  .header-actions {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex-shrink: 0; }}
  .theme-toggle {{
    display: inline-flex; align-items: center; gap: 6px; font-family: 'Fira Sans', sans-serif; font-size: 11.5px; font-weight: 600;
    padding: 7px 12px; border: 1px solid var(--line); border-radius: 9px; background: var(--surface); color: var(--ink);
    cursor: pointer; white-space: nowrap; flex-shrink: 0;
  }}
  .theme-toggle:hover {{ border-color: var(--2e-blue-claro); }}
  .update-badge {{
    display: inline-flex; align-items: center; gap: 6px; font-family: 'Fira Sans', sans-serif; font-size: 11px; font-weight: 600;
    padding: 7px 12px; border-radius: 9px; border: 1px solid var(--line); white-space: nowrap; flex-shrink: 0;
    background: var(--surface); color: var(--ink-faint);
  }}
  .update-badge.ok {{ background: rgba(52,199,122,0.14); color: var(--good); border-color: var(--good); }}
  .update-badge.stale {{ background: rgba(227,32,62,0.12); color: var(--bad); border-color: var(--bad); }}
  @media (max-width: 480px) {{
    .app {{ padding: 18px 14px 40px; }}
    h1 {{ font-size: 17px; }}
    .kpi .v {{ font-size: 19px; }}
    table {{ font-size: 11.5px; }}
    th, td {{ padding: 6px 7px; }}
  }}
</style>
</head>
<body>
<div class="app">
  <div class="header-row">
    <h1>Cumplimiento de Vuelos — Guías 2ebox {data['anio_reporte']}</h1>
    <div class="header-actions">
      <span class="update-badge" id="update-badge">Actualizado: cargando…</span>
      <button class="theme-toggle" id="theme-toggle-btn" onclick="alternarTema()">🌙 Modo oscuro</button>
    </div>
  </div>
  <p class="sub">
    Guías regulares listas para volar (pago + factura en Miami) que resultan afectadas por
    demoras de vuelo. La pestaña <b>Individuales</b> y la pestaña <b>Consolidadas</b> (varias
    guías originales fundidas en una sola en bodega, con un patrón de espera distinto por
    naturaleza) miden lo mismo con los mismos dos criterios ("vuelo exacto" / "misma semana",
    elegibles adentro de cada una), aplicados a cada población por separado. El incidente
    siempre se cuenta en la semana/mes del vuelo que le correspondía (donde se generó el
    atraso), no en el que finalmente voló.
  </p>

  <div class="tabs-principal">
    <button id="tab-btn-individuales" class="active" onclick="verPestana('individuales')">Individuales</button>
    <button id="tab-btn-consolidadas" onclick="verPestana('consolidadas')">Consolidadas</button>
    <button id="tab-btn-guias-afectadas" onclick="verPestana('guias-afectadas')">Guías afectadas</button>
    <button id="tab-btn-capacidad" onclick="verPestana('capacidad')">Capacidad de Vuelos</button>
    <button id="tab-btn-conclusiones" onclick="verPestana('conclusiones')">Conclusiones</button>
    <button id="tab-btn-modelo-aduana" onclick="verPestana('modelo-aduana')">Modelo Aduana</button>
  </div>

  <div id="tab-individuales" class="pestana active">{seccion_individuales}</div>
  <div id="tab-consolidadas" class="pestana">{seccion_consolidadas}</div>
  <div id="tab-guias-afectadas" class="pestana">{seccion_guias_afectadas}</div>
  <div id="tab-capacidad" class="pestana">{seccion_capacidad}</div>
  <div id="tab-conclusiones" class="pestana">{seccion_conclusiones}</div>
  <div id="tab-modelo-aduana" class="pestana">{seccion_modelo_aduana}</div>

  <details class="foot-note">
    <summary>Notas técnicas y metodología</summary>
    <p>
      <b>Fuente:</b> NocoDB, tabla <code>ebox_cumplimiento</code> (espejo de
      <code>dataconsolider.ebox_cumplimiento</code>) y <code>guia_hijas</code> (para el
      peso), base <code>pifk61tmzhes073</code>, guías con <code>fecha_ingreso</code> desde
      2025-12-15 (colchón para calcular correctamente el primer vuelo correspondiente de
      guías listas a inicios de enero {data['anio_reporte']}).
    </p>
    <p>
      <b>"Lista para volar":</b> <code>fecha_lista = MAX(fecha_primer_pago,
      fecha_miami_con_factura)</code> — ambos campos ya vienen resueltos en
      <code>ebox_cumplimiento</code>. Si falta alguno, la guía no entra al análisis
      (nunca quedó lista).
    </p>
    <p>
      <b>Calendario real de vuelos:</b> no existe una tabla con la fecha exacta de
      despacho por vuelo, así que se reconstruye agrupando
      <code>fecha_despachado_aeropuerto</code> de todas las guías del período —
      como el despacho es una actualización masiva por lote, las guías de un mismo
      vuelo comparten timestamp casi exacto. Se agrupan por gap: se cortan en un
      vuelo nuevo cuando el salto al siguiente despacho ordenado supera 10 minutos
      (evita partir un mismo lote lento en 2-3 "vuelos" falsos, sin riesgo de
      fusionar vuelos reales distintos, separados por horas o días). Se
      descartan los grupos de 1 sola guía (carga, no vuelo regular de
      guías) — {data['total_vuelos_calendario']} vuelos regulares detectados entre
      {data['vuelos_calendario'][0]['ts'][:10] if data['vuelos_calendario'] else 's/d'} y
      {data['vuelos_calendario'][-1]['ts'][:10] if data['vuelos_calendario'] else 's/d'},
      mayoritariamente miércoles y viernes (con corrimientos puntuales, coherente
      con feriados/ajustes avisados por correo).
    </p>
    <p>
      <b>Criterio "vuelo exacto":</b> para cada guía lista, se busca el primer vuelo del
      calendario con fecha ≥ fecha_lista ("vuelo esperado"). Se compara contra el vuelo real
      en que brotó (agrupado igual que el calendario). Es incidente si brotó en un vuelo
      <b>posterior</b> al esperado, o si todavía no ha brotado y el esperado ya pasó.
    </p>
    <p>
      <b>Criterio "misma semana":</b> mismo cálculo de vuelo esperado, pero <b>no</b> cuenta
      como incidente si el vuelo real cayó en la misma semana calendario (lunes a domingo)
      que el esperado, aunque no haya sido ese vuelo puntual — solo si cayó en una semana
      posterior, o si nunca brotó.
    </p>
    <p>
      En ambos criterios, <b>no</b> se cuenta como incidente si brotó antes del vuelo
      esperado (pasa con clientes con crédito, cuyo pago queda registrado en el sistema
      después del envío — no es que "perdieron" su vuelo). Kilos y clientes únicos
      (columna <code>casilla</code>) se calculan sobre el conjunto de guías afectadas de
      cada definición y período.
    </p>
    <p>
      <b>Guías excluidas del análisis:</b> sin fecha de pago o sin factura en Miami
      registrada (nunca quedaron "listas"); guías cuyo primer vuelo posible
      todavía no ha ocurrido (muy recientes, pendientes de evaluar).
    </p>
    <p>
      <b>Individuales vs. consolidadas:</b> guías <b>consolidadas</b> (varias guías originales
      fundidas en una guía nueva en bodega, <code>guia_hijas.consolidacion &gt; 0</code>) se
      identifican y se sacan de la pestaña "Individuales" — tienen su propia pestaña
      "Consolidadas" (mismos dos criterios, elegibles adentro, aplicados solo a esa población)
      para no mezclar su patrón de espera (distinto por naturaleza: quedan "listas" recién
      cuando se arma el bulto) con el de las guías individuales. La pestaña "Conclusiones"
      compara ambas poblaciones mes a mes para explicar el patrón abril-junio — ver
      metodología completa en el docstring de <code>extraer_cumplimiento_vuelos.py</code>.
    </p>
    <p>
      Generado por <code>extraer_cumplimiento_vuelos.py</code> +
      <code>build_dashboard.py</code>, carpeta
      <code>analisis_vuelos_no_volados/</code>. Ver <code>cumplimiento_vuelos.json</code>
      para el detalle guía a guía de cada definición.
    </p>
  </details>
</div>
<script>
  function actualizarBotonTema() {{
    var claro = document.documentElement.getAttribute('data-theme') === 'light';
    document.getElementById('theme-toggle-btn').textContent = claro ? '🌙 Modo oscuro' : '☀️ Modo claro';
  }}
  function alternarTema() {{
    var claro = document.documentElement.getAttribute('data-theme') === 'light';
    if (claro) {{
      document.documentElement.removeAttribute('data-theme');
    }} else {{
      document.documentElement.setAttribute('data-theme', 'light');
    }}
    try {{ localStorage.setItem('cumplimiento-vuelos-tema', claro ? 'dark' : 'light'); }} catch (e) {{}}
    actualizarBotonTema();
  }}
  actualizarBotonTema();

  // Badge "Actualizado: ..." -- pedido de Jorge (2026-09-03): saber de un
  // vistazo si el reporte es de hoy. Se calcula en el NAVEGADOR (no al
  // generar el HTML) para que siga siendo correcto aunque se mire horas o
  // dias despues de la ultima corrida del pipeline automatico. GENERADO_ISO
  // viene con tz UTC explicito (ver docstring del extractor) -- new Date()
  // lo convierte solo a la hora local de quien mira el reporte.
  (function () {{
    var el = document.getElementById('update-badge');
    if (!el) return;
    var GENERADO_ISO = {json.dumps(data['generado'])};
    var d = new Date(GENERADO_ISO);
    if (isNaN(d.getTime())) {{ el.textContent = 'Actualizado: s/d'; return; }}
    var ahora = new Date();
    var pad = function (n) {{ return String(n).padStart(2, '0'); }};
    var fecha = pad(d.getDate()) + '-' + pad(d.getMonth() + 1) + '-' + d.getFullYear();
    var hora = pad(d.getHours()) + ':' + pad(d.getMinutes());
    var esHoy = d.getFullYear() === ahora.getFullYear() && d.getMonth() === ahora.getMonth() && d.getDate() === ahora.getDate();
    if (esHoy) {{
      el.className = 'update-badge ok';
      el.textContent = '🟢 Actualizado hoy ' + hora;
    }} else {{
      var dias = Math.max(1, Math.round((ahora - d) / 86400000));
      el.className = 'update-badge stale';
      el.textContent = '🔴 Desactualizado — ' + fecha + ' ' + hora + ' (hace ' + dias + (dias === 1 ? ' día' : ' días') + ')';
    }}
  }})();

  function verPestana(scope) {{
    ['individuales', 'consolidadas', 'guias-afectadas', 'capacidad', 'conclusiones', 'modelo-aduana'].forEach(function (s) {{
      document.getElementById('tab-' + s).classList.toggle('active', s === scope);
      document.getElementById('tab-btn-' + s).classList.toggle('active', s === scope);
    }});
  }}
  function verSubtab(base, scope) {{
    ['estricto', 'semana', 'neto'].forEach(function (s) {{
      var pane = document.getElementById('subtab-' + base + '-' + s);
      var btn = document.getElementById('subtab-btn-' + base + '-' + s);
      if (pane) pane.classList.toggle('active', s === scope);
      if (btn) btn.classList.toggle('active', s === scope);
    }});
  }}
  function ordenarTabla(tableId, col, tipo) {{
    var table = document.getElementById(tableId);
    var tbody = table.querySelector('tbody');
    var filas = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    var ths = table.querySelectorAll('thead th');
    var th = ths[col];
    var asc = th.getAttribute('data-asc') !== 'true';
    filas.sort(function (a, b) {{
      var va = a.children[col].getAttribute('data-v');
      var vb = b.children[col].getAttribute('data-v');
      if (tipo === 'num') {{ va = parseFloat(va); vb = parseFloat(vb); }}
      if (va < vb) return asc ? -1 : 1;
      if (va > vb) return asc ? 1 : -1;
      return 0;
    }});
    filas.forEach(function (tr) {{ tbody.appendChild(tr); }});
    ths.forEach(function (h) {{ h.removeAttribute('data-asc'); h.classList.remove('sorted-asc', 'sorted-desc'); }});
    th.setAttribute('data-asc', asc ? 'true' : 'false');
    th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
  }}
  function verVista(scope, v) {{
    document.getElementById('view-' + scope + '-chart-semanal').classList.toggle('active', v === 'semanal');
    document.getElementById('view-' + scope + '-chart-mensual').classList.toggle('active', v === 'mensual');
    document.getElementById('btn-' + scope + '-semanal').classList.toggle('active', v === 'semanal');
    document.getElementById('btn-' + scope + '-mensual').classList.toggle('active', v === 'mensual');
  }}
  function verTabla(scope, v) {{
    document.getElementById('view-' + scope + '-tabla-semanal').classList.toggle('active', v === 'semanal');
    document.getElementById('view-' + scope + '-tabla-mensual').classList.toggle('active', v === 'mensual');
    document.getElementById('btn-' + scope + '-tabla-semanal').classList.toggle('active', v === 'semanal');
    document.getElementById('btn-' + scope + '-tabla-mensual').classList.toggle('active', v === 'mensual');
  }}
  function verVistaCapacidad(v) {{
    ['semanal', 'mensual', 'porvuelo'].forEach(function (s) {{
      document.getElementById('view-capacidad-chart-' + s).classList.toggle('active', s === v);
      document.getElementById('btn-capacidad-' + s).classList.toggle('active', s === v);
    }});
  }}
  function verTablaCapacidad(v) {{
    ['semanal', 'mensual', 'porvuelo'].forEach(function (s) {{
      document.getElementById('view-capacidad-tabla-' + s).classList.toggle('active', s === v);
      document.getElementById('btn-capacidad-tabla-' + s).classList.toggle('active', s === v);
    }});
  }}
</script>
</body>
</html>
"""

with open("cumplimiento_vuelos.html", "w", encoding="utf-8") as f:
    f.write(HTML)
print("cumplimiento_vuelos.html generado")
