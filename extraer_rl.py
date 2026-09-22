"""
Reporte de Logistica y Operaciones 2ebox — extractor de datos desde NocoDB.

Trae, para todas las guias con vuelo (2023 -> hoy):
  - los 12 timestamps del funnel de transito (ebox_cumplimiento)
  - el vuelo / AWB / forwarder real de cada guia (guia_madres, via la tabla
    puente M2M guia_hijas<->guia_madres)
  - la unidad de negocio y el peso de cada guia (reporte_rentabilidad.n_guia)

Salida: data/datos_crudos.json  (registros compactos, uno por guia)
        data/meta.json          (forwarders, unidades, rango de fechas, corridas)

Metodologia de costos (confirmado con Jorge, 2026-09-08):
  costo de flete internacional por guia = guia_madres.tarifa_costo (USD/kg)
  * peso de la guia (kg). Costo total del forwarder = suma; costo por kilo =
  suma_costo / suma_peso; costo promedio por guia = suma_costo / n_guias.

Metodologia de venta / margen bruto (confirmado con Jorge, 2026-09-21, guia
  168500 de prueba -- admin muestra "Transporte Internacional" USD 56,43):
  tarifa de venta por guia, en orden de prioridad:
  (1) instrucciones_especiales de guia_hijas trae "TARIFA <n>" a mano (USD/kg
      directo) -- pasa con TODAS las guias de Carga y con algunas Casilla
      especiales. Manda sobre el calculo de abajo cuando existe.
  (2) si no: (guia_hijas.valores.RR.transporte_internacional_usd +
      guia_hijas.valores.HandlingFee convertido a USD via valores.Dolar) /
      peso de la guia. HandlingFee esta incluido a proposito (Jorge: "esta
      bien considerarlo").
  venta_usd (por guia) = tarifa de venta x peso_fact (mismo peso facturable
  que el costo). Margen bruto = venta_usd - costo_flete_usd (o costo_est_usd
  con el switch de estimados); margen % = margen / venta_usd.

Unidad de negocio: se cruza 2ebox_rentabilidad.UnidadNegocio por n_guia, con
  overrides por casilla para Carga/Retail/Netnow (ver clasifica_unidad() mas
  abajo; confirmado contra la tabla NocoDB "UnidadesNegocio", mw38m5vp1umede0).
  Las guias sin match quedan como 'Casilla'.

  OJO -- dos cosas distintas se llaman "Carga" en este dominio:
  (a) guia_madres.tipo_transporte == "CARGA": el AWB del vuelo es de carga
      dedicada (no de pasajeros/courier). SI se incluye en este reporte desde
      2026-09-21 -- antes se excluia por completo y dejaba a los clientes de
      la unidad de negocio Carga (Reuse, Sindal) casi sin guias contadas.
  (b) el flujo de Carga por PALLETS/OTs propio (tablas ebox_carga_rentabilidad
      / cargas / ots) -- un sistema totalmente aparte de guia_hijas/guia_madres,
      que SIGUE fuera de esta version (pendiente, ver docs/SYSTEM_MAP.md).

El token vive hardcodeado como default (mismo criterio que el resto de la
carpeta); si existe la env var NOCO_TOKEN, tiene prioridad.
"""
import json
import math
import os
import re
import statistics
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOCO_TOKEN = os.environ.get("NOCO_TOKEN")
if not NOCO_TOKEN:
    raise SystemExit("Falta la variable de entorno NOCO_TOKEN (secret del repo).")
NOCO_BASE = "pifk61tmzhes073"
NOCO_URL = "https://noco.2ebox.com/api/v1/db/data/noco"

TBL_CUMPLIMIENTO = "m4feao7xeudu8k9"
TBL_GUIA_MADRES = "m5t0y2pg3d0qt7h"
TBL_GUIA_MADRE_HIJAS = "mpwefzshqgun0m7"   # tabla puente M2M (system)
TBL_GUIA_HIJAS = "m4b0yh4lwpxsvri"          # para venta (valores JSON + Instrucciones)
# 2ebox_rentabilidad: 1 fila por guia (mismo universo que ebox_cumplimiento,
# ~58k filas), trae NGuia / UnidadNegocio / Peso y responde rapido por la API
# (el "reporte_rentabilidad" es una vista pesada: ~10s por pagina, no sirve).
TBL_RENTABILIDAD = "m0pibgo29ydt3l1"

FECHA_DESDE = "2023-01-01"
OUT = Path(__file__).parent / "data"

