#!/usr/bin/env python3
"""Descarga todas las propiedades publicadas por REMAX Power en remax.com.ar
y genera un catálogo HTML autónomo (fotos enlazadas al CDN de RE/MAX).

Uso: python3 build.py [salida.html] [datos.json]
"""
import json, sys, time, html, datetime, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://api-ar.redremax.com/remaxweb-ar/api"
OFFICE_ID = "76e01cd6-407a-43e6-b9ee-fa27fc7b8702"
CDN = "https://d1acdg20u0pmxj.cloudfront.net"
HERE = Path(__file__).resolve().parent

TYPES = {
    "deposito": "Depósito", "consultorio": "Consultorio", "chacra": "Chacra", "quinta": "Quinta",
    "galpon": "Galpón", "cochera": "Cochera", "fondo_de_comercio": "Fondo de comercio", "campo": "Campo",
    "terrenos_y_lotes": "Terreno / lote", "local": "Local", "oficina": "Oficina", "otros": "Otros",
    "edificio": "Edificio", "hotel": "Hotel", "ph": "PH", "casa_triplex": "Casa", "casa_duplex": "Casa",
    "casa": "Casa", "departamento_triplex": "Departamento", "departamento_semipiso": "Departamento",
    "departamento_piso": "Departamento", "departamento_penthouse": "Departamento",
    "departamento_monoambiente": "Departamento", "departamento_loft": "Departamento",
    "departamento_estandar": "Departamento", "departamento_duplex": "Departamento",
}
SUBTYPES = {
    "casa_triplex": "Tríplex", "casa_duplex": "Dúplex", "departamento_triplex": "Tríplex",
    "departamento_semipiso": "Semipiso", "departamento_piso": "Piso", "departamento_penthouse": "Penthouse",
    "departamento_monoambiente": "Monoambiente", "departamento_loft": "Loft", "departamento_duplex": "Dúplex",
}
OPS = {"sale": "Venta", "rent": "Alquiler", "temporal": "Temporario"}


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PowerCatalogo/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def fetch_list():
    items, page = [], 0
    while True:
        url = (f"{API}/listings/findAllWithEntrepreneurships?page={page}&pageSize=100&sort=-createdAt"
               f"&in=operationId:1,2,3&eq=officeId:{OFFICE_ID}")
        d = get(url)["data"]
        items += d["data"]
        page += 1
        if page >= d["totalPages"]:
            return items, d["totalItems"]


def fetch_detail(item):
    try:
        time.sleep(0.15)
        return get(f"{API}/listings/findBySlug/{item['slug']}")["data"] or item
    except Exception:
        return item


def photo(raw, size="1080xAUTO"):
    parts = raw.split("/")  # listings/<id>/<photo>
    return f"{CDN}/{parts[0]}/{parts[1]}/{size}/{parts[2]}.jpg"


def agent_photo(a):
    raw = a.get("rawPhoto") or ""
    parts = raw.split("/")
    if len(parts) == 3:
        return f"{CDN}/{parts[0]}/{parts[1]}/180x180/{parts[2]}.webp"
    return f"{CDN}/{a['photo']}" if a.get("photo") else ""


def num(v):
    try:
        v = float(v or 0)
        return int(v) if v.is_integer() else round(v, 2)
    except (TypeError, ValueError):
        return 0


def compact(d):
    t = (d.get("type") or {}).get("value", "otros")
    op = (d.get("operation") or {}).get("value", "")
    a = d.get("associate") or {}
    phone = next((p["value"] for p in a.get("phones") or [] if p.get("primary")), None) or \
        ((a.get("phones") or [{}])[0].get("value") if a.get("phones") else "")
    email = next((e["value"] for e in a.get("emails") or [] if e.get("primary")), "")
    geo = d.get("geo") or {}
    loc = (d.get("location") or {}).get("coordinates") or []
    photos = [photo(p["rawValue"]) for p in sorted(d.get("photos") or [], key=lambda p: p.get("position") or 0)
              if p.get("rawValue")]
    feats = [f.get("value") for f in d.get("features") or [] if f.get("value")]
    return {
        "id": d.get("id"), "slug": d.get("slug"), "code": d.get("internalId"),
        "title": (d.get("title") or "").strip(), "desc": (d.get("description") or "").strip(),
        "op": OPS.get(op, op), "type": TYPES.get(t, t.replace("_", " ").title()), "sub": SUBTYPES.get(t, ""),
        "price": num(d.get("price")) if d.get("priceExposure", True) else 0,
        "cur": (d.get("currency") or {}).get("value", ""),
        "exp": num(d.get("expensesPrice")), "expCur": (d.get("expensesCurrency") or {}).get("value", ""),
        "addr": d.get("displayAddress") or "", "area": (geo.get("label") or "").replace(", Capital Federal", ", CABA"),
        "rooms": num(d.get("totalRooms")), "beds": num(d.get("bedrooms")), "baths": num(d.get("bathrooms")),
        "park": num(d.get("parkingSpaces")), "year": num(d.get("yearBuilt")),
        "mTot": num(d.get("dimensionTotalBuilt")), "mCov": num(d.get("dimensionCovered")),
        "mLand": num(d.get("dimensionLand")),
        "credit": bool(d.get("aptCredit")), "pro": bool(d.get("professionalUse")),
        "feats": feats, "photos": photos, "video": d.get("video") or "",
        "lat": loc[1] if len(loc) == 2 else None, "lng": loc[0] if len(loc) == 2 else None,
        "agent": {"name": (a.get("name") or "").strip(), "phone": phone or "", "email": email,
                  "photo": agent_photo(a)},
        "url": f"https://www.remax.com.ar/listings/{d.get('slug')}",
    }


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "propiedades-power.html"
    data_out = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "propiedades-power.json"
    items, total = fetch_list()
    print(f"Listado: {len(items)} de {total}", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=6) as ex:
        details = list(ex.map(fetch_detail, items))
    props = [compact(d) for d in details]
    full = sum(1 for d in details if "description" in d)
    print(f"Detalle completo: {full}/{len(props)}", file=sys.stderr)
    if len(props) < 0.8 * total:
        sys.exit("Faltan demasiadas propiedades; no se actualiza el catálogo.")
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    payload = {"updated": now.strftime("%d/%m/%Y %H:%M"), "total": len(props), "items": props}
    out.parent.mkdir(parents=True, exist_ok=True)
    data_out.parent.mkdir(parents=True, exist_ok=True)
    data_out.write_text(json.dumps(payload, ensure_ascii=False))
    tpl = (HERE / "template.html").read_text()
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(tpl.replace("__DATA__", blob))
    print(f"OK -> {out} ({out.stat().st_size // 1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
