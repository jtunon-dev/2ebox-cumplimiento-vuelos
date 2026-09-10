# Reporte Logística 2ebox — actualización automática

Publica todos los días, sin depender de que ningún PC esté encendido, el
**Reporte Logística 2ebox**: un solo HTML con dos secciones que se navegan
desde la barra superior.

| Sección | Qué muestra |
|---|---|
| **Cumplimiento de Vuelos** | Qué guías regulares (courier) no volaron en el primer vuelo que les correspondía (2026). Resumen, Individuales, Consolidadas, Guías afectadas, Capacidad de Vuelos, Conclusiones, Modelo Aduana. |
| **Rendimiento Logístico** | Performance por forwarder/AWB (costo total, costo/kg, costo/guía, tránsito aéreo, matriz año×mes) y Análisis de Tiempos (diagrama de estados 2ebox con tiempos entre estados, funnel, días corridos/hábiles). Datos 2023–hoy. |

Cada sección es un reporte independiente embebido en su propio `<iframe>`
(aislamiento total de CSS/JS).

## Cómo funciona

1. **Cumplimiento de Vuelos**
   - `extraer_cumplimiento_vuelos.py` → `cumplimiento_vuelos.json`
   - `build_dashboard.py` → `cumplimiento_vuelos.html`
2. **Rendimiento Logístico**
   - `extraer_rl.py` → `data/datos_crudos.json` + `data/meta.json`
   - `build_rl_dashboard.py` → `reporte-logistica-operaciones.html`
3. **Integración**
   - `build_integrado.py` → `reporte-integrado-2ebox.html` (el que se publica)
4. El workflow `.github/workflows/actualizar.yml` corre los 5 pasos todos los
   días a las ~08:00 hora de Chile (o a mano desde *Actions → Run workflow*) y
   publica el HTML integrado en GitHub Pages como `index.html`. También deja
   `cumplimiento-vuelos.html` y `rendimiento-logistico.html` sueltos por si se
   quieren linkear directo.

Todos los `.json`/`.html` están en `.gitignore` — se generan, no se commitean.

## Configuración (una sola vez)

- **Secret `NOCO_TOKEN`**: token de acceso a la API de NocoDB. Se configura en
  *Settings → Secrets and variables → Actions → New repository secret*. Ambos
  extractores lo leen de la variable de entorno `NOCO_TOKEN`; si no existe,
  fallan (nunca hay token hardcodeado en este repo público).
- **GitHub Pages**: *Settings → Pages → Source: GitHub Actions*.

## Editar el reporte

El código se desarrolla en la carpeta de trabajo (`Projects/BBDD y Reportería
2ebox/`, dos subcarpetas separadas). Para publicar cambios: copiar los scripts
`.py` acá, restaurar el bloque `NOCO_TOKEN` sin default en `extraer_rl.py`,
commit + push a `main`, y `gh workflow run actualizar.yml`.
