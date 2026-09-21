"""
Reporte Logística 2ebox — integra en un solo HTML dos reportes que se
mantienen independientes:

  1. Cumplimiento de Vuelos  (analisis_vuelos_no_volados/cumplimiento_vuelos.html)
  2. Rendimiento Logístico    (reporte-logistica-operaciones.html, solo las
     sub-secciones Performance y Análisis de Tiempos por ahora)

Cada reporte va COMPLETO dentro de su propio <iframe> (aislamiento total de
CSS/JS — ninguno de los dos se toca). El shell solo agrega la navegación
superior entre las 2 secciones. Los iframes se cargan de forma perezosa
(recién al abrir su pestaña) y conservan su estado al cambiar de sección.

Uso:  python build_integrado.py
Requiere que ambos HTML ya estén generados por sus respectivos build_dashboard.py.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent


def _first(*cands):
    for c in cands:
        if c.exists():
            return c
    return cands[0]


# Funciona tanto en el repo publico (layout plano) como en la carpeta de
# desarrollo (Projects/BBDD y Reportería 2ebox/...).
CUMPL_HTML = _first(
    BASE / "cumplimiento_vuelos.html",
    BASE.parent / "analisis_vuelos_no_volados" / "cumplimiento_vuelos.html",
)
RL_HTML = _first(
    BASE / "reporte-logistica-operaciones.html",
    BASE / "reporte_logistica_operaciones" / "reporte-logistica-operaciones.html",
)
OUT = BASE / "reporte-integrado-2ebox.html"
_now = datetime.now(timezone.utc)
GEN = _now.strftime("%d-%m-%Y %H:%M UTC")
GEN_ISO = _now.isoformat()


def js_string(html_text):
    """HTML -> literal de string JS seguro para incrustar dentro de <script>."""
    return json.dumps(html_text).replace("</", "<\\/")


cumpl = CUMPL_HTML.read_text(encoding="utf-8")
# el shell ahora trae su propio badge de actualizacion + toggle de tema
# compartido para los 2 reportes -> se ocultan los de Cumplimiento de Vuelos
# (siguen existiendo para cuando este reporte se ve standalone).
cumpl = cumpl.replace("</style>", "#update-badge,#theme-toggle-btn{display:none}</style>", 1)

rl = RL_HTML.read_text(encoding="utf-8")
# Rendimiento Logístico embebido: por ahora solo Performance + Análisis de
# Tiempos -> se quitan los botones de pestaña Resumen y Análisis de Productos
# (las <section> quedan ocultas en el DOM, no molestan; el JS las sigue
# encontrando).
rl = rl.replace('<button class="tab" data-tab="resumen">Resumen</button>', "")
rl = rl.replace('<button class="tab" data-tab="productos">Análisis de Productos</button>', "")
# el shell ya tiene su barra de marca y su propio badge/toggle compartido ->
# en el embed se oculta la marca/fecha/toggle de la barra interna de
# Rendimiento Logístico (deja solo las pestañas).
rl = rl.replace("</style>", ".topbar .brand,.topbar .gen,#theme-toggle-btn{display:none}.topbar{padding:7px 20px}</style>", 1)

SHELL = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporte Logística 2ebox</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Russo+One&family=Fira+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{--2e-blue-dark:#152C4A;--2e-red-light:#E63551;--2e-blue-light:#A7C5E1;--2e-grey-light:#F6FAFD}
*{box-sizing:border-box}
html,body{margin:0;height:100%;font-family:'Fira Sans',system-ui,sans-serif;background:var(--2e-grey-light)}
body{display:flex;flex-direction:column}
.snav{background:var(--2e-blue-dark);color:#fff;display:flex;align-items:center;gap:6px;padding:9px 18px;flex:none;flex-wrap:wrap}
.snav .brand{font-family:'Russo One',sans-serif;font-size:16px;letter-spacing:.4px;margin-right:14px}
.snav .brand b{color:var(--2e-red-light)}
.snav button{background:transparent;border:none;color:var(--2e-blue-light);font-family:'Russo One',sans-serif;
  font-size:12.5px;letter-spacing:.4px;padding:8px 16px;border-radius:8px;cursor:pointer}
.snav button:hover{color:#fff;background:rgba(255,255,255,.08)}
.snav button.active{background:var(--2e-grey-light);color:var(--2e-blue-dark)}
.snav .right{margin-left:auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.update-badge{display:inline-flex;align-items:center;gap:6px;font-family:'Fira Sans',sans-serif;font-size:11px;font-weight:600;
  padding:6px 11px;border-radius:9px;border:1px solid rgba(255,255,255,.22);white-space:nowrap;
  background:rgba(255,255,255,.06);color:var(--2e-blue-light)}
.update-badge.ok{background:rgba(52,199,122,.16);color:#34C77A;border-color:rgba(52,199,122,.4)}
.update-badge.stale{background:rgba(227,32,62,.16);color:#FF6B84;border-color:rgba(227,32,62,.4)}
.theme-toggle{display:inline-flex;align-items:center;gap:6px;font-family:'Fira Sans',sans-serif;font-size:11.5px;font-weight:600;
  padding:6px 12px;border:1px solid rgba(255,255,255,.22);border-radius:9px;background:rgba(255,255,255,.06);
  color:#fff;cursor:pointer;white-space:nowrap}
.theme-toggle:hover{background:rgba(255,255,255,.14)}
.frames{flex:1;min-height:0;position:relative}
.frames iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:#fff}
.frames iframe[hidden]{display:none}
</style>
</head>
<body>
<div class="snav" id="snav">
  <span class="brand">2e<b>box</b> · Reporte Logística</span>
  <button data-s="cumpl" class="active">Cumplimiento de Vuelos</button>
  <button data-s="rl">Rendimiento Logístico</button>
  <div class="right">
    <span class="update-badge" id="update-badge">cargando…</span>
    <button class="theme-toggle" id="theme-toggle-shell" onclick="alternarTemaShell()">🌙 Modo oscuro</button>
  </div>
</div>
<div class="frames">
  <iframe id="f-cumpl" title="Cumplimiento de Vuelos"></iframe>
  <iframe id="f-rl" title="Rendimiento Logístico" hidden></iframe>
</div>
<script>
const SRC = { cumpl: __CUMPL__, rl: __RL__ };
const done = {};

// Tema compartido: un solo control en el shell mueve los 2 iframes (cada
// reporte por si solo sigue soportando su propio toggle interno cuando se
// mira standalone -- ver build_dashboard.py / build_rl_dashboard.py). Se
// fuerza SIEMPRE (nunca se deja "sin atributo") para no heredar una
// preferencia vieja que haya quedado en localStorage de una visita
// standalone anterior (mismo origen que el shell -> mismo localStorage).
let TEMA = "light";
try { TEMA = localStorage.getItem("integrado-tema") || "light"; } catch (e) {}

function actualizarBotonTemaShell(){
  document.getElementById("theme-toggle-shell").textContent = TEMA === "dark" ? "☀️ Modo claro" : "🌙 Modo oscuro";
}
function aplicarTemaEnFrame(k){
  if(!done[k]) return; // se inyecta en el srcdoc al cargar -- ver show()
  const f = document.getElementById("f-"+k);
  try{
    f.contentDocument.documentElement.setAttribute("data-theme", TEMA);
    if(k==="rl" && f.contentWindow.aplicarTemaGraficos){
      f.contentWindow.aplicarTemaGraficos();
      f.contentWindow.render();
    }
  }catch(e){}
}
function alternarTemaShell(){
  TEMA = TEMA === "dark" ? "light" : "dark";
  try { localStorage.setItem("integrado-tema", TEMA); } catch (e) {}
  actualizarBotonTemaShell();
  ["cumpl","rl"].forEach(aplicarTemaEnFrame);
}

function show(s){
  if(!(s in SRC)) s = "cumpl";
  document.querySelectorAll("#snav button[data-s]").forEach(b=>b.classList.toggle("active", b.dataset.s===s));
  ["cumpl","rl"].forEach(k=>{
    const f = document.getElementById("f-"+k);
    if(k===s && !done[k]){
      const html = SRC[k].replace("</head>", "<script>document.documentElement.setAttribute(\"data-theme\",\"" + TEMA + "\")<\/script></head>");
      f.srcdoc = html;
      done[k] = 1;
    }
    f.hidden = k!==s;
  });
  try{ history.replaceState(null, "", "#"+s); }catch(e){}
}
document.getElementById("snav").addEventListener("click", e=>{
  const b = e.target.closest("button[data-s]"); if(b) show(b.dataset.s);
});
actualizarBotonTemaShell();
show(location.hash.replace("#",""));

// Badge de actualizacion -- mismo criterio que Cumplimiento de Vuelos
// standalone (verde = hoy, rojo = "hace N dias"), calculado en el
// navegador para que siga siendo correcto sin importar cuando se mire.
(function () {
  var el = document.getElementById("update-badge");
  var GENERADO_ISO = "__GEN_ISO__";
  var d = new Date(GENERADO_ISO);
  if (isNaN(d.getTime())) { el.textContent = "s/d"; return; }
  var ahora = new Date();
  var pad = function (n) { return String(n).padStart(2, "0"); };
  var MESES_CORTOS = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  var fechaCorta = pad(d.getDate()) + "-" + MESES_CORTOS[d.getMonth()];
  var hora = pad(d.getHours()) + ":" + pad(d.getMinutes());
  var esHoy = d.getFullYear() === ahora.getFullYear() && d.getMonth() === ahora.getMonth() && d.getDate() === ahora.getDate();
  if (esHoy) {
    el.className = "update-badge ok";
    el.textContent = "🟢 " + fechaCorta + " " + hora;
  } else {
    var dias = Math.max(1, Math.round((ahora - d) / 86400000));
    el.className = "update-badge stale";
    el.textContent = "🔴 " + fechaCorta + " " + hora + " (hace " + dias + (dias === 1 ? " día" : " días") + ")";
  }
})();
</script>
</body>
</html>
"""

def fill(shell):
    return (shell.replace("__GEN_ISO__", GEN_ISO)
            .replace("__CUMPL__", js_string(cumpl))
            .replace("__RL__", js_string(rl)))

OUT.write_text(fill(SHELL), encoding="utf-8")
print(f"-> {OUT.name}  ({len(fill(SHELL))//1024} KB)")

# variante Artifact: se le sacan al SHELL (no al contenido embebido) los tags
# <!doctype>/<html>/<head>/<body> antes de rellenar.
shell_frag = SHELL
for tag in ("<!doctype html>", '<html lang="es">', "</html>", "<head>", "</head>", "<body>", "</body>"):
    shell_frag = shell_frag.replace(tag, "")
(BASE / "artifact-integrado.html").write_text(fill(shell_frag).strip(), encoding="utf-8")
print(f"-> artifact-integrado.html")
print(f"   cumplimiento: {len(cumpl)//1024} KB · rendimiento: {len(rl)//1024} KB")
