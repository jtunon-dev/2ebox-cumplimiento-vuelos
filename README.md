# Cumplimiento de Vuelos 2ebox — actualización automática

Publica todos los días, sin depender de que ningún PC esté encendido, el
reporte de qué guías no volaron en el primer vuelo que les correspondía
(2ebox, año 2026).

## Cómo funciona

1. `extraer_cumplimiento_vuelos.py` se conecta a NocoDB (`noco.2ebox.com`,
   público en internet) y calcula el detalle guía a guía + capacidad de
   vuelos, guardando `cumplimiento_vuelos.json`.
2. `build_dashboard.py` lee ese JSON y genera `cumplimiento_vuelos.html`
   (un archivo autocontenido, sin dependencias externas).
3. El workflow de GitHub Actions (`.github/workflows/actualizar.yml`) corre
   los dos scripts todos los días a las ~08:00 hora de Chile (también se
   puede disparar a mano desde la pestaña *Actions* del repo, botón
   *Run workflow*) y publica el HTML resultante en GitHub Pages.

## Configuración (una sola vez)

- **Secret `NOCO_TOKEN`**: el token de acceso a la API de NocoDB. Se
  configura en *Settings → Secrets and variables → Actions → New repository
  secret*. El script lo lee de la variable de entorno `NOCO_TOKEN`; si no
  existe, cae a un valor por defecto (el mismo que usa la copia local del
  script) — pero en este repo automatizado siempre debe venir del secret.
- **GitHub Pages**: en *Settings → Pages*, la fuente (*Source*) debe estar
  en **GitHub Actions** (no "Deploy from a branch") — el workflow ya está
  escrito para ese modo.

## Importante — este repo es PÚBLICO

El dashboard publicado incluye datos operativos de 2ebox a nivel de guía
individual (números de guía, casillas de cliente, kilos, códigos de
convenio, AWB de vuelos). Al ser un repo público, tanto el código fuente
(la metodología completa) como el reporte publicado en GitHub Pages son
visibles para cualquiera con el link, sin login. Esta decisión fue
explícita (Jorge, 2026-09-02) priorizando simplicidad y costo cero sobre
mantener el reporte privado. Si esto cambia, ver las alternativas
(Cloudflare Pages + Access, o GitHub Pro con repo privado) evaluadas en esa
conversación.

## Correr localmente

```
python extraer_cumplimiento_vuelos.py
python build_dashboard.py
```

Genera `cumplimiento_vuelos.json` y `cumplimiento_vuelos.html` en la carpeta
actual (no se commitean — están en `.gitignore`).
