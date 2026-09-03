"""Extrae de NocoDB (tabla dataconsolider.ebox_cumplimiento, espejada como
`ebox_cumplimiento` en la base pifk61tmzhes073) las guias regulares del 2026
y calcula, para cada una, si voló en el PRIMER vuelo que le correspondía o
si se quedó fuera de él (y voló despues, o todavia no vuela).

Metodologia (confirmada con Jorge, 2026-09-01):
- Una guia queda "lista para volar" cuando tiene fecha de pago Y esta en
  Miami con factura -- exactamente los campos `fecha_primer_pago` y
  `fecha_miami_con_factura` que ya trae ebox_cumplimiento. fecha_lista =
  MAX(fecha_primer_pago, fecha_miami_con_factura). Si falta alguna de las
  dos, la guia no entra al analisis (nunca quedo lista).
- El "vuelo" de cada guia es su `guia_madre` real (tabla `guia_madres`,
  cruzada via la relacion M2M `guia_hijas.guia_madres` -- ver seccion
  "Correccion de fondo" mas abajo, 2026-09-02). Cada guia_madre con
  `tipo_transporte != "CARGA"` es un vuelo regular; su fecha real de salida
  es MIN(fecha_despachado_aeropuerto) de sus guias miembro que ya
  despacharon. Version anterior (hasta 2026-09-01) reconstruia el
  calendario agrupando timestamps de despacho por proximidad (gap de 10
  min) en vez de usar el guia_madre real -- reemplazada por errores
  encontrados con datos reales (ver docstring de mas abajo).
- Vuelos de "carga" (AWB propio, canal de envio distinto al vuelo regular
  de miercoles/viernes) quedan excluidos: cualquier guia cuyo guia_madre
  tenga `tipo_transporte == "CARGA"` se excluye por completo del analisis
  -- pedido explicito de Jorge ("los vuelos que tienen 1 guia son carga"),
  aplicado ahora con el dato real del sistema en vez de una heuristica de
  tamano de cluster (que fallaba en ambas direcciones -- ver mas abajo).
- Para cada guia lista, "el vuelo que le correspondia" es el primer vuelo
  del calendario (ordenado cronologicamente) con fecha_despacho >=
  fecha_lista. Se compara contra el vuelo real en el que broto (el ts de
  SU guia_madre, si ya despacho). Si no coinciden -> la guia NO volo en su
  primer vuelo correspondiente (broto despues, o sigue sin volar aun si el
  vuelo correspondiente ya paso).
- El incidente se cuenta en la semana/mes del vuelo que le correspondia (no
  en el que finalmente broto), porque es ahi donde se genero el atraso.

Se calculan DOS definiciones de incidente en paralelo (pedido de Jorge,
2026-09-01), sobre la misma poblacion de guias evaluables:
- **estricto**: no volo en el vuelo exacto que le correspondia (la logica de
  arriba, sin cambios).
- **semana**: mas permisivo -- no cuenta como incidente si broto en OTRO
  vuelo dentro de la MISMA semana calendario (lunes a domingo) del vuelo que
  le correspondia, aunque no haya sido ese vuelo puntual. Solo es incidente
  si broto en una semana POSTERIOR, o si nunca broto.
- En ambas definiciones, para contar como "afectada" la guia tiene que haber
  pasado por el estado "Asociado a Guia Madre" (`fecha_asignado_guia_madre`
  no nula) -- confirma que de verdad quedo en cola para otro vuelo, y no que
  el pedido se anulo/dio de baja antes de llegar a esa etapa (pedido de
  Jorge, 2026-09-01: encontro 5 casos "DAR DE BAJA"/"Nula" sin asignacion
  que antes se contaban como "nunca volo" sin haberlo sido nunca).

Para cada definicion se agregan ademas kilos afectados (suma de `peso`,
desde `guia_hijas`) y clientes unicos afectados (columna `casilla` de
`ebox_cumplimiento`), pedido explicito de Jorge.

Se trae un colchon desde 2025-12-15 (para poder calcular correctamente el
"primer vuelo correspondiente" de guias listas en los primeros dias de
enero 2026), pero el reporte final solo cuenta semanas/meses de 2026.

--- Correccion de fondo: vuelos por guia_madre real, no por clustering (2026-09-02) ---
Jorge encontro un caso concreto mal clasificado: la guia 157540 (Sindal SPA)
aparecia en "Guias afectadas" como "aun no vuela", pero en el sistema se
vio que se despacho a aeropuerto el MISMO dia que se le asigno guia madre
(16-ene-2026). Investigando la causa raiz (consulta directa a NocoDB,
tabla guia_madres via la relacion M2M guia_hijas.guia_madres): esa guia
viajo por un guia_madre con `tipo_transporte = "CARGA"` (AWB propio,
un solo bulto) -- un canal de envio real y valido, pero DISTINTO al vuelo
regular de miercoles/viernes. El metodo anterior (agrupar
fecha_despachado_aeropuerto por gap de tiempo, y tratar como "carga"
cualquier cluster de 1 sola guia) es una heuristica -- y fallaba en ambas
direcciones:
  1. Guias CARGA reales (como la 157540) que el sistema ya marca
     explicitamente con tipo_transporte="CARGA" quedaban en el analisis
     como "no volo", generando incidentes falsos que nunca se resuelven
     (su cluster de 1 guia nunca calzaba con ningun vuelo del calendario).
  2. Al reves: se encontraron 7 guia_madres con tipo_transporte="COURIER"
     (vuelo regular real, aerolineas Trans Caribbean/Mercury/LATAM) que
     tambien tienen 1 sola guia -- la heuristica los excluia del calendario
     de vuelos por error, tratandolos como carga cuando no lo eran.
Fix: se abandona el clustering por tiempo. Ahora el "vuelo" de cada guia se
determina por su guia_madre REAL (tabla `guia_madres`, relacionada 1:1 en la
practica via la tabla de union M2M `guia_hijas.guia_madres` -- ver
`TBL_GUIA_MADRE_HIJAS`), usando directamente el campo `tipo_transporte`:
  - `tipo_transporte == "CARGA"` -> la guia se EXCLUYE por completo del
    analisis (no es vuelo regular, es otro canal de envio -- mismo criterio
    que ya pedia Jorge para "vuelos de 1 sola guia", ahora aplicado con el
    dato real en vez de una heuristica de tamano de cluster).
  - Cualquier otro valor (COURIER, o vacio) -> SI es vuelo regular, sin
    importar cuantas guias tenga ese guia_madre en particular.
Cada "vuelo" del calendario es ahora, literalmente, un guia_madre distinto
(su ts = MIN(fecha_despachado_aeropuerto) de sus guias miembro que ya
despacharon). Esto tambien entrega gratis el AWB y la aerolinea real de
cada guia y de cada vuelo (pedido de Jorge, 2026-09-02: agregar columna
"N° vuelo / AWB" en Guias afectadas y en Capacidad de Vuelos).

--- Correccion de fondo (2): guia_madre de 1 sola guia = vuelo dedicado, sea CARGA o COURIER (2026-09-02) ---
Jorge planteo: cuando un guia_madre tiene 1 sola guia, da lo mismo si su
tipo_transporte es CARGA o COURIER -- significa que ese guia_madre se creo
y asigno ESPECIALMENTE para esa guia (no es que la guia "perdiera" un cupo
en un vuelo regular compartido con otras guias). Por lo tanto no tiene
sentido evaluarla bajo el criterio "no volo en el vuelo que le
correspondia": nunca hubo un vuelo regular al que tuviera que subirse.
Fix: el criterio de exclusion pasa de `tipo_transporte == "CARGA"` a
`tipo_transporte == "CARGA" OR items == 1` (el campo `items` de
`guia_madres`, tamano real del manifiesto). Esto tambien saca del
CALENDARIO de vuelos a los guia_madres COURIER de 1 sola guia (los 7 casos
mencionados arriba) -- ya no cuentan como "el vuelo que le correspondia" a
NINGUNA otra guia tampoco, porque no son vuelos regulares compartidos.

--- Correccion de fondo (3): hora de corte de manifiesto (2026-09-02) ---
Jorge aclaro un matiz operativo: existe un horario de corte para subir a un
vuelo -- en operaciones se validan los pagos normalmente hasta las 12:00 del
DIA del vuelo (miercoles/viernes). Si el pago llega a esa hora o despues,
la guia queda fuera de ESE vuelo aunque el despacho fisico ocurra mas tarde
ese mismo dia -- se asigna al PRIMER vuelo siguiente. Ejemplo dado: guia
llega jueves, sube factura el viernes, pero el cliente paga el viernes a
las 14:00 -> esa guia queda fuera del vuelo del viernes y le corresponde el
miercoles de la semana siguiente, no el viernes (aunque el despacho de ese
viernes sea, por ejemplo, en la tarde).
Hasta ahora `primer_vuelo_desde()` solo comparaba timestamps crudos
(ts_vuelo >= fecha_lista) -- no distinguia "alcanzo a validarse antes del
corte" de "broto el mismo dia pero de pura casualidad porque el despacho
fisico fue tarde". Fix: se agrega CORTE_MANIFIESTO_HORA (12:00) -- si el
primer vuelo con ts >= fecha_lista cae el MISMO dia calendario que
fecha_lista Y fecha_lista.hour >= 12, ese vuelo no cuenta como "el que le
correspondia"; se sigue buscando el vuelo siguiente (que puede ser otro vuelo
ese mismo dia, si lo hay, o el proximo dia de vuelo). No afecta `vuelo_real`
(el vuelo en que la guia efectivamente broto, un hecho empirico) -- solo la
determinacion de `vuelo_esperado`.

--- Investigacion de causa (2026-09-01) ---
Jorge pidio razonar por que abril-junio muestran tasas tan altas, y ademas
pidio separar las guias CONSOLIDADAS (varias guias originales fundidas en
una guia nueva por bodega, antes de volar) del resto, porque sospechaba que
la espera de consolidacion podia ser la causa.

Se investigaron dos hipotesis con los datos:
1. **Capacidad total de vuelos**: se comparo, semana a semana, la demanda
   acumulada (guias evaluables) contra la oferta acumulada (suma de
   n_guias de los vuelos del calendario) -- la oferta SIEMPRE supera a la
   demanda acumulada en 2026. Descartado como causa sistemica. La unica
   excepcion real es la semana del 25-may (Memorial Day en EEUU): esa
   semana los vuelos cargaron muy por debajo del promedio (71 guias vs
   ~120-150 habitual), lo que explica que sea la peor semana del año
   (73,4%) -- un caso puntual, no la explicacion del patron abril-junio.
2. **Retraso de asignacion a guia madre**: se midio, guia a guia, cuanto
   tiempo pasa entre "lista para volar" (fecha_lista) y
   `fecha_asignado_guia_madre`. La mediana sube de <2h (dic-mar) a
   4-11,5h (may-jul) -- ver `lag_asignacion_por_mes` en el JSON de salida.
   Esto calza con que el 85% de los incidentes (estricto) se saltan
   EXACTAMENTE 1 vuelo (alcanzan el siguiente) -- consistente con quedar
   listas justo despues del corte de manifiesto de su vuelo por un
   procesamiento mas lento, no con quedar varias semanas varadas.
3. **Consolidacion, probada y DESCARTADA como causa del patron abril-junio**:
   se separaron las guias NUEVAS de consolidacion (`guia_hijas.consolidacion
   > 0`, identificadas via `investigar_consolidacion.py`) del resto. Tienen
   una tasa de incidencia estructuralmente mas alta en meses tranquilos
   (ene-mar, ~2x la de las individuales -- logico: quedan "listas" de golpe
   justo cuando se arma el bulto consolidado, con poco margen para el corte
   del vuelo), pero el tiempo que tardan en armarse los bultos se mantuvo
   estable todo el año (mediana ~7-8 dias, sin repunte en mayo-junio) y el
   salto abril-junio ocurre en AMBAS poblaciones casi por igual (ver
   `por_mes_poblacion` en el JSON) -- confirma que la causa es compartida
   y sistemica (el retraso de asignacion del punto 2), no algo propio de
   la consolidacion. El bloque `poblacion` en `bloque_definicion()` de
   abajo hace este split; la guia_hijas.consolidacion se trae junto al
   peso en la misma llamada.
"""
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, date, timedelta, timezone
import statistics

