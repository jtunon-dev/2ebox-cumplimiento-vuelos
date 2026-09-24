"""
Genera reporte-logistica-operaciones.html a partir de data/datos_crudos.json
+ data/meta.json (ver extraer_datos.py). Dashboard estilo Power BI, tema
oficial de marca 2ebox: filtros a la izquierda (año / mes / forwarder /
unidad de negocio) y pestañas arriba.

v1: pestañas Performance y Análisis de Tiempos completas; Resumen y Análisis
de Productos quedan como placeholder.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"

datos = json.loads((DATA / "datos_crudos.json").read_text(encoding="utf-8"))
meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
um = json.loads((DATA / "ultima_milla.json").read_text(encoding="utf-8"))
GEN = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC")

PAYLOAD = json.dumps({
    "cols": datos["cols"], "rows": datos["rows"], "meta": meta, "generado": GEN,
}, ensure_ascii=False, separators=(",", ":"))
PAYLOAD_UM = json.dumps(um, ensure_ascii=False, separators=(",", ":"))
# Llenado de Vuelos (extraer_llenado.py) -- opcional: si el extractor no corrió,
# la pestaña queda vacía con un aviso en vez de romper el build completo.
_ll_path = DATA / "llenado_vuelos.json"
ll = json.loads(_ll_path.read_text(encoding="utf-8")) if _ll_path.exists() else {"vuelos": [], "guias": []}
# las guías ya subidas a un AWB no usan los campos de T5 (pendientes) -> fuera, para
# no inflar el HTML (el reporte integrado embebe este archivo completo)
_SOLO_T5 = ("cif", "ag", "adv", "desc", "mcf", "pag", "ex", "cli", "fob_cart", "tramo", "regla", "p", "cli_hist")
for _g in ll["guias"]:
    if _g.get("vid"):
        for _k in _SOLO_T5:
            _g.pop(_k, None)
PAYLOAD_LL = json.dumps(ll, ensure_ascii=False, separators=(",", ":"))

HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Logística y Operaciones 2ebox</title>
<script>
  // Igual que Cumplimiento de Vuelos: se aplica ANTES de pintar la pagina
  // para que no haya parpadeo de tema al recargar (recuerda la eleccion en
  // localStorage, por navegador). El reporte integrado sobreescribe esto
  // desde su propio control compartido.
  (function () {
    try {
      var t = localStorage.getItem('rl-tema');
      if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    } catch (e) {}
  })();
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;500;600;700&family=Russo+One&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{
  --2e-red:#E3203E; --2e-red-light:#E63551;
  --2e-blue:#5691DF; --2e-blue-light:#A7C5E1; --2e-blue-dark:#152C4A; --2e-blue-darker:#0D1721;
  --2e-grey:#DFEAF4; --2e-grey-light:#F6FAFD; --2e-grey-dark:#7B92A4;
  --font-display:'Russo One',sans-serif; --font-body:'Fira Sans',sans-serif;
  --bg:#F6FAFD; --surface:#FFFFFF; --surface-2:#EAF1F7;
  --ink:#152C4A; --ink-faint:#7B92A4;
  --line:rgba(21,44,74,0.14);
  --diag-normal-fill:#EAF1FA; --diag-normal-stroke:#5691DF;
  --diag-final-fill:#E4F3EA; --diag-final-stroke:#2E9E6B;
  --diag-branch-fill:#EEF3F9; --diag-branch-stroke:#C9D6E6;
  --diag-ret-fill:#FFF3E0; --diag-ret-stroke:#E0A100; --diag-ret-ink:#7A5B00;
}
/* Modo oscuro (pedido de Jorge, 2026-09-21: controlado desde el banner del
   reporte integrado, mismos tonos que usa Cumplimiento de Vuelos para que
   ambos reportes combinen). Solo se remapean fondo/superficie/texto -- los
   colores de marca (rojo/azul) se mantienen. */
:root[data-theme="dark"]{
  --bg:#0D1721; --surface:#13233A; --surface-2:#182B45;
  --ink:#EFEFEF; --ink-faint:#7B92A4;
  --line:rgba(167,197,225,0.14);
  --diag-normal-fill:#16334F; --diag-normal-stroke:#5691DF;
  --diag-final-fill:#123322; --diag-final-stroke:#34C77A;
  --diag-branch-fill:#182B45; --diag-branch-stroke:rgba(167,197,225,0.3);
  --diag-ret-fill:#3A2A05; --diag-ret-stroke:#E0A100; --diag-ret-ink:#F0C674;
}
*{box-sizing:border-box}
body{margin:0;font-family:var(--font-body);color:var(--ink);background:var(--bg);font-size:14px}
h1,h2,h3,h4{font-family:var(--font-display);font-weight:400;margin:0}

.topbar{background:var(--2e-blue-dark);color:#fff;display:flex;align-items:center;gap:20px;padding:11px 20px;flex-wrap:wrap}
.topbar .brand{font-family:var(--font-display);font-size:18px;letter-spacing:.4px}
.topbar .brand b{color:var(--2e-red-light)}
.tabs{display:flex;gap:3px;flex-wrap:wrap;margin-left:auto}
.tab{background:transparent;border:none;color:var(--2e-blue-light);font-family:var(--font-display);font-size:12.5px;
  padding:8px 14px;border-radius:8px;cursor:pointer;letter-spacing:.3px}
.tab:hover{color:#fff;background:rgba(255,255,255,.08)}
.tab.active{background:var(--surface);color:var(--ink)}
.gen{font-size:11px;color:var(--2e-blue-light);width:100%;margin-top:1px}
.theme-toggle{display:inline-flex;align-items:center;gap:6px;font-family:var(--font-body);font-size:11.5px;font-weight:600;
  padding:7px 12px;border:1px solid rgba(255,255,255,.25);border-radius:9px;background:rgba(255,255,255,.08);
  color:#fff;cursor:pointer;white-space:nowrap}
.theme-toggle:hover{background:rgba(255,255,255,.16)}

.wrap{display:flex;align-items:flex-start}
.sidebar{width:240px;flex:none;background:var(--surface);border-right:1px solid var(--line);padding:16px 14px;
  position:sticky;top:0;max-height:100vh;overflow-y:auto}
.main{flex:1;padding:20px 24px;min-width:0}

.fg{margin-bottom:16px}
.fg h4{font-size:11.5px;letter-spacing:.5px;text-transform:uppercase;margin-bottom:7px;display:flex;justify-content:space-between}
.fg h4 button{font-family:var(--font-body);font-size:10px;color:var(--2e-blue);background:none;border:none;cursor:pointer;text-transform:none}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{border:1px solid var(--line);background:var(--surface-2);border-radius:8px;padding:4px 9px;font-size:12px;cursor:pointer;user-select:none;color:var(--ink)}
.chip:hover{border-color:var(--2e-blue-light)}
.chip.on{background:var(--2e-blue);border-color:var(--2e-blue);color:#fff}
.chip.mes{min-width:36px;text-align:center}
.reset-all{width:100%;margin-top:2px;background:var(--2e-red);color:#fff;border:none;border-radius:9px;padding:9px;
  font-family:var(--font-display);font-size:11.5px;letter-spacing:.4px;cursor:pointer}
.reset-all:hover{background:var(--2e-blue-dark)}
.scope-note{font-size:11px;color:var(--ink-faint);margin-top:10px;line-height:1.55}

.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:11px;margin-bottom:16px}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:13px 14px}
.kpi .v{font-family:var(--font-display);font-size:22px;line-height:1.15}
.kpi .l{font-size:11px;color:var(--ink-faint);margin-top:5px;text-transform:uppercase;letter-spacing:.3px}
.kpi .s{font-size:11px;color:var(--2e-blue);margin-top:3px}

.panel{background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:15px 16px 13px;margin-bottom:15px}
.panel h3{font-size:13.5px;letter-spacing:.3px;margin-bottom:3px}
.panel .sub{font-size:11px;color:var(--ink-faint);margin-bottom:11px;line-height:1.5}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:15px}
.grid-2>.panel{margin-bottom:0}
@media(max-width:1080px){.grid-2{grid-template-columns:1fr}}
.chart-box{position:relative;height:290px}
.chart-box.tall{height:360px}

.metric-switch{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}
.metric-switch button{border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:8px;padding:6px 12px;font-size:12px;cursor:pointer;font-family:var(--font-body)}
.metric-switch button.on{background:var(--2e-blue-dark);color:#fff;border-color:var(--2e-blue-dark)}

.notice{background:#FFF8E6;border:1px solid #F0D48A;border-radius:10px;padding:9px 12px;font-size:11.5px;color:#7A5B00;margin-bottom:14px;line-height:1.5}

table.dt{width:100%;border-collapse:collapse;font-size:12.5px}
table.dt th,table.dt td{padding:7px 9px;text-align:right;border-bottom:1px solid var(--line)}
table.dt th{font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:.3px;cursor:pointer;white-space:nowrap;background:var(--surface-2);color:var(--ink)}
table.dt th:first-child,table.dt td:first-child{text-align:left}
table.dt tbody tr:hover{background:var(--surface-2)}
table.dt tfoot td{font-weight:700;border-top:2px solid var(--ink);border-bottom:none}
.tbl-scroll{overflow-x:auto}
/* matriz año×mes: compacta, no estira a todo el ancho */
table.dt-compact{width:auto;min-width:0;font-size:12px}
table.dt-compact th,table.dt-compact td{padding:5px 12px;white-space:nowrap}
table.dt-compact td:first-child,table.dt-compact th:first-child{position:sticky;left:0;background:var(--surface)}
table.dt-compact th:first-child{background:var(--surface-2)}
table.dt-compact .mx-n{color:var(--ink-faint);font-size:10px;margin-left:3px}

.placeholder{background:var(--surface);border:1px dashed var(--2e-blue-light);border-radius:13px;padding:46px 20px;text-align:center;color:var(--ink-faint)}
.placeholder h3{color:var(--ink);margin-bottom:8px}
.hidden{display:none!important}

.fstage{display:flex;align-items:center;gap:10px;margin-bottom:6px;font-size:12px}
.fstage .lbl{width:240px;flex:none}
.fstage .track{flex:1;background:var(--surface-2);border-radius:5px;overflow:hidden}
.fstage .bar{height:19px;border-radius:5px}
.fstage .val{width:120px;flex:none;text-align:right;color:var(--ink-faint)}
.flegend{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--ink-faint);margin:10px 0 4px}
.flegend span::before{content:"";display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:middle;background:var(--c)}
#t-diagram svg{display:block}
#t-diagram .node rect{rx:9;stroke-width:1.5}
#t-diagram .node text{font-family:var(--font-body);font-size:11px;fill:var(--ink)}
#t-diagram .edgelbl{font-family:var(--font-body);font-size:10.5px;font-weight:600;fill:var(--ink)}
#t-diagram .edgesub{font-family:var(--font-body);font-size:9px;fill:var(--ink-faint)}
#t-diagram .branch rect{fill:var(--surface-2);stroke:var(--line)}
#t-diagram .branch text{fill:var(--ink-faint)}

/* --- Llenado de Vuelos --- */
.ll-filters{display:flex;flex-wrap:wrap;gap:14px 22px;align-items:flex-end;background:var(--surface);border:1px solid var(--line);
  border-radius:13px;padding:12px 16px;margin-bottom:15px}
.ll-filters .fg{margin:0}
.ll-filters select,.ll-filters input{font-family:var(--font-body);font-size:12px;padding:5px 8px;border:1px solid var(--line);
  border-radius:8px;background:var(--surface-2);color:var(--ink)}
.ll-filters select{max-width:260px}
.ll-filters input[type=date]{width:130px}
a.lk{color:var(--2e-blue);cursor:pointer;text-decoration:none;font-weight:600}
a.lk:hover{text-decoration:underline}
.kpi.hl{border-color:var(--2e-blue);box-shadow:inset 3px 0 0 var(--2e-blue)}
.badge{display:inline-block;border-radius:6px;padding:1px 7px;font-size:10.5px;font-weight:600;white-space:nowrap}
.b-alta{background:#E4F3EA;color:#1E7A4F}.b-media{background:#FFF3E0;color:#8A5A00}.b-baja{background:#FDE7EA;color:#B3162F}
.b-pc{background:#EAF1FA;color:#2F6DB5}.b-warn{background:#FDE7EA;color:#B3162F;margin:1px 2px}
:root[data-theme="dark"] .b-alta{background:#123322;color:#34C77A}
:root[data-theme="dark"] .b-media{background:#3A2A05;color:#F0C674}
:root[data-theme="dark"] .b-baja,:root[data-theme="dark"] .b-warn{background:#3D1219;color:#FF8A9A}
:root[data-theme="dark"] .b-pc{background:#16334F;color:#A7C5E1}
table.ll-mx td{text-align:center;vertical-align:top;min-width:82px}
table.ll-mx td:first-child{text-align:left;white-space:nowrap}
table.ll-mx .mes td{background:var(--surface-2);font-family:var(--font-display);font-size:11px;text-align:left}
table.ll-mx .cv{display:block;line-height:1.25}
table.ll-mx .cv b{font-size:13px}
table.ll-mx .cv small{display:block;font-size:9.5px;color:var(--ink-faint)}
table.ll-mx .tot{color:var(--ink-faint);font-size:10.5px}
</style>
</head>
<body>
<div class="topbar">
  <span class="brand">2e<b>box</b> · Logística y Operaciones</span>
  <div class="tabs" id="tabs">
    <button class="tab" data-tab="resumen">Resumen</button>
    <button class="tab active" data-tab="performance">Performance</button>
    <button class="tab" data-tab="productos">Análisis de Productos</button>
    <button class="tab" data-tab="tiempos">Análisis de Tiempos</button>
    <button class="tab" data-tab="ultimamilla">Última Milla</button>
    <button class="tab" data-tab="llenado">Llenado de Vuelos</button>
  </div>
  <span class="gen" id="gen"></span>
  <button class="theme-toggle" id="theme-toggle-btn" onclick="alternarTemaRL()">🌙 Modo oscuro</button>
</div>

<div class="wrap">
  <aside class="sidebar">
    <div class="fg"><h4>Año <button data-clear="fy">todos</button></h4><div class="chips" id="f-fy"></div></div>
    <div class="fg"><h4>Mes <button data-clear="fm">todos</button></h4><div class="chips" id="f-fm"></div></div>
    <div class="fg"><h4>Forwarder (AWB) <button data-clear="fw">todos</button></h4><div class="chips" id="f-fw"></div></div>
    <div class="fg"><h4>Unidad de negocio <button data-clear="un">todas</button></h4><div class="chips" id="f-un"></div></div>
    <button class="reset-all" id="reset-all">Limpiar todos los filtros</button>
    <div class="scope-note" id="scope-note"></div>
  </aside>

  <main class="main">
    <section id="tab-resumen" class="hidden">
      <div class="placeholder"><h3>Resumen</h3><p>Se construye al final, junto con Análisis de Productos.</p></div>
    </section>

    <section id="tab-performance">
      <div class="metric-switch" id="perf-metric">
        <button data-m="costo" class="on">Costo real de flete (2025+)</button>
        <button data-m="costoest">Costo con estimados</button>
        <button data-m="volumen">Volumen y entrega (todos los años)</button>
      </div>
      <div class="notice" id="perf-notice"></div>
      <div class="kpi-row" id="perf-kpis"></div>
      <div class="grid-2" id="perf-costo-charts">
        <div class="panel"><h3>Costo total de flete por forwarder</h3><div class="sub">USD · tarifa_costo (USD/kg del vuelo) × kilos de cada guía</div><div class="chart-box"><canvas id="c-costo-total"></canvas></div></div>
        <div class="panel"><h3>Costo por kilo por forwarder</h3><div class="sub">USD/kg · costo total ÷ kilos transportados</div><div class="chart-box"><canvas id="c-costo-kg"></canvas></div></div>
      </div>
      <div class="grid-2" id="perf-costo-charts2" style="margin-top:15px">
        <div class="panel"><h3>Costo promedio por guía por forwarder</h3><div class="sub">USD · costo total ÷ guías con costo (LATAM/Mercury salen altos: llevan guías consolidadas pesadas)</div><div class="chart-box"><canvas id="c-costo-guia"></canvas></div></div>
        <div class="panel"><h3>Evolución mensual del costo por kilo</h3><div class="sub">USD/kg por mes de vuelo, por forwarder</div><div class="chart-box"><canvas id="c-costo-kg-mes"></canvas></div></div>
      </div>
      <div class="grid-2" style="margin-top:15px">
        <div class="panel"><h3>Guías totales vs entregadas por forwarder</h3><div class="sub">Transportadas y cuántas ya se entregaron al cliente</div><div class="chart-box"><canvas id="c-guias"></canvas></div></div>
        <div class="panel"><h3>Tiempo de tránsito aéreo por forwarder</h3><div class="sub">Días · mediana de (arribo a Chile − despacho a aeropuerto)</div><div class="chart-box"><canvas id="c-transito"></canvas></div></div>
      </div>
      <div class="panel"><h3>Detalle por forwarder</h3><div class="sub">Clic en el encabezado para ordenar</div><div class="tbl-scroll"><table class="dt" id="perf-table"></table></div></div>
      <div class="grid-2">
        <div class="panel">
          <h3>Matriz año × mes</h3>
          <div class="sub">Filas = mes, columnas = año. El número chico gris es la cantidad de guías (o de vuelos, en "kg/AWB"). Respeta forwarder y unidad de negocio, no año/mes. Tarifa = costo ÷ kilos facturables con costo (solo desde 2025). Carga se costea por peso volumétrico; Casilla por kilo real.</div>
          <div class="metric-switch" id="mx-metric">
            <button data-x="tarifa" class="on">Tarifa promedio (US$/kg)</button>
            <button data-x="kilos">Kilos promedio (kg/guía)</button>
            <button data-x="kilosvuelo">Kilos promedio por vuelo (kg/AWB)</button>
            <button data-x="guias">Cantidad de guías</button>
          </div>
          <div class="tbl-scroll"><table class="dt dt-compact" id="perf-matrix"></table></div>
        </div>
        <div class="panel">
          <h3>Matriz año × mes — margen / venta</h3>
          <div class="sub">Mismo criterio que la matriz de tarifa. Solo guías con costo Y venta calzados (ver nota de margen arriba). El número chico gris es la cantidad de guías (o de vuelos, en "por vuelo").</div>
          <div class="metric-switch" id="mg-valor">
            <button data-v="margen" class="on">Margen</button>
            <button data-v="venta">Venta</button>
          </div>
          <div class="metric-switch" id="mg-metric">
            <button data-g="vuelo" class="on">Promedio por vuelo</button>
            <button data-g="guia">Promedio por guía</button>
            <button data-g="total">Total</button>
          </div>
          <div class="tbl-scroll"><table class="dt dt-compact" id="perf-matrix-margen"></table></div>
        </div>
      </div>
      <div class="panel">
        <h3>Kilos volados por semana</h3>
        <div class="sub">Semana = lunes de despacho a aeropuerto. Clic en el encabezado para ordenar (por defecto, cronológico). Respeta todos los filtros de la izquierda.</div>
        <div class="tbl-scroll" style="max-height:420px;overflow-y:auto"><table class="dt" id="perf-semanas"></table></div>
      </div>
    </section>

    <section id="tab-productos" class="hidden">
      <div class="placeholder"><h3>Análisis de Productos</h3><p>Pendiente — se aborda al final del proyecto.</p></div>
    </section>

    <section id="tab-tiempos" class="hidden">
      <div class="metric-switch" id="t-metric">
        <button data-t="corridos" class="on">Días corridos</button>
        <button data-t="habiles">Días hábiles (lun–vie)</button>
      </div>
      <div class="kpi-row" id="t-kpis"></div>
      <div class="panel">
        <h3>Diagrama de estados 2ebox — flujo Casilla</h3>
        <div class="sub">Los estados del sistema 2ebox (Google Sheet "Flujo 2ebox") con la <b>mediana de tiempo entre cada estado</b> sobre las guías filtradas, en días <b>corridos o hábiles</b> según el switch de arriba. Los estados grises son ramas que no siempre ocurren. Comparar unidades (Casilla vs Carga) con el filtro de la izquierda — los tiempos cambian mucho.</div>
        <div id="t-diagram" style="overflow-x:auto"></div>
      </div>
      <div class="panel">
        <h3>Funnel de tiempos — flujo completo del servicio 2ebox</h3>
        <div class="sub">Mediana de días en cada tramo, sobre las guías filtradas. El total real puerta a puerta va en la tarjeta de arriba; acá se apila la mediana de cada tramo (la suma de medianas no coincide con la mediana del total — la diferencia es la cola de guías con esperas largas de factura/pago).</div>
        <div class="flegend" id="t-legend"></div>
        <div id="t-funnel-tiempos"></div>
      </div>
      <div class="grid-2">
        <div class="panel"><h3>Funnel de volumen</h3><div class="sub">Cuántas guías alcanzaron cada etapa (base: despachadas a aeropuerto)</div><div id="t-funnel-vol"></div></div>
        <div class="panel"><h3>Días por tramo — mediana vs p90</h3><div class="sub">p90 = el 90% de las guías tardó eso o menos</div><div class="chart-box tall"><canvas id="c-tramos"></canvas></div></div>
      </div>
      <div class="grid-2" style="margin-top:15px">
        <div class="panel"><h3>Evolución mensual del tiempo total puerta a puerta</h3><div class="sub">Mediana de días ingreso → entrega, por mes de vuelo</div><div class="chart-box"><canvas id="c-total-mes"></canvas></div></div>
        <div class="panel"><h3>Tiempo total puerta a puerta por forwarder</h3><div class="sub">Mediana de días</div><div class="chart-box"><canvas id="c-total-fw"></canvas></div></div>
      </div>
      <div class="panel"><h3>Detalle por tramo del funnel</h3><div class="sub">Días · sobre las guías filtradas</div><div class="tbl-scroll"><table class="dt" id="t-table"></table></div></div>
    </section>

    <section id="tab-ultimamilla" class="hidden">
      <p class="sub">
        Tramo despacho en bodega 2ebox Chile → entregado al cliente, por courier de última milla
        (<code>guia_hijas.ultima_milla</code>: 2 = DropGo, 1 = Bluexpress, resto = sin courier / retiro
        personal). Solo guías <b>ya entregadas</b>, desde ~inicio de 2026 (antes no había courier
        asignado en el sistema). No usa los filtros de la izquierda — tiene los suyos propios.
      </p>
      <div class="fg" style="margin-bottom:16px">
        <h4 style="display:flex;justify-content:space-between">Courier <button data-clear="umc">todos</button></h4>
        <div class="chips" id="f-umc"></div>
      </div>
      <div class="kpi-row" id="um-kpis"></div>

      <div class="panel">
        <h3>Tiempos por mes según courier</h3>
        <div class="sub">Días calendario despacho → entrega, por mes. Una línea por courier.</div>
        <div class="metric-switch" id="um-metric">
          <button data-u="prom" class="on">Promedio</button>
          <button data-u="mediana">Mediana</button>
        </div>
        <div class="chart-box"><canvas id="c-um-mes"></canvas></div>
      </div>

      <div class="panel">
        <h3>Matriz por región</h3>
        <div class="sub">Clic en el encabezado para ordenar · respeta el filtro de courier de arriba</div>
        <div class="tbl-scroll"><table class="dt" id="um-region-table"></table></div>
      </div>

      <div class="panel">
        <h3>RM vs. Regiones (totalizado)</h3>
        <div class="tbl-scroll"><table class="dt" id="um-zona-table"></table></div>
      </div>

      <div class="panel">
        <h3>Matriz por comuna</h3>
        <div class="sub">Clic en el encabezado para ordenar · respeta el filtro de courier de arriba</div>
        <div class="tbl-scroll"><table class="dt" id="um-comuna-table"></table></div>
      </div>
    </section>

    <section id="tab-llenado" class="hidden">
      <p class="sub">
        Cómo se llenan los vuelos (AWB) desde que se crean hasta el <b>despacho a aeropuerto</b>. Fuente: NocoDB
        (<code>guia_madres</code>, <code>guia_hijas</code>, <code>ebox_cumplimiento</code>). <b>Venta</b> = flete
        internacional + handling (USD); <b>costo</b> = tarifa_costo del AWB × kg facturables (Casilla kilo real, Carga
        mayor entre real y volumétrico); <b>margen</b> = venta − costo. El total a pagar (CLP, incluye IVA) se muestra
        solo como referencia. MercadoLibre y Retail van a costo (margen 0). No usa los filtros de la izquierda:
        tiene los suyos. Clic en un AWB o una casilla de cualquier tabla para filtrar toda la sección.
      </p>
      <div class="ll-filters">
        <div class="fg"><h4>Vuelo (AWB)</h4><select id="ll-vuelo"></select></div>
        <div class="fg"><h4>Casilla</h4><input id="ll-cas" list="ll-cas-list" placeholder="CL…" style="width:130px"><datalist id="ll-cas-list"></datalist></div>
        <div class="fg"><h4>Periodo (creación del AWB)</h4>
          <input type="date" id="ll-desde"> <input type="date" id="ll-hasta">
          <div class="metric-switch" id="ll-per" style="margin:6px 0 0">
            <button data-p="4s">4 semanas</button><button data-p="3m" class="on">3 meses</button>
            <button data-p="anio">Año actual</button><button data-p="todo">Todo</button>
          </div>
        </div>
        <div class="fg"><h4>Ejecutiva <button data-llclear="ej">todas</button></h4><div class="chips" id="ll-ej"></div></div>
        <div class="fg"><h4>Tipo de cliente <button data-llclear="seg">todos</button></h4><div class="chips" id="ll-seg"></div></div>
        <button class="reset-all" id="ll-reset" style="width:auto;padding:9px 16px">Limpiar</button>
      </div>
      <div class="notice" id="ll-notice"></div>
      <div class="kpi-row" id="ll-kpis"></div>

      <div class="panel">
        <h3>T1 · Vuelos en llenado</h3>
        <div class="sub">AWB creados y todavía sin despacho a aeropuerto. Kg reales y venta/kg destacados. El volumen (kg volumétrico) es solo referencia.</div>
        <div class="tbl-scroll"><table class="dt" id="ll-t1"></table></div>
      </div>

      <div class="grid-2">
        <div class="panel"><h3>G1 · Curva de llenado</h3><div class="sub">Kg reales acumulados por día desde la creación del AWB. Línea punteada = curva promedio de los últimos vuelos despachados del mismo forwarder (referencia de equilibrio: no hay costos fijos por AWB en la base).</div><div class="chart-box"><canvas id="c-ll-curva"></canvas></div></div>
        <div class="panel"><h3>G2 · Margen acumulado día a día</h3><div class="sub">US$ de margen acumulado por día desde la creación, vs. el promedio de los vuelos anteriores del mismo forwarder.</div><div class="chart-box"><canvas id="c-ll-margen"></canvas></div></div>
      </div>

      <div class="panel" style="margin-top:15px">
        <h3>G3 · Proyección al cierre</h3>
        <div class="sub" id="ll-proy-sub"></div>
        <div class="grid-2">
          <div class="chart-box" style="height:170px"><canvas id="c-ll-proy-kg"></canvas></div>
          <div class="chart-box" style="height:170px"><canvas id="c-ll-proy-mg"></canvas></div>
        </div>
      </div>

      <div class="panel">
        <h3>T5 · Guías listas para subir (1 a 1) y probabilidad de vuelo</h3>
        <div class="sub">Guías "listas para volar" (pago + Miami con factura) sin AWB. <b>Cartera</b> = FOB del cliente ya subido al vuelo abierto + sus otras guías listas. Tramos: &lt; 500 (sin ad valorem), 500–3.000 (ad valorem 6% sobre CIF), ≥ 3.000 (agente de aduana). <b>Regla</b>: Alta si &lt; 500, guía única o Computadores y Partes (exenta); Media 500–3.000; Baja ≥ 3.000. <b>%</b> = tasa histórica de guías en ese tramo que volaron en su primer vuelo, promediada con el historial del cliente si tiene ≥ 3 guías. Ad valorem = el que ya calculó el sistema para la guía.</div>
        <div class="metric-switch" id="ll-t5-sw">
          <button data-s="pag" class="on">Listas (pago + factura)</button>
          <button data-s="sinpago">Con factura, sin pago</button>
          <button data-s="todas">Todas</button>
        </div>
        <div class="kpi-row" id="ll-t5-kpis"></div>
        <div class="tbl-scroll" style="max-height:520px;overflow-y:auto"><table class="dt" id="ll-t5"></table></div>
      </div>

      <div class="panel">
        <h3>T3 · Matriz de subida de guías</h3>
        <div class="sub">Filas = semanas (agrupadas por mes), columnas = día de subida al AWB (hora Chile). Cada celda: guías subidas ese día y, abajo, el AWB. Si se trabajaron 2 vuelos en paralelo, aparecen los dos.</div>
        <div class="tbl-scroll" style="max-height:560px;overflow-y:auto"><table class="dt ll-mx" id="ll-t3"></table></div>
      </div>

      <div class="panel">
        <h3>T2 · Vuelos despachados y tiempo de ciclo</h3>
        <div class="sub">Días entre la creación del AWB y el despacho a aeropuerto. Margen final = venta − costo de las guías del vuelo.</div>
        <div class="tbl-scroll" style="max-height:460px;overflow-y:auto"><table class="dt" id="ll-t2"></table></div>
      </div>

      <div class="panel">
        <h3>T4 · Ratios por vuelo vs. promedio</h3>
        <div class="sub">Promedio = vuelos despachados del periodo filtrado. Alertas: venta/kg bajo 85% del promedio, kg/guía sobre 150% del promedio (guías pesadas), o un solo cliente con más del 40% de los kg.</div>
        <div class="tbl-scroll" style="max-height:460px;overflow-y:auto"><table class="dt" id="ll-t4"></table></div>
      </div>

      <div class="panel">
        <h3>G4 · Composición del vuelo</h3>
        <div class="sub">Últimos 12 vuelos del filtro. La última barra es el promedio por vuelo del periodo. Incluye MercadoLibre y Retail aunque estén desmarcados arriba.</div>
        <div class="metric-switch" id="ll-g4-by"><button data-b="seg" class="on">Por tipo de cliente</button><button data-b="ej">Por ejecutiva</button></div>
        <div class="metric-switch" id="ll-g4-m"><button data-m="kg" class="on">Kg reales</button><button data-m="tp">Total a pagar (CLP)</button><button data-m="mg">Margen (US$)</button></div>
        <div class="chart-box tall"><canvas id="c-ll-comp"></canvas></div>
      </div>

      <div class="grid-2">
        <div class="panel"><h3>G5 · Kg vs. venta por guía</h3><div class="sub">Un punto por guía de los últimos 8 vuelos del filtro, color por vuelo. Abajo a la derecha = guías pesadas que pagan poco.</div><div class="chart-box tall"><canvas id="c-ll-disp"></canvas></div></div>
        <div class="panel"><h3>G6 · Tiempo de espera para subir</h3><div class="sub">Días entre "lista para volar" y la subida al AWB (0 si se subió antes de quedar lista). Histograma y promedio semanal.</div>
          <div class="chart-box" style="height:175px"><canvas id="c-ll-esp-h"></canvas></div>
          <div class="chart-box" style="height:175px;margin-top:8px"><canvas id="c-ll-esp-s"></canvas></div>
        </div>
      </div>
    </section>
  </main>
</div>

<script>
const DB = __PAYLOAD__;
const CI = {}; DB.cols.forEach((c,i)=>CI[c]=i);
const UM = __PAYLOAD_UM__;
const MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
const FW_COLOR = {
  "SKY":"#5691DF","LATAM Cargo":"#E3203E","Trans Caribbean":"#152C4A","Avianca":"#2E9E6B",
  "Kalitta":"#7B92A4","Tampa Cargo":"#E0A100","Air Express":"#A7C5E1","Mercury":"#B5651D",
  "Sin forwarder":"#C9C9C9"
};
const fwColor = fw => FW_COLOR[fw] || "#9AAEC2";

// Estados reales del flujo Casilla 2ebox (Google Sheet "Flujo 2ebox", 2025).
// ESTADOS[i] -> ESTADOS[i+1] es el tramo STAGES[i].
const ESTADOS = ["Recepcionado en USA","Ingresado a Miami","Miami con factura","Primer pago",
  "Asociado a Guía Madre","Despachado a Aeropuerto","Arribado a Chile","Recibido Aduana",
  "En Bodega 2ebox Chile","En despacho","Entregado"];
const STAGES = [
  {k:"d_rec_ing",  de:"Recepcionado en USA", a:"Ingresado a Miami",      flujo:"Miami"},
  {k:"d_ing_mcf",  de:"Ingresado a Miami",   a:"Miami con factura",      flujo:"Cliente / Miami"},
  {k:"d_mcf_pago", de:"Miami con factura",   a:"Primer pago",            flujo:"Cliente / Miami"},
  {k:"d_pago_asig",de:"Primer pago",         a:"Asociado a Guía Madre",  flujo:"Miami"},
  {k:"d_asig_desp",de:"Asociado a Guía Madre",a:"Despachado a Aeropuerto",flujo:"Miami"},
  {k:"d_desp_arr", de:"Despachado a Aeropuerto",a:"Arribado a Chile",    flujo:"Vuelo"},
  {k:"d_arr_adu",  de:"Arribado a Chile",    a:"Recibido Aduana",        flujo:"Internación"},
  {k:"d_adu_bod",  de:"Recibido Aduana",     a:"En Bodega 2ebox Chile",  flujo:"Internación"},
  {k:"d_bod_dch",  de:"En Bodega 2ebox Chile",a:"En despacho",           flujo:"Última milla"},
  {k:"d_dch_ent",  de:"En despacho",         a:"Entregado",              flujo:"Última milla"},
];
STAGES.forEach(s=>s.lbl=s.de+" → "+s.a);
const FLUJO_COLOR = {"Cliente / Miami":"#A7C5E1","Miami":"#5691DF","Vuelo":"#E3203E","Internación":"#152C4A","Última milla":"#2E9E6B"};

const F = {fy:new Set(), fm:new Set(), fw:new Set(), un:new Set(), umc:new Set()};
let TAB = "performance", PMETRIC = "costo", MXMETRIC = "tarifa", MGMETRIC = "vuelo", MGVALUE = "margen", TMETRIC = "corridos", UMMETRIC = "prom";
const charts = {};
// key del tramo según toggle corridos/hábiles: "d_xxx" -> "dh_xxx"
const dk = k => TMETRIC==="habiles" ? k.replace(/^d_/,"dh_") : k;

// todos los forwarders reales aparecen sueltos (Jorge, 2026-09-22) -- antes
// los de <5 guias se plegaban en "Otro", pero eso escondia forwarders reales
// como DHL.
const YEARS = [...new Set(DB.rows.map(r=>r[CI.fy]))].sort();
const FWS = DB.meta.forwarders.map(x=>x[0]);
const UNS = DB.meta.unidades.map(x=>x[0]);
const UM_COURIERS = UM.meta.por_courier.map(x=>x[0]);

const H2D = h => h==null ? null : h/24;
function median(a){const v=a.filter(x=>x!=null).sort((x,y)=>x-y);if(!v.length)return null;const m=v.length>>1;return v.length%2?v[m]:(v[m-1]+v[m])/2;}
function pctl(a,p){const v=a.filter(x=>x!=null).sort((x,y)=>x-y);if(!v.length)return null;return v[Math.min(v.length-1,Math.floor(v.length*p))];}
function mean(a){const v=a.filter(x=>x!=null);return v.length?v.reduce((s,x)=>s+x,0)/v.length:null;}
const nf = new Intl.NumberFormat("es-CL");
const fmtN = n => n==null?"–":nf.format(Math.round(n));
const fmt1 = n => n==null?"–":n.toLocaleString("es-CL",{maximumFractionDigits:1});
const fmt2 = n => n==null?"–":n.toLocaleString("es-CL",{maximumFractionDigits:2});
const fmtUSD = n => n==null?"–":"US$"+nf.format(Math.round(n));
const fmtKg = n => n==null?"–":nf.format(Math.round(n))+" kg";

function filtered(){
  return DB.rows.filter(r=>
    (!F.fy.size||F.fy.has(r[CI.fy])) && (!F.fm.size||F.fm.has(r[CI.fm])) &&
    (!F.fw.size||F.fw.has(r[CI.fw])) && (!F.un.size||F.un.has(r[CI.un])));
}

function buildChips(){
  const mk=(host,items,key,fmt)=>{host.innerHTML="";items.forEach(v=>{
    const c=document.createElement("span");
    c.className="chip"+(key==="fm"?" mes":"");
    c.textContent=fmt?fmt(v):v;
    c.onclick=()=>{F[key].has(v)?F[key].delete(v):F[key].add(v);c.classList.toggle("on");render();};
    host.appendChild(c);});};
  mk(document.getElementById("f-fy"),YEARS,"fy");
  mk(document.getElementById("f-fm"),[1,2,3,4,5,6,7,8,9,10,11,12],"fm",m=>MESES[m-1]);
  mk(document.getElementById("f-fw"),FWS,"fw");
  mk(document.getElementById("f-un"),UNS,"un");
  mk(document.getElementById("f-umc"),UM_COURIERS,"umc");
}
document.querySelectorAll("[data-clear]").forEach(b=>b.onclick=()=>{
  const k=b.dataset.clear;F[k].clear();
  document.querySelectorAll(`#f-${k} .chip`).forEach(c=>c.classList.remove("on"));render();});
document.getElementById("reset-all").onclick=()=>{
  Object.values(F).forEach(s=>s.clear());
  document.querySelectorAll(".chip.on").forEach(c=>c.classList.remove("on"));render();};

document.getElementById("tabs").onclick=e=>{
  const b=e.target.closest(".tab");if(!b)return;TAB=b.dataset.tab;
  document.querySelectorAll(".tab").forEach(t=>t.classList.toggle("active",t===b));
  ["resumen","performance","productos","tiempos","ultimamilla","llenado"].forEach(t=>
    document.getElementById("tab-"+t).classList.toggle("hidden",t!==TAB));
  // Llenado de Vuelos tiene sus propios filtros arriba -> se esconde la barra lateral
  document.querySelector(".sidebar").classList.toggle("hidden",TAB==="llenado");
  render();};
document.getElementById("perf-metric").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;PMETRIC=b.dataset.m;
  document.querySelectorAll("#perf-metric button").forEach(x=>x.classList.toggle("on",x===b));
  render();};
document.getElementById("mx-metric").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;MXMETRIC=b.dataset.x;
  document.querySelectorAll("#mx-metric button").forEach(x=>x.classList.toggle("on",x===b));
  renderMatrix();};
document.getElementById("mg-metric").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;MGMETRIC=b.dataset.g;
  document.querySelectorAll("#mg-metric button").forEach(x=>x.classList.toggle("on",x===b));
  renderMatrixMargen();};
document.getElementById("mg-valor").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;MGVALUE=b.dataset.v;
  document.querySelectorAll("#mg-valor button").forEach(x=>x.classList.toggle("on",x===b));
  renderMatrixMargen();};
document.getElementById("t-metric").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;TMETRIC=b.dataset.t;
  document.querySelectorAll("#t-metric button").forEach(x=>x.classList.toggle("on",x===b));
  renderTiempos();};
document.getElementById("um-metric").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;UMMETRIC=b.dataset.u;
  document.querySelectorAll("#um-metric button").forEach(x=>x.classList.toggle("on",x===b));
  renderUltimaMilla();};

function newChart(id,cfg){if(charts[id])charts[id].destroy();charts[id]=new Chart(document.getElementById(id),cfg);}
const baseOpts={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},animation:false};

// CK = índice de la columna de costo activa (real o estimado)
function byForwarder(rows, CK){
  const g={};
  rows.forEach(r=>{
    const k=r[CI.fw];
    (g[k]||(g[k]={fw:k,n:0,ent:0,peso:0,pesoVol:0,costo:0,nCosto:0,pesoCosto:0,venta:0,costoMg:0,nMg:0,vuelos:new Set(),transit:[],total:[]}));
    const o=g[k];o.n++;o.ent+=r[CI.entregada];o.peso+=r[CI.peso]||0;o.pesoVol+=r[CI.peso_vol]||0;
    if(r[CI.gm_id])o.vuelos.add(r[CI.gm_id]);
    if(CK!=null && r[CK]){
      o.costo+=r[CK];o.nCosto++;o.pesoCosto+=r[CI.peso_fact]||0;  // peso_fact = billable (Carga)
      // margen: solo guias con costo Y venta calzados (no diluir con ceros fantasma)
      if(r[CI.venta_usd]){o.venta+=r[CI.venta_usd];o.costoMg+=r[CK];o.nMg++;}
    }
    if(r[CI.d_desp_arr]!=null)o.transit.push(H2D(r[CI.d_desp_arr]));
    if(r[CI.d_total]!=null)o.total.push(H2D(r[CI.d_total]));
  });
  return Object.values(g).map(o=>({...o, nVuelos:o.vuelos.size,
    entPct:o.n?o.ent/o.n*100:0, transitMed:median(o.transit), totalMed:median(o.total),
    volRatio:o.peso?o.pesoVol/o.peso:null, guiasVuelo:o.vuelos.size?o.n/o.vuelos.size:null,
    costoKg:o.pesoCosto?o.costo/o.pesoCosto:null, costoGuia:o.nCosto?o.costo/o.nCosto:null,
    margenUsd:o.nMg?o.venta-o.costoMg:null, margenPct:o.venta?(o.venta-o.costoMg)/o.venta*100:null,
    margenGuia:o.nMg?(o.venta-o.costoMg)/o.nMg:null,
  })).sort((a,b)=>b.n-a.n);
}

function renderPerformance(){
  const rows=filtered();
  const costoMode = PMETRIC==="costo" || PMETRIC==="costoest";
  const useEst = PMETRIC==="costoest";
  const CK = !costoMode ? null : (useEst ? CI.costo_est_usd : CI.costo_flete_usd);
  const g=byForwarder(rows, CK);
  const totN=rows.length, totEnt=rows.reduce((s,r)=>s+r[CI.entregada],0);
  const totPeso=rows.reduce((s,r)=>s+(r[CI.peso]||0),0);
  const totPesoVol=rows.reduce((s,r)=>s+(r[CI.peso_vol]||0),0);
  const rowsCosto = costoMode ? rows.filter(r=>r[CK]) : [];
  const totCosto=rowsCosto.reduce((s,r)=>s+r[CK],0);
  const pesoCosto=rowsCosto.reduce((s,r)=>s+(r[CI.peso_fact]||0),0);  // peso facturable
  const nEstReal = rows.filter(r=>r[CI.costo_estimado]).length;
  const rowsMg = costoMode ? rowsCosto.filter(r=>r[CI.venta_usd]) : [];
  const totVenta=rowsMg.reduce((s,r)=>s+r[CI.venta_usd],0);
  const totCostoMg=rowsMg.reduce((s,r)=>s+r[CK],0);
  const totMargen=totVenta-totCostoMg;
  const nVuelos = new Set(rows.filter(r=>r[CI.gm_id]).map(r=>r[CI.gm_id])).size;
  const transitAll=median(rows.map(r=>H2D(r[CI.d_desp_arr])));
  const p2p=median(rows.map(r=>H2D(r[CI.d_total])));

  document.getElementById("perf-costo-charts").classList.toggle("hidden",!costoMode);
  document.getElementById("perf-costo-charts2").classList.toggle("hidden",!costoMode);
  const nt=document.getElementById("perf-notice");
  if(costoMode){
    nt.classList.remove("hidden");
    nt.innerHTML = useEst
      ? `<b>Costo con estimados.</b> Donde el vuelo no trae <code>tarifa_costo</code> real, se imputa la mediana de tarifa del <b>mismo forwarder en el mismo año</b> (mes → trimestre → año). `+
        `No se cruza de año (las tarifas aéreas cambian), así que <b>2023–2024 siguen casi sin cubrir</b> — ningún vuelo de esos años tiene tarifa real para calibrar. `+
        `Filtro actual: <b>${fmtN(rowsCosto.length)}</b> guías con costo (${fmtN(rowsCosto.length-nEstReal)} real + ${fmtN(nEstReal)} estimado), de ${fmtN(totN)}.`
      : `<b>Costo real.</b> Solo guías cuyo vuelo tiene <code>tarifa_costo</code> cargada en NocoDB (desde 2025). `+
        `Filtro actual: <b>${fmtN(rowsCosto.length)}</b> guías con costo real, de ${fmtN(totN)}. `+
        `Probá "Costo con estimados" para rellenar 2025 con la tarifa del mismo forwarder.`;
    nt.innerHTML += ` <b>Margen:</b> venta = <code>instrucciones_especiales</code> ("TARIFA") si existe, si no `+
      `(transporte internacional + handling) ÷ peso, ambos de <code>guia_hijas</code>. Solo se calcula donde hay `+
      `costo Y venta calzados: <b>${fmtN(rowsMg.length)}</b> guías de ${fmtN(rowsCosto.length)} con costo.`;
  } else nt.classList.add("hidden");

  const kpis = costoMode ? [
    ["Vuelos (AWB)",fmtN(nVuelos),nVuelos?fmt1(totN/nVuelos)+" guías/vuelo":""],
    ["Guías con costo",fmtN(rowsCosto.length), useEst&&nEstReal?fmtN(nEstReal)+" estimadas":""],
    ["Costo total de flete",fmtUSD(totCosto)],
    ["Costo promedio por guía",fmtUSD(rowsCosto.length?totCosto/rowsCosto.length:null)],
    ["Costo por kilo",pesoCosto?"US$"+fmt2(totCosto/pesoCosto):"–"],
    ["Kilo/vol vs real",totPeso?"×"+fmt2(totPesoVol/totPeso):"–","peso volumétrico ÷ peso real"],
    ["Margen bruto total",rowsMg.length?fmtUSD(totMargen):"–",fmtN(rowsMg.length)+" guías con venta"],
    ["Margen %",totVenta?fmt1(totMargen/totVenta*100)+"%":"–"],
    ["Margen promedio por guía",rowsMg.length?fmtUSD(totMargen/rowsMg.length):"–"],
  ] : [
    ["Vuelos (AWB)",fmtN(nVuelos),nVuelos?fmt1(totN/nVuelos)+" guías/vuelo":""],
    ["Guías transportadas",fmtN(totN)],
    ["Guías entregadas",fmtN(totEnt),(totN?(totEnt/totN*100).toFixed(1):0)+"% de entrega"],
    ["Kilos transportados",fmtKg(totPeso)],
    ["Kilo/vol (peso volumétrico)",fmtKg(totPesoVol),totPeso?"×"+fmt2(totPesoVol/totPeso)+" vs peso real":""],
    ["Puerta a puerta (mediana)",fmt1(p2p)+" d"],
  ];
  document.getElementById("perf-kpis").innerHTML=kpis.map(([l,v,s])=>
    `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div>${s?`<div class="s">${s}</div>`:""}</div>`).join("");

  const labels=g.map(x=>x.fw), col=g.map(x=>fwColor(x.fw));
  if(costoMode){
    const gc=g.filter(x=>x.costo>0);
    newChart("c-costo-total",{type:"bar",data:{labels:gc.map(x=>x.fw),datasets:[{data:gc.map(x=>Math.round(x.costo)),backgroundColor:gc.map(x=>fwColor(x.fw))}]},
      options:{...baseOpts,plugins:{...baseOpts.plugins,tooltip:{callbacks:{label:c=>fmtUSD(c.raw)}}}}});
    newChart("c-costo-kg",{type:"bar",data:{labels:gc.map(x=>x.fw),datasets:[{data:gc.map(x=>x.costoKg?+x.costoKg.toFixed(2):0),backgroundColor:gc.map(x=>fwColor(x.fw))}]},
      options:{...baseOpts,plugins:{...baseOpts.plugins,tooltip:{callbacks:{label:c=>"US$"+fmt2(c.raw)+" /kg"}}}}});
    newChart("c-costo-guia",{type:"bar",data:{labels:gc.map(x=>x.fw),datasets:[{data:gc.map(x=>x.costoGuia?+x.costoGuia.toFixed(1):0),backgroundColor:gc.map(x=>fwColor(x.fw))}]},
      options:{...baseOpts,plugins:{...baseOpts.plugins,tooltip:{callbacks:{label:c=>fmtUSD(c.raw)+" /guía"}}}}});
    const meses=[...new Set(rowsCosto.map(r=>r[CI.fy]*100+r[CI.fm]))].sort();
    const mLbl=meses.map(m=>MESES[m%100-1]+" "+String(Math.floor(m/100)).slice(2));
    const topFw=gc.slice(0,5).map(x=>x.fw);
    newChart("c-costo-kg-mes",{type:"line",data:{labels:mLbl,datasets:topFw.map(fw=>({
      label:fw,borderColor:fwColor(fw),backgroundColor:"transparent",spanGaps:true,tension:.3,
      data:meses.map(m=>{const rr=rowsCosto.filter(r=>r[CI.fw]===fw&&r[CI.fy]*100+r[CI.fm]===m);
        const p=rr.reduce((s,r)=>s+(r[CI.peso]||0),0),c=rr.reduce((s,r)=>s+r[CK],0);
        return p?+(c/p).toFixed(2):null;})}))},
      options:{...baseOpts,plugins:{legend:{display:true,position:"bottom"}}}});
  }

  newChart("c-guias",{type:"bar",data:{labels,datasets:[
      {label:"Transportadas",data:g.map(x=>x.n),backgroundColor:"#A7C5E1"},
      {label:"Entregadas",data:g.map(x=>x.ent),backgroundColor:"#5691DF"}]},
    options:{...baseOpts,plugins:{legend:{display:true,position:"bottom"}}}});
  newChart("c-transito",{type:"bar",data:{labels,datasets:[{data:g.map(x=>x.transitMed?+x.transitMed.toFixed(1):0),backgroundColor:col}]},
    options:{...baseOpts,plugins:{...baseOpts.plugins,tooltip:{callbacks:{label:c=>fmt1(c.raw)+" días"}}}}});

  const T=document.getElementById("perf-table");
  const ck = useEst?"Costo est.":"Costo real";
  const cH = costoMode ? ["Guías c/costo",ck+" total (US$)","Costo/kg (US$)","Costo/guía (US$)","Venta (US$)","Margen (US$)","Margen %"] : [];
  const cR = x => costoMode ? [fmtN(x.nCosto),x.costo?fmtUSD(x.costo):"–",x.costoKg?fmt2(x.costoKg):"–",x.costoGuia?fmt1(x.costoGuia):"–",
    x.venta?fmtUSD(x.venta):"–",x.margenUsd!=null?fmtUSD(x.margenUsd):"–",x.margenPct!=null?fmt1(x.margenPct)+"%":"–"] : [];
  const head=["Forwarder","Vuelos","Guías","Guías/vuelo","Entregadas","Kilos","Kilo/vol","Vol/real",...cH,"Tránsito aéreo (d)","Puerta a puerta (d)"];
  const body=g.map(x=>[x.fw,fmtN(x.nVuelos),fmtN(x.n),x.guiasVuelo?fmt1(x.guiasVuelo):"–",fmtN(x.ent),fmtKg(x.peso),fmtKg(x.pesoVol),
    x.volRatio?"×"+fmt2(x.volRatio):"–",...cR(x),
    x.transitMed?fmt1(x.transitMed):"–",x.totalMed?fmt1(x.totalMed):"–"]);
  const cF = costoMode ? [fmtN(rowsCosto.length),totCosto?fmtUSD(totCosto):"–",pesoCosto?fmt2(totCosto/pesoCosto):"–",rowsCosto.length?fmt1(totCosto/rowsCosto.length):"–",
    totVenta?fmtUSD(totVenta):"–",rowsMg.length?fmtUSD(totMargen):"–",totVenta?fmt1(totMargen/totVenta*100)+"%":"–"] : [];
  const foot=["Total",fmtN(nVuelos),fmtN(totN),nVuelos?fmt1(totN/nVuelos):"–",fmtN(totEnt),fmtKg(totPeso),fmtKg(totPesoVol),
    totPeso?"×"+fmt2(totPesoVol/totPeso):"–",...cF,transitAll?fmt1(transitAll):"–",fmt1(p2p)];
  renderTable(T,head,body,foot);
  renderMatrix();
  renderMatrixMargen();
  renderSemanas(rows);
}

// Kilos volados por semana -- respeta TODOS los filtros (fy/fm/fw/un), a
// diferencia de las matrices de arriba (que ignoran fy/fm a propósito).
function renderSemanas(rows){
  const g={};
  rows.forEach(r=>{
    const wk=r[CI.semana]; if(!wk) return;
    (g[wk]||(g[wk]={peso:0,n:0,vuelos:new Set()}));
    g[wk].peso+=r[CI.peso]||0; g[wk].n++;
    if(r[CI.gm_id]) g[wk].vuelos.add(r[CI.gm_id]);
  });
  const weeks=Object.keys(g).sort();
  const head=["Semana","Vuelos","Guías","Kilos","Kilos/guía"];
  const body=weeks.map(wk=>{const o=g[wk];
    return [wk, fmtN(o.vuelos.size), fmtN(o.n), fmtKg(o.peso), o.n?fmt1(o.peso/o.n):"–"];});
  const totPeso=weeks.reduce((s,wk)=>s+g[wk].peso,0), totN=weeks.reduce((s,wk)=>s+g[wk].n,0);
  const totVuelos=new Set(); weeks.forEach(wk=>g[wk].vuelos.forEach(v=>totVuelos.add(v)));
  const foot=["Total", fmtN(totVuelos.size), fmtN(totN), fmtKg(totPeso), totN?fmt1(totPeso/totN):"–"];
  renderTable(document.getElementById("perf-semanas"), head, body, foot);
}

// Matriz año x mes — respeta filtros de forwarder y unidad (no año/mes)
function renderMatrix(){
  const rows=DB.rows.filter(r=>(!F.fw.size||F.fw.has(r[CI.fw])) && (!F.un.size||F.un.has(r[CI.un])));
  const years=YEARS;
  const acc={};
  years.forEach(y=>{for(let m=1;m<=12;m++)acc[y+"-"+m]={peso:0,n:0,costo:0,pesoC:0,vuelos:new Set()};});
  rows.forEach(r=>{
    const o=acc[r[CI.fy]+"-"+r[CI.fm]]; if(!o)return;
    o.n++; o.peso+=r[CI.peso]||0;
    if(r[CI.gm_id]) o.vuelos.add(r[CI.gm_id]);
    if(r[CI.costo_est_usd]){ o.costo+=r[CI.costo_est_usd]; o.pesoC+=r[CI.peso_fact]||0; }
  });
  const M=MXMETRIC;  // "tarifa" | "kilos" | "kilosvuelo" | "guias"
  const agg = ks => {
    let peso=0,n=0,costo=0,pesoC=0; const vs=new Set();
    ks.forEach(k=>{const o=acc[k];peso+=o.peso;n+=o.n;costo+=o.costo;pesoC+=o.pesoC;o.vuelos.forEach(x=>vs.add(x));});
    return {peso,n,costo,pesoC,nv:vs.size};
  };
  const val = a => M==="tarifa"     ? (a.costo && a.pesoC ? a.costo/a.pesoC : null)
                 : M==="kilosvuelo" ? (a.nv ? a.peso/a.nv : null)
                 : M==="guias"      ? (a.n || null)
                                    : (a.n ? a.peso/a.n : null);
  const fmt2f = v => v.toLocaleString("es-CL",{minimumFractionDigits:2,maximumFractionDigits:2});
  const fmtCell = v => v==null ? "–" : (M==="tarifa" ? fmt2f(v) : M==="guias" ? fmtN(v) : fmt1(v));
  const subN = a => M==="guias" ? 0 : M==="kilosvuelo" ? a.nv : a.n;   // n mostrado: vuelos o guías (guias ya es el valor principal)

  const cellVal = k => val(agg([k]));
  const vals=[]; for(const k in acc){const v=cellVal(k); if(v!=null)vals.push(v);}
  const lo=Math.min(...vals), hi=Math.max(...vals);
  const bg=v=>{ if(v==null||hi===lo)return ""; const t=(v-lo)/(hi-lo);
    return `background:rgba(86,145,223,${(0.06+t*0.4).toFixed(2)})`; };
  const cnt=x=> x?`<span class="mx-n">· ${fmtN(x)}</span>`:"";

  const T=document.getElementById("perf-matrix");
  const unit = M==="kilosvuelo" ? "kg/AWB" : "";
  let html=`<thead><tr><th>Mes</th>`+years.map(y=>`<th>${y}</th>`).join("")+`<th>Todos</th></tr></thead><tbody>`;
  for(let m=1;m<=12;m++){
    html+=`<tr><td>${MESES[m-1]}</td>`;
    years.forEach(y=>{const a=agg([y+"-"+m]); const v=val(a);
      html+=`<td style="${bg(v)}">${fmtCell(v)}${cnt(subN(a))}</td>`;});
    const ra=agg(years.map(y=>y+"-"+m));
    html+=`<td><b>${fmtCell(val(ra))}</b>${cnt(subN(ra))}</td></tr>`;
  }
  html+=`<tr><td><b>Todos</b></td>`;
  years.forEach(y=>{ const a=agg(Array.from({length:12},(_,i)=>y+"-"+(i+1)));
    html+=`<td><b>${fmtCell(val(a))}</b>${cnt(subN(a))}</td>`;});
  html+=`<td><b>${fmtCell(val(agg(Object.keys(acc))))}</b></td></tr></tbody>`;
  T.innerHTML=html;
}

// Matriz año x mes — margen (venta - costo). Igual criterio que renderMatrix
// pero solo suma filas con costo Y venta calzados (mismo par usado en
// byForwarder/KPIs de margen), asi que costo aca es costo_est_usd (no el
// costo_flete_usd real puro) para no perder cobertura fuera de 2025-2026.
function renderMatrixMargen(){
  const rows=DB.rows.filter(r=>(!F.fw.size||F.fw.has(r[CI.fw])) && (!F.un.size||F.un.has(r[CI.un])));
  const years=YEARS;
  const acc={};
  years.forEach(y=>{for(let m=1;m<=12;m++)acc[y+"-"+m]={venta:0,costo:0,n:0,vuelos:new Set()};});
  rows.forEach(r=>{
    const o=acc[r[CI.fy]+"-"+r[CI.fm]]; if(!o)return;
    if(r[CI.costo_est_usd] && r[CI.venta_usd]){
      o.venta+=r[CI.venta_usd]; o.costo+=r[CI.costo_est_usd]; o.n++;
      if(r[CI.gm_id]) o.vuelos.add(r[CI.gm_id]);
    }
  });
  const M=MGMETRIC;    // "vuelo" | "guia" | "total"
  const V=MGVALUE;     // "margen" | "venta"
  const agg = ks => {
    let venta=0,costo=0,n=0; const vs=new Set();
    ks.forEach(k=>{const o=acc[k];venta+=o.venta;costo+=o.costo;n+=o.n;o.vuelos.forEach(x=>vs.add(x));});
    return {venta,costo,n,nv:vs.size,margen:venta-costo};
  };
  const val = a => {
    if(!a.n) return null;
    const base = V==="venta" ? a.venta : a.margen;
    return M==="vuelo" ? (a.nv ? base/a.nv : null)
         : M==="guia"  ? base/a.n
                        : base;
  };
  const fmtCell = v => v==null ? "–" : fmtUSD(v);
  const subN = a => M==="vuelo" ? a.nv : a.n;

  const cellVal = k => val(agg([k]));
  const vals=[]; for(const k in acc){const v=cellVal(k); if(v!=null)vals.push(v);}
  const lo=Math.min(...vals), hi=Math.max(...vals);
  const bg=v=>{ if(v==null||hi===lo)return ""; const t=(v-lo)/(hi-lo);
    return `background:rgba(86,145,223,${(0.06+t*0.4).toFixed(2)})`; };
  const cnt=x=> x?`<span class="mx-n">· ${fmtN(x)}</span>`:"";

  const T=document.getElementById("perf-matrix-margen");
  let html=`<thead><tr><th>Mes</th>`+years.map(y=>`<th>${y}</th>`).join("")+`<th>Todos</th></tr></thead><tbody>`;
  for(let m=1;m<=12;m++){
    html+=`<tr><td>${MESES[m-1]}</td>`;
    years.forEach(y=>{const a=agg([y+"-"+m]); const v=val(a);
      html+=`<td style="${bg(v)}">${fmtCell(v)}${cnt(subN(a))}</td>`;});
    const ra=agg(years.map(y=>y+"-"+m));
    html+=`<td><b>${fmtCell(val(ra))}</b>${cnt(subN(ra))}</td></tr>`;
  }
  html+=`<tr><td><b>Todos</b></td>`;
  years.forEach(y=>{ const a=agg(Array.from({length:12},(_,i)=>y+"-"+(i+1)));
    html+=`<td><b>${fmtCell(val(a))}</b>${cnt(subN(a))}</td>`;});
  html+=`<td><b>${fmtCell(val(agg(Object.keys(acc))))}</b></td></tr></tbody>`;
  T.innerHTML=html;
}

// --- Diagrama de estados (SVG horizontal, estilo flujo 2ebox) ---
function renderDiagram(rows, sv){
  const N=ESTADOS.length, W=124, GAP=46, PITCH=W+GAP, H=250, midY=120, nodeH=46;
  const totW=N*W+(N-1)*GAP+20;
  const nx=i=>10+i*PITCH, ncx=i=>nx(i)+W/2;
  const wrap=(t)=>{ // parte el label en <=2 lineas
    const w=t.split(" "); if(w.length<3) return [t];
    let a=[],b=[],half=Math.ceil(w.length/2); w.forEach((x,i)=>(i<half?a:b).push(x));
    return [a.join(" "), b.join(" ")];
  };
  const node=(i,txt,cls,y)=>{
    const ls=wrap(txt), yy=y??(midY-nodeH/2);
    const fill = cls==="branch"?"var(--diag-branch-fill)":(i===N-1?"var(--diag-final-fill)":"var(--diag-normal-fill)");
    const stroke = cls==="branch"?"var(--diag-branch-stroke)":(i===N-1?"var(--diag-final-stroke)":"var(--diag-normal-stroke)");
    let t=`<g class="node ${cls||""}"><rect x="${nx(i)}" y="${yy}" width="${W}" height="${nodeH}" rx="9" fill="${fill}" stroke="${stroke}"/>`;
    ls.forEach((l,k)=>t+=`<text x="${ncx(i)}" y="${yy+nodeH/2+(ls.length>1?(k?7:-4):3)}" text-anchor="middle">${l}</text>`);
    return t+"</g>";
  };
  // arista main i -> i+1 con la mediana del stage i
  const edge=(i)=>{
    const s=STAGES[i], vals=sv[s.k], m=median(vals), n=vals.filter(x=>x!=null).length;
    const x1=nx(i)+W, x2=nx(i+1), y=midY;
    return `<line x1="${x1}" y1="${y}" x2="${x2-7}" y2="${y}" stroke="${FLUJO_COLOR[s.flujo]}" stroke-width="2"/>`
      +`<path d="M${x2-7},${y-4} L${x2},${y} L${x2-7},${y+4} Z" fill="${FLUJO_COLOR[s.flujo]}"/>`
      +`<text class="edgelbl" x="${(x1+x2)/2}" y="${y-8}" text-anchor="middle">${m==null?"s/d":fmt1(m)+" d"}</text>`
      +`<text class="edgesub" x="${(x1+x2)/2}" y="${y+13}" text-anchor="middle">n=${fmtN(n)}</text>`;
  };
  let svg=`<svg viewBox="0 0 ${totW} ${H}" width="${totW}" height="${H}" role="img">`;
  for(let i=0;i<N-1;i++) svg+=edge(i);
  ESTADOS.forEach((e,i)=>svg+=node(i,e));
  // ramas (sin timing salvo retención)
  const nRet=rows.reduce((a,r)=>a+r[CI.retenida],0), pRet=rows.length?100*nRet/rows.length:0;
  const branchTop=(i,txt)=>`<line x1="${ncx(i)}" y1="${midY-nodeH/2}" x2="${ncx(i)}" y2="34" stroke="var(--diag-branch-stroke)" stroke-dasharray="3 3"/>`+node(i,txt,"branch",8);
  const branchBot=(i,txt,y)=>`<line x1="${ncx(i)}" y1="${midY+nodeH/2}" x2="${ncx(i)}" y2="${(y||195)}" stroke="var(--diag-branch-stroke)" stroke-dasharray="3 3"/>`+node(i,txt,"branch",y||195);
  svg+=branchTop(1,"Nula / Restringido / Retiro Miami");
  svg+=branchBot(1,"Solicitud consolidación → Consolidado",196);
  svg+=`<line x1="${ncx(7)}" y1="${midY+nodeH/2}" x2="${ncx(7)+PITCH/2}" y2="196" stroke="var(--diag-branch-stroke)" stroke-dasharray="3 3"/>`
      +`<g class="node branch"><rect x="${nx(7)+30}" y="196" width="${W+40}" height="${nodeH}" rx="9" fill="var(--diag-ret-fill)" stroke="var(--diag-ret-stroke)"/>`
      +`<text x="${nx(7)+30+(W+40)/2}" y="216" text-anchor="middle" fill="var(--diag-ret-ink)">En Retención</text>`
      +`<text x="${nx(7)+30+(W+40)/2}" y="230" text-anchor="middle" fill="var(--diag-ret-ink)" font-size="10">${fmtN(nRet)} guías · ${fmt1(pRet)}%</text></g>`;
  svg+=branchTop(9,"Entrega Fallida");
  svg+="</svg>";
  document.getElementById("t-diagram").innerHTML=svg;
}

function renderTiempos(){
  const rows=filtered();
  // sv keyed por s.k (corridos), pero poblado desde la columna corridos/hábiles según toggle
  const sv={}; STAGES.forEach(s=>sv[s.k]=rows.map(r=>H2D(r[CI[dk(s.k)]])));
  const totalD=rows.map(r=>H2D(r[CI[dk("d_total")]]));
  const sum=(r,ks)=>ks.every(k=>r[CI[dk(k)]]!=null)?H2D(ks.reduce((s,k)=>s+r[CI[dk(k)]],0)):null;
  const miamiD=rows.map(r=>sum(r,["d_ing_mcf","d_mcf_pago","d_pago_asig","d_asig_desp"]));
  const intD=rows.map(r=>sum(r,["d_arr_adu","d_adu_bod","d_bod_dch","d_dch_ent"]));

  document.getElementById("t-kpis").innerHTML=[
    ["Guías con vuelo (filtro)",fmtN(rows.length)],
    ["Total puerta a puerta",fmt1(median(totalD))+" d","p90: "+fmt1(pctl(totalD,.9))+" d"],
    ["Etapa Miami (ingreso→despacho)",fmt1(median(miamiD))+" d"],
    ["Tránsito aéreo",fmt1(median(sv.d_desp_arr))+" d"],
    ["Internación Chile → entrega",fmt1(median(intD))+" d"],
    ["Guías retenidas en aduana",fmtN(rows.reduce((s,r)=>s+r[CI.retenida],0)),(rows.length?(100*rows.reduce((s,r)=>s+r[CI.retenida],0)/rows.length).toFixed(1):0)+"%"],
  ].map(([l,v,s])=>`<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div>${s?`<div class="s">${s}</div>`:""}</div>`).join("");

  renderDiagram(rows, sv);
  document.getElementById("t-legend").innerHTML=Object.entries(FLUJO_COLOR).map(([k,c])=>`<span style="--c:${c}">${k}</span>`).join("");

  const meds=STAGES.map(s=>({...s,med:median(sv[s.k])||0}));
  const mx=Math.max(...meds.map(m=>m.med),0.1);
  document.getElementById("t-funnel-tiempos").innerHTML=meds.map(m=>`
    <div class="fstage"><span class="lbl">${m.lbl}</span>
      <div class="track"><div class="bar" style="width:${Math.max(1.5,m.med/mx*100)}%;background:${FLUJO_COLOR[m.flujo]}"></div></div>
      <span class="val">${fmt1(m.med)} d</span></div>`).join("")
    +(()=>{const suma=meds.reduce((s,m)=>s+m.med,0),real=median(totalD)||0,big=Math.max(suma,real,0.1);
      return `<div class="fstage" style="margin-top:8px;border-top:1px dashed var(--2e-grey);padding-top:8px">
        <span class="lbl"><b>Suma de medianas por tramo</b></span>
        <div class="track"><div class="bar" style="width:${suma/big*100}%;background:var(--2e-grey-dark)"></div></div>
        <span class="val"><b>${fmt1(suma)} d</b></span></div>
      <div class="fstage"><span class="lbl"><b>Mediana real puerta a puerta</b></span>
        <div class="track"><div class="bar" style="width:${real/big*100}%;background:var(--2e-blue-dark)"></div></div>
        <span class="val"><b>${fmt1(real)} d</b></span></div>`;})();

  // conteo monotono: "alcanzo esta etapa" = tiene su timestamp O el de una etapa posterior
  const reachedArr = r=>r[CI.d_desp_arr]!=null || r[CI.d_arr_adu]!=null || r[CI.d_adu_bod]!=null || r[CI.d_bod_dch]!=null || r[CI.d_dch_ent]!=null || r[CI.entregada];
  const reachedAdu = r=>r[CI.d_arr_adu]!=null || r[CI.d_adu_bod]!=null || r[CI.d_bod_dch]!=null || r[CI.d_dch_ent]!=null || r[CI.entregada];
  const reachedBod = r=>r[CI.d_adu_bod]!=null || r[CI.d_bod_dch]!=null || r[CI.d_dch_ent]!=null || r[CI.entregada];
  const reachedDch = r=>r[CI.d_bod_dch]!=null || r[CI.d_dch_ent]!=null || r[CI.entregada];
  const reach=[
    ["Despachadas a aeropuerto",rows.length],
    ["Arribadas a Chile",rows.filter(reachedArr).length],
    ["Recibidas en aduana",rows.filter(reachedAdu).length],
    ["En bodega 2ebox Chile",rows.filter(reachedBod).length],
    ["En despacho última milla",rows.filter(reachedDch).length],
    ["Entregadas al cliente",rows.filter(r=>r[CI.entregada]).length],
  ];
  const rmx=reach[0][1]||1;
  document.getElementById("t-funnel-vol").innerHTML=reach.map(([l,n])=>`
    <div class="fstage"><span class="lbl">${l}</span>
      <div class="track"><div class="bar" style="width:${Math.max(1.5,n/rmx*100)}%;background:#5691DF"></div></div>
      <span class="val">${fmtN(n)} · ${(n/rmx*100).toFixed(0)}%</span></div>`).join("");

  newChart("c-tramos",{type:"bar",data:{labels:STAGES.map(s=>s.lbl),datasets:[
      {label:"Mediana",data:STAGES.map(s=>+(median(sv[s.k])||0).toFixed(2)),backgroundColor:"#5691DF"},
      {label:"p90",data:STAGES.map(s=>+(pctl(sv[s.k],.9)||0).toFixed(2)),backgroundColor:"#A7C5E1"}]},
    options:{...baseOpts,indexAxis:"y",plugins:{legend:{display:true,position:"bottom"}}}});

  const meses=[...new Set(rows.map(r=>r[CI.fy]*100+r[CI.fm]))].sort();
  const mLbl=meses.map(m=>MESES[m%100-1]+" "+String(Math.floor(m/100)).slice(2));
  newChart("c-total-mes",{type:"line",data:{labels:mLbl,datasets:[{label:"Mediana días",
      data:meses.map(m=>{const v=rows.filter(r=>r[CI.fy]*100+r[CI.fm]===m).map(r=>H2D(r[CI[dk("d_total")]]));return median(v)?+median(v).toFixed(1):null;}),
      borderColor:"#E3203E",backgroundColor:"rgba(227,32,62,.08)",fill:true,tension:.3,spanGaps:true},
    {label:"Promedio días",
      data:meses.map(m=>{const v=rows.filter(r=>r[CI.fy]*100+r[CI.fm]===m).map(r=>H2D(r[CI[dk("d_total")]]));return mean(v)?+mean(v).toFixed(1):null;}),
      borderColor:"#5691DF",backgroundColor:"rgba(86,145,223,.08)",fill:false,tension:.3,spanGaps:true}]},
    options:{...baseOpts,plugins:{...baseOpts.plugins,legend:{display:true,position:"bottom"}}}});

  const fwT={};
  rows.forEach(r=>{const v=H2D(r[CI[dk("d_total")]]); if(v!=null)(fwT[r[CI.fw]]=fwT[r[CI.fw]]||[]).push(v);});
  const gfw=Object.entries(fwT).map(([fw,a])=>({fw,med:median(a),n:a.length})).sort((a,b)=>b.n-a.n);
  newChart("c-total-fw",{type:"bar",data:{labels:gfw.map(x=>x.fw),datasets:[{data:gfw.map(x=>x.med?+x.med.toFixed(1):0),backgroundColor:gfw.map(x=>fwColor(x.fw))}]},
    options:{...baseOpts,plugins:{...baseOpts.plugins,tooltip:{callbacks:{label:c=>fmt1(c.raw)+" días"}}}}});

  const T=document.getElementById("t-table");
  const head=["Tramo","Flujo","n","Mediana (d)","Promedio (d)","p90 (d)"];
  const body=STAGES.map(s=>[s.lbl,s.flujo,fmtN(sv[s.k].filter(x=>x!=null).length),fmt1(median(sv[s.k])),fmt1(mean(sv[s.k])),fmt1(pctl(sv[s.k],.9))]);
  body.push(["TOTAL puerta a puerta","—",fmtN(totalD.filter(x=>x!=null).length),fmt1(median(totalD)),fmt1(mean(totalD)),fmt1(pctl(totalD,.9))]);
  renderTable(T,head,body,null);
}

function renderTable(t,head,body,foot){
  let sc=-1,sd=1;
  const num=s=>parseFloat(String(s).replace(/\./g,"").replace(",",".").replace(/[^\d.-]/g,""));
  function draw(){
    let rs=body.map(r=>r.slice());
    if(sc>=0)rs.sort((a,b)=>{const pa=num(a[sc]),pb=num(b[sc]);
      return (!isNaN(pa)&&!isNaN(pb))?(pa-pb)*sd:String(a[sc]).localeCompare(String(b[sc]))*sd;});
    t.innerHTML="<thead><tr>"+head.map((h,i)=>`<th data-i="${i}">${h}${sc===i?(sd>0?" ▲":" ▼"):""}</th>`).join("")+"</tr></thead><tbody>"
      +rs.map(r=>"<tr>"+r.map(c=>`<td>${c}</td>`).join("")+"</tr>").join("")+"</tbody>"
      +(foot?"<tfoot><tr>"+foot.map(c=>`<td>${c}</td>`).join("")+"</tr></tfoot>":"");
    t.querySelectorAll("th").forEach(th=>th.onclick=()=>{const i=+th.dataset.i;if(sc===i)sd*=-1;else{sc=i;sd=1;}draw();});
  }
  draw();
}

// --- Última Milla -- dataset propio (UM), NO usa F.fy/fm/fw/un, solo F.umc ---
function umFiltered(){
  return UM.rows.filter(r=>!F.umc.size||F.umc.has(r.courier));
}
function umAgg(rows){
  const dias=rows.map(r=>r.dias_desp_ent).filter(x=>x!=null);
  const kilos=rows.reduce((s,r)=>s+(r.peso||0),0);
  return {n:rows.length, prom:mean(dias), mediana:median(dias), kilos, kilosProm:rows.length?kilos/rows.length:null};
}
function umFmtRow(label,a){
  return [label, fmtN(a.n), a.prom!=null?fmt1(a.prom)+" d":"–", a.mediana!=null?fmt1(a.mediana)+" d":"–", fmtKg(a.kilos), a.kilosProm!=null?fmt1(a.kilosProm)+" kg":"–"];
}
function renderUltimaMilla(){
  const rows=umFiltered();
  const tot=umAgg(rows);
  document.getElementById("um-kpis").innerHTML=[
    ["Guías entregadas",fmtN(tot.n)],
    ["Tiempo promedio",tot.prom!=null?fmt1(tot.prom)+" d":"–"],
    ["Mediana",tot.mediana!=null?fmt1(tot.mediana)+" d":"–"],
    ["Kilos totales",fmtKg(tot.kilos)],
    ["Kilos / guía",tot.kilosProm!=null?fmt1(tot.kilosProm)+" kg":"–"],
  ].map(([l,v])=>`<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");

  // --- gráfico: tiempos por mes según courier ---
  const meses=[...new Set(rows.map(r=>r.mes).filter(Boolean))].sort();
  const couriersPresentes=UM_COURIERS.filter(c=>rows.some(r=>r.courier===c));
  const COURIER_COLOR={"DropGo":"#E3203E","Bluexpress":"#5691DF","Sin courier / otro":"#7B92A4"};
  newChart("c-um-mes",{type:"line",data:{labels:meses,datasets:couriersPresentes.map(c=>({
      label:c,
      data:meses.map(m=>{
        const a=umAgg(rows.filter(r=>r.courier===c&&r.mes===m));
        const v=UMMETRIC==="mediana"?a.mediana:a.prom;
        return v!=null?+v.toFixed(2):null;
      }),
      borderColor:COURIER_COLOR[c]||"#9AAEC2",
      backgroundColor:(COURIER_COLOR[c]||"#9AAEC2")+"20",
      fill:false,tension:.3,spanGaps:true}))},
    options:{...baseOpts,plugins:{...baseOpts.plugins,legend:{display:true,position:"bottom"}}}});

  // --- matriz por región ---
  const byKey=(rows,key)=>{const g={};rows.forEach(r=>{const k=r[key]||"?";(g[k]=g[k]||[]).push(r);});return g;};
  const regHead=["Región","Guías","Tiempo promedio","Mediana","Kilos totales","Kilos/guía"];
  const byRegion=byKey(rows,"region");
  const regBody=Object.entries(byRegion).map(([k,rs])=>umFmtRow(k,umAgg(rs))).sort((a,b)=>
    parseFloat(b[1].replace(/\./g,""))-parseFloat(a[1].replace(/\./g,"")));
  renderTable(document.getElementById("um-region-table"),regHead,regBody,umFmtRow("Total",tot));

  // --- RM vs Regiones (totalizado) ---
  const byZona=byKey(rows,"zona");
  const zonaOrder=["RM","Regiones","?"].filter(k=>byZona[k]);
  const zonaBody=zonaOrder.map(k=>umFmtRow(k==="?"?"Sin región":k,umAgg(byZona[k])));
  renderTable(document.getElementById("um-zona-table"),regHead,zonaBody,umFmtRow("Total",tot));

  // --- matriz por comuna ---
  const byComuna=byKey(rows,"comuna");
  const comHead=["Comuna","Guías","Tiempo promedio","Mediana","Kilos totales","Kilos/guía"];
  const comBody=Object.entries(byComuna).map(([k,rs])=>umFmtRow(k,umAgg(rs))).sort((a,b)=>
    parseFloat(b[1].replace(/\./g,""))-parseFloat(a[1].replace(/\./g,"")));
  renderTable(document.getElementById("um-comuna-table"),comHead,comBody,umFmtRow("Total",tot));
}

// ================= Llenado de Vuelos -- dataset propio (LL), filtros propios (LF) =================
const LL = __PAYLOAD_LL__;
const LLV = {}; (LL.vuelos||[]).forEach(v=>LLV[v.id]=v);
const LLBY = {}; (LL.guias||[]).forEach(g=>{(LLBY[g.vid]=LLBY[g.vid]||[]).push(g);});
const LL_SEGS = ["Natural","Empresa","Carga","MercadoLibre","Retail"];
const LL_EJS = ["Kathy","Tiare","Sin ejecutiva"];
const SEG_COLOR = {Natural:"#5691DF",Empresa:"#7B92A4",Carga:"#E0A100",MercadoLibre:"#2E9E6B",Retail:"#E3203E"};
const EJ_COLOR = {Kathy:"#E3203E",Tiare:"#5691DF","Sin ejecutiva":"#A7C5E1"};
const LL_PAL = ["#E3203E","#5691DF","#2E9E6B","#E0A100","#152C4A","#B5651D","#7B92A4","#A7C5E1"];
const LF = {vuelo:0, cas:"", ej:new Set(), seg:new Set(["Natural","Empresa","Carga"]), desde:"", hasta:"", per:"3m"};
let LLG4BY="seg", LLG4M="kg", LLT5="pag";

const llDay = s => s ? Date.UTC(+s.slice(0,4),+s.slice(5,7)-1,+s.slice(8,10))/864e5 : null;
const llHrs = s => s ? Date.UTC(+s.slice(0,4),+s.slice(5,7)-1,+s.slice(8,10),+s.slice(11,13)||0,+s.slice(14,16)||0)/36e5 : null;
const llToday = () => { const d=new Date(); return Date.UTC(d.getFullYear(),d.getMonth(),d.getDate())/864e5; };
const dayStr = n => new Date(n*864e5).toISOString().slice(0,10);
const llMon = d => d - ((new Date(d*864e5).getUTCDay()+6)%7);
function isoWeek(s){
  const d=new Date(llDay(s)*864e5); d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7)+3);
  const y=d.getUTCFullYear(), j4=new Date(Date.UTC(y,0,4));
  return y+"-S"+String(1+Math.round(((d-j4)/864e5-3+((j4.getUTCDay()+6)%7))/7)).padStart(2,"0");
}
const fmtD = s => s ? s.slice(8,10)+"-"+s.slice(5,7)+"-"+s.slice(2,4) : "–";
const fmtCLP = n => n==null?"–":"$"+nf.format(Math.round(n));
const lkV = v => `<a class="lk" data-lv="${v.id}">${v.awb}</a>`;
const lkC = c => c ? `<a class="lk" data-lc="${c}">${c}</a>` : "–";

const gOk = g => (!LF.cas||g.cas===LF.cas) && (!LF.ej.size||LF.ej.has(g.ej)) && (!LF.seg.size||LF.seg.has(g.seg));
const gOkNoSeg = g => (!LF.cas||g.cas===LF.cas) && (!LF.ej.size||LF.ej.has(g.ej));
const llT5Ok = g => LLT5==="todas" || (LLT5==="pag" ? g.pag===1 : g.pag===0);
const llEnPeriodo = s => { const d=s.slice(0,10); return (!LF.desde||d>=LF.desde)&&(!LF.hasta||d<=LF.hasta); };
// los vuelos abiertos se muestran siempre; el periodo filtra por fecha de creación del AWB
const vOk = v => LF.vuelo ? v.id===LF.vuelo : (v.estado==="abierto" || llEnPeriodo(v.creado));
const vGuias = (v,f=gOk) => (LLBY[v.id]||[]).filter(f);
function llAgg(gs){
  const a={n:0,kg:0,kgv:0,kgf:0,fob:0,fobclp:0,tp:0,venta:0,costo:0};
  gs.forEach(g=>{a.n++;a.kg+=g.kg;a.kgv+=g.kgv;a.kgf+=g.kgf;a.fob+=g.fob;a.fobclp+=g.fob*g.dol;a.tp+=g.tp;a.venta+=g.venta;a.costo+=g.costo;});
  a.mg=a.venta-a.costo; return a;
}
function llFlights(){
  return LL.vuelos.filter(vOk).map(v=>({v,a:llAgg(vGuias(v))}))
    .filter(x=>x.a.n>0||LF.vuelo).sort((x,y)=>x.v.creado<y.v.creado?-1:1);
}
// referencia histórica: últimos 10 vuelos regulares despachados del mismo forwarder
const llHist = (fw,antesDe) => LL.vuelos.filter(v=>v.fw===fw&&v.estado==="despachado"&&v.tipo==="COURIER"&&(!antesDe||v.creado<antesDe)).slice(-10);
function llCurve(v,key){
  const d0=llDay(v.creado), fin=v.desp?llDay(v.desp):llToday();
  const n=Math.max(0,Math.min(30,fin-d0)), arr=new Array(n+1).fill(0);
  vGuias(v).forEach(g=>{const d=g.asig?Math.max(0,Math.min(n,llDay(g.asig)-d0)):0; arr[d]+=key==="kg"?g.kg:g.venta-g.costo;});
  for(let i=1;i<arr.length;i++)arr[i]+=arr[i-1];
  return arr;
}
function llAvgCurve(vs,key,len){
  const cs=vs.map(v=>llCurve(v,key)); if(!cs.length)return null;
  return Array.from({length:len},(_,i)=>mean(cs.map(c=>c[Math.min(i,c.length-1)])));
}
const legendBottom = {display:true,position:"bottom",labels:{boxWidth:10,font:{size:10}}};

function buildLLControls(){
  if(!LL.vuelos||!LL.vuelos.length)return;
  const sel=document.getElementById("ll-vuelo");
  sel.innerHTML='<option value="0">Todos los vuelos</option>'+LL.vuelos.slice().reverse().map(v=>
    `<option value="${v.id}">${v.awb} · ${v.fw} · ${fmtD(v.creado)}${v.estado==="abierto"?" · ABIERTO":""}</option>`).join("");
  sel.onchange=()=>{LF.vuelo=+sel.value;renderLlenado();};
  document.getElementById("ll-cas-list").innerHTML=[...new Set(LL.guias.map(g=>g.cas).filter(Boolean))].sort()
    .map(c=>`<option value="${c}">`).join("");
  const cas=document.getElementById("ll-cas");
  cas.onchange=()=>{LF.cas=cas.value.trim().toUpperCase();renderLlenado();};
  const chips=(id,items,set)=>{const h=document.getElementById(id);h.innerHTML="";items.forEach(v=>{
    const c=document.createElement("span");c.className="chip"+(set.has(v)?" on":"");c.textContent=v;
    c.onclick=()=>{set.has(v)?set.delete(v):set.add(v);c.classList.toggle("on");renderLlenado();};h.appendChild(c);});};
  chips("ll-ej",LL_EJS,LF.ej); chips("ll-seg",LL_SEGS,LF.seg);
  document.querySelectorAll("[data-llclear]").forEach(b=>b.onclick=()=>{LF[b.dataset.llclear].clear();
    document.querySelectorAll(`#ll-${b.dataset.llclear} .chip`).forEach(c=>c.classList.remove("on"));renderLlenado();});
  document.getElementById("ll-per").onclick=e=>{const b=e.target.closest("button");if(!b)return;llSetPer(b.dataset.p);renderLlenado();};
  ["desde","hasta"].forEach(k=>document.getElementById("ll-"+k).onchange=e=>{LF[k]=e.target.value;
    document.querySelectorAll("#ll-per button").forEach(b=>b.classList.remove("on"));renderLlenado();});
  document.getElementById("ll-reset").onclick=()=>{LF.vuelo=0;LF.cas="";LF.ej.clear();LF.seg=new Set(["Natural","Empresa","Carga"]);
    sel.value="0";cas.value="";chips("ll-ej",LL_EJS,LF.ej);chips("ll-seg",LL_SEGS,LF.seg);llSetPer("3m");renderLlenado();};
  const sw=(id,fn)=>document.getElementById(id).onclick=e=>{const b=e.target.closest("button");if(!b)return;
    document.querySelectorAll(`#${id} button`).forEach(x=>x.classList.toggle("on",x===b));fn(b);renderLlenado();};
  sw("ll-g4-by",b=>LLG4BY=b.dataset.b); sw("ll-g4-m",b=>LLG4M=b.dataset.m); sw("ll-t5-sw",b=>LLT5=b.dataset.s);
  // clic en un AWB o una casilla desde cualquier tabla -> filtra toda la sección
  document.getElementById("tab-llenado").addEventListener("click",e=>{
    const a=e.target.closest("a.lk");if(!a)return;
    if(a.dataset.lv){LF.vuelo=+a.dataset.lv;sel.value=a.dataset.lv;}
    if(a.dataset.lc){LF.cas=a.dataset.lc;cas.value=a.dataset.lc;}
    renderLlenado();window.scrollTo({top:0,behavior:"smooth"});});
  llSetPer("3m");
}
function llSetPer(p){
  const t=llToday(); LF.hasta="";
  LF.desde = p==="4s"?dayStr(t-28) : p==="3m"?dayStr(t-91) : p==="anio"?new Date().getFullYear()+"-01-01" : "";
  document.getElementById("ll-desde").value=LF.desde; document.getElementById("ll-hasta").value="";
  document.querySelectorAll("#ll-per button").forEach(b=>b.classList.toggle("on",b.dataset.p===p));
}

function renderLlenado(){
  const nt=document.getElementById("ll-notice");
  if(!LL.guias||!LL.guias.length){nt.textContent="Sin datos de llenado: falta correr extraer_llenado.py.";return;}
  const fl=llFlights();
  const imp=LL.vuelos.filter(v=>v.estado==="abierto"&&v.tarifa_imp).map(v=>v.awb);
  nt.innerHTML=`Datos al ${LL.generado} (hora Chile). Vuelos analizados desde ${fmtD(LL.awb_desde)}. `+
    (imp.length?`Tarifa de costo <b>estimada</b> (*) para ${imp.join(", ")}: el AWB aún no la tiene cargada; se usa la mediana de los últimos 90 días del forwarder. `:"")+
    `El periodo filtra por creación del AWB; los vuelos abiertos se muestran siempre.`;
  renderLLKpis(fl); renderLLT1(fl); renderLLCurvas(fl); renderLLProy(); renderLLT5();
  renderLLT3(); renderLLT2(fl); renderLLT4(fl); renderLLG4(fl); renderLLG5(fl); renderLLG6();
}
function renderLLKpis(fl){
  const ab=fl.filter(x=>x.v.estado==="abierto"), de=fl.filter(x=>x.v.estado==="despachado");
  const A=llAgg(ab.flatMap(x=>vGuias(x.v))), D=llAgg(de.flatMap(x=>vGuias(x.v)));
  const ciclo=mean(de.map(x=>x.v.desp?llDay(x.v.desp)-llDay(x.v.creado):null));
  const pend=LL.guias.filter(g=>g.vid===0&&gOk(g)&&g.pag===1);
  const k=(v,l,s,hl)=>`<div class="kpi${hl?" hl":""}"><div class="v">${v}</div><div class="l">${l}</div>${s?`<div class="s">${s}</div>`:""}</div>`;
  document.getElementById("ll-kpis").innerHTML=
    k(fmtN(ab.length),"Vuelos abiertos",`${fmtN(A.n)} guías subidas`)+
    k(fmtKg(A.kg),"Kg en vuelos abiertos","kilo real",true)+
    k(A.kgf?"US$"+fmt2(A.venta/A.kgf):"–","Venta / kg abiertos",A.kgf?`costo US$${fmt2(A.costo/A.kgf)}/kg`:"",true)+
    k(fmtUSD(A.mg),"Margen estimado abiertos",A.venta?`${fmt1(100*A.mg/A.venta)}% de la venta`:"")+
    k(fmtN(de.length),"Vuelos despachados",`${fmtKg(D.kg)} · margen ${fmtUSD(D.mg)}`)+
    k(ciclo==null?"–":fmt1(ciclo)+" d","Ciclo creación → despacho","promedio del periodo")+
    k(fmtN(pend.length),"Guías listas sin AWB",fmtKg(pend.reduce((s,g)=>s+g.kg,0)));
}
function renderLLT1(fl){
  const rows=fl.filter(x=>x.v.estado==="abierto"), t=document.getElementById("ll-t1");
  if(!rows.length){t.innerHTML="<tbody><tr><td>No hay vuelos abiertos con el filtro actual.</td></tr></tbody>";return;}
  const vk=a=>a.kgf?a.venta/a.kgf:null, mk=a=>a.kgf?a.mg/a.kgf:null;
  const body=rows.map(({v,a})=>[isoWeek(v.creado),lkV(v)+(v.tipo==="CARGA"?' <span class="badge b-pc">carga</span>':""),v.fw,
    fmtD(v.creado),fmtN(llToday()-llDay(v.creado)),fmtN(a.n),`<b>${fmt1(a.kg)}</b>`,fmt1(a.kgv),fmtUSD(a.fob),fmtCLP(a.tp),
    `<b>${fmt2(vk(a))}</b>`,fmt2(v.tarifa)+(v.tarifa_imp?"*":""),fmtUSD(a.mg),fmt2(mk(a))]);
  const T=llAgg(rows.flatMap(x=>vGuias(x.v)));
  renderTable(t,["Semana","Vuelo / AWB","Forwarder","Creación","Días abierto","Guías","Kg reales","Kg vol. (ref.)","FOB US$",
    "Total a pagar (ref.)","Venta US$/kg","Costo US$/kg","Margen US$","Margen US$/kg"],body,
    ["Total","","","","",fmtN(T.n),fmt1(T.kg),fmt1(T.kgv),fmtUSD(T.fob),fmtCLP(T.tp),fmt2(vk(T)),"",fmtUSD(T.mg),fmt2(mk(T))]);
}
function renderLLCurvas(fl){
  let sel=LF.vuelo?[LLV[LF.vuelo]]:fl.filter(x=>x.v.estado==="abierto"&&x.v.tipo==="COURIER").map(x=>x.v);
  if(!sel.length)sel=fl.filter(x=>x.v.estado==="despachado").slice(-3).map(x=>x.v);
  const fw=sel[0]?sel[0].fw:null, hist=fw?llHist(fw,sel[0].creado):[];
  [["kg","c-ll-curva","kg acumulados"],["mg","c-ll-margen","US$ margen acumulado"]].forEach(([key,id,yl])=>{
    const cs=sel.map(v=>llCurve(v,key));
    const len=Math.max(8,...cs.map(c=>c.length));
    const avg=llAvgCurve(hist,key,len);
    const ds=cs.map((c,i)=>({label:sel[i].awb,data:c,borderColor:LL_PAL[i%8],backgroundColor:LL_PAL[i%8],tension:.2,pointRadius:2}));
    if(avg)ds.push({label:`Promedio últimos ${hist.length} vuelos ${fw}`,data:avg,borderColor:"#7B92A4",borderDash:[6,4],pointRadius:0,tension:.2});
    newChart(id,{type:"line",data:{labels:Array.from({length:len},(_,i)=>"Día "+i),datasets:ds},
      options:{...baseOpts,plugins:{legend:legendBottom},scales:{y:{title:{display:true,text:yl}}}}});
  });
}
const llPw = g => g.p!=null ? g.p : ({Alta:.9,Media:.6,Baja:.3}[g.regla]||.5);
function renderLLProy(){
  const sub=document.getElementById("ll-proy-sub");
  const tgt=(LF.vuelo&&LLV[LF.vuelo].estado==="abierto")?LLV[LF.vuelo]:LLV[LL.vuelo_objetivo];
  if(!tgt){sub.textContent="No hay un vuelo regular abierto para proyectar.";
    ["c-ll-proy-kg","c-ll-proy-mg"].forEach(id=>{if(charts[id]){charts[id].destroy();delete charts[id];}});return;}
  const a=llAgg(vGuias(tgt));
  const pend=LL.guias.filter(g=>g.vid===0&&gOk(g)&&llT5Ok(g));
  const kgP=pend.reduce((s,g)=>s+g.kg*llPw(g),0), mgP=pend.reduce((s,g)=>s+(g.venta-g.costo)*llPw(g),0);
  const hist=llHist(tgt.fw,tgt.creado).map(v=>llAgg(vGuias(v)));
  const hKg=mean(hist.map(h=>h.kg)), hMg=mean(hist.map(h=>h.mg));
  sub.innerHTML=`Vuelo <b>${tgt.awb}</b> (${tgt.fw}, creado ${fmtD(tgt.creado)}): lo ya subido + las guías pendientes de T5 `+
    `(según su selector) ponderadas por su probabilidad. Cierre proyectado: <b>${fmtKg(a.kg+kgP)}</b> y <b>${fmtUSD(a.mg+mgP)}</b> de margen `+
    `vs. promedio de ${hist.length} vuelos ${tgt.fw}: ${fmtKg(hKg)} y ${fmtUSD(hMg)}.`;
  const mk=(id,act,pro,avg,t)=>newChart(id,{type:"bar",data:{labels:["Este vuelo","Promedio histórico"],datasets:[
    {label:"Actual",data:[act,null],backgroundColor:"#5691DF",stack:"s"},
    {label:"Pendiente ponderado",data:[pro,null],backgroundColor:"#A7C5E1",stack:"s"},
    {label:"Promedio",data:[null,avg],backgroundColor:"#7B92A4",stack:"s"}]},
    options:{...baseOpts,indexAxis:"y",plugins:{legend:legendBottom,title:{display:true,text:t}},scales:{x:{stacked:true},y:{stacked:true}}}});
  mk("c-ll-proy-kg",a.kg,kgP,hKg,"Kg reales"); mk("c-ll-proy-mg",a.mg,mgP,hMg,"Margen US$");
}
function renderLLT5(){
  const ref=g=>g.lista||g.mcf;
  const ps=LL.guias.filter(g=>g.vid===0&&gOk(g)&&llT5Ok(g)).sort((a,b)=>ref(a)<ref(b)?-1:1);
  const T=llAgg(ps), kgP=ps.reduce((s,g)=>s+g.kg*llPw(g),0);
  const k=(v,l)=>`<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`;
  document.getElementById("ll-t5-kpis").innerHTML=k(fmtN(T.n),"Guías pendientes")+k(fmtKg(T.kg),"Kg si se sube todo hoy")+
    k(fmtUSD(T.venta),"Venta US$")+k(fmtUSD(T.mg),"Margen US$")+k(fmtKg(kgP),"Kg esperados (× prob.)");
  const t=document.getElementById("ll-t5");
  if(!ps.length){t.innerHTML="<tbody><tr><td>No hay guías pendientes con el filtro actual.</td></tr></tbody>";return;}
  const hoy=Date.now()/36e5;
  const badge=g=>`<span class="badge b-${g.regla.toLowerCase()}">${g.regla}${g.p!=null?" · "+Math.round(g.p*100)+"%":""}</span>`;
  renderTable(t,["Guía","Casilla","Cliente","Ejecutiva","Pagada","Lista desde","Días esperando","Kg","FOB US$","Venta US$",
    "Margen est. US$","Categoría","FOB cartera cliente","Tramo","Ad valorem (CLP)","Probabilidad","Hist. cliente","Descripción"],
    ps.map(g=>[g.ng,lkC(g.cas),g.cli||"–",g.ej,g.pag?"Sí":"No",fmtD(ref(g)),fmt1(Math.max(0,(hoy-llHrs(ref(g))-new Date().getTimezoneOffset()/60)/24)),
      fmt1(g.kg),fmtUSD(g.fob),fmtUSD(g.venta),fmtUSD(g.venta-g.costo),
      g.ex?'<span class="badge b-pc">Computadores y Partes (exenta)</span>':"General",
      fmtUSD(g.fob_cart),g.tramo,fmtCLP(g.adv),badge(g),g.cli_hist||"–",g.desc||""]));
}
function renderLLT3(){
  const t=document.getElementById("ll-t3");
  const gs=LL.guias.filter(g=>g.vid&&g.asig&&gOk(g)&&(!LF.vuelo||g.vid===LF.vuelo)&&(LF.vuelo||llEnPeriodo(g.asig)));
  const cell={};
  gs.forEach(g=>{const d=llDay(g.asig);(cell[d]=cell[d]||{})[g.vid]=((cell[d]||{})[g.vid]||0)+1;});
  const days=Object.keys(cell).map(Number);
  if(!days.length){t.innerHTML="<tbody><tr><td>Sin subidas en el filtro.</td></tr></tbody>";return;}
  const weeks=[...new Set(days.map(llMon))].sort((a,b)=>b-a);
  let h="<thead><tr><th>Semana (lunes)</th>"+["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"].map(x=>`<th>${x}</th>`).join("")+"<th>Total</th></tr></thead><tbody>",mes0="";
  weeks.forEach(w=>{
    const ws=dayStr(w), mes=ws.slice(0,7);
    if(mes!==mes0){h+=`<tr class="mes"><td colspan="9">${MESES[+mes.slice(5,7)-1]} ${mes.slice(0,4)}</td></tr>`;mes0=mes;}
    let tot=0; h+=`<tr><td>${fmtD(ws)}</td>`;
    for(let i=0;i<7;i++){const c=cell[w+i];
      h+="<td>"+(c?Object.entries(c).sort((a,b)=>b[1]-a[1]).map(([vid,n])=>{tot+=n;const v=LLV[vid];
        return `<span class="cv"><b>${n}</b><small><a class="lk" data-lv="${vid}">${v?v.awb:vid}</a></small></span>`;}).join(""):"")+"</td>";}
    h+=`<td class="tot">${tot}</td></tr>`;});
  t.innerHTML=h+"</tbody>";
}
function renderLLT2(fl){
  const rows=fl.filter(x=>x.v.estado==="despachado"&&x.a.n).reverse();
  const cic=v=>v.desp?llDay(v.desp)-llDay(v.creado):null;
  const T=llAgg(rows.flatMap(x=>vGuias(x.v)));
  renderTable(document.getElementById("ll-t2"),["Vuelo / AWB","Forwarder","Tipo","Creación","Despacho","Días ciclo","Guías","Kg reales",
    "Venta US$","Costo US$","Margen US$","Margen %","Venta US$/kg"],
    rows.map(({v,a})=>[lkV(v),v.fw,v.tipo==="CARGA"?"Carga":"Regular",fmtD(v.creado),fmtD(v.desp),fmtN(cic(v)),fmtN(a.n),fmt1(a.kg),
      fmtUSD(a.venta),fmtUSD(a.costo),fmtUSD(a.mg),a.venta?fmt1(100*a.mg/a.venta)+"%":"–",fmt2(a.kgf?a.venta/a.kgf:null)]),
    ["Total","","","","",fmt1(mean(rows.map(x=>cic(x.v)))),fmtN(T.n),fmt1(T.kg),fmtUSD(T.venta),fmtUSD(T.costo),fmtUSD(T.mg),
      T.venta?fmt1(100*T.mg/T.venta)+"%":"–",fmt2(T.kgf?T.venta/T.kgf:null)]);
}
function renderLLT4(fl){
  const r=x=>({vk:x.a.kgf?x.a.venta/x.a.kgf:null,tf:x.a.fobclp?x.a.tp/x.a.fobclp:null,fk:x.a.kg?x.a.fob/x.a.kg:null,kg:x.a.n?x.a.kg/x.a.n:null});
  const base=fl.filter(x=>x.v.estado==="despachado"&&x.v.tipo==="COURIER"&&x.a.n).map(r);
  const avg={};["vk","tf","fk","kg"].forEach(k=>avg[k]=mean(base.map(q=>q[k])));
  const rows=fl.filter(x=>x.a.n).reverse().map(x=>{
    const q=r(x), al=[];
    // el promedio es de vuelos regulares: a los AWB de carga (tarifa distinta) no se les aplica
    if(x.v.tipo==="COURIER"&&q.vk!=null&&avg.vk&&q.vk<.85*avg.vk)al.push("venta/kg baja");
    if(x.v.tipo==="COURIER"&&q.kg!=null&&avg.kg&&q.kg>1.5*avg.kg)al.push("guías pesadas");
    const byc={};vGuias(x.v).forEach(g=>byc[g.cas]=(byc[g.cas]||0)+g.kg);
    const top=Object.entries(byc).sort((a,b)=>b[1]-a[1])[0];
    if(top&&x.a.n>3&&top[1]>.4*x.a.kg)al.push(`${top[0]} = ${Math.round(100*top[1]/x.a.kg)}% de los kg`);
    return [lkV(x.v),x.v.estado==="abierto"?"Abierto":"Despachado",fmt2(q.vk),fmt2(q.tf),fmt2(q.fk),fmt1(q.kg),
      al.map(a=>`<span class="badge b-warn">⚠ ${a}</span>`).join("")||"–"];});
  renderTable(document.getElementById("ll-t4"),["Vuelo / AWB","Estado","Venta US$/kg","Total a pagar ÷ FOB","FOB US$/kg","Kg/guía","Alertas"],
    rows,["Promedio despachados","",fmt2(avg.vk),fmt2(avg.tf),fmt2(avg.fk),fmt1(avg.kg),""]);
}
function renderLLG4(fl){
  const last=fl.slice(-12), cats=LLG4BY==="seg"?LL_SEGS:LL_EJS, col=LLG4BY==="seg"?SEG_COLOR:EJ_COLOR;
  const val=g=>LLG4M==="kg"?g.kg:LLG4M==="tp"?g.tp:g.venta-g.costo;
  const per=x=>{const o={};cats.forEach(c=>o[c]=0);vGuias(x.v,gOkNoSeg).forEach(g=>o[LLG4BY==="seg"?g.seg:g.ej]+=val(g));return o;};
  const data=last.map(per), desp=fl.filter(x=>x.v.estado==="despachado").map(per);
  newChart("c-ll-comp",{type:"bar",data:{labels:last.map(x=>x.v.awb+" · "+fmtD(x.v.creado).slice(0,5)).concat(["Promedio"]),
    datasets:cats.map(c=>({label:c,data:data.map(o=>o[c]).concat([desp.length?mean(desp.map(o=>o[c])):0]),backgroundColor:col[c]}))},
    options:{...baseOpts,plugins:{legend:legendBottom},scales:{x:{stacked:true},y:{stacked:true}}}});
}
function renderLLG5(fl){
  const last=fl.slice(-8);
  newChart("c-ll-disp",{type:"scatter",data:{datasets:last.map((x,i)=>({label:x.v.awb,
    data:vGuias(x.v).map(g=>({x:g.kg,y:g.venta,ng:g.ng,cas:g.cas})),backgroundColor:LL_PAL[i%8]+"B3",pointRadius:3}))},
    options:{...baseOpts,plugins:{legend:legendBottom,tooltip:{callbacks:{label:c=>`Guía ${c.raw.ng} · ${c.raw.cas}: ${fmt1(c.raw.x)} kg · US$${fmt1(c.raw.y)}`}}},
      scales:{x:{title:{display:true,text:"kg reales"}},y:{title:{display:true,text:"venta US$"}}}}});
}
function renderLLG6(){
  const gs=LL.guias.filter(g=>g.vid&&g.asig&&g.lista&&gOk(g)&&(!LF.vuelo||g.vid===LF.vuelo)&&(LF.vuelo||llEnPeriodo(g.asig)));
  const w=g=>Math.max(0,(llHrs(g.asig)-llHrs(g.lista))/24);
  const bins=[[0,1,"< 1"],[1,2,"1–2"],[2,3,"2–3"],[3,5,"3–5"],[5,7,"5–7"],[7,14,"7–14"],[14,1e9,"14+"]];
  newChart("c-ll-esp-h",{type:"bar",data:{labels:bins.map(b=>b[2]+" d"),datasets:[{label:"Guías",
    data:bins.map(b=>gs.filter(g=>w(g)>=b[0]&&w(g)<b[1]).length),backgroundColor:"#5691DF"}]},options:baseOpts});
  const sem={};gs.forEach(g=>{const m=llMon(llDay(g.asig));(sem[m]=sem[m]||[]).push(w(g));});
  const ks=Object.keys(sem).map(Number).sort((a,b)=>a-b);
  newChart("c-ll-esp-s",{type:"line",data:{labels:ks.map(k=>fmtD(dayStr(k))),datasets:[{label:"Días promedio",
    data:ks.map(k=>mean(sem[k])),borderColor:"#E3203E",backgroundColor:"#E3203E",tension:.2,pointRadius:2}]},
    options:{...baseOpts,scales:{y:{title:{display:true,text:"días promedio (semana de subida)"}}}}});
}

function render(){
  if(TAB==="llenado"){renderLlenado();return;}
  const rows=filtered();
  const m=DB.meta;
  document.getElementById("scope-note").innerHTML=
    `<b>${fmtN(rows.length)}</b> / ${fmtN(m.n_registros)} guías con vuelo en el filtro<br>`+
    `Universo: guías despachadas a aeropuerto, ${m.fecha_desde.slice(0,4)}–hoy (incluye AWB de carga dedicada)<br>`+
    `Fuente: NocoDB 2ebox · ${DB.generado}`;
  if(TAB==="performance")renderPerformance();
  else if(TAB==="tiempos")renderTiempos();
  else if(TAB==="ultimamilla")renderUltimaMilla();
}

document.getElementById("gen").textContent="Generado "+DB.generado+" · fuente: NocoDB 2ebox";

// Chart.js no lee variables CSS solo -- hay que fijar los colores de eje/
// grilla a mano segun el tema activo y reconstruir los graficos (newChart
// destruye y recrea, asi que basta con volver a llamar render()).
function chartTextColor(){ return document.documentElement.getAttribute("data-theme")==="dark" ? "#A7C5E1" : "#152C4A"; }
function chartGridColor(){ return document.documentElement.getAttribute("data-theme")==="dark" ? "rgba(167,197,225,.14)" : "rgba(21,44,74,.10)"; }
function aplicarTemaGraficos(){
  Chart.defaults.color = chartTextColor();
  Chart.defaults.borderColor = chartGridColor();
  Chart.defaults.scale.grid.color = chartGridColor();
}
function actualizarBotonTemaRL(){
  var oscuro = document.documentElement.getAttribute("data-theme")==="dark";
  document.getElementById("theme-toggle-btn").textContent = oscuro ? "☀️ Modo claro" : "🌙 Modo oscuro";
}
function alternarTemaRL(){
  var oscuro = document.documentElement.getAttribute("data-theme")==="dark";
  if(oscuro) document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme","dark");
  try{ localStorage.setItem("rl-tema", oscuro?"light":"dark"); }catch(e){}
  actualizarBotonTemaRL();
  aplicarTemaGraficos();
  render();
}
actualizarBotonTemaRL();
aplicarTemaGraficos();
buildChips();
buildLLControls();
render();
</script>
</body>
</html>
"""

out = HTML.replace("__PAYLOAD__", PAYLOAD).replace("__PAYLOAD_UM__", PAYLOAD_UM).replace("__PAYLOAD_LL__", PAYLOAD_LL)
(BASE / "reporte-logistica-operaciones.html").write_text(out, encoding="utf-8")
print(f"HTML -> reporte-logistica-operaciones.html  ({len(out)//1024} KB)")

# Variante para publicar como Artifact de Claude: sin <!doctype>/<html>/<head>/
# <body> (el runtime de Artifacts los agrega al publicar).
frag = out
for tag in ("<!doctype html>", '<html lang="es">', "</html>", "<head>", "</head>", "<body>", "</body>"):
    frag = frag.replace(tag, "")
(BASE / "artifact.html").write_text(frag.strip(), encoding="utf-8")
print(f"Artifact -> artifact.html  ({len(frag)//1024} KB)")
print(f"  registros: {meta['n_registros']}  forwarders: {[f[0] for f in meta['forwarders']]}")
