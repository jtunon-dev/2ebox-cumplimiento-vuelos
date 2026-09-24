"""
Llenado de Vuelos 2ebox -- extractor de datos desde NocoDB para la pestaña
"Llenado de Vuelos" del Reporte de Logística y Operaciones.

Spec: SPEC_llenado_vuelos_2ebox.md (Jorge, 2026-09-24). Decisiones tomadas con
Jorge al revisar el spec contra Noco (2026-09-24):
  - Ingreso / venta de la guía = flete internacional + handling (igual que el
    resto del reporte, ver extraer_datos.py). total_pagar trae IVA, flete
    nacional y seguro -> se muestra solo como referencia, NO como ingreso.
  - Peso: Casilla se cobra por kilo real; Carga por el mayor entre real y
    volumétrico, en kilos enteros hacia arriba (misma regla que el reporte).
  - Ejecutiva por clientes.codigo_convenio: KC2EBOX + CPLAZA2EBOX + DiamanteK
    = Kathy (CPLAZA es su canal de referidos), TB2EBOX + DiamanteT = Tiare.
  - "Piezas y partes de PC" (exenta de ad valorem) = guia_hijas.id_tipo_impuesto
    = 3 ("Computadores y Partes", tabla tipo_impuesto_chile).
  - Punto de equilibrio: no hay costos fijos por AWB en la base -> la
    referencia es el promedio histórico de vuelos del mismo forwarder.

Hallazgos que respaldan las reglas (guías desde 2026-06, verificado en Noco):
  - ad valorem = 6% del CIF (valores.RR.advalorem / (CIF x dólar) entre 5,8% y
    6,2%). Sumando FOB por cliente+vuelo: entre 500 y 3.000 USD el 99% paga ad
    valorem; bajo 500 igual paga ~28% (no se explica con CIF) -> para cada guía
    se usa el ad valorem / agente que YA calculó el sistema en valores.RR.
  - "Lista para volar" = MAX(fecha_primer_pago, fecha_miami_con_factura) de
    ebox_cumplimiento (definición confirmada con Jorge 2026-09-01, análisis de
    vuelos no volados).
  - Fecha de subida de la guía al AWB = ebox_cumplimiento.fecha_asignado_guia_madre.

Salida: data/llenado_vuelos.json
"""
import json
import math
import os
import statistics
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOCO_TOKEN = os.environ.get("NOCO_TOKEN")
if not NOCO_TOKEN:
    try:  # copia local: reutiliza el token del extractor principal (no existe en el repo)
        from extraer_datos import NOCO_TOKEN
    except ImportError:
        raise SystemExit("Falta la variable de entorno NOCO_TOKEN (secret del repo).")
NOCO_BASE = "pifk61tmzhes073"
NOCO_URL = "https://noco.2ebox.com/api/v1/db/data/noco"

TBL_CUMPLIMIENTO = "m4feao7xeudu8k9"
TBL_GUIA_MADRES = "m5t0y2pg3d0qt7h"
TBL_GUIA_MADRE_HIJAS = "mpwefzshqgun0m7"
TBL_GUIA_HIJAS = "m4b0yh4lwpxsvri"
TBL_CLIENTES = "mrog0ys27qhusnw"
TBL_HIST = "mgzgcbyxeu7225b"   # guias_hijas_estados_historial

AWB_DESDE = "2025-07-01"      # vuelos analizados (historia para promedios)
GUIAS_DESDE = "2025-04-01"    # guías: colchón antes del primer AWB analizado
PENDIENTE_MAX_DIAS = 120      # guías listas sin AWB más antiguas que esto no se consideran
OUT = Path(__file__).parent / "data"

try:
    from zoneinfo import ZoneInfo
    TZ_CL = ZoneInfo("America/Santiago")
except Exception:  # Windows sin tzdata
    TZ_CL = timezone(timedelta(hours=-3))

AWB_PREFIX_FW = {"045": "LATAM Cargo", "230": "Copa", "272": "Kalitta", "456": "Trans Caribbean",
                 "510": "Air Express", "605": "SKY", "992": "DHL"}