# Este repo es PUBLICO (ver README) -- a diferencia de la copia local del
# script (que sí trae un default hardcodeado para comodidad), aquí el token
# SOLO puede venir del secret de GitHub Actions. Nunca hardcodear el valor
# real en este archivo.
NOCO_TOKEN = os.environ.get("NOCO_TOKEN")
if not NOCO_TOKEN:
    raise SystemExit(
        "Falta la variable de entorno NOCO_TOKEN. En GitHub Actions debe venir "
        "del secret del repo (Settings -> Secrets and variables -> Actions)."
    )
NOCO_BASE = "pifk61tmzhes073"
NOCO_BASE_URL = "https://noco.2ebox.com/api/v1/db/data/noco"
TBL_CUMPLIMIENTO = "m4feao7xeudu8k9"
TBL_GUIA_HIJAS = "m4b0yh4lwpxsvri"
TBL_GUIA_MADRES = "m5t0y2pg3d0qt7h"
# Tabla `consolidaciones` (registro del bulto armado en bodega): id, fob
# (0 = se cerro el bulto con al menos una factura pendiente), fecha (creacion
# del registro en sistema, al FINAL de la coordinacion por correo),
# consolidaciones_guias (cuantas guias originales se fundieron), estado
# (1=Creada, 2=Finalizada). Se enlaza con la guia-bulto via
# guia_hijas.consolidacion == consolidaciones.id. Usada para clasificar si el
# atraso de una guia consolidada se explica por el propio proceso de
# consolidacion (2026-09-02, T-0006).
TBL_CONSOLIDACIONES = "mtz3g6ngt242ep9"
# Tabla de union M2M interna que NocoDB genera para la relacion
# guia_hijas.guia_madres <-> guia_madres.guia_hijas. No aparece en el listado
# de tablas normal (es "system"), pero es consultable directo por id via la
# API de datos. Encontrada 2026-09-02 inspeccionando
# /api/v1/db/meta/tables/{TBL_GUIA_HIJAS} -> columna "guia_madres" ->
# colOptions.fk_mm_model_id. Si esto alguna vez deja de responder (cambio de
# esquema en NocoDB), volver a sacar el id desde ahi.
TBL_GUIA_MADRE_HIJAS = "mpwefzshqgun0m7"

FIELDS = (
    "n_guia,casilla,id_estado,fecha_ingreso,fecha_primer_pago,fecha_miami_con_factura,"
    "fecha_asignado_guia_madre,fecha_despachado_aeropuerto"
)
FIELDS_GUIA_HIJAS = "n_guia,peso,consolidacion,v_codigo_convenio"
FIELDS_GUIA_MADRES = "id,awb,flight_date,flight_number,tipo_transporte,items,fecha_creacion"
FECHA_DESDE = "2025-12-15"
ANIO_REPORTE = 2026
# Dias entre que se crea el registro de la consolidacion (bulto armado) y que
# la guia-bulto queda "lista para volar" (pago + factura), por encima de los
# cuales se considera que el atraso lo genero el propio proceso de
# consolidacion (goteo de facturas / re-armado del bulto) y no la operacion
# de vuelo. Calibrado contra el grupo de control (guias-bulto que SI
# alcanzaron su vuelo) -- ver control_armado_dias_volaron_ok en el JSON.
UMBRAL_ARMADO_LENTO_DIAS = 3
# Hora de corte de manifiesto: operaciones valida pagos hasta las 12:00 del
# DIA del vuelo -- un pago que llega a esa hora o despues ya no alcanza el
# manifiesto de ese vuelo, aunque el despacho fisico ocurra mas tarde ese
# mismo dia. Confirmado por Jorge, 2026-09-02 (ver "Correccion de fondo (3)"
# en el docstring del modulo).
CORTE_MANIFIESTO_HORA = 12


