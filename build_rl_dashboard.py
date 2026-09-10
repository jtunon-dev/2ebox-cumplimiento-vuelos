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
GEN = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC")

PAYLOAD = json.dumps({
    "cols": datos["cols"], "rows": datos["rows"], "meta": meta, "generado": GEN,
}, ensure_ascii=False, separators=(",", ":"))

HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Logística y Operaciones 2ebox</title>
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
}
*{box-sizing:border-box}
body{margin:0;font-family:var(--font-body);color:var(--2e-blue-dark);background:var(--2e-grey-light);font-size:14px}
h1,h2,h3,h4{font-family:var(--font-display);font-weight:400;margin:0}

.topbar{background:var(--2e-blue-dark);color:#fff;display:flex;align-items:center;gap:20px;padding:11px 20px;flex-wrap:wrap}
.topbar .brand{font-family:var(--font-display);font-size:18px;letter-spacing:.4px}
.topbar .brand b{color:var(--2e-red-light)}
.tabs{display:flex;gap:3px;flex-wrap:wrap;margin-left:auto}
.tab{background:transparent;border:none;color:var(--2e-blue-light);font-family:var(--font-display);font-size:12.5px;
  padding:8px 14px;border-radius:8px;cursor:pointer;letter-spacing:.3px}
.tab:hover{color:#fff;background:rgba(255,255,255,.08)}
.tab.active{background:var(--2e-grey-light);color:var(--2e-blue-dark)}
.gen{font-size:11px;color:var(--2e-blue-light);width:100%;margin-top:1px}

.wrap{display:flex;align-items:flex-start}
.sidebar{width:240px;flex:none;background:#fff;border-right:1px solid var(--2e-grey);padding:16px 14px;
  position:sticky;top:0;max-height:100vh;overflow-y:auto}
.main{flex:1;padding:20px 24px;min-width:0}

.fg{margin-bottom:16px}
.fg h4{font-size:11.5px;letter-spacing:.5px;text-transform:uppercase;margin-bottom:7px;display:flex;justify-content:space-between}
.fg h4 button{font-family:var(--font-body);font-size:10px;color:var(--2e-blue);background:none;border:none;cursor:pointer;text-transform:none}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{border:1px solid var(--2e-grey);background:var(--2e-grey-light);border-radius:8px;padding:4px 9px;font-size:12px;cursor:pointer;user-select:none}
.chip:hover{border-color:var(--2e-blue-light)}
.chip.on{background:var(--2e-blue);border-color:var(--2e-blue);color:#fff}
.chip.mes{min-width:36px;text-align:center}
.reset-all{width:100%;margin-top:2px;background:var(--2e-red);color:#fff;border:none;border-radius:9px;padding:9px;
  font-family:var(--font-display);font-size:11.5px;letter-spacing:.4px;cursor:pointer}
.reset-all:hover{background:var(--2e-blue-dark)}
.scope-note{font-size:11px;color:var(--2e-grey-dark);margin-top:10px;line-height:1.55}

.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:11px;margin-bottom:16px}
.kpi{background:#fff;border:1px solid var(--2e-grey);border-radius:13px;padding:13px 14px}
.kpi .v{font-family:var(--font-display);font-size:22px;line-height:1.15}
.kpi .l{font-size:11px;color:var(--2e-grey-dark);margin-top:5px;text-transform:uppercase;letter-spacing:.3px}
.kpi .s{font-size:11px;color:var(--2e-blue);margin-top:3px}

.panel{background:#fff;border:1px solid var(--2e-grey);border-radius:13px;padding:15px 16px 13px;margin-bottom:15px}
.panel h3{font-size:13.5px;letter-spacing:.3px;margin-bottom:3px}
.panel .sub{font-size:11px;color:var(--2e-grey-dark);margin-bottom:11px;line-height:1.5}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:15px}
.grid-2>.panel{margin-bottom:0}
@media(max-width:1080px){.grid-2{grid-template-columns:1fr}}
.chart-box{position:relative;height:290px}
.chart-box.tall{height:360px}

.metric-switch{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}
.metric-switch button{border:1px solid var(--2e-grey);background:#fff;border-radius:8px;padding:6px 12px;font-size:12px;cursor:pointer;font-family:var(--font-body)}
.metric-switch button.on{background:var(--2e-blue-dark);color:#fff;border-color:var(--2e-blue-dark)}

.notice{background:#FFF8E6;border:1px solid #F0D48A;border-radius:10px;padding:9px 12px;font-size:11.5px;color:#7A5B00;margin-bottom:14px;line-height:1.5}

table.dt{width:100%;border-collapse:collapse;font-size:12.5px}
table.dt th,table.dt td{padding:7px 9px;text-align:right;border-bottom:1px solid var(--2e-grey)}
table.dt th{font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:.3px;cursor:pointer;white-space:nowrap;background:var(--2e-grey-light)}
table.dt th:first-child,table.dt td:first-child{text-align:left}
table.dt tbody tr:hover{background:var(--2e-grey-light)}
table.dt tfoot td{font-weight:700;border-top:2px solid var(--2e-blue-dark);border-bottom:none}
.tbl-scroll{overflow-x:auto}
/* matriz año×mes: compacta, no estira a todo el ancho */
table.dt-compact{width:auto;min-width:0;font-size:12px}
table.dt-compact th,table.dt-compact td{padding:5px 12px;white-space:nowrap}
table.dt-compact td:first-child,table.dt-compact th:first-child{position:sticky;left:0;background:#fff}
table.dt-compact th:first-child{background:var(--2e-grey-light)}
table.dt-compact .mx-n{color:var(--2e-grey-dark);font-size:10px;margin-left:3px}

.placeholder{background:#fff;border:1px dashed var(--2e-blue-light);border-radius:13px;padding:46px 20px;text-align:center;color:var(--2e-grey-dark)}
.placeholder h3{color:var(--2e-blue-dark);margin-bottom:8px}
.hidden{display:none!important}

.fstage{display:flex;align-items:center;gap:10px;margin-bottom:6px;font-size:12px}
.fstage .lbl{width:240px;flex:none}
.fstage .track{flex:1;background:var(--2e-grey-light);border-radius:5px;overflow:hidden}
.fstage .bar{height:19px;border-radius:5px}
.fstage .val{width:120px;flex:none;text-align:right;color:var(--2e-grey-dark)}
.flegend{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--2e-grey-dark);margin:10px 0 4px}
.flegend span::before{content:"";display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:middle;background:var(--c)}
#t-diagram svg{display:block}
#t-diagram .node rect{rx:9;stroke-width:1.5}
#t-diagram .node text{font-family:var(--font-body);font-size:11px;fill:var(--2e-blue-dark)}
#t-diagram .edgelbl{font-family:var(--font-body);font-size:10.5px;font-weight:600;fill:var(--2e-blue-dark)}
#t-diagram .edgesub{font-family:var(--font-body);font-size:9px;fill:var(--2e-grey-dark)}
#t-diagram .branch rect{fill:#EEF3F9;stroke:#C9D6E6}
#t-diagram .branch text{fill:var(--2e-grey-dark)}
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
  </div>
  <span class="gen" id="gen"></span>
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
      <div class="panel">
        <h3>Matriz año × mes</h3>
        <div class="sub">Filas = mes, columnas = año. El número chico gris es la cantidad de guías (o de vuelos, en "kg/AWB"). Respeta forwarder y unidad de negocio, no año/mes. Tarifa = costo ÷ kilos facturables con costo (solo desde 2025). Carga se costea por peso volumétrico; Casilla por kilo real.</div>
        <div class="metric-switch" id="mx-metric">
          <button data-x="tarifa" class="on">Tarifa promedio (US$/kg)</button>
          <button data-x="kilos">Kilos promedio (kg/guía)</button>
          <button data-x="kilosvuelo">Kilos promedio por vuelo (kg/AWB)</button>
        </div>
        <div class="tbl-scroll"><table class="dt dt-compact" id="perf-matrix"></table></div>
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
  </main>
</div>

<script>
const DB = __PAYLOAD__;
const CI = {}; DB.cols.forEach((c,i)=>CI[c]=i);
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

const F = {fy:new Set(), fm:new Set(), fw:new Set(), un:new Set()};
let TAB = "performance", PMETRIC = "costo", MXMETRIC = "tarifa", TMETRIC = "corridos";
const charts = {};
// key del tramo según toggle corridos/hábiles: "d_xxx" -> "dh_xxx"
const dk = k => TMETRIC==="habiles" ? k.replace(/^d_/,"dh_") : k;

// forwarders con muy pocas guias historicas -> se pliegan como "Otro"
const FW_SMALL = new Set(DB.meta.forwarders.filter(x=>x[1]<5).map(x=>x[0]));
DB.rows.forEach(r=>{ if(FW_SMALL.has(r[CI.fw])) r[CI.fw]="Otro"; });
const YEARS = [...new Set(DB.rows.map(r=>r[CI.fy]))].sort();
const FWS = DB.meta.forwarders.filter(x=>x[1]>=5).map(x=>x[0]).concat(FW_SMALL.size?["Otro"]:[]);
const UNS = DB.meta.unidades.map(x=>x[0]);

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
  ["resumen","performance","productos","tiempos"].forEach(t=>
    document.getElementById("tab-"+t).classList.toggle("hidden",t!==TAB));
  render();};
document.getElementById("perf-metric").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;PMETRIC=b.dataset.m;
  document.querySelectorAll("#perf-metric button").forEach(x=>x.classList.toggle("on",x===b));
  render();};
document.getElementById("mx-metric").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;MXMETRIC=b.dataset.x;
  document.querySelectorAll("#mx-metric button").forEach(x=>x.classList.toggle("on",x===b));
  renderMatrix();};
document.getElementById("t-metric").onclick=e=>{
  const b=e.target.closest("button");if(!b)return;TMETRIC=b.dataset.t;
  document.querySelectorAll("#t-metric button").forEach(x=>x.classList.toggle("on",x===b));
  renderTiempos();};

function newChart(id,cfg){if(charts[id])charts[id].destroy();charts[id]=new Chart(document.getElementById(id),cfg);}
const baseOpts={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},animation:false};

// CK = índice de la columna de costo activa (real o estimado)
function byForwarder(rows, CK){
  const g={};
  rows.forEach(r=>{
    const k=r[CI.fw];
    (g[k]||(g[k]={fw:k,n:0,ent:0,peso:0,pesoVol:0,costo:0,nCosto:0,pesoCosto:0,vuelos:new Set(),transit:[],total:[]}));
    const o=g[k];o.n++;o.ent+=r[CI.entregada];o.peso+=r[CI.peso]||0;o.pesoVol+=r[CI.peso_vol]||0;
    if(r[CI.gm_id])o.vuelos.add(r[CI.gm_id]);
    if(CK!=null && r[CK]){o.costo+=r[CK];o.nCosto++;o.pesoCosto+=r[CI.peso_fact]||0;}  // peso_fact = billable (Carga)
    if(r[CI.d_desp_arr]!=null)o.transit.push(H2D(r[CI.d_desp_arr]));
    if(r[CI.d_total]!=null)o.total.push(H2D(r[CI.d_total]));
  });
  return Object.values(g).map(o=>({...o, nVuelos:o.vuelos.size,
    entPct:o.n?o.ent/o.n*100:0, transitMed:median(o.transit), totalMed:median(o.total),
    volRatio:o.peso?o.pesoVol/o.peso:null, guiasVuelo:o.vuelos.size?o.n/o.vuelos.size:null,
    costoKg:o.pesoCosto?o.costo/o.pesoCosto:null, costoGuia:o.nCosto?o.costo/o.nCosto:null,
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
  } else nt.classList.add("hidden");

  const kpis = costoMode ? [
    ["Vuelos (AWB)",fmtN(nVuelos),nVuelos?fmt1(totN/nVuelos)+" guías/vuelo":""],
    ["Guías con costo",fmtN(rowsCosto.length), useEst&&nEstReal?fmtN(nEstReal)+" estimadas":""],
    ["Costo total de flete",fmtUSD(totCosto)],
    ["Costo promedio por guía",fmtUSD(rowsCosto.length?totCosto/rowsCosto.length:null)],
    ["Costo por kilo",pesoCosto?"US$"+fmt2(totCosto/pesoCosto):"–"],
    ["Kilo/vol vs real",totPeso?"×"+fmt2(totPesoVol/totPeso):"–","peso volumétrico ÷ peso real"],
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
  const cH = costoMode ? ["Guías c/costo",ck+" total (US$)","Costo/kg (US$)","Costo/guía (US$)"] : [];
  const cR = x => costoMode ? [fmtN(x.nCosto),x.costo?fmtUSD(x.costo):"–",x.costoKg?fmt2(x.costoKg):"–",x.costoGuia?fmt1(x.costoGuia):"–"] : [];
  const head=["Forwarder","Vuelos","Guías","Guías/vuelo","Entregadas","% entrega","Kilos","Kilo/vol","Vol/real",...cH,"Tránsito aéreo (d)","Puerta a puerta (d)"];
  const body=g.map(x=>[x.fw,fmtN(x.nVuelos),fmtN(x.n),x.guiasVuelo?fmt1(x.guiasVuelo):"–",fmtN(x.ent),x.entPct.toFixed(1)+"%",fmtKg(x.peso),fmtKg(x.pesoVol),
    x.volRatio?"×"+fmt2(x.volRatio):"–",...cR(x),
    x.transitMed?fmt1(x.transitMed):"–",x.totalMed?fmt1(x.totalMed):"–"]);
  const cF = costoMode ? [fmtN(rowsCosto.length),totCosto?fmtUSD(totCosto):"–",pesoCosto?fmt2(totCosto/pesoCosto):"–",rowsCosto.length?fmt1(totCosto/rowsCosto.length):"–"] : [];
  const foot=["Total",fmtN(nVuelos),fmtN(totN),nVuelos?fmt1(totN/nVuelos):"–",fmtN(totEnt),(totN?(totEnt/totN*100).toFixed(1):0)+"%",fmtKg(totPeso),fmtKg(totPesoVol),
    totPeso?"×"+fmt2(totPesoVol/totPeso):"–",...cF,transitAll?fmt1(transitAll):"–",fmt1(p2p)];
  renderTable(T,head,body,foot);
  renderMatrix();
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
  const M=MXMETRIC;  // "tarifa" | "kilos" | "kilosvuelo"
  const agg = ks => {
    let peso=0,n=0,costo=0,pesoC=0; const vs=new Set();
    ks.forEach(k=>{const o=acc[k];peso+=o.peso;n+=o.n;costo+=o.costo;pesoC+=o.pesoC;o.vuelos.forEach(x=>vs.add(x));});
    return {peso,n,costo,pesoC,nv:vs.size};
  };
  const val = a => M==="tarifa"     ? (a.costo && a.pesoC ? a.costo/a.pesoC : null)
                 : M==="kilosvuelo" ? (a.nv ? a.peso/a.nv : null)
                                    : (a.n ? a.peso/a.n : null);
  const fmtCell = v => v==null ? "–" : (M==="tarifa" ? fmt2(v) : fmt1(v));
  const subN = a => M==="kilosvuelo" ? a.nv : a.n;   // n mostrado: vuelos o guías

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
    const fill = cls==="branch"?"#EEF3F9":(i===N-1?"#E4F3EA":"#EAF1FA");
    const stroke = cls==="branch"?"#C9D6E6":(i===N-1?"#2E9E6B":"#5691DF");
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
  const branchTop=(i,txt)=>`<line x1="${ncx(i)}" y1="${midY-nodeH/2}" x2="${ncx(i)}" y2="34" stroke="#C9D6E6" stroke-dasharray="3 3"/>`+node(i,txt,"branch",8);
  const branchBot=(i,txt,y)=>`<line x1="${ncx(i)}" y1="${midY+nodeH/2}" x2="${ncx(i)}" y2="${(y||195)}" stroke="#C9D6E6" stroke-dasharray="3 3"/>`+node(i,txt,"branch",y||195);
  svg+=branchTop(1,"Nula / Restringido / Retiro Miami");
  svg+=branchBot(1,"Solicitud consolidación → Consolidado",196);
  svg+=`<line x1="${ncx(7)}" y1="${midY+nodeH/2}" x2="${ncx(7)+PITCH/2}" y2="196" stroke="#C9D6E6" stroke-dasharray="3 3"/>`
      +`<g class="node branch"><rect x="${nx(7)+30}" y="196" width="${W+40}" height="${nodeH}" rx="9" fill="#FFF3E0" stroke="#E0A100"/>`
      +`<text x="${nx(7)+30+(W+40)/2}" y="216" text-anchor="middle" fill="#7A5B00">En Retención</text>`
      +`<text x="${nx(7)+30+(W+40)/2}" y="230" text-anchor="middle" fill="#7A5B00" font-size="10">${fmtN(nRet)} guías · ${fmt1(pRet)}%</text></g>`;
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
      borderColor:"#E3203E",backgroundColor:"rgba(227,32,62,.08)",fill:true,tension:.3,spanGaps:true}]},options:baseOpts});

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

function render(){
  const rows=filtered();
  const m=DB.meta;
  document.getElementById("scope-note").innerHTML=
    `<b>${fmtN(rows.length)}</b> / ${fmtN(m.n_registros)} guías con vuelo en el filtro<br>`+
    `Universo: guías despachadas a aeropuerto, ${m.fecha_desde.slice(0,4)}–hoy, flujo courier (Carga excluida)<br>`+
    `Fuente: NocoDB 2ebox · ${DB.generado}`;
  if(TAB==="performance")renderPerformance();
  else if(TAB==="tiempos")renderTiempos();
}

document.getElementById("gen").textContent="Generado "+DB.generado+" · fuente: NocoDB 2ebox";
buildChips();
render();
</script>
</body>
</html>
"""

out = HTML.replace("__PAYLOAD__", PAYLOAD)
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