EJECUTIVA_CONVENIO = {"KC2EBOX": "Kathy", "CPLAZA2EBOX": "Kathy", "DiamanteK": "Kathy",
                      "TB2EBOX": "Tiare", "DiamanteT": "Tiare"}
# mismos overrides por casilla que extraer_datos.clasifica_unidad()
CARGA_CASILLAS = {"CL39580000", "CL39580001", "CL68910000", "CL42000001", "CL81001000", "CL9251K002"}
ML_CASILLAS = {"CL93829002"}
RETAIL_CASILLAS = {"CL16504001", "CL16504002"}
ESTADOS_FUERA = {5, 6, 8, 9, 11, 25}  # retiro Miami, retorno, nula, baja, reembolso, consolidado
# estado del AWB (guia_madres.id_estado): 12/13 = todavía asociando guías
# (abierto); 14 = despachado a aeropuerto; > 14 = ya voló / en Chile.
ESTADOS_AWB_ABIERTO = {12, 13}
TIPO_IMP_EXENTO = 3                    # Computadores y Partes
UMBRAL_ADV, UMBRAL_AGENTE = 500, 3000


def noco_fetch_all(table_id, where="", fields="", page_size=1000, label=""):
    rows, offset = [], 0
    while True:
        params = f"limit={page_size}&offset={offset}&shuffle=0"
        if where:
            params += "&where=" + urllib.parse.quote(where)
        if fields:
            params += f"&fields={fields}"
        req = urllib.request.Request(f"{NOCO_URL}/{NOCO_BASE}/{table_id}?{params}",
                                     headers={"xc-token": NOCO_TOKEN})
        for intento in range(4):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
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
    return rows


