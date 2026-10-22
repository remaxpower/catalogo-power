#!/usr/bin/env python3
"""Catálogo de TODO RE/MAX Argentina (sección aparte del catálogo de Power).

Descarga el listado completo de propiedades activas de remax.com.ar (unas 70.000),
lo divide en un archivo por provincia y arma la página con buscador y filtros.
La ficha completa (descripción y todas las fotos) se trae en vivo al abrir cada
propiedad, así no hace falta bajar 70.000 fichas por día.

Si la descarga falla, copia la última versión publicada para no dejar la sección vacía.

Uso: python3 build_remax.py <carpeta_salida> [url_publicada]
Ej.: python3 build_remax.py site/remax https://remaxpower.github.io/catalogo-power/remax
"""
import json, sys, time, re, datetime, unicodedata, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://api-ar.redremax.com/remaxweb-ar/api"
HERE = Path(__file__).resolve().parent
PAGE_SIZE = 500
OPS = {"sale": 0, "rent": 1, "temporal": 2}
CURS = {"USD": 0, "ARS": 1}


def get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PowerCatalogo/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionError):
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def page_url(n):
    return (f"{API}/listings/findAllWithEntrepreneurships?page={n}&pageSize={PAGE_SIZE}"
            f"&sort=-createdAt&in=operationId:1,2,3")


def slugify(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "otros"


def num(v):
    try:
        v = float(v or 0)
        return int(v) if v.is_integer() else round(v, 2)
    except (TypeError, ValueError):
        return 0


def fetch_all():
    first = get(page_url(0))["data"]
    pages, total = first["totalPages"], first["totalItems"]
    with ThreadPoolExecutor(max_workers=6) as ex:
        rest = list(ex.map(lambda n: get(page_url(n))["data"]["data"], range(1, pages)))
    seen, items = set(), []
    for chunk in [first["data"]] + rest:
        for x in chunk:
            if x.get("id") not in seen:
                seen.add(x.get("id"))
                items.append(x)
    return items, total


def build(out):
    items, total = fetch_all()
    print(f"Listado: {len(items)} de {total}", file=sys.stderr)
    if len(items) < 0.9 * total or len(items) < 1000:
        raise RuntimeError("Faltan demasiadas propiedades")

    offices, office_idx = [], {}
    provs = {}  # nombre -> {"agents": [], "aidx": {}, "items": []}
    for x in items:
        a = x.get("associate") or {}
        oname = (a.get("officeName") or "Sin oficina").strip()
        if oname not in office_idx:
            office_idx[oname] = len(offices)
            offices.append(oname)
        geo = (x.get("geoLabel") or "").replace("Capital Federal", "CABA")
        parts = [p.strip() for p in geo.split(",") if p.strip()]
        prov = parts[-1] if parts else "Sin ubicación"
        P = provs.setdefault(prov, {"agents": [], "aidx": {}, "items": []})
        aid = a.get("id") or oname
        if aid not in P["aidx"]:
            phone = next((p["value"] for p in a.get("phones") or [] if p.get("isPrimary")), None) or \
                ((a.get("phones") or [{}])[0].get("value", "") if a.get("phones") else "")
            email = next((e["value"] for e in a.get("emails") or [] if e.get("isPrimary")), "") or \
                ((a.get("emails") or [{}])[0].get("value", "") if a.get("emails") else "")
            raw = (a.get("rawPhoto") or "").split("/")
            P["aidx"][aid] = len(P["agents"])
            P["agents"].append([(a.get("name") or "").strip(), phone or "", email or "",
                                f"{raw[1]}/{raw[2]}" if len(raw) == 3 else "", office_idx[oname]])
        ent = bool(x.get("entrepreneurship"))
        price = num(x.get("price")) if x.get("priceExposure", True) else 0
        cur = ((x.get("ecurrency") if ent else None) or x.get("currency") or {}).get("value", "")
        ph = (x.get("photos") or [{}])[0].get("rawValue", "") if x.get("photos") else ""
        ph = "/".join(ph.split("/")[1:3]) if ph.count("/") == 2 else ""
        loc = (x.get("location") or {}).get("coordinates") or []
        P["items"].append([
            x.get("slug") or "", x.get("internalId") or "", (x.get("title") or "").strip(),
            OPS.get((x.get("operation") or {}).get("value"), 0), (x.get("type") or {}).get("value", "otros"),
            price, CURS.get(cur, cur), num(x.get("expensesPrice")),
            CURS.get((x.get("expensesCurrency") or {}).get("value", ""), ""),
            (x.get("displayAddress") or "").strip(), ", ".join(parts[:-1]),
            num(x.get("totalRooms")), num(x.get("bedrooms")), num(x.get("bathrooms")),
            num(x.get("dimensionTotalBuilt")), num(x.get("dimensionCovered")), num(x.get("dimensionLand")),
            round(loc[1], 5) if len(loc) == 2 else 0, round(loc[0], 5) if len(loc) == 2 else 0,
            ph, P["aidx"][aid], 1 if ent else 0,
        ])

    out.mkdir(parents=True, exist_ok=True)
    (out / "data").mkdir(exist_ok=True)
    for old in (out / "data").glob("*.json"):
        old.unlink()
    plist = []
    for name, P in sorted(provs.items(), key=lambda kv: -len(kv[1]["items"])):
        slug = slugify(name)
        (out / "data" / f"{slug}.json").write_text(
            json.dumps({"agents": P["agents"], "items": P["items"]}, ensure_ascii=False, separators=(",", ":")))
        plist.append({"name": name, "slug": slug, "n": len(P["items"])})
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    meta = {"updated": now.strftime("%d/%m/%Y %H:%M"), "total": len(items), "provinces": plist, "offices": offices}
    (out / "data" / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
    (out / "index.html").write_text((HERE / "template_remax.html").read_text())
    print(f"OK -> {out} ({len(plist)} provincias, {len(offices)} oficinas)", file=sys.stderr)


def restore_previous(out, base):
    """Si falla la descarga, vuelve a publicar la última versión que estaba online."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "data").mkdir(exist_ok=True)
    meta = get(f"{base}/data/meta.json")
    (out / "data" / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
    for p in meta["provinces"]:
        d = get(f"{base}/data/{p['slug']}.json")
        (out / "data" / f"{p['slug']}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
    (out / "index.html").write_text((HERE / "template_remax.html").read_text())
    print(f"Se republicó la versión anterior ({meta['updated']})", file=sys.stderr)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "site" / "remax"
    base = sys.argv[2] if len(sys.argv) > 2 else ""
    try:
        build(out)
    except Exception as e:
        print(f"No se pudo actualizar todo RE/MAX: {e}", file=sys.stderr)
        if not base:
            raise
        restore_previous(out, base)


if __name__ == "__main__":
    main()