def noco_fetch_all(table_id, where="", fields="", page_size=1000):
    rows = []
    offset = 0
    while True:
        params = f"limit={page_size}&offset={offset}&shuffle=0"
        if where:
            params += "&where=" + urllib.parse.quote(where)
        if fields:
            params += f"&fields={fields}"
        url = f"{NOCO_BASE_URL}/{NOCO_BASE}/{table_id}?{params}"
        req = urllib.request.Request(url, headers={"xc-token": NOCO_TOKEN})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        batch = data.get("list", [])
        rows.extend(batch)
        total = data.get("pageInfo", {}).get("totalRows", 0)
        offset += len(batch)
        print(f"  {offset}/{total}", end="\r")
        if offset >= total or not batch:
            break
    print()
    return rows


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S%z")
    except ValueError:
        return datetime.strptime(s[:19] + "+00:00", "%Y-%m-%d %H:%M:%S%z")


def fetch_mapa_guia_madre(ids_guia_madre, chunk_size=150):
    """Devuelve dict str(n_guia) -> int(id_guia_madre), consultando la tabla
    de union M2M (TBL_GUIA_MADRE_HIJAS) en bloques -- el operador `in` de
    NocoDB no es confiable con listas muy largas en una sola consulta."""
    mapa = {}
    ids = list(ids_guia_madre)
    for i in range(0, len(ids), chunk_size):
        bloque = ids[i : i + chunk_size]
        where = "(id_guia_madre,in," + ",".join(str(x) for x in bloque) + ")"
        filas = noco_fetch_all(TBL_GUIA_MADRE_HIJAS, where=where)
        for f in filas:
            n_guia = (f.get("guia_hijas") or {}).get("n_guia")
            id_madre = f.get("id_guia_madre")
            if n_guia is not None and id_madre is not None:
                mapa[str(n_guia)] = id_madre
    return mapa


def iso_semana(dt):
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def lunes_de_semana(dt):
    d = dt.date()
    return d - timedelta(days=d.weekday())


def calcular_capacidad_vuelos(detalle, vuelos):
    """Capacidad por vuelo (pedido de Jorge, 2026-09-01, 6ta iteracion):
    'tope de lo que se ingreso' (guias que efectivamente volaron en ese
    vuelo) vs 'lo que se podria haber ingresado' (tamano de la cola de
    guias YA listas -- pago+factura -- que todavia no habian volado, justo
    antes de que ese vuelo saliera). La cola incluye tanto a las guias que
    SI abordan ese vuelo como a las que quedan esperando uno posterior --
    la brecha (podria - ingreso) es capacidad que ese vuelo especifico dejo
    sin usar. Ya excluye vuelos de 1 sola guia (carga) porque `vuelos` ya
    viene filtrado asi desde el calculo del calendario.

    Nota: 'ingreso' (n_guias, kg) se calcula de nuevo aqui recorriendo
    `detalle` completo por vuelo_real -- no reutiliza vuelos[]['n_guias']
    directamente porque aqui tambien necesitamos los kilos por vuelo, que
    el calendario no trae.

    Invariante que SIEMPRE debe cumplirse: podria >= ingreso (si X guias
    volaron, esas X ya estaban "listas" por definicion -- no puede haber
    menos demanda que capacidad realizada). El caso credito (guia que
    broto -- por cualquier canal -- ANTES de que su pago quedara
    registrado) se saca de la cola PERSISTENTE para no quedar fantasma
    inflando vuelos futuros, pero igual se suma al 'podria' del vuelo
    puntual en el que broto -- si no, quedaba contando menos demanda que
    capacidad realizada en ese vuelo, lo cual no tiene sentido (confirmado
    por Jorge, 2026-09-01).

    Bug real encontrado y corregido 2026-09-01 (2da vuelta): la cola
    agregaba/sacaba guias usando `vuelo_real` (que queda en None para
    despachos de CARGA, guias de 1 sola guia, excluidas a proposito del
    calendario de vuelos regulares). Eso hacia que una guia despachada por
    carga quedara "fantasma" en la cola PARA SIEMPRE -- nunca se sacaba,
    porque su vuelo_real nunca iguala al ts de ningun vuelo regular. Como
    la carga a veces es flete pesado (cientos de kg), kg_podria se inflaba
    sin limite mes a mes (llegaba a mas de 8.000 kg por vuelo hacia
    agosto). Fix: la cola usa `despacho_cualquiera` (cualquier canal,
    incluida carga) para decidir cuando una guia deja de estar "esperando"
    -- una guia despachada por carga sale de la cola igual, aunque no
    cuente como `ingreso` de ningun vuelo regular (eso sigue viniendo solo
    de `vuelo_real`, sin cambios)."""
    ingreso_por_vuelo = defaultdict(lambda: {"n": 0, "kg": 0.0})
    guias_por_vuelo_real = defaultdict(list)
    for d in detalle:
        if d["vuelo_real"]:
            b = ingreso_por_vuelo[d["vuelo_real"]]
            b["n"] += 1
            b["kg"] += d["peso"] or 0
            guias_por_vuelo_real[d["vuelo_real"]].append(d)

    guia_por_id = {d["n_guia"]: d for d in detalle}
    guias_por_lista = sorted(detalle, key=lambda d: d["fecha_lista"])
    ptr = 0
    n_total = len(guias_por_lista)
    pendientes = {}  # n_guia -> peso

    resultado = []
    for v in vuelos:
        ts_iso = v["ts"].isoformat()
        while ptr < n_total and datetime.fromisoformat(guias_por_lista[ptr]["fecha_lista"]) <= v["ts"]:
            d = guias_por_lista[ptr]
            ptr += 1
            # Caso credito: broto (por cualquier canal) ANTES de quedar
            # "lista" -- si se agrega igual a la cola PERSISTENTE, nunca se
            # saca (su despacho ya quedo atras cronologicamente) y queda
            # como fantasma. No compite por cupo de ningun vuelo futuro, se
            # excluye de `pendientes` -- pero se cuenta igual en el
            # 'podria' de SU PROPIO vuelo mas abajo si corresponde.
            desp = d["despacho_cualquiera"]
            if desp and desp < d["fecha_lista"]:
                continue
            pendientes[d["n_guia"]] = d["peso"] or 0

        # guias que vuelan en ESTE vuelo pero quedaron fuera de la cola
        # persistente (caso credito) -- se suman aqui para no romper el
        # invariante podria >= ingreso, sin persistir en `pendientes`.
        credito_este_vuelo = [d for d in guias_por_vuelo_real.get(ts_iso, []) if d["n_guia"] not in pendientes]

        n_podria = len(pendientes) + len(credito_este_vuelo)
        kg_podria = round(sum(pendientes.values()) + sum(d["peso"] or 0 for d in credito_este_vuelo), 1)
        ingreso = ingreso_por_vuelo[ts_iso]

        resultado.append({
            "ts": ts_iso,
            "awb": v.get("awb", ""),
            "aerolinea": v.get("aerolinea", ""),
            "n_ingreso": ingreso["n"],
            "kg_ingreso": round(ingreso["kg"], 1),
            "n_podria": n_podria,
            "kg_podria": kg_podria,
        })

        # sacar de la cola a TODAS las guias que ya salieron por cualquier
        # canal hasta este punto (vuelo regular O carga) -- no solo las que
        # volaron en ESTE vuelo puntual.
        resueltas = [
            ng for ng in pendientes
            if guia_por_id[ng]["despacho_cualquiera"] and guia_por_id[ng]["despacho_cualquiera"] <= ts_iso
        ]
        for ng in resueltas:
            del pendientes[ng]

    return resultado