# --- Normalizacion de forwarders ---
# El prefijo del AWB (primeros 3 digitos = prefijo IATA de la aerolinea) es la
# fuente MAS confiable del forwarder -- el campo flight_number viene sucio o
# vacio. Mapa derivado de los datos reales de 2ebox (cruzar awb[:3] con
# flight_number en guia_madres, 2026-09-08). Los prefijos ambiguos (729 tiene
# Avianca + Tampa Cargo; 805 tiene Mercury + Kalitta + LAN) NO se ponen aca y
# caen al fallback por flight_number.
AWB_PREFIX_FW = {
    "045": "LATAM Cargo",
    "230": "Copa",
    "272": "Kalitta",
    "456": "Trans Caribbean",
    "510": "Air Express",
    "605": "SKY",
    "992": "DHL",
}

FORWARDER_ALIASES = {
    "sky": "SKY", "sky airline": "SKY", "sky cargo": "SKY",
    "latam": "LATAM Cargo", "latam cargo": "LATAM Cargo", "lan": "LATAM Cargo",
    "trans caribbean": "Trans Caribbean", "trans caribean": "Trans Caribbean",
    "trans caribbean -dhl": "Trans Caribbean", "transcaribbean": "Trans Caribbean",
    "mercury": "Mercury",
    "avianca": "Avianca", "avianca cargo": "Avianca",
    "kalitta": "Kalitta", "kalitta air": "Kalitta", "kalita": "Kalitta",
    "tampa cargo": "Tampa Cargo", "tampa": "Tampa Cargo",
    "air express": "Air Express", "air express s.a.": "Air Express",
    "air express sa": "Air Express",
    "copa": "Copa",
    "dhl": "DHL",
}


def norm_forwarder(awb, flight_number):
    a = (awb or "").strip()
    p = a[:3]
    if p in AWB_PREFIX_FW:
        return AWB_PREFIX_FW[p]
    s = (flight_number or "").strip()
    if not s:
        return "Sin forwarder"
    key = s.lower().replace("  ", " ")
    if key in FORWARDER_ALIASES:
        return FORWARDER_ALIASES[key]
    for frag, canon in (("kalitta", "Kalitta"), ("tampa", "Tampa Cargo"),
                        ("air express", "Air Express"), ("sky", "SKY"),
                        ("avianca", "Avianca"), ("latam", "LATAM Cargo"),
                        ("caribbean", "Trans Caribbean"), ("caribean", "Trans Caribbean"),
                        ("mercury", "Mercury"), ("copa", "Copa")):
        if frag in key:
            return canon
    return s.title()


def noco_fetch_all(table_id, where="", fields="", page_size=1000, label=""):
    rows, offset = [], 0
    while True:
        params = f"limit={page_size}&offset={offset}&shuffle=0"
        if where:
            params += "&where=" + urllib.parse.quote(where)
        if fields:
            params += f"&fields={fields}"
        url = f"{NOCO_URL}/{NOCO_BASE}/{table_id}?{params}"
        req = urllib.request.Request(url, headers={"xc-token": NOCO_TOKEN})
        for intento in range(4):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = json.loads(r.read())
                break
            except Exception as e:
                if intento == 3:
                    raise
                print(f"  {label} reintento {intento+1} tras error: {e}", flush=True)
        batch = data.get("list", [])
        rows.extend(batch)
        total = data.get("pageInfo", {}).get("totalRows", 0)
        offset += len(batch)
        print(f"  {label} {offset}/{total}", flush=True)
        if offset >= total or not batch:
            break
    print(f"  {label} -> {len(rows)} filas", flush=True)
    return rows


def parse_dt(s):
    if not s:
        return None
    s = str(s)
    try:
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def horas(a, b):
    """Horas entre a y b (b-a). None si falta alguna o si es negativo/absurdo."""
    if a is None or b is None:
        return None
    d = (b - a).total_seconds() / 3600.0
    if d < 0 or d > 365 * 24:
        return None
    return round(d, 2)


