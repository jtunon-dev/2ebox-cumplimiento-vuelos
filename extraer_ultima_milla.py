"""
Extrae de NocoDB la última milla de las guías 2ebox (2026) y las clasifica por
courier: DropGo (guia_hijas.ultima_milla == 2, confirmado 100% RM) vs Bluexpress
(ultima_milla == 1, mayoría regiones + sobredimensionados RM). ultima_milla -1/0
= sin courier asignado (entrega personal / retiro en bodega / pendiente).

Por guía calcula los tramos de última milla con los estados del sistema 2ebox
(guias_hijas_estados_historial):
  18 En Bodega 2ebox Chile  ->  20 En despacho  ->  21 Entregado
  (+ 26 Reagendado, 28 Entrega Fallida, 29 Enviado a CD como incidencias)

SLA (promesa 2ebox): entrega same-day 90%, next-day el 10% restante.
El "day" se evalúa en hora de Chile (UTC-3 oct-mar, UTC-4 abr-sep).
OJO: el reloj real del SLA de DropGo arranca cuando DropGo ingiere la orden
("Listo para envío"), que suele ser ~1 día después del estado 20 de 2ebox
-> este cálculo desde el estado 20 es una cota superior. El detalle fino
(eventos internos DropGo) requiere el portal app.dropgo.cl (token de sesión).

Salida: data/ultima_milla.json
"""
import json
import os
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

TBL_GUIA_HIJAS = "m4b0yh4lwpxsvri"
TBL_HIST_ESTADOS = "mgzgcbyxeu7225b"
TBL_DIRECCIONES = "m4sgieddhip29md"

COURIER = {2: "DropGo", 1: "Bluexpress"}
EST = {18: "en_bodega_cl", 20: "en_despacho", 21: "entregado",
       26: "reagendado", 28: "entrega_fallida", 29: "enviado_cd"}
N_GUIA_MIN = 157000          # ~inicio 2026
OUT = Path(__file__).parent / "data"


def noco_fetch_all(table_id, where="", fields="", label=""):
    rows, offset = [], 0
    while True:
        p = f"limit=1000&offset={offset}"
        if where:
            p += "&where=" + urllib.parse.quote(where)
        if fields:
            p += "&fields=" + fields
        req = urllib.request.Request(f"{NOCO_URL}/{NOCO_BASE}/{table_id}?{p}", headers={"xc-token": NOCO_TOKEN})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
        b = d.get("list", [])
        rows += b
        offset += len(b)
        print(f"  {label} {offset}/{d['pageInfo']['totalRows']}", flush=True)
        if offset >= d["pageInfo"]["totalRows"] or not b:
            break
    return rows


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def a_chile(dt):
    if dt is None:
        return None
    off = -3 if dt.month in (1, 2, 3, 10, 11, 12) else -4  # DST aproximado
    return dt + timedelta(hours=off)


def horas(a, b):
    if a is None or b is None:
        return None
    h = (b - a).total_seconds() / 3600
    return round(h, 2) if -1 < h < 24 * 120 else None