def _calcular_capacidad_por_periodo(detalle, vuelos, clave_fn, nombre_clave):
    """Capacidad agregada por periodo (SEMANA o MES, segun `clave_fn`) --
    simulacion propia, no un rollup del resultado por vuelo. Sumar
    'n_ingreso' de varios vuelos del mismo periodo es correcto (aditivo),
    pero 'n_podria' es un STOCK (tamano de cola en un instante), no un
    FLUJO -- ni sumarlo entre vuelos del mismo periodo (cuenta la misma
    guia esperando varias veces) ni tomar el maximo puntual (da promedio
    bajo, %uso pasa de 100% de forma incoherente) representa bien "cuantas
    guias distintas podrian haber volado". La forma correcta es tratar el
    periodo completo como un solo checkpoint: la cola se mide una vez,
    justo antes del ULTIMO vuelo del periodo (incluye a todas las que ya
    entraron en vuelos anteriores del mismo periodo, mas las que siguen
    esperando), y se descuentan de una sola vez todas las que volaron en
    CUALQUIER vuelo de ese periodo.

    Invariante (igual que calcular_capacidad_vuelos()): podria >= ingreso
    siempre -- las guias "caso credito" (broto -- por cualquier canal --
    ANTES de quedar "lista", confirmado por Jorge que si pueden volar sin
    haber pagado) que quedan fuera de la cola persistente igual se suman
    al 'podria' del periodo en que efectivamente volaron, sin persistir en
    la cola hacia periodos futuros.

    Mismo fix que calcular_capacidad_vuelos() (2026-09-01, 2da vuelta): la
    cola usa `despacho_cualquiera` (no `vuelo_real`) para decidir cuando
    una guia deja de estar "esperando" -- una guia despachada por carga
    (1 sola guia, excluida del calendario de vuelos regulares) sale de la
    cola igual, aunque no cuente como `ingreso` de ningun vuelo regular.
    Sin esto, la carga (a veces flete pesado) quedaba fantasma en la cola
    para siempre e inflaba kg_podria sin limite.

    clave_fn(datetime) -> clave de periodo (comparable/ordenable).
    nombre_clave: nombre del campo de salida para esa clave (ej. "semana"
    o "mes")."""
    ingreso_por_vuelo = defaultdict(lambda: {"n": 0, "kg": 0.0})
    guias_por_vuelo_real = defaultdict(list)
    for d in detalle:
        if d["vuelo_real"]:
            b = ingreso_por_vuelo[d["vuelo_real"]]
            b["n"] += 1
            b["kg"] += d["peso"] or 0
            guias_por_vuelo_real[d["vuelo_real"]].append(d)

    periodos_vuelos = {}
    for v in vuelos:
        clave = clave_fn(v["ts"])
        periodos_vuelos.setdefault(clave, []).append(v)

    guia_por_id = {d["n_guia"]: d for d in detalle}
    guias_por_lista = sorted(detalle, key=lambda d: d["fecha_lista"])
    ptr = 0
    n_total = len(guias_por_lista)
    pendientes = {}

    resultado = []
    for clave in sorted(periodos_vuelos.keys()):
        vuelos_periodo = periodos_vuelos[clave]
        ts_final = max(v["ts"] for v in vuelos_periodo)
        while ptr < n_total and datetime.fromisoformat(guias_por_lista[ptr]["fecha_lista"]) <= ts_final:
            d = guias_por_lista[ptr]
            ptr += 1
            desp = d["despacho_cualquiera"]
            if desp and desp < d["fecha_lista"]:
                continue
            pendientes[d["n_guia"]] = d["peso"] or 0

        # guias "caso credito" que vuelan en ALGUN vuelo de este periodo
        # pero quedaron fuera de la cola persistente -- se suman aqui para
        # no romper el invariante podria >= ingreso.
        credito_este_periodo = [
            d for v in vuelos_periodo
            for d in guias_por_vuelo_real.get(v["ts"].isoformat(), [])
            if d["n_guia"] not in pendientes
        ]

        n_podria = len(pendientes) + len(credito_este_periodo)
        kg_podria = round(sum(pendientes.values()) + sum(d["peso"] or 0 for d in credito_este_periodo), 1)
        n_ingreso = sum(ingreso_por_vuelo[v["ts"].isoformat()]["n"] for v in vuelos_periodo)
        kg_ingreso = round(sum(ingreso_por_vuelo[v["ts"].isoformat()]["kg"] for v in vuelos_periodo), 1)

        resultado.append({
            nombre_clave: clave,
            "ts_final": ts_final.isoformat(),
            "n_vuelos": len(vuelos_periodo),
            "n_ingreso": n_ingreso,
            "kg_ingreso": kg_ingreso,
            "n_podria": n_podria,
            "kg_podria": kg_podria,
        })

        # sacar de la cola a TODAS las guias que ya salieron por cualquier
        # canal hasta el final de este periodo (vuelo regular O carga).
        ts_final_iso = ts_final.isoformat()
        resueltas = [
            ng for ng in pendientes
            if guia_por_id[ng]["despacho_cualquiera"] and guia_por_id[ng]["despacho_cualquiera"] <= ts_final_iso
        ]
        for ng in resueltas:
            del pendientes[ng]

    return resultado


def calcular_capacidad_semanal(detalle, vuelos):
    return _calcular_capacidad_por_periodo(
        detalle, vuelos, lambda ts: lunes_de_semana(ts).isoformat(), "semana"
    )


def calcular_capacidad_mensual(detalle, vuelos):
    return _calcular_capacidad_por_periodo(
        detalle, vuelos, lambda ts: f"{ts.year}-{ts.month:02d}", "mes"
    )


def _pct_at(vals, p):
    v = sorted(x for x in vals if x is not None)
    return round(v[min(len(v) - 1, int(len(v) * p))], 1) if v else None


def _resumen_friccion_consolidacion(detalle):
    """Cuantifica el efecto de la friccion de consolidacion sobre el
    cumplimiento de vuelos (pedido de Jorge, T-0006: volver cuantitativa la
    info del correo de consolidaciones). Compara, sobre ANIO_REPORTE:
      - la tasa de "no volo en su vuelo exacto" de guias-bulto vs individuales
        (para ver si, tras el fix de corte de manifiesto, todavia hay brecha);
      - de las guias-bulto afectadas, cuantas tienen cada senal de friccion
        (factura pendiente al cerrar el bulto / armado lento), y si esas
        senales aparecen mas seguido que en el grupo de control (las que SI
        volaron a tiempo) -- si la tasa es parecida, la senal NO discrimina;
      - el efecto del criterio "neto" (descontar solo las de factura pendiente).
    Alimenta Conclusiones (punto 3) y da el contexto para los filtros nuevos de
    la pestaña Guias afectadas."""
    en_anio = lambda d: datetime.fromisoformat(d["vuelo_esperado"]).year == ANIO_REPORTE
    cons = [d for d in detalle if d["consolidada"] and en_anio(d)]
    indiv = [d for d in detalle if not d["consolidada"] and en_anio(d)]
    afect = [d for d in cons if d["no_volo_estricto"]]
    ok = [d for d in cons if not d["no_volo_estricto"] and d["vuelo_real"]]

    def tasa(rows):
        a = sum(1 for d in rows if d["no_volo_estricto"])
        return {"evaluables": len(rows), "afectadas": a,
                "pct": round(a / len(rows) * 100, 1) if rows else 0}

    def rate_senal(rows, pred):
        m = [d for d in rows if pred(d)]
        return {"n": len(m), "pct": round(len(m) / len(rows) * 100, 1) if rows else 0}

    es_lento = lambda d: d["armado_lag_dias"] is not None and d["armado_lag_dias"] > UMBRAL_ARMADO_LENTO_DIAS
    por_mes = {}
    for d in afect:
        mo = datetime.fromisoformat(d["vuelo_esperado"]).strftime("%Y-%m")
        b = por_mes.setdefault(mo, {"total": 0, "factura_pendiente": 0, "armado_lento": 0})
        b["total"] += 1
        if d["cons_friccion"]:
            b[d["cons_friccion"]] += 1

    neto_afect = sum(1 for d in cons if d["no_volo_neto_consolidacion"])
    return {
        "umbral_armado_lento_dias": UMBRAL_ARMADO_LENTO_DIAS,
        "tasa_consolidadas": tasa(cons),
        "tasa_individuales": tasa(indiv),
        "tasa_consolidadas_neto": {
            "evaluables": len(cons), "afectadas": neto_afect,
            "pct": round(neto_afect / len(cons) * 100, 1) if cons else 0,
        },
        "afectadas_con_factura_pendiente": rate_senal(afect, lambda d: d["cons_friccion"] == "factura_pendiente"),
        "afectadas_con_armado_lento": rate_senal(afect, es_lento),
        # grupo de control: mismas senales entre las guias-bulto que SI
        # volaron a tiempo. Si el pct es parecido al de las afectadas, la
        # senal no predice el atraso.
        "control_con_factura_pendiente": rate_senal(ok, lambda d: d["cons_fob_cero"]),
        "control_con_armado_lento": rate_senal(ok, es_lento),
        "por_mes": dict(sorted(por_mes.items())),
    }


