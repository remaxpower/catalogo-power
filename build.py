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


# ---------- Páginas de texto simple (para que el agente de WhatsApp/Meta pueda leerlas) ----------
import re, unicodedata

SITE = "https://remaxpower.github.io/catalogo-power"
TXT_HEAD = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="googlebot" content="noindex"><meta name="bingbot" content="noindex">
<title>{title}</title>
<style>body{{font:15px/1.55 system-ui,sans-serif;max-width:860px;margin:0 auto;padding:16px;color:#111}}
h1{{font-size:22px}}h2{{font-size:17px;margin:22px 0 4px}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ddd;padding:6px 4px;text-align:left;vertical-align:top}}a{{color:#0043ff}}
.small{{color:#555;font-size:13px}}</style></head><body>"""
TXT_FOOT = "</body></html>"


def slugify(t):
    t = unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "sin-nombre"


def money(v, cur):
    return f"{cur} {int(v):,}".replace(",", ".") if v else "Consultar"


def facts(p):
    rows = [("Operación", p["op"]), ("Tipo", " ".join(x for x in [p["type"], p["sub"]] if x)),
            ("Dirección (aproximada)", p["addr"]), ("Barrio / zona", p["area"]),
            ("Precio", money(p["price"], p["cur"])),
            ("Expensas", money(p["exp"], p["expCur"]) if p["exp"] else ""),
            ("Ambientes", p["rooms"] or ""), ("Dormitorios", p["beds"] or ""), ("Baños", p["baths"] or ""),
            ("Cocheras", p["park"] or ""), ("Superficie total", f'{p["mTot"]} m²' if p["mTot"] else ""),
            ("Superficie cubierta", f'{p["mCov"]} m²' if p["mCov"] else ""),
            ("Terreno", f'{p["mLand"]} m²' if p["mLand"] else ""),
            ("Antigüedad", f'{datetime.date.today().year - p["year"]} años' if p["year"] else ""),
            ("Apto crédito", "Sí" if p["credit"] else ""), ("Apto profesional", "Sí" if p["pro"] else ""),
            ("Agente", p["agent"]["name"]), ("Teléfono del agente", p["agent"]["phone"]),
            ("Email del agente", p["agent"]["email"]), ("Código", p["code"]),
            ("Publicación oficial", p["url"])]
    return [(k, v) for k, v in rows if v not in ("", None, 0)]


def one_line(p):
    bits = [f'{p["op"]} {p["type"]}'.strip(), p["addr"], p["area"],
            f'{p["rooms"]} amb.' if p["rooms"] else "", f'{p["beds"]} dorm.' if p["beds"] else "",
            f'{p["mTot"]} m²' if p["mTot"] else "", money(p["price"], p["cur"]),
            f'Agente: {p["agent"]["name"]}']
    return " · ".join(b for b in bits if b)


def write_text_pages(props, root, updated):
    esc = html.escape
    root = Path(root)
    (root / "propiedades").mkdir(parents=True, exist_ok=True)
    (root / "agentes").mkdir(parents=True, exist_ok=True)
    for p in props:
        p["_page"] = f"propiedades/{p['slug']}.html"
        rows = "".join(f"<tr><th>{esc(k)}</th><td>{esc(str(v))}</td></tr>" for k, v in facts(p))
        feats = ", ".join(p["feats"])
        body = (f"<h1>{esc(p['title'])}</h1><p>{esc(one_line(p))}</p><table>{rows}</table>"
                + (f"<h2>Descripción</h2><p>{esc(p['desc']).replace(chr(10), '<br>')}</p>" if p["desc"] else "")
                + (f"<h2>Características</h2><p>{esc(feats)}</p>" if feats else "")
                + f"<p class='small'>REMAX Power · José Hernández 2719, CABA · +54 (11) 4787-9300. "
                  f"Datos actualizados el {esc(updated)}. Medidas y valores aproximados; confirmar con el agente.</p>"
                + f"<p><a href='../propiedades/index.html'>Ver todas las propiedades</a></p>")
        (root / p["_page"]).write_text(TXT_HEAD.format(title=esc(p["title"])) + body + TXT_FOOT)

    def listing(ps, title, intro, prefix):
        trs = "".join(
            f"<tr><td><a href='{prefix}{esc(p['_page'])}'>{esc(p['title'])}</a><br>"
            f"<span class='small'>{esc(one_line(p))}</span></td></tr>" for p in ps)
        return (TXT_HEAD.format(title=esc(title)) + f"<h1>{esc(title)}</h1><p>{esc(intro)}</p>"
                f"<p class='small'>Actualizado el {esc(updated)} · {len(ps)} propiedades.</p><table>{trs}</table>" + TXT_FOOT)

    (root / "propiedades" / "index.html").write_text(listing(
        props, "Propiedades publicadas por REMAX Power",
        "Listado completo de propiedades en venta, alquiler y alquiler temporario de REMAX Power (José Hernández 2719, Belgrano, CABA).",
        "../"))
    agents = {}
    for p in props:
        if p["agent"]["name"]:
            agents.setdefault(p["agent"]["name"], []).append(p)
    links = []
    for name, ps in sorted(agents.items()):
        slug = slugify(name)
        (root / "agentes" / slug).mkdir(parents=True, exist_ok=True)
        (root / "agentes" / slug / "index.html").write_text(listing(
            ps, f"Propiedades de {name} · REMAX Power",
            f"Propiedades que comercializa {name}, agente de REMAX Power (José Hernández 2719, Belgrano, CABA).",
            "../../"))
        links.append(f"<tr><td><a href='{slug}/index.html'>{html.escape(name)}</a> ({len(ps)})</td></tr>")
    (root / "agentes" / "index.html").write_text(
        TXT_HEAD.format(title="Agentes de REMAX Power") + "<h1>Agentes de REMAX Power</h1><table>"
        + "".join(links) + "</table>" + TXT_FOOT)
    # Texto plano para subir como documento si hace falta
    txt = [f"PROPIEDADES DE REMAX POWER (actualizado {updated}) - {len(props)} propiedades", ""]
    for p in props:
        txt += [p["title"]] + [f"{k}: {v}" for k, v in facts(p)] + [f"Más info: {SITE}/{p['_page']}", ""]
    (root / "propiedades.txt").write_text("\n".join(txt))
    for p in props:
        p.pop("_page", None)
    return len(agents)


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
    n_ag = write_text_pages(props, out.parent, payload["updated"])
    print(f"OK -> {out} ({out.stat().st_size // 1024} KB) + {len(props)} fichas de texto, {n_ag} agentes", file=sys.stderr)


if __name__ == "__main__":
    main()