def parse_dt(s):
    if not s:
        return None
    s = str(s)
    for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(s[:n], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def local(dt):
    """'YYYY-MM-DD HH:MM' en hora de Chile (para día de la semana / día de subida)."""
    return dt.astimezone(TZ_CL).strftime("%Y-%m-%d %H:%M") if dt else None


def parse_valores(raw):
    try:
        v = json.loads(raw or "{}")
        if isinstance(v, str):
            v = json.loads(v)
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def forwarder(awb, flight_number):
    p = (awb or "").strip()[:3]
    if p in AWB_PREFIX_FW:
        return AWB_PREFIX_FW[p]
    s = (flight_number or "").strip().lower()
    for frag, canon in (("kalitta", "Kalitta"), ("tampa", "Tampa Cargo"), ("air express", "Air Express"),
                        ("sky", "SKY"), ("avianca", "Avianca"), ("latam", "LATAM Cargo"),
                        ("carib", "Trans Caribbean"), ("mercury", "Mercury"), ("copa", "Copa"), ("dhl", "DHL")):
        if frag in s:
            return canon
    return s.title() or "Sin forwarder"


def tramo(fob):
    return "<500" if fob <= UMBRAL_ADV else ("500-3000" if fob < UMBRAL_AGENTE else ">=3000")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now(timezone.utc)

    print("[1/5] guia_madres ...", flush=True)
    madres = noco_fetch_all(TBL_GUIA_MADRES, where=f"(fecha_creacion,ge,exactDate,2025-01-01)",
                            fields="id,awb,flight_number,flight_date,fecha_creacion,id_estado,tipo_transporte,tarifa_costo",
                            label="madres")
    vuelos = {}
    for m in madres:
        vuelos[m["id"]] = {
            "id": m["id"], "awb": m.get("awb") or "", "fw": forwarder(m.get("awb"), m.get("flight_number")),
            "tipo": (m.get("tipo_transporte") or "").upper() or "COURIER",
            "creado_dt": parse_dt(m.get("fecha_creacion")), "flight_dt": parse_dt(m.get("flight_date")),
            "tarifa": num(m.get("tarifa_costo")), "id_estado": m.get("id_estado"),
        }
    min_id = min(vuelos) if vuelos else 0

    print("[2/5] puente guía <-> AWB ...", flush=True)
    madre_por_guia = {}
    for p in noco_fetch_all(TBL_GUIA_MADRE_HIJAS, where=f"(id_guia_madre,ge,{min_id})",
                            fields="id_guia_madre,guia_hijas", label="puente"):
        ng = (p.get("guia_hijas") or {}).get("n_guia")
        if ng is not None and p.get("id_guia_madre") in vuelos:
            madre_por_guia[str(ng)] = p["id_guia_madre"]

    print("[3/5] ebox_cumplimiento (fechas lista / subida / despacho) ...", flush=True)
    cumpl = {}
    for c in noco_fetch_all(TBL_CUMPLIMIENTO, where=f"(fecha_ingreso,ge,exactDate,{GUIAS_DESDE})",
                            fields="n_guia,id_estado,fecha_primer_pago,fecha_miami_con_factura,"
                                   "fecha_asignado_guia_madre,fecha_despachado_aeropuerto",
                            label="cumplimiento"):
        pago, mcf = parse_dt(c.get("fecha_primer_pago")), parse_dt(c.get("fecha_miami_con_factura"))
        cumpl[str(c.get("n_guia"))] = {
            "lista": max(pago, mcf) if (pago and mcf) else None,
            "asig": parse_dt(c.get("fecha_asignado_guia_madre")),
            "desp": parse_dt(c.get("fecha_despachado_aeropuerto")),
            "mcf": mcf,
            "estado": c.get("id_estado"),
        }

    # ebox_cumplimiento.fecha_despachado_aeropuerto viene casi vacía (ej. 3 de 54
    # guías de un vuelo ya despachado) -> la fecha real sale del historial de
    # estados (primera vez en estado 14 "Despachado a Aeropuerto").
    print("[3b/5] historial: despacho a aeropuerto (estado 14) ...", flush=True)
    n_min = min((int(k) for k in cumpl if k.isdigit()), default=0)
    for h in noco_fetch_all(TBL_HIST, where=f"(id_guia_hija,gte,{n_min})~and(id_estado,eq,14)",
                            fields="id_guia_hija,fecha", label="hist e14"):
        ng, dt = str(h.get("id_guia_hija")), parse_dt(h.get("fecha"))
        if dt and ng in cumpl and (not cumpl[ng].get("desp_h") or dt < cumpl[ng]["desp_h"]):
            cumpl[ng]["desp_h"] = dt
    for c in cumpl.values():
        c["desp"] = c.get("desp_h") or c["desp"]

    print("[4/5] clientes con convenio de ejecutiva ...", flush=True)
    ejec_por_casilla = {}
    for conv, ej in EJECUTIVA_CONVENIO.items():
        for r in noco_fetch_all(TBL_CLIENTES, where=f"(codigo_convenio,eq,{conv})", fields="casilla", label=conv):
            if r.get("casilla"):
                ejec_por_casilla[r["casilla"].strip().upper()] = ej

    print("[5/5] guia_hijas (peso, FOB, venta, aduana) ...", flush=True)
    gh = noco_fetch_all(TBL_GUIA_HIJAS, where=f"(fecha,ge,exactDate,{GUIAS_DESDE})",
                        fields="n_guia,id_estado,peso,ancho,largo,alto,costo_producto,valores,id_tipo_impuesto,"
                               "total_pagar,instrucciones_especiales,es_empresa,cliente_stamp,descripcion",
                        label="guia_hijas")

    # tarifa de costo imputada (vuelos sin tarifa_costo cargada, típico del AWB
    # abierto): mediana del forwarder en los últimos 90 días de vuelos con tarifa.
    tarifas_fw = defaultdict(list)
    for v in vuelos.values():
        if v["tarifa"] > 0 and v["creado_dt"] and v["creado_dt"] >= ahora - timedelta(days=90):
            tarifas_fw[v["fw"]].append(v["tarifa"])
    tarifa_fw = {fw: statistics.median(xs) for fw, xs in tarifas_fw.items()}
    tarifa_default = tarifa_fw.get("SKY") or (statistics.median(sum(tarifas_fw.values(), [])) if tarifas_fw else 0)
    for v in vuelos.values():
        v["tarifa_imp"] = 0
        if v["tarifa"] <= 0:
            v["tarifa"] = tarifa_fw.get(v["fw"], tarifa_default)
            v["tarifa_imp"] = 1

    import re
    tarifa_re = re.compile(r"tarifa\s*\$?\s*(\d+[.,]?\d*)", re.IGNORECASE)

    guias = []
    desp_vuelo = defaultdict(list)
    for g in gh:
        ng = str(g.get("n_guia"))
        estado = g.get("id_estado")
        if estado in ESTADOS_FUERA:
            continue
        vid = madre_por_guia.get(ng)
        c = cumpl.get(ng, {})
        if vid is None:
            # pendiente: en Miami con factura, sin AWB, todavía en paso 1. "pag" = 1
            # si además tiene pago (= "lista para volar", definición oficial); las
            # con factura sin pago se guardan aparte porque en la práctica también
            # se suben a vuelos antes de pagar (~30% de las asociadas en ago-sep 2026).
            ref = c.get("lista") or c.get("mcf")
            if not ref or (estado or 99) >= 12 or ref < ahora - timedelta(days=PENDIENTE_MAX_DIAS):
                continue
        stamp = parse_valores(g.get("cliente_stamp"))
        casilla = (stamp.get("Casilla") or "").strip().upper()
        email = (stamp.get("Email") or "").strip().lower()
        if casilla in ML_CASILLAS or email.endswith("@mail.mercadolibre.cl"):
            seg = "MercadoLibre"
        elif casilla in RETAIL_CASILLAS:
            seg = "Retail"
        elif casilla in CARGA_CASILLAS:
            seg = "Carga"
        else:
            seg = "Empresa" if (g.get("es_empresa") or stamp.get("Empresa")) else "Natural"
        nombre = " ".join(x for x in (stamp.get("Nombre"), stamp.get("Apellido")) if x).strip()

        val = parse_valores(g.get("valores"))
        rr = val.get("RR") if isinstance(val.get("RR"), dict) else {}
        dolar = num(val.get("Dolar")) or 950.0
        kg = num(g.get("peso"))
        kgv = num(g.get("ancho")) * num(g.get("largo")) * num(g.get("alto")) / 6000.0
        kgf = math.ceil(max(kg, kgv)) if seg == "Carga" else kg

        v = vuelos.get(vid) if vid else None
        tarifa_costo = v["tarifa"] if v else tarifa_default
        costo = tarifa_costo * kgf
        m = tarifa_re.search(g.get("instrucciones_especiales") or "")
        t_instr = None
        if m:
            try:
                t_instr = float(m.group(1).replace(",", "."))
            except ValueError:
                pass
        if t_instr and 0 < t_instr < 50:
            venta = t_instr * kgf
        else:
            total_usd = (num(rr.get("transporte_internacional_usd")) or num(val.get("TarifaUsd"))) + \
                        (num(val.get("HandlingFee")) or num(rr.get("handling_fee"))) / dolar
            venta = (total_usd / kg * kgf) if kg else total_usd
        if seg in ("MercadoLibre", "Retail"):
            venta = costo  # flete a costo, margen se ve en la tienda (Jorge 2026-09-22)

        f_desp = c.get("desp")
        if vid and f_desp:
            desp_vuelo[vid].append(f_desp)
        guias.append({
            "ng": int(ng), "vid": vid or 0, "cas": casilla, "cli": nombre[:30],
            "ej": ejec_por_casilla.get(casilla, "Sin ejecutiva"), "seg": seg,
            "kg": round(kg, 2), "kgv": round(kgv, 2), "kgf": round(kgf, 2),
            "fob": round(num(g.get("costo_producto")), 2), "cif": round(num(val.get("CIF")), 2),
            "adv": round(num(rr.get("advalorem"))), "ag": round(num(rr.get("agente_aduana"))),
            "ex": 1 if g.get("id_tipo_impuesto") == TIPO_IMP_EXENTO else 0,
            "tp": round(num(g.get("total_pagar"))), "dol": round(dolar, 2),
            "venta": round(venta, 2), "costo": round(costo, 2),
            "_lista": c.get("lista"), "_asig": c.get("asig"), "_desp": f_desp,
            "_mcf": c.get("mcf"), "pag": 1 if c.get("lista") else 0,
            "desc": (g.get("descripcion") or "")[:40],
        })

    # estado de cada vuelo: despachado si alguna guía ya tiene despacho a aeropuerto
    for vid, v in vuelos.items():
        ds = desp_vuelo.get(vid)
        v["desp_dt"] = min(ds) if ds else None
    usados = {g["vid"] for g in guias if g["vid"]}
    for vid in list(vuelos):
        v = vuelos[vid]
        if vid not in usados or not v["creado_dt"] or v["creado_dt"] < parse_dt(AWB_DESDE):
            del vuelos[vid]
            continue
        abierto = v["id_estado"] in ESTADOS_AWB_ABIERTO
        if not abierto and not v["desp_dt"]:
            v["desp_dt"] = v["flight_dt"]  # sin historial de despacho: fecha de vuelo declarada
        v["estado"] = "abierto" if abierto else "despachado"
    guias = [g for g in guias if g["vid"] == 0 or g["vid"] in vuelos]

    # ---- probabilidad de vuelo v2 (empírica) ----
    # Para cada guía ya volada en un vuelo regular (COURIER) que tuvo fecha
    # "lista": el vuelo que le correspondía es el primer vuelo regular
    # despachado después de quedar lista. Voló a tiempo si su propio vuelo
    # despachó en o antes de ese. El tramo se mide con la "cartera lista" del
    # cliente en ese momento (todas sus guías listas y aún no despachadas),
    # que es exactamente lo que ve el cliente cuando decide subir o separar.
    regulares = sorted((v["desp_dt"], vid) for vid, v in vuelos.items()
                       if v["tipo"] == "COURIER" and v["desp_dt"])
    desp_times = [t for t, _ in regulares]
    import bisect
    por_cliente = defaultdict(list)
    for g in guias:
        if g["seg"] not in ("MercadoLibre", "Retail") and g["_lista"]:
            por_cliente[g["cas"]].append(g)
    tasa = defaultdict(lambda: [0, 0])
    tasa_cli = defaultdict(lambda: [0, 0])
    for cas, gs in por_cliente.items():
        for g in gs:
            if not g["vid"] or vuelos[g["vid"]]["tipo"] != "COURIER" or not g["_desp"]:
                continue
            i = bisect.bisect_left(desp_times, g["_lista"])
            if i >= len(desp_times):
                continue
            T = desp_times[i]
            a_tiempo = vuelos[g["vid"]]["desp_dt"] <= T
            cartera = [x for x in gs if x["_lista"] and x["_lista"] <= T and (not x["_desp"] or x["_desp"] >= T)]
            fob = sum(x["fob"] for x in cartera)
            key = (tramo(fob), g["ex"], 1 if len(cartera) <= 1 else 0)
            tasa[key][0] += a_tiempo
            tasa[key][1] += 1
            tasa_cli[cas][0] += a_tiempo
            tasa_cli[cas][1] += 1
    tasas = {"|".join(map(str, k)): [ok, n] for k, (ok, n) in tasa.items()}
    tasa_tramo = defaultdict(lambda: [0, 0])
    for (tr, ex, uni), (ok, n) in tasa.items():
        tasa_tramo[tr][0] += ok
        tasa_tramo[tr][1] += n

    # ---- probabilidad de las guías pendientes ----
    abiertos = sorted((v["creado_dt"], vid) for vid, v in vuelos.items()
                      if v["estado"] == "abierto" and v["tipo"] == "COURIER")
    vuelo_objetivo = abiertos[0][1] if abiertos else 0
    # la cartera incluye también las guías con factura sin pago del cliente
    sin_pago = defaultdict(list)
    for g in guias:
        if g["vid"] == 0 and not g["pag"] and g["seg"] not in ("MercadoLibre", "Retail"):
            sin_pago[g["cas"]].append(g)
    for cas in set(por_cliente) | set(sin_pago):
        gs = por_cliente.get(cas, []) + sin_pago.get(cas, [])
        pend = [g for g in gs if g["vid"] == 0]
        if not pend:
            continue
        subidas = [g for g in gs if g["vid"] and vuelos[g["vid"]]["estado"] == "abierto"]
        cartera = pend + subidas
        fob = sum(x["fob"] for x in cartera)
        tr = tramo(fob)
        unica = len(cartera) <= 1
        ok, n = tasa_cli[cas]
        for g in pend:
            if unica or tr == "<500" or g["ex"]:
                regla = "Alta"
            elif tr == "500-3000":
                regla = "Media"
            else:
                regla = "Baja"
            ok_t, n_t = tasa.get((tr, g["ex"], 1 if unica else 0), tasa_tramo[tr])
            p = ok_t / n_t if n_t else None
            if n >= 3 and p is not None:
                p = 0.5 * p + 0.5 * ok / n
            g.update({"fob_cart": round(fob, 2), "tramo": tr, "regla": regla,
                      "p": round(p, 3) if p is not None else None,
                      "cli_hist": f"{ok}/{n}" if n else ""})
    for g in guias:
        if g["vid"] == 0 and "regla" not in g:
            g.update({"fob_cart": g["fob"], "tramo": tramo(g["fob"]), "regla": "Alta", "p": None, "cli_hist": ""})

    # ---- salida ----
    out_vuelos = []
    for vid, v in sorted(vuelos.items(), key=lambda kv: kv[1]["creado_dt"]):
        out_vuelos.append({"id": vid, "awb": v["awb"], "fw": v["fw"], "tipo": v["tipo"],
                           "creado": local(v["creado_dt"]), "desp": local(v["desp_dt"]),
                           "estado": v["estado"], "tarifa": round(v["tarifa"], 3), "tarifa_imp": v["tarifa_imp"]})
    for g in guias:
        g["lista"], g["asig"], g["desp"] = local(g.pop("_lista")), local(g.pop("_asig")), local(g.pop("_desp"))
        g["mcf"] = local(g.pop("_mcf"))
    out = {
        "generado": ahora.astimezone(TZ_CL).strftime("%d-%m-%Y %H:%M"),
        "awb_desde": AWB_DESDE, "vuelo_objetivo": vuelo_objetivo,
        "tarifa_fw": {k: round(v, 3) for k, v in tarifa_fw.items()},
        "tasas": tasas, "tasa_tramo": {k: v for k, v in tasa_tramo.items()},
        "vuelos": out_vuelos, "guias": guias,
    }
    (OUT / "llenado_vuelos.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                                            encoding="utf-8")
    pend = [g for g in guias if g["vid"] == 0]
    print(f"  pendientes: {sum(g['pag'] for g in pend)} listas (pago+factura) + "
          f"{sum(1 - g['pag'] for g in pend)} con factura sin pago")
    print(f"\n{len(out_vuelos)} vuelos ({Counter(v['estado'] for v in out_vuelos)}) · "
          f"{len(guias) - len(pend)} guías en vuelos · {len(pend)} listas sin AWB")
    print(f"  segmentos: {Counter(g['seg'] for g in guias).most_common()}")
    print(f"  ejecutivas: {Counter(g['ej'] for g in guias).most_common()}")
    print(f"  tasa a tiempo por tramo: {dict(tasa_tramo)}")
    print(f"  abiertos: {[(vuelos[v]['awb'], vuelos[v]['fw']) for _, v in abiertos]}  objetivo: {vuelo_objetivo}")


if __name__ == "__main__":
    main()