def main():
    now_utc = datetime.now(timezone.utc)
    print(f"Descargando ebox_cumplimiento desde {FECHA_DESDE}...")
    where = f"(fecha_ingreso,ge,exactDate,{FECHA_DESDE})"
    filas = noco_fetch_all(TBL_CUMPLIMIENTO, where=where, fields=FIELDS)
    print(f"  {len(filas)} guias descargadas")

    print(f"Descargando peso (guia_hijas) desde {FECHA_DESDE}...")
    filas_peso = noco_fetch_all(
        TBL_GUIA_HIJAS,
        where=f"(fecha,ge,exactDate,{FECHA_DESDE})",
        fields=FIELDS_GUIA_HIJAS,
    )
    peso_por_guia = {str(r.get("n_guia")): (r.get("peso") or 0) for r in filas_peso}
    # consolidacion > 0 => esta guia es el resultado de FUNDIR varias guias
    # originales en una sola (bodega), no una guia individual normal. El valor
    # es el id del registro en la tabla `consolidaciones` (se conserva para
    # enlazarlo mas abajo, no solo el booleano).
    consolidacion_id_por_guia = {str(r.get("n_guia")): (r.get("consolidacion") or -1) for r in filas_peso}
    consolidada_por_guia = {ng: (cid > 0) for ng, cid in consolidacion_id_por_guia.items()}
    convenio_por_guia = {str(r.get("n_guia")): (r.get("v_codigo_convenio") or "") for r in filas_peso}
    print(f"  {len(peso_por_guia)} pesos descargados ({sum(consolidada_por_guia.values())} son guias de consolidacion)")

    # Registro de cada bulto consolidado (tabla `consolidaciones`). Se trae un
    # colchon mas amplio hacia atras porque una guia-bulto de inicios de enero
    # puede enlazar a una consolidacion creada en diciembre.
    print("Descargando consolidaciones (registro del bulto armado)...")
    filas_cons = noco_fetch_all(
        TBL_CONSOLIDACIONES,
        where="(fecha,ge,exactDate,2025-11-01)",
        fields="id,fob,fecha,peso,estado,consolidaciones_guias",
    )
    cons_info = {
        r["id"]: {
            "fob": r.get("fob"),
            "fecha": parse_dt(r.get("fecha")),
            "n_guias": r.get("consolidaciones_guias") or 0,
            "estado": r.get("estado"),
        }
        for r in filas_cons
        if r.get("id") is not None
    }
    n_fob0 = sum(1 for c in cons_info.values() if (c["fob"] or 0) == 0)
    print(f"  {len(cons_info)} consolidaciones descargadas ({n_fob0} con FOB 0 = factura pendiente al cerrar el bulto)")

    print("Descargando guia_madres (vuelos/AWB reales)...")
    filas_madres = noco_fetch_all(TBL_GUIA_MADRES, fields=FIELDS_GUIA_MADRES)
    madres_info = {
        r["id"]: {
            "awb": r.get("awb") or "",
            "aerolinea": r.get("flight_number") or "",
            "tipo_transporte": r.get("tipo_transporte") or "",
            "items": r.get("items") or 0,
        }
        for r in filas_madres
        if r.get("id") is not None
    }
    print(f"  {len(madres_info)} guia_madres descargados")

    print("Cruzando guias con su guia_madre real (tabla de union)...")
    mapa_guia_madre = fetch_mapa_guia_madre(madres_info.keys())
    print(f"  {len(mapa_guia_madre)} guias con guia_madre resuelta")

    guias = []
    for r in filas:
        n_guia = r.get("n_guia")
        id_madre = mapa_guia_madre.get(str(n_guia))
        madre = madres_info.get(id_madre)
        # Vuelo "dedicado" (fuera de alcance de este analisis): CARGA (canal
        # de envio distinto), O un guia_madre con 1 sola guia en total --
        # sea CARGA o COURIER, un guia_madre de 1 guia se crea y asigna
        # especialmente para ESA guia, nunca hubo un vuelo regular
        # compartido al que tuviera que subirse (pedido de Jorge,
        # 2026-09-02, ver "Correccion de fondo (2)" en el docstring).
        es_vuelo_dedicado = madre is not None and (madre["tipo_transporte"] == "CARGA" or madre["items"] == 1)
        cons_id = consolidacion_id_por_guia.get(str(n_guia), -1)
        cons = cons_info.get(cons_id) if cons_id and cons_id > 0 else None
        guias.append({
            "n_guia": n_guia,
            "casilla": r.get("casilla"),
            "peso": peso_por_guia.get(str(n_guia), 0),
            "consolidada": consolidada_por_guia.get(str(n_guia), False),
            "cons_id": cons_id if cons_id and cons_id > 0 else None,
            "cons_fob": (cons["fob"] if cons else None),
            "cons_fob_cero": (cons is not None and (cons["fob"] or 0) == 0),
            "cons_n_guias": (cons["n_guias"] if cons else None),
            "cons_fecha": (cons["fecha"] if cons else None),
            "convenio": convenio_por_guia.get(str(n_guia), ""),
            "pago": parse_dt(r.get("fecha_primer_pago")),
            "factura": parse_dt(r.get("fecha_miami_con_factura")),
            "asignado": parse_dt(r.get("fecha_asignado_guia_madre")),
            "despacho": parse_dt(r.get("fecha_despachado_aeropuerto")),
            "id_guia_madre": id_madre,
            "awb": madre["awb"] if madre else None,
            "aerolinea": madre["aerolinea"] if madre else None,
            "es_vuelo_dedicado": es_vuelo_dedicado,
        })

    # --- 1. Calendario real de vuelos: cada guia_madre distinto con
    # tipo_transporte != CARGA es un vuelo (ver docstring "Correccion de
    # fondo" arriba) -- ya no se clusteriza por tiempo. Su ts = MIN(despacho)
    # de sus guias miembro que ya despacharon.
    n_dedicadas_excluidas = sum(1 for g in guias if g["es_vuelo_dedicado"])
    por_madre = defaultdict(list)
    for g in guias:
        if g["id_guia_madre"] is not None and not g["es_vuelo_dedicado"]:
            por_madre[g["id_guia_madre"]].append(g)

    vuelos = []
    vuelo_ts_por_madre = {}
    for id_madre, miembros in por_madre.items():
        despachos = [m["despacho"] for m in miembros if m["despacho"]]
        if not despachos:
            continue  # guia_madre aun no ha despachado -- todavia no es un vuelo del calendario
        ts = min(despachos)
        info = madres_info[id_madre]
        vuelos.append({"ts": ts, "n_guias": len(despachos), "awb": info["awb"], "aerolinea": info["aerolinea"]})
        vuelo_ts_por_madre[id_madre] = ts
    vuelos.sort(key=lambda v: v["ts"])

    print(f"\nGuias excluidas por vuelo dedicado (CARGA, o guia_madre de 1 sola guia): {n_dedicadas_excluidas}")
    print(f"Vuelos regulares en el calendario (via guia_madre real): {len(vuelos)}")
    if vuelos:
        print(f"  Primero: {vuelos[0]['ts']}  Ultimo: {vuelos[-1]['ts']}")

    vuelos_ts = [v["ts"] for v in vuelos]

    def primer_vuelo_desde(fecha_lista):
        # Primer vuelo del calendario con ts >= fecha_lista, respetando el
        # corte de manifiesto (busqueda lineal ordenada; volumen bajo,
        # ~90-150 vuelos, no hace falta bisect). Si fecha_lista cae el MISMO
        # dia calendario de un vuelo pero a las CORTE_MANIFIESTO_HORA (12:00)
        # o despues, ese vuelo no cuenta -- operaciones ya no alcanza a
        # validar el pago para ese manifiesto, aunque el despacho fisico sea
        # mas tarde ese mismo dia. Se sigue buscando el vuelo siguiente
        # (ejemplo de Jorge, 2026-09-02: factura sube viernes, pago llega
        # viernes 14:00 -> queda para el miercoles siguiente, no para el
        # vuelo del viernes aunque ese vuelo despache en la tarde).
        for ts in vuelos_ts:
            if ts < fecha_lista:
                continue
            if ts.date() == fecha_lista.date() and fecha_lista.hour >= CORTE_MANIFIESTO_HORA:
                continue  # mismo dia del vuelo, pero paso el corte de manifiesto
            return ts
        return None

    # --- 2. Por guia: fecha en que quedo lista, vuelo correspondiente,
    # vuelo real, y si "no volo en su primer vuelo".
    detalle = []
    for g in guias:
        if g["es_vuelo_dedicado"]:
            continue  # CARGA, o guia_madre de 1 sola guia -- fuera de alcance, ver docstring "Correccion de fondo (2)"
        if not g["pago"] or not g["factura"]:
            continue  # nunca quedo lista (falta pago o factura) -- fuera de alcance
        fecha_lista = max(g["pago"], g["factura"])
        esperado_ts = primer_vuelo_desde(fecha_lista)
        if esperado_ts is None:
            continue  # su primer vuelo posible todavia no ha ocurrido -- pendiente, no evaluable aun

        # real_ts = ts del vuelo (guia_madre) al que esta guia esta asociada,
        # si ese guia_madre ya despacho. None si todavia esta esperando (su
        # guia_madre no ha volado) o si nunca fue asignada a uno.
        real_ts = vuelo_ts_por_madre.get(g["id_guia_madre"])

        # Ojo: clientes con credito SI pueden volar sin haber pagado
        # (confirmado por Jorge, 2026-09-01 -- ebox_cumplimiento.con_credito
        # marca estos casos) -- el pago se registra despues del envio, no
        # antes, asi que real_ts puede quedar ANTES de fecha_lista/esperado.
        # Eso no es "perdio su vuelo", es que broto antes de que el pago
        # quedara registrado en el sistema. Solo cuenta como incidente si
        # broto DESPUES del vuelo que le correspondia, o si todavia no ha
        # brotado y ese vuelo ya paso.
        #
        # Pedido de Jorge (2026-09-01, 5ta iteracion): ademas, para contar
        # como "afectada" la guia tiene que haber pasado efectivamente por
        # el estado "Asociado a Guia Madre" (fecha_asignado_guia_madre no
        # nula) -- eso confirma que de verdad quedo en cola para otro vuelo
        # posterior, y no que nunca se proceso (ej. pedido anulado/dado de
        # baja antes de llegar a esa etapa). Se encontraron 5 casos asi
        # (guias "DAR DE BAJA"/"Nula" sin fecha_asignado_guia_madre) que
        # antes se contaban como "nunca volo" sin serlo realmente.
        alcanzo_asignacion = g["asignado"] is not None
        no_volo_estricto = alcanzo_asignacion and ((real_ts is None) or (real_ts > esperado_ts))
        # Definicion "semana": mas permisiva -- no es incidente si broto en
        # otro vuelo dentro de la MISMA semana calendario del esperado.
        no_volo_semana = alcanzo_asignacion and ((real_ts is None) or (
            real_ts > esperado_ts and lunes_de_semana(real_ts) != lunes_de_semana(esperado_ts)
        ))

        # --- Senales cuantitativas para clasificar el atraso ---
        # margen_horas: cuanto tiempo tuvo la guia entre quedar "lista" y la
        # salida del vuelo que le correspondia. Negativo si quedo lista DESPUES
        # de que ese vuelo ya habia salido (caso credito, o cierre muy tardio).
        margen_horas = round((esperado_ts - fecha_lista).total_seconds() / 3600, 1)
        # armado_lag_dias (solo guias-bulto): dias entre que se creo el
        # registro de la consolidacion y que la guia-bulto quedo "lista"
        # (pago + factura). Un lag alto = el bulto se armo pero la factura/el
        # pago se resolvieron mucho despues (goteo de facturas / bulto
        # re-armado -- documentado en el correo).
        armado_lag_dias = None
        if g["consolidada"] and g["cons_fecha"] is not None:
            armado_lag_dias = round((fecha_lista - g["cons_fecha"]).total_seconds() / 86400, 1)
        # vuelos_saltados: cuantos vuelos del calendario salieron entre el
        # esperado (incluido) y el real (excluido), o hasta ahora si no ha
        # volado. Parte en >=1 para las afectadas (el propio esperado cuenta
        # como saltado porque no se subio a el).
        limite_dt = real_ts or now_utc
        vuelos_saltados = sum(1 for ts in vuelos_ts if esperado_ts <= ts < limite_dt)

        # --- Friccion de consolidacion (2026-09-02, T-0006) ---
        # Etiqueta descriptiva para las guias-bulto: senala si el atraso pudo
        # generarse aguas arriba, en el propio proceso de consolidacion
        # (coordinacion por correo + goteo de facturas + re-armado del bulto,
        # documentado en CONSOLIDACIONES_CORREO.md), en vez de en la operacion
        # de vuelo:
        #   "factura_pendiente": la consolidacion se cerro con FOB 0 = habia al
        #       menos una factura sin cargar al armar el bulto -> la fecha
        #       "lista" (que exige factura en Miami) quedo tironeada por eso.
        #       Es la unica senal que se usa para el criterio "neto" de abajo:
        #       limpia y sin ambiguedad (es un dato de sistema, no una
        #       heuristica de tiempo).
        #   "armado_lento": entre crear el registro del bulto y quedar "lista"
        #       pasaron > UMBRAL_ARMADO_LENTO_DIAS. NOTA: en los datos esto NO
        #       discrimina (aparece en ~21% de las guias-bulto que SI volaron a
        #       tiempo y en ~25% de las afectadas) -- por eso queda solo como
        #       FILTRO exploratorio en la pestaña Guias afectadas, NO entra al
        #       criterio "neto".
        #   "": ninguna de las dos.
        # El margen al vuelo tampoco se usa: el grupo de control mostro que las
        # guias-bulto que vuelan a tiempo tambien tienen margenes bajos
        # (mediana ~27 h despues del fix de corte de manifiesto) -- no discrimina.
        if not g["consolidada"]:
            cons_friccion = ""
        elif g["cons_fob_cero"]:
            cons_friccion = "factura_pendiente"
        elif armado_lag_dias is not None and armado_lag_dias > UMBRAL_ARMADO_LENTO_DIAS:
            cons_friccion = "armado_lento"
        else:
            cons_friccion = ""

        # "neto de consolidacion": criterio "vuelo exacto" descontando solo las
        # guias-bulto cuyo atraso se explica por factura pendiente al cerrar el
        # bulto (FOB 0). Ajuste chico y defendible -- NO descuenta "armado
        # lento" (no discrimina). Para guias individuales es identico a estricto.
        no_volo_neto_consolidacion = no_volo_estricto and not (
            g["consolidada"] and no_volo_estricto and g["cons_fob_cero"]
        )

        clase_atraso = "consolidada" if g["consolidada"] else "individual"

        detalle.append({
            "n_guia": g["n_guia"],
            "casilla": g["casilla"],
            "peso": g["peso"],
            "consolidada": g["consolidada"],
            "cons_id": g["cons_id"],
            "cons_fob": g["cons_fob"],
            "cons_fob_cero": g["cons_fob_cero"],
            "cons_n_guias": g["cons_n_guias"],
            "margen_horas": margen_horas,
            "armado_lag_dias": armado_lag_dias,
            "vuelos_saltados": vuelos_saltados,
            "clase_atraso": clase_atraso,
            "cons_friccion": cons_friccion,
            "convenio": g["convenio"],
            "fecha_lista": fecha_lista.isoformat(),
            "fecha_asignado_guia_madre": g["asignado"].isoformat() if g["asignado"] else None,
            "vuelo_esperado": esperado_ts.isoformat(),
            "vuelo_real": real_ts.isoformat() if real_ts else None,
            "awb": g["awb"],
            "aerolinea": g["aerolinea"],
            # despacho propio de la guia (== vuelo_real cuando ya volo, dado
            # que las guias CARGA ahora se excluyen ANTES de llegar aca --
            # ver el "continue" de arriba). Se conserva este campo separado
            # (en vez de reusar vuelo_real) porque calcular_capacidad_vuelos()
            # / _calcular_capacidad_por_periodo() lo usan explicitamente para
            # decidir cuando sacar una guia de la cola de "podria"; hasta
            # 2026-09-01 esto era necesario para blindarse de guias CARGA
            # fantasma en la cola (ya no pueden ocurrir, se excluyen antes),
            # pero se deja igual como respaldo -- no cambia el resultado.
            "despacho_cualquiera": g["despacho"].isoformat() if g["despacho"] else None,
            "no_volo_estricto": no_volo_estricto,
            "no_volo_semana": no_volo_semana,
            "no_volo_neto_consolidacion": no_volo_neto_consolidacion,
        })

    # --- 2b. Lag de asignacion: horas entre "lista para volar" y
    # fecha_asignado_guia_madre, por mes de fecha_lista. Soporta la
    # conclusion "se alargo el tiempo de asignacion a guia madre".
    lag_por_mes = defaultdict(list)
    for g in guias:
        if not g["pago"] or not g["factura"] or not g["asignado"]:
            continue
        fecha_lista = max(g["pago"], g["factura"])
        if g["asignado"] < fecha_lista:
            continue  # dato raro (asignado antes de quedar "lista"), se ignora
        lag_horas = (g["asignado"] - fecha_lista).total_seconds() / 3600
        mo = f"{fecha_lista.year}-{fecha_lista.month:02d}"
        lag_por_mes[mo].append(lag_horas)

    lag_resumen_por_mes = {}
    for mo, vals in sorted(lag_por_mes.items()):
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        lag_resumen_por_mes[mo] = {
            "n": n,
            "mediana_horas": round(statistics.median(vals_sorted), 1),
            "p90_horas": round(vals_sorted[int(n * 0.9)], 1) if n else 0,
        }

    print(f"Guias evaluables (con pago+factura y con vuelo correspondiente ya ocurrido): {len(detalle)}")
    inc_estricto = [d for d in detalle if d["no_volo_estricto"]]
    inc_semana = [d for d in detalle if d["no_volo_semana"]]
    print(f"No volaron en su vuelo EXACTO correspondiente: {len(inc_estricto)} ({len(inc_estricto)/len(detalle)*100:.1f}%)")
    print(f"No volaron dentro de la SEMANA de su vuelo correspondiente: {len(inc_semana)} ({len(inc_semana)/len(detalle)*100:.1f}%)")
    _fr = _resumen_friccion_consolidacion(detalle)
    print(
        f"Friccion consolidacion ({ANIO_REPORTE}): consolidadas "
        f"{_fr['tasa_consolidadas']['pct']}% vs individuales {_fr['tasa_individuales']['pct']}% "
        f"| neto (sin factura pendiente) {_fr['tasa_consolidadas_neto']['pct']}%"
    )
    print(
        f"  senales en afectadas vs control -- factura pendiente: "
        f"{_fr['afectadas_con_factura_pendiente']['pct']}% vs {_fr['control_con_factura_pendiente']['pct']}% | "
        f"armado lento (>{UMBRAL_ARMADO_LENTO_DIAS}d): "
        f"{_fr['afectadas_con_armado_lento']['pct']}% vs {_fr['control_con_armado_lento']['pct']}%"
    )

    def bloque_definicion(flag_key, poblacion_filtro=None):
        """Arma el bloque de salida (totales, agregados semana/mes, detalle)
        para una definicion de incidente (flag_key = 'no_volo_estricto' o
        'no_volo_semana').

        poblacion_filtro: None = todas las guias (individuales +
        consolidadas, comportamiento original); True = solo consolidadas;
        False = solo individuales. Jorge pidio (2026-09-01) que el reporte
        principal ("Vuelo exacto"/"Misma semana") deje de mezclarlas -- las
        guias consolidadas tienen un patron de espera distinto por
        naturaleza (ver docstring del modulo) y ahora viven en su propia
        pestaña "Consolidadas", separada de "el caso" principal."""
        base = detalle if poblacion_filtro is None else [
            d for d in detalle if d["consolidada"] == poblacion_filtro
        ]
        incidentes = [d for d in base if d[flag_key]]
        semanas = defaultdict(lambda: {"evaluables": 0, "incidentes": 0, "kilos": 0.0, "kilos_evaluables": 0.0, "_casillas": set()})
        meses = defaultdict(lambda: {"evaluables": 0, "incidentes": 0, "kilos": 0.0, "kilos_evaluables": 0.0, "_casillas": set()})
        # split individuales/consolidadas por mes, solo evaluables+incidentes+pct
        # (soporta la conclusion "la consolidacion no explica el patron
        # abril-junio" -- ver docstring)
        poblacion_por_mes = defaultdict(lambda: {
            "individuales": {"evaluables": 0, "incidentes": 0},
            "consolidadas": {"evaluables": 0, "incidentes": 0},
        })

        for d in base:
            esperado = datetime.fromisoformat(d["vuelo_esperado"])
            if esperado.year != ANIO_REPORTE:
                continue
            wk_key = lunes_de_semana(esperado).isoformat()
            mo_key = f"{esperado.year}-{esperado.month:02d}"
            semanas[wk_key]["evaluables"] += 1
            semanas[wk_key]["kilos_evaluables"] += d["peso"] or 0
            meses[mo_key]["evaluables"] += 1
            meses[mo_key]["kilos_evaluables"] += d["peso"] or 0
            pob_key = "consolidadas" if d["consolidada"] else "individuales"
            poblacion_por_mes[mo_key][pob_key]["evaluables"] += 1
            if d[flag_key]:
                semanas[wk_key]["incidentes"] += 1
                semanas[wk_key]["kilos"] += d["peso"] or 0
                semanas[wk_key]["_casillas"].add(d["casilla"])
                meses[mo_key]["incidentes"] += 1
                meses[mo_key]["kilos"] += d["peso"] or 0
                meses[mo_key]["_casillas"].add(d["casilla"])
                poblacion_por_mes[mo_key][pob_key]["incidentes"] += 1

        def cerrar(bucket):
            out = {}
            for k, v in sorted(bucket.items()):
                out[k] = {
                    "evaluables": v["evaluables"],
                    "incidentes": v["incidentes"],
                    "pct": round(v["incidentes"] / v["evaluables"] * 100, 1) if v["evaluables"] else 0,
                    "kilos": round(v["kilos"], 1),
                    "kilos_evaluables": round(v["kilos_evaluables"], 1),
                    "pct_kilos": round(v["kilos"] / v["kilos_evaluables"] * 100, 1) if v["kilos_evaluables"] else 0,
                    "clientes": len(v["_casillas"]),
                }
            return out

        def cerrar_poblacion(bucket):
            out = {}
            for mo, v in sorted(bucket.items()):
                fila = {}
                for pob in ("individuales", "consolidadas"):
                    ev, inc = v[pob]["evaluables"], v[pob]["incidentes"]
                    fila[pob] = {
                        "evaluables": ev,
                        "incidentes": inc,
                        "pct": round(inc / ev * 100, 1) if ev else 0,
                    }
                out[mo] = fila
            return out

        incidentes_2026 = [
            d for d in incidentes if datetime.fromisoformat(d["vuelo_esperado"]).year == ANIO_REPORTE
        ]
        # base completa (todas las evaluables de esta poblacion, afectadas o
        # no) restringida a ANIO_REPORTE -- da el denominador de referencia
        # para los KPIs ("284 de 1.081", no solo "284"). Pedido de Jorge,
        # 2026-09-01.
        base_2026 = [
            d for d in base if datetime.fromisoformat(d["vuelo_esperado"]).year == ANIO_REPORTE
        ]
        return {
            "total_incidentes": len(incidentes_2026),
            "total_kilos": round(sum(d["peso"] or 0 for d in incidentes_2026), 1),
            "total_clientes": len(set(d["casilla"] for d in incidentes_2026)),
            "total_evaluables": len(base_2026),
            "total_kilos_evaluables": round(sum(d["peso"] or 0 for d in base_2026), 1),
            "total_clientes_evaluables": len(set(d["casilla"] for d in base_2026)),
            "por_semana": cerrar(semanas),
            "por_mes": cerrar(meses),
            "por_mes_poblacion": cerrar_poblacion(poblacion_por_mes),
            "detalle_incidentes": sorted(
                [
                    {
                        k: v for k, v in d.items()
                        if k not in ("no_volo_estricto", "no_volo_semana", "no_volo_neto_consolidacion")
                    }
                    for d in incidentes_2026
                ],
                key=lambda d: d["vuelo_esperado"],
            ),
        }

    print("Calculando capacidad por vuelo (tope ingresado vs cola disponible)...")
    capacidad_vuelos = calcular_capacidad_vuelos(detalle, vuelos)
    capacidad_semanal = calcular_capacidad_semanal(detalle, vuelos)
    capacidad_mensual = calcular_capacidad_mensual(detalle, vuelos)

    salida = {
        # UTC explicito (no datetime.now() naive) -- el pipeline corre a veces
        # local (hora Chile) y a veces en GitHub Actions (hora UTC del
        # runner); si se guarda naive, "generado" significa cosas distintas
        # segun donde corrio, lo que rompe la comparacion "es de hoy" del
        # badge de actualizacion en el dashboard (2026-09-03). Con tz UTC
        # explicito, el navegador del que mira el reporte lo convierte solo
        # a su hora local via `new Date(iso)`.
        "generado": datetime.now(timezone.utc).isoformat(),
        "anio_reporte": ANIO_REPORTE,
        "fecha_desde_colchon": FECHA_DESDE,
        "total_vuelos_calendario": len(vuelos),
        "vuelos_calendario": [
            {"ts": v["ts"].isoformat(), "n_guias": v["n_guias"], "awb": v["awb"], "aerolinea": v["aerolinea"]}
            for v in vuelos
        ],
        "capacidad_por_vuelo": [
            c for c in capacidad_vuelos if datetime.fromisoformat(c["ts"]).year == ANIO_REPORTE
        ],
        "capacidad_por_semana": [
            {k: v for k, v in c.items() if k != "ts_final"}
            for c in capacidad_semanal if datetime.fromisoformat(c["ts_final"]).year == ANIO_REPORTE
        ],
        "capacidad_por_mes": [
            {k: v for k, v in c.items() if k != "ts_final"}
            for c in capacidad_mensual if datetime.fromisoformat(c["ts_final"]).year == ANIO_REPORTE
        ],
        "total_guias_evaluables": len(detalle),
        # Universo COMPLETO evaluable de 2026 (individuales + consolidadas
        # mezcladas, afectadas Y no afectadas) -- NO es un rollup de
        # incidentes. Pedido de Jorge (2026-09-03): en "Guias afectadas"
        # quiere el denominador real de cada filtro (ej. "36 de 300 guias",
        # no solo "36"), y eso exige saber cuantas guias evaluables (con o
        # sin incidente) caen en cada combinacion de filtros -- imposible de
        # sacar solo de `detalle_incidentes` (que ya viene pre-filtrado a
        # incidentes). Mismos campos que necesita build_guias_afectadas()
        # para clasificar cada fila por mes/ejecutiva/convenio/poblacion/
        # tamaño/fricción, mas los dos flags de incidente (para que el
        # frontend sepa, sin recalcular nada, si esa guia es "afectada" bajo
        # cada criterio).
        "universo_evaluable_2026": [
            {
                k: d[k] for k in (
                    "n_guia", "casilla", "peso", "consolidada", "cons_id",
                    "cons_n_guias", "cons_friccion", "armado_lag_dias",
                    "convenio", "vuelo_esperado", "vuelo_real", "awb",
                    "aerolinea", "no_volo_estricto", "no_volo_semana",
                )
            }
            for d in detalle
            if datetime.fromisoformat(d["vuelo_esperado"]).year == ANIO_REPORTE
        ],
        "lag_asignacion_por_mes": lag_resumen_por_mes,
        # "estricto"/"semana" = TODAS las guias (individuales + consolidadas
        # mezcladas) -- se conservan para calculos que si necesitan el total
        # (ej. capacidad de vuelos en la pestaña Conclusiones). El reporte
        # principal (pestañas del dashboard) usa "individuales"; las
        # consolidadas viven en su propia pestaña -- ver bloque_definicion().
        "estricto": bloque_definicion("no_volo_estricto"),
        "semana": bloque_definicion("no_volo_semana"),
        "individuales": {
            "estricto": bloque_definicion("no_volo_estricto", poblacion_filtro=False),
            "semana": bloque_definicion("no_volo_semana", poblacion_filtro=False),
        },
        "consolidadas": {
            "estricto": bloque_definicion("no_volo_estricto", poblacion_filtro=True),
            "semana": bloque_definicion("no_volo_semana", poblacion_filtro=True),
            # "neto" (2026-09-02, T-0006): mismo criterio "vuelo exacto" pero
            # descontando SOLO las guias-bulto cuyo atraso se explica por
            # factura pendiente al cerrar el bulto (FOB 0) -- ajuste chico y
            # sin ambiguedad. El "armado lento" NO se descuenta (no discrimina
            # en los datos -- ver consolidadas_friccion.control_*).
            "neto": bloque_definicion("no_volo_neto_consolidacion", poblacion_filtro=True),
        },
        # Cuantificacion del efecto de la friccion de consolidacion sobre el
        # cumplimiento de vuelos -- alimenta la pestaña Conclusiones (punto 3)
        # y da contexto a los filtros nuevos de la pestaña Guias afectadas.
        "consolidadas_friccion": _resumen_friccion_consolidacion(detalle),
    }

    with open("cumplimiento_vuelos.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print("\nGuardado -> cumplimiento_vuelos.json")


if __name__ == "__main__":
    main()