def dias_calendario(a, b):
    """Diferencia en días calendario (fecha de b − fecha de a) en hora Chile.
    0 = same day, 1 = next day, ..."""
    ca, cb = a_chile(a), a_chile(b)
    if ca is None or cb is None:
        return None
    d = (cb.date() - ca.date()).days
    return d if 0 <= d <= 120 else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    print("[1/3] guia_hijas (entregadas 2026) ...")
    gh = noco_fetch_all(
        TBL_GUIA_HIJAS,
        where=f"(n_guia,gte,{N_GUIA_MIN})~and(id_estado,eq,21)",
        fields="n_guia,ultima_milla,id_direccion,id_cliente,ancho,alto,largo,peso",
        label="guia_hijas",
    )
    gmap = {r["n_guia"]: r for r in gh if r.get("n_guia")}
    print(f"  {len(gmap)} guías entregadas")

    print("[2/3] direcciones (comuna/región) ...")
    dir_ids = list({r["id_direccion"] for r in gh if r.get("id_direccion")})
    dmap = {}
    for i in range(0, len(dir_ids), 200):
        lote = dir_ids[i:i + 200]
        w = "(id,in," + ",".join(str(x) for x in lote) + ")"
        for r in noco_fetch_all(TBL_DIRECCIONES, where=w, fields="id,comunas,regiones", label=f"dir {i}"):
            dmap[r["id"]] = {
                "comuna": (r.get("comunas") or {}).get("nombre"),
                "region": (r.get("regiones") or {}).get("nombre"),
            }

    print("[3/3] historial de estados (última milla) ...")
    hist = noco_fetch_all(
        TBL_HIST_ESTADOS,
        where=f"(id_guia_hija,gte,{N_GUIA_MIN})",
        fields="id_guia_hija,id_estado,fecha",
        label="hist",
    )
    # primera fecha de cada estado relevante por guía
    por_guia = defaultdict(dict)
    for h in hist:
        e = h.get("id_estado")
        if e not in EST:
            continue
        ng = h.get("id_guia_hija")
        dt = parse_dt(h.get("fecha"))
        if dt is None:
            continue
        k = EST[e]
        if k not in por_guia[ng] or dt < por_guia[ng][k]:
            por_guia[ng][k] = dt

    registros = []
    cnt_courier = Counter()
    for ng, r in gmap.items():
        um = r.get("ultima_milla")
        courier = COURIER.get(um, "Sin courier / otro" if um in (-1, 0) else f"cod {um}")
        di = dmap.get(r.get("id_direccion"), {})
        region = di.get("region") or "?"
        comuna = di.get("comuna") or "?"
        rm = region == "METROPOLITANA DE SANTIAGO"
        h = por_guia.get(ng, {})
        f_bod, f_desp, f_ent = h.get("en_bodega_cl"), h.get("en_despacho"), h.get("entregado")
        dmax = max((r.get("ancho") or 0), (r.get("alto") or 0), (r.get("largo") or 0))
        sobredim = dmax > 80 or (r.get("peso") or 0) > 25

        ent_dc = dias_calendario(f_desp, f_ent)   # días calendario despacho -> entrega
        registros.append({
            "n_guia": ng,
            "courier": courier,
            "region": region,
            "comuna": comuna,
            "zona": "RM" if rm else ("?" if region == "?" else "Regiones"),
            "peso": round(r.get("peso") or 0, 2),
            "sobredim": sobredim,
            "mes": (a_chile(f_desp) or a_chile(f_ent)).strftime("%Y-%m") if (f_desp or f_ent) else None,
            "h_bod_desp": horas(f_bod, f_desp),
            "h_desp_ent": horas(f_desp, f_ent),
            "h_bod_ent": horas(f_bod, f_ent),
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

    meta = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_guia_min": N_GUIA_MIN,
        "n_registros": len(registros),
        "por_courier": cnt_courier.most_common(),
    }
    (OUT / "ultima_milla.json").write_text(
        json.dumps({"meta": meta, "rows": registros}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")

    # --- resumen en consola (DropGo) ---
    dg = [x for x in registros if x["courier"] == "DropGo" and x["dias_desp_ent"] is not None]
    print(f"\n=== DropGo: {len(dg)} guías entregadas con tramo despacho->entrega ===")
    sla = Counter(x["sla"] for x in dg)
    tot = len(dg)
    for k in ("same_day", "next_day", "d2", "d3+"):
        print(f"  {k:9}: {sla[k]:5}  ({100*sla[k]/tot:.1f}%)")
    hh = sorted(x["h_desp_ent"] for x in dg if x["h_desp_ent"] is not None)
    if hh:
        print(f"  horas despacho->entrega: mediana {hh[len(hh)//2]:.1f} h  p90 {hh[int(len(hh)*.9)]:.1f} h")
    print(f"  reagendadas: {sum(x['reagendado'] for x in dg)}  |  entrega fallida: {sum(x['entrega_fallida'] for x in dg)}")
    print("\n  Top comunas DropGo (n, %same-day):")
    by_com = defaultdict(list)
    for x in dg:
        by_com[x["comuna"]].append(x)
    for com, xs in sorted(by_com.items(), key=lambda kv: -len(kv[1]))[:15]:
        sd = sum(1 for x in xs if x["sla"] == "same_day")
        print(f"    {com:20} n={len(xs):4}  same-day {100*sd/len(xs):5.1f}%")
    print(f"\n-> data/ultima_milla.json  ({len(registros)} guías)")
    print("   por courier:", cnt_courier.most_common())


if __name__ == "__main__":
    main()
