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
GEN = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC")


def js_string(html_text):
    """HTML -> literal de string JS seguro para incrustar dentro de <script>."""
    return json.dumps(html_text).replace("</", "<\\/")


cumpl = CUMPL_HTML.read_text(encoding="utf-8")

rl = RL_HTML.read_text(encoding="utf-8")
# Rendimiento Logístico embebido: por ahora solo Performance + Análisis de
# Tiempos -> se quitan los botones de pestaña Resumen y Análisis de Productos
# (las <section> quedan ocultas en el DOM, no molestan; el JS las sigue
# encontrando).
rl = rl.replace('<button class="tab" data-tab="resumen">Resumen</button>', "")
rl = rl.replace('<button class="tab" data-tab="productos">Análisis de Productos</button>', "")
# el shell ya tiene su barra de marca -> en el embed se oculta la marca/fecha
# de la barra interna del reporte de rendimiento (deja solo las pestañas).
rl = rl.replace("</style>", ".topbar .brand,.topbar .gen{display:none}.topbar{padding:7px 20px}</style>", 1)

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
.snav .gen{margin-left:auto;font-size:10.5px;color:var(--2e-blue-light)}
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
  <span class="gen">Integrado __GEN__</span>
</div>
<div class="frames">
  <iframe id="f-cumpl" title="Cumplimiento de Vuelos"></iframe>
  <iframe id="f-rl" title="Rendimiento Logístico" hidden></iframe>
</div>
<script>
const SRC = { cumpl: __CUMPL__, rl: __RL__ };
const done = {};
function show(s){
  if(!(s in SRC)) s = "cumpl";
  document.querySelectorAll("#snav button").forEach(b=>b.classList.toggle("active", b.dataset.s===s));
  ["cumpl","rl"].forEach(k=>{
    const f = document.getElementById("f-"+k);
    if(k===s && !done[k]){ f.srcdoc = SRC[k]; done[k] = 1; }
    f.hidden = k!==s;
  });
  try{ history.replaceState(null, "", "#"+s); }catch(e){}
}
document.getElementById("snav").addEventListener("click", e=>{
  const b = e.target.closest("button[data-s]"); if(b) show(b.dataset.s);
});
show(location.hash.replace("#",""));
</script>
</body>
</html>
"""

def fill(shell):
    return (shell.replace("__GEN__", GEN)
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