def horas_habiles(a, b):
    """Horas HÁBILES entre a y b (lunes a viernes; sábado y domingo = 0), en la
    misma escala que horas() -- 1 día hábil = 24. Sirve para el toggle
    "días corridos / días hábiles" del análisis de tiempos. Se compara en el
    mismo reloj UTC en que vienen los timestamps de NocoDB (igual que horas())."""
    if a is None or b is None or b < a:
        return horas(a, b) if (a and b and b >= a) else None
    if (b - a).total_seconds() > 365 * 24 * 3600:
        return None
    total_dias = 0.0
    cur = a
    while cur < b:
        sig_medianoche = (cur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        tramo_fin = min(sig_medianoche, b)
        if cur.weekday() < 5:  # 0-4 = lun-vie
            total_dias += (tramo_fin - cur).total_seconds() / 86400.0
        cur = tramo_fin
    return round(total_dias * 24, 2)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now(timezone.utc)

    # 1. guia_madres (vuelos / AWB / forwarder / tarifa de costo)
    print("[1/4] guia_madres ...")
    madres = noco_fetch_all(
        TBL_GUIA_MADRES,
        fields="id,awb,flight_number,flight_date,fecha_creacion,tipo_transporte,tarifa_costo,peso_total,items,dinero_total",
        label="guia_madres",
    )
    madre_info = {}
    for m in madres:
        mid = m.get("id")
        if mid is None:
            continue
        madre_info[mid] = {
            "awb": m.get("awb") or "",
            "forwarder": norm_forwarder(m.get("awb"), m.get("flight_number")),
            "tipo_transporte": (m.get("tipo_transporte") or "").upper(),
            "tarifa_costo": m.get("tarifa_costo") or 0,
            "peso_total": m.get("peso_total") or 0,
            "items": m.get("items") or 0,
            "flight_date": parse_dt(m.get("flight_date")),
            "fecha_creacion": parse_dt(m.get("fecha_creacion")),
        }

    # --- Imputacion de tarifa de costo (para vuelos sin tarifa_costo cargada) ---
    # tarifa_costo es un dato del VUELO (guia_madre), no de la guia: todas las
    # guias de un mismo vuelo comparten la tarifa, asi que no se puede "tomar de
    # otra guia del mismo vuelo". Lo que si es estable es la tarifa de un mismo
    # forwarder en un mismo periodo (ej. SKY 2025 = 1,7 USD/kg en TODOS sus
    # vuelos). Se arma una mediana de tarifa por (forwarder, año-mes), con
    # fallback a (forwarder, año) y a (forwarder). Solo 2025-2026 tienen algun
    # vuelo con tarifa real -> para 2023-2024 no hay con que calibrar (queda 0).
    def _fecha_vuelo(m):
        return m["flight_date"] or m["fecha_creacion"]
    _q = lambda mes: (mes - 1) // 3 + 1
    tarifas_mes, tarifas_trim, tarifas_anio = defaultdict(list), defaultdict(list), defaultdict(list)
    for m in madre_info.values():
        tc = m["tarifa_costo"]
        fv = _fecha_vuelo(m)
        if tc and tc > 0 and fv:
            fw = m["forwarder"]
            tarifas_mes[(fw, fv.year, fv.month)].append(tc)
            tarifas_trim[(fw, fv.year, _q(fv.month))].append(tc)
            tarifas_anio[(fw, fv.year)].append(tc)
    _med = lambda xs: statistics.median(xs) if xs else None

    def tarifa_imputada(fw, anio, mes):
        # Solo dentro del MISMO año (mes -> trimestre -> año). No se cruza de
        # año: las tarifas aereas cambian año a año, aplicar la de 2025 a 2023
        # seria inventar. -> 2023-2024 quedan casi sin cobertura (ningun vuelo
        # de esos años tiene tarifa real cargada).
        return (_med(tarifas_mes.get((fw, anio, mes)))
                or _med(tarifas_trim.get((fw, anio, _q(mes))))
                or _med(tarifas_anio.get((fw, anio))))

    # 2. tabla puente M2M: n_guia -> id_guia_madre
    print("[2/4] puente guia_hijas <-> guia_madres ...")
    puente = noco_fetch_all(TBL_GUIA_MADRE_HIJAS, fields="id_guia_madre,guia_hijas", label="puente")
    madre_por_guia = {}
    for p in puente:
        gh = p.get("guia_hijas") or {}
        ng = gh.get("n_guia")
        idm = p.get("id_guia_madre")
        if ng is not None and idm is not None:
            madre_por_guia[str(ng)] = idm

    # 3. 2ebox_rentabilidad: n_guia -> unidad de negocio, peso, valor FOB, casilla, email
    #    (mismo universo que ebox_cumplimiento, responde rapido por la API).
    #    OJO: los campos TarifaInternacional* de esta tabla vienen sucios
    #    (mezclan USD/CLP, a veces total y no por kg) -- NO sirven como costo.
    #    El unico costo de flete confiable es guia_madres.tarifa_costo (2025+).
    print("[3/4] 2ebox_rentabilidad (unidad, peso, FOB, casilla) ...", flush=True)
    rent = noco_fetch_all(
        TBL_RENTABILIDAD,
        fields="NGuia,UnidadNegocio,Peso,ValorFOBUSD,VolumenInternacional,Casilla,Email",
        label="rentabilidad",
    )
    # --- Unidad de negocio (Jorge, 2026-09-09) ---
    # El campo 2ebox_rentabilidad.UnidadNegocio esta "mal hecho": no distingue
    # bien Carga. La regla real: todo lo trabajado en la seccion Carga es Carga
    # (aunque no se haya usado bien hasta ahora). Se fuerza por casilla:
    #   - Reuse (2 cuentas), Sindal y Smartdeal = clientes de Carga.
    #   - Netnow es cliente de carga "a veces" pero su caso va SEPARADO -> Netnow.
    #   - CL16504001/2 (Retail Tienda Shopify / Falabella) = Retail.
    CARGA_CASILLAS = {"CL39580000", "CL39580001",  # Servicios Intermediarios Reuse Chile SpA / Jose Tomas Ulloa
                      "CL68910000",                # Sindal (Martin Penna)
                      "CL42000001", "CL81001000",  # otras que el campo ya marcaba Carga
                      "CL9251K002"}                 # Smartdeal (info@smartdeal.cl) -- ya no importa (solo 2024),
                                                     # se mantiene para que sus 9 guias historicas cuenten como Carga
    RETAIL_CASILLAS = {"CL16504001", "CL16504002"}
    NETNOW_CASILLA_EXTRA = {"CL21703000"}          # NET NOW TECNOLOGIA Y COMPUTACION S.A.
    UNIDAD_MAP = {"ML": "Marketplace", "MERCADO": "Marketplace", "SHOPIFY": "Marketplace",
                  "RETAIL": "Retail", "CASILLA": "Casilla", "NETNOW": "Netnow", "CARGA": "Carga"}

    def clasifica_unidad(casilla, email, unidad_raw):
        c = (casilla or "").strip().upper()
        e = (email or "").strip().lower()
        if c in CARGA_CASILLAS:
            return "Carga"
        if c in RETAIL_CASILLAS:
            return "Retail"
        if e.endswith("@netnow.cl") or c in NETNOW_CASILLA_EXTRA:
            return "Netnow"
        u = (unidad_raw or "").strip().upper()
        return UNIDAD_MAP.get(u, (unidad_raw or "").strip() or "Casilla")

    unidad_por_guia, peso_por_guia, fob_por_guia, pesovol_por_guia = {}, {}, {}, {}
    for r in rent:
        ng = r.get("NGuia")
        if ng is None:
            continue
        ng = str(ng)
        unidad_por_guia[ng] = clasifica_unidad(r.get("Casilla"), r.get("Email"), r.get("UnidadNegocio"))
        if r.get("Peso"):
            peso_por_guia[ng] = r["Peso"]
        if r.get("ValorFOBUSD"):
            fob_por_guia[ng] = r["ValorFOBUSD"]
        # VolumenInternacional = peso volumetrico internacional en kg
        # (dimensiones L*A*Al / 6000), ~100% de cobertura en todos los años.
        if r.get("VolumenInternacional"):
            pesovol_por_guia[ng] = r["VolumenInternacional"]

    # 3b. guia_hijas: venta (para el margen bruto = venta - costo del vuelo).
    # Confirmado con Jorge (2026-09-21) contra la guia 168500 (Casilla, sin
    # nota en Instrucciones): el admin muestra "Transporte Internacional"
    # USD 56,43 = valores.RR.transporte_internacional_usd (51,14) +
    # valores.HandlingFee convertido a USD (5.000 CLP / valores.Dolar). Ese
    # total / peso = tarifa de venta USD/kg.
    #   - Para guias de CARGA (y algunas Casilla especiales, Jorge) el valor
    #     de venta real esta anotado a mano en instrucciones_especiales como
    #     "TARIFA <numero>" (USD/kg directo, ya no hay que dividir por peso)
    #     -- ese dato MANDA por sobre el calculo de guia_hijas.valores.
    print("[3b/5] guia_hijas (venta para margen) ...")
    gh_venta = noco_fetch_all(
        TBL_GUIA_HIJAS,
        fields="n_guia,valores,instrucciones_especiales",
        label="guia_hijas venta",
    )
    _tarifa_re = re.compile(r"tarifa\s*\$?\s*(\d+[.,]?\d*)", re.IGNORECASE)

    def _tarifa_de_instrucciones(texto):
        if not texto:
            return None
        m = _tarifa_re.search(texto)
        if not m:
            return None
        try:
            v = float(m.group(1).replace(",", "."))
        except ValueError:
            return None
        return v if 0 < v < 50 else None  # USD/kg razonable; descarta matches espurios

    venta_kg_por_guia, venta_fuente_por_guia = {}, {}
    for r in gh_venta:
        ng = r.get("n_guia")
        if ng is None:
            continue
        ng = str(ng)
        v_instr = _tarifa_de_instrucciones(r.get("instrucciones_especiales"))
        if v_instr is not None:
            venta_kg_por_guia[ng] = v_instr
            venta_fuente_por_guia[ng] = "instrucciones"
            continue
        raw = r.get("valores")
        if not raw:
            continue
        try:
            val = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(val, dict):
            continue
        rr = val.get("RR") or {}
        if not isinstance(rr, dict):
            rr = {}

        def _num(x):
            try:
                return float(x)
            except (TypeError, ValueError):
                return 0

        transp_usd = _num(rr.get("transporte_internacional_usd")) or _num(val.get("TarifaUsd"))
        dolar = _num(val.get("Dolar"))
        handling_clp = _num(val.get("HandlingFee")) or _num(rr.get("handling_fee"))
        handling_usd = (handling_clp / dolar) if dolar else 0
        total_usd = transp_usd + handling_usd
        peso_g = peso_por_guia.get(ng) or 0
        if total_usd and peso_g:
            venta_kg_por_guia[ng] = total_usd / peso_g
            venta_fuente_por_guia[ng] = "calculado"

    # 4. ebox_cumplimiento: timestamps del funnel (2023 -> hoy)
    print("[4/5] ebox_cumplimiento (funnel de tiempos) ...")
    # NOTA: en ebox_cumplimiento las columnas fecha_en_retencion y
    # fecha_en_bodega vienen VACIAS -> se sacan de guias_hijas_estados_historial
    # (paso 5). Los estados reales del flujo Casilla estan en el Google Sheet
    # "Flujo 2ebox" (id 1qNtzp5fKHj9fj6_UoQ9sZUbc9tAAcBu1xM3Qa0hd9tM).
    fields_c = ("n_guia,casilla,tipo_venta,id_estado,fecha_recepcion,fecha_ingreso,fecha_miami_sin_factura,"
                "fecha_subida_factura,fecha_miami_con_factura,fecha_primer_pago,fecha_ultimo_pago,"
                "fecha_asignado_guia_madre,fecha_despachado_aeropuerto,fecha_arribado_chile,"
                "fecha_recibido_aduana,fecha_en_despacho,fecha_entregado")
    cumpl = noco_fetch_all(
        TBL_CUMPLIMIENTO,
        where=f"(fecha_ingreso,ge,exactDate,{FECHA_DESDE})",
        fields=fields_c,
        label="cumplimiento",
    )

    # 5. guias_hijas_estados_historial: primera fecha de "En Bodega 2ebox Chile"
    #    (id_estado 18) y "En Retencion" (id_estado 23) -- no estan en ebox_cumplimiento.
    print("[5/5] historial de estados (bodega CD / retencion) ...", flush=True)
    TBL_HIST = "mgzgcbyxeu7225b"
    n_min_hist = 109000
    bod_por_guia, ret_por_guia = {}, {}
    for est, dst in ((18, bod_por_guia), (23, ret_por_guia)):
        filas = noco_fetch_all(
            TBL_HIST,
            where=f"(id_guia_hija,gte,{n_min_hist})~and(id_estado,eq,{est})",
            fields="id_guia_hija,fecha",
            label=f"hist e{est}",
        )
        for f in filas:
            ng = str(f.get("id_guia_hija"))
            dt = parse_dt(f.get("fecha"))
            if dt and (ng not in dst or dt < dst[ng]):
                dst[ng] = dt

    # --- construir registros por guia ---
    # Solo guias CON vuelo real (despachadas a aeropuerto). Antes se excluian
    # aqui las guias cuyo guia_madre tenia tipo_transporte == "CARGA" (AWB de
    # carga dedicado) -- eso dejaba a los clientes de la unidad de negocio
    # "Carga" (Reuse, Sindal, etc.) casi sin guias en el reporte, porque casi
    # todo lo que mueven vuela en AWB de carga. Jorge confirmo (2026-09-21,
    # verificado contra guia_madres y la tabla NocoDB UnidadesNegocio: Reuse
    # / CL39580001 tiene 31 guias con fecha_despachado_aeropuerto en 2026,
    # todas en AWB tipo_transporte=CARGA) que esas guias SI deben contarse --
    # el forwarder/tarifa_costo/peso_fact ya se resuelven igual sin importar
    # el tipo_transporte. Se sigue registrando el tipo en cada fila (ver
    # "tipo_transporte" mas abajo) para poder filtrar/analizar por separado
    # si hace falta.
    registros = []
    forwarders_cnt = Counter()
    unidades_cnt = Counter()
    sin_madre = 0
    carga_awb = 0
    for g in cumpl:
        ng = str(g.get("n_guia"))
        f_rec = parse_dt(g.get("fecha_recepcion"))
        f_ing = parse_dt(g.get("fecha_ingreso"))
        f_msf = parse_dt(g.get("fecha_miami_sin_factura"))
        f_sf = parse_dt(g.get("fecha_subida_factura"))
        f_mcf = parse_dt(g.get("fecha_miami_con_factura"))
        f_pago = parse_dt(g.get("fecha_primer_pago"))
        f_asig = parse_dt(g.get("fecha_asignado_guia_madre"))
        f_desp = parse_dt(g.get("fecha_despachado_aeropuerto"))
        f_arr = parse_dt(g.get("fecha_arribado_chile"))
        f_adu = parse_dt(g.get("fecha_recibido_aduana"))
        f_ret = ret_por_guia.get(ng)
        f_bod = bod_por_guia.get(ng)
        f_dch = parse_dt(g.get("fecha_en_despacho"))
        f_ent = parse_dt(g.get("fecha_entregado"))

        if f_desp is None:
            continue  # todavia no vuela -> fuera de Performance y del funnel de vuelo

        idm = madre_por_guia.get(ng)
        madre = madre_info.get(idm) if idm is not None else None
        if madre is None:
            sin_madre += 1
            forwarder = "Sin forwarder"
            tarifa_costo = 0
        else:
            if madre["tipo_transporte"] == "CARGA":
                carga_awb += 1
            forwarder = madre["forwarder"]
            tarifa_costo = madre["tarifa_costo"] or 0

        # periodo de referencia = mes del vuelo (despacho a aeropuerto)
        fy, fm = f_desp.year, f_desp.month
        # semana = lunes de la semana del despacho (para "kilos por semana", Jorge 2026-09-22)
        semana = (f_desp - timedelta(days=f_desp.weekday())).strftime("%Y-%m-%d")
        peso = peso_por_guia.get(ng) or 0
        peso_vol = round(pesovol_por_guia.get(ng) or 0, 2)
        unidad = unidad_por_guia.get(ng, "Casilla")
        # peso de costeo / facturable: Casilla se cobra por kilo REAL; Carga por
        # el MAYOR entre peso y peso volumetrico (Jorge, 2026-09-09), y ese
        # maximo se factura en KILOS ENTEROS, redondeado HACIA ARRIBA (Jorge,
        # 2026-09-21 -- ej. guia 167546: peso real 76 kg, peso volumetrico
        # 148,92 kg -> se cobran 149 kg cerrados, no 148,92).
        peso_fact = math.ceil(max(peso, peso_vol)) if unidad == "Carga" else round(peso, 2)
        fob = round(fob_por_guia.get(ng) or 0, 1)
        # costo_flete_usd: costo real de flete (guia_madres.tarifa_costo del
        # vuelo, USD/kg x peso facturable). Solo hay tarifa_costo real desde 2025.
        # costo_est_usd: idem pero rellenando con tarifa imputada por
        # (forwarder, mes) cuando el vuelo no trae tarifa. En 2023-2024 no hay
        # tarifa de ningun vuelo -> sigue en 0.
        tarifa_est = tarifa_costo if tarifa_costo and tarifa_costo > 0 else (tarifa_imputada(forwarder, fy, fm) or 0)
        costo_flete_usd = round(tarifa_costo * peso_fact, 2) if (tarifa_costo and peso_fact) else 0
        costo_est_usd = round(tarifa_est * peso_fact, 2) if (tarifa_est and peso_fact) else 0
        costo_estimado = 1 if (costo_est_usd and not costo_flete_usd) else 0
        # venta_usd: tarifa de venta (instrucciones o calculada, ver bloque 3b) x
        # peso facturable. Margen bruto = venta_usd - costo_flete_usd (o costo_est_usd).
        tarifa_venta = venta_kg_por_guia.get(ng) or 0
        venta_usd = round(tarifa_venta * peso_fact, 2) if (tarifa_venta and peso_fact) else 0

        # tramos del funnel -- estados reales del flujo Casilla 2ebox.
        # Se guarda cada tramo en 2 versiones: dias CORRIDOS (horas) y dias
        # HABILES (horas_habiles, lun-vie), para el toggle del analisis de tiempos.
        tramos = [
            ("rec_ing",  f_rec, f_ing),           # Recepcion USA -> Ingreso a Miami
            ("ing_mcf",  f_ing, f_mcf),           # Ingreso Miami -> Miami con factura
            ("mcf_pago", f_mcf, f_pago),          # Disponible -> Primer pago
            ("pago_asig", f_pago or f_mcf, f_asig),  # Pago -> Asociado a Guia Madre
            ("asig_desp", f_asig, f_desp),        # Asociado -> Despachado a Aeropuerto
            ("desp_arr", f_desp, f_arr),          # TRANSITO AEREO
            ("arr_adu",  f_arr, f_adu),           # Arribado -> Recibido Aduana
            ("adu_bod",  f_adu, f_bod),           # Recibido Aduana -> En Bodega CD
            ("bod_dch",  f_bod, f_dch),           # En Bodega CD -> En Despacho
            ("dch_ent",  f_dch, f_ent),           # En Despacho -> Entregado
            ("total",    f_ing, f_ent),           # puerta a puerta
        ]
        d_corr = [horas(a, b) for _, a, b in tramos]
        d_hab = [horas_habiles(a, b) for _, a, b in tramos]

        registros.append([
            fy, fm, forwarder, unidad, (idm or 0),
            1 if f_ent else 0,                 # entregada
            1 if f_ret else 0,                 # paso por retencion
            round(peso, 2), peso_vol, peso_fact, fob,
            costo_flete_usd, costo_est_usd, costo_estimado, venta_usd, semana,
        ] + d_corr + d_hab)
        forwarders_cnt[forwarder] += 1
        unidades_cnt[unidad] += 1

    _T = ["rec_ing", "ing_mcf", "mcf_pago", "pago_asig", "asig_desp",
          "desp_arr", "arr_adu", "adu_bod", "bod_dch", "dch_ent", "total"]
    COLS = ["fy", "fm", "fw", "un", "gm_id", "entregada", "retenida",
            "peso", "peso_vol", "peso_fact", "fob_usd",
            "costo_flete_usd", "costo_est_usd", "costo_estimado", "venta_usd", "semana"] \
        + ["d_" + t for t in _T] + ["dh_" + t for t in _T]

    ci = {c: i for i, c in enumerate(COLS)}
    por_anio = Counter(r[ci["fy"]] for r in registros)
    n_vuelos = len({r[ci["gm_id"]] for r in registros if r[ci["gm_id"]]})
    con_costo = Counter(r[ci["fy"]] for r in registros if r[ci["costo_flete_usd"]])
    con_costo_est = Counter(r[ci["fy"]] for r in registros if r[ci["costo_est_usd"]])
    con_venta = Counter(r[ci["fy"]] for r in registros if r[ci["venta_usd"]])
    meta = {
        "generado": ahora.isoformat(timespec="seconds"),
        "fecha_desde": FECHA_DESDE,
        "n_registros": len(registros),
        "n_vuelos": n_vuelos,
        "n_sin_madre": sin_madre,
        "n_carga_awb": carga_awb,
        "cols": COLS,
        "forwarders": forwarders_cnt.most_common(),
        "unidades": unidades_cnt.most_common(),
        "anios": sorted({r[0] for r in registros}),
        "por_anio": dict(sorted(por_anio.items())),
        "cobertura_costo": dict(sorted(con_costo.items())),
        "cobertura_costo_est": dict(sorted(con_costo_est.items())),
        "cobertura_venta": dict(sorted(con_venta.items())),
    }

    (OUT / "datos_crudos.json").write_text(
        json.dumps({"cols": COLS, "rows": registros}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{len(registros)} registros -> data/datos_crudos.json")
    print(f"  sin guia_madre: {sin_madre}  |  en AWB de carga (incluidas): {carga_awb}")
    print(f"  forwarders: {forwarders_cnt.most_common()}")
    print(f"  unidades:   {unidades_cnt.most_common()}")
    print(f"  anios:      {meta['anios']}")
    print(f"  cobertura venta: {meta['cobertura_venta']}  "
          f"(fuentes: {Counter(venta_fuente_por_guia.values()).most_common()})")


# ============================================================================
# Última Milla (pestaña "Última Milla" del dashboard) -- corre en el MISMO
# script/paso de CI que main() (no un extractor aparte) para no tener que
# tocar el workflow de Actions. Clasifica por courier de última milla
# (guia_hijas.ultima_milla: 2=DropGo, 1=Bluexpress, resto=sin courier) y
# calcula el tramo en_despacho -> entregado por guía, con región/comuna.
# Ver ultima_milla/extraer_ultima_milla.py (carpeta de desarrollo) para el
# docstring completo de la metodología.
# ============================================================================
TBL_GUIA_HIJAS_UM = "m4b0yh4lwpxsvri"
TBL_HIST_ESTADOS_UM = "mgzgcbyxeu7225b"
TBL_DIRECCIONES_UM = "m4sgieddhip29md"
COURIER_UM = {2: "DropGo", 1: "Bluexpress"}
EST_UM = {18: "en_bodega_cl", 20: "en_despacho", 21: "entregado",
          26: "reagendado", 28: "entrega_fallida", 29: "enviado_cd"}
N_GUIA_MIN_UM = 157000          # ~inicio 2026 -- antes no había courier asignado


def _a_chile(dt):
    if dt is None:
        return None
    off = -3 if dt.month in (1, 2, 3, 10, 11, 12) else -4  # DST aproximado
    return dt + timedelta(hours=off)


def _dias_calendario_um(a, b):
    """Días calendario (fecha de b − fecha de a) en hora Chile. 0=same day."""
    ca, cb = _a_chile(a), _a_chile(b)
    if ca is None or cb is None:
        return None
    d = (cb.date() - ca.date()).days
    return d if 0 <= d <= 120 else None


def extraer_ultima_milla():
    print("\n=== Última Milla ===")
    print("[1/3] guia_hijas (entregadas) ...")
    gh = noco_fetch_all(
        TBL_GUIA_HIJAS_UM,
        where=f"(n_guia,gte,{N_GUIA_MIN_UM})~and(id_estado,eq,21)",
        fields="n_guia,ultima_milla,id_direccion,id_cliente,ancho,alto,largo,peso",
        label="guia_hijas um",
    )
    gmap = {r["n_guia"]: r for r in gh if r.get("n_guia")}

    print("[2/3] direcciones (comuna/región) ...")
    dir_ids = list({r["id_direccion"] for r in gh if r.get("id_direccion")})
    dmap = {}
    for i in range(0, len(dir_ids), 200):
        lote = dir_ids[i:i + 200]
        w = "(id,in," + ",".join(str(x) for x in lote) + ")"
        for r in noco_fetch_all(TBL_DIRECCIONES_UM, where=w, fields="id,comunas,regiones", label=f"dir um {i}"):
            dmap[r["id"]] = {
                "comuna": (r.get("comunas") or {}).get("nombre"),
                "region": (r.get("regiones") or {}).get("nombre"),
            }

    print("[3/3] historial de estados (última milla) ...")
    hist = noco_fetch_all(
        TBL_HIST_ESTADOS_UM,
        where=f"(id_guia_hija,gte,{N_GUIA_MIN_UM})",
        fields="id_guia_hija,id_estado,fecha",
        label="hist um",
    )
    por_guia = defaultdict(dict)
    for h in hist:
        e = h.get("id_estado")
        if e not in EST_UM:
            continue
        ng = h.get("id_guia_hija")
        dt = parse_dt(h.get("fecha"))
        if dt is None:
            continue
        k = EST_UM[e]
        if k not in por_guia[ng] or dt < por_guia[ng][k]:
            por_guia[ng][k] = dt

    registros = []
    cnt_courier = Counter()
    for ng, r in gmap.items():
        um = r.get("ultima_milla")
        courier = COURIER_UM.get(um, "Sin courier / otro" if um in (-1, 0) else f"cod {um}")
        di = dmap.get(r.get("id_direccion"), {})
        region = di.get("region") or "?"
        comuna = di.get("comuna") or "?"
        rm = region == "METROPOLITANA DE SANTIAGO"
        h = por_guia.get(ng, {})
        f_desp, f_ent = h.get("en_despacho"), h.get("entregado")
        ent_dc = _dias_calendario_um(f_desp, f_ent)
        registros.append({
            "n_guia": ng,
            "courier": courier,
            "region": region,
            "comuna": comuna,
            "zona": "RM" if rm else ("?" if region == "?" else "Regiones"),
            "peso": round(r.get("peso") or 0, 2),
            "mes": (_a_chile(f_desp) or _a_chile(f_ent)).strftime("%Y-%m") if (f_desp or f_ent) else None,
            "h_desp_ent": horas(f_desp, f_ent),
            "dias_desp_ent": ent_dc,
            "sla": (None if ent_dc is None else
                    "same_day" if ent_dc == 0 else
                    "next_day" if ent_dc == 1 else
                    "d2" if ent_dc == 2 else "d3+"),
            "reagendado": "reagendado" in h,
            "entrega_fallida": "entrega_fallida" in h,
            "f_desp": (f_desp.isoformat() if f_desp else None),
            "f_ent": (f_ent.isoformat() if f_ent else None),
        })
        cnt_courier[courier] += 1

    meta_um = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_guia_min": N_GUIA_MIN_UM,
        "n_registros": len(registros),
        "por_courier": cnt_courier.most_common(),
    }
    (OUT / "ultima_milla.json").write_text(
        json.dumps({"meta": meta_um, "rows": registros}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    print(f"\n-> data/ultima_milla.json  ({len(registros)} guías)  por courier: {cnt_courier.most_common()}")


if __name__ == "__main__":
    main()
    extraer_ultima_milla()
