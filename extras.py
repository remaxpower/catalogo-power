#!/usr/bin/env python3
"""
Genera, a partir de propiedades.json (lo arma build.py), los archivos que usa
el agente de IA de WhatsApp Business / Meta:

  feed.csv          -> feed de catálogo para Meta Commerce Manager (programado, diario)
  listado.html      -> listado completo en HTML simple (fuente "sitio web" del agente)
  listado.txt       -> mismo listado en texto plano (por si se quiere subir como documento)
  fichas/<id>.html  -> una página simple por propiedad (link de cada producto del catálogo)
  sitemap.xml       -> índice de todas las páginas

Uso: python3 extras.py <carpeta_site> <url_base>
Ej.: python3 extras.py site https://remaxpower.github.io/catalogo-power
"""
import csv, html, json, re, sys
from pathlib import Path

OFICINA = "RE/MAX Power"
OFI_DIR = "José Hernández 2719, Belgrano, CABA"
OFI_TEL = "+54 11 4787-9300"


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def fmt_int(v):
    return f"{int(round(num(v))):,}".replace(",", ".")


def fmt_m2(v):
    n = num(v)
    if not n:
        return ""
    s = f"{n:,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " m²"


def precio_txt(p):
    pr = num(p.get("price"))
    if pr <= 0:
        return "Consultar precio"
    txt = f"{p.get('cur') or ''} {fmt_int(pr)}".strip()
    if p.get("op") == "Alquiler":
        txt += " por mes"
    return txt


def expensas_txt(p):
    e = num(p.get("exp"))
    return f"{p.get('expCur') or 'ARS'} {fmt_int(e)}" if e > 0 else ""


def ficha_id(p):
    base = p.get("code") or p.get("id")
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(base)).strip("-")


def operacion_txt(op):
    return {"Venta": "en venta", "Alquiler": "en alquiler", "Temporario": "en alquiler temporario"}.get(op, op or "")


def datos(p):
    """Lista (etiqueta, valor) con los datos clave, sin vacíos."""
    out = [
        ("Operación", p.get("op")),
        ("Tipo", " / ".join(x for x in [p.get("type"), p.get("sub")] if x)),
        ("Precio", precio_txt(p)),
        ("Expensas", expensas_txt(p)),
        ("Dirección", p.get("addr")),
        ("Barrio / zona", p.get("area")),
        ("Superficie total", fmt_m2(p.get("mTot"))),
        ("Superficie cubierta", fmt_m2(p.get("mCov"))),
        ("Superficie terreno", fmt_m2(p.get("mLand"))),
        ("Ambientes", fmt_int(p["rooms"]) if num(p.get("rooms")) else ""),
        ("Dormitorios", fmt_int(p["beds"]) if num(p.get("beds")) else ""),
        ("Baños", fmt_int(p["baths"]) if num(p.get("baths")) else ""),
        ("Cocheras", fmt_int(p["park"]) if num(p.get("park")) else ""),
        ("Año de construcción", str(int(num(p["year"]))) if num(p.get("year")) > 1800 else ""),
        ("Apto crédito", "Sí" if p.get("credit") else ""),
        ("Apto profesional", "Sí" if p.get("pro") else ""),
        ("Código", p.get("code")),
    ]
    return [(k, v) for k, v in out if v]


def titulo(p):
    t = (p.get("title") or "").strip()
    if t.isupper():
        t = t.capitalize()
    if not t:
        t = f"{p.get('type', 'Propiedad')} {operacion_txt(p.get('op'))} en {p.get('area', '')}"
    return t[:150]


def resumen(p):
    partes = [f"{p.get('type', 'Propiedad')} {operacion_txt(p.get('op'))}"]
    if p.get("area"):
        partes.append(p["area"])
    if num(p.get("rooms")):
        partes.append(f"{fmt_int(p['rooms'])} amb.")
    if num(p.get("mTot")):
        partes.append(fmt_m2(p["mTot"]))
    partes.append(precio_txt(p))
    return " · ".join(partes)


def agente_txt(p):
    a = p.get("agent") or {}
    return ", ".join(x for x in [a.get("name"), a.get("phone"), a.get("email")] if x)


# ---------------------------------------------------------------- feed Meta
def feed(items, base, out):
    cols = ["id", "title", "description", "availability", "condition", "price", "link",
            "image_link", "additional_image_link", "brand", "product_type",
            "custom_label_0", "custom_label_1", "custom_label_2", "custom_label_3"]
    salteadas = 0
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for p in items:
            fotos = [x for x in (p.get("photos") or []) if x]
            pr = num(p.get("price"))
            # Meta exige precio e imagen
            if not fotos or pr <= 0 or not p.get("cur"):
                salteadas += 1
                continue
            lineas = [resumen(p), ""]
            lineas += [f"{k}: {v}" for k, v in datos(p)]
            if p.get("feats"):
                lineas.append("Características: " + ", ".join(p["feats"]))
            if agente_txt(p):
                lineas.append(f"Agente: {agente_txt(p)}")
            lineas += ["", (p.get("desc") or "").strip()]
            desc = "\n".join(lineas).strip()[:9000]
            w.writerow({
                "id": ficha_id(p),
                "title": titulo(p),
                "description": desc,
                "availability": "in stock",
                "condition": "new",
                "price": f"{pr:.2f} {p['cur']}",
                "link": f"{base}/fichas/{ficha_id(p)}.html",
                "image_link": fotos[0],
                "additional_image_link": ",".join(fotos[1:11]),
                "brand": OFICINA,
                "product_type": " > ".join(x for x in [p.get("op"), p.get("type"), p.get("area")] if x),
                "custom_label_0": p.get("op") or "",
                "custom_label_1": p.get("type") or "",
                "custom_label_2": p.get("area") or "",
                "custom_label_3": f"{fmt_int(p['rooms'])} ambientes" if num(p.get("rooms")) else "",
            })
    return salteadas


# ---------------------------------------------------------------- HTML simple
CSS = """body{font-family:system-ui,Arial,sans-serif;max-width:860px;margin:0 auto;padding:16px;color:#1a1a1a;line-height:1.5}
h1{font-size:1.5rem;color:#003da5}h2{font-size:1.15rem;margin-top:1.6em}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}
th{width:38%;color:#555;font-weight:600}img{max-width:100%;height:auto;border-radius:8px}
.fotos{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px}
a{color:#003da5}.desc{white-space:pre-line}li{margin:.4em 0}"""


def pagina(title, body, desc=""):
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">
<style>{CSS}</style></head><body>
{body}
<hr><p>{esc(OFICINA)} · {esc(OFI_DIR)} · Tel. {esc(OFI_TEL)}</p>
</body></html>
"""


def ficha_html(p, base):
    filas = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in datos(p))
    fotos = "".join(f'<img src="{esc(u)}" alt="{esc(titulo(p))} - foto {i+1}" loading="lazy">'
                    for i, u in enumerate((p.get("photos") or [])[:12]))
    feats = ", ".join(p.get("feats") or [])
    a = p.get("agent") or {}
    body = f"""<p><a href="{base}/listado.html">← Todas las propiedades</a></p>
<h1>{esc(titulo(p))}</h1>
<p><strong>{esc(resumen(p))}</strong></p>
<table>{filas}</table>
{f'<h2>Características</h2><p>{esc(feats)}</p>' if feats else ''}
<h2>Descripción</h2><div class="desc">{esc((p.get('desc') or '').strip())}</div>
<h2>Agente</h2><p>{esc(a.get('name', ''))}{(' · ' + esc(a.get('phone'))) if a.get('phone') else ''}{(' · ' + esc(a.get('email'))) if a.get('email') else ''}</p>
{f'<p><a href="{esc(p["url"])}">Ver publicación en remax.com.ar</a></p>' if p.get('url') else ''}
<h2>Fotos</h2><div class="fotos">{fotos}</div>"""
    return pagina(f"{titulo(p)} | {OFICINA}", body, resumen(p))


def listado(items, base, updated):
    grupos = {}
    for p in items:
        grupos.setdefault(p.get("op") or "Otras", []).append(p)
    orden = [g for g in ["Venta", "Alquiler", "Temporario"] if g in grupos] + \
            [g for g in grupos if g not in ("Venta", "Alquiler", "Temporario")]
    h = [f"<h1>Propiedades de {esc(OFICINA)}</h1>",
         f"<p>{len(items)} propiedades publicadas. Actualizado: {esc(updated)}. "
         "Cada propiedad tiene su ficha con todos los datos.</p>"]
    t = [f"PROPIEDADES DE {OFICINA} — {len(items)} publicadas — actualizado {updated}",
         f"Oficina: {OFI_DIR} · Tel. {OFI_TEL}", ""]
    for g in orden:
        ps = sorted(grupos[g], key=lambda p: (p.get("type") or "", p.get("area") or "", num(p.get("price"))))
        h.append(f"<h2>{esc(g)} ({len(ps)})</h2><ul>")
        t += [f"=== {g.upper()} ({len(ps)}) ===", ""]
        for p in ps:
            url = f"{base}/fichas/{ficha_id(p)}.html"
            extra = " · ".join(x for x in [p.get("addr"), f"Expensas {expensas_txt(p)}" if expensas_txt(p) else "",
                                           f"{fmt_int(p['beds'])} dorm." if num(p.get("beds")) else "",
                                           f"{fmt_int(p['baths'])} baños" if num(p.get("baths")) else "",
                                           f"{fmt_int(p['park'])} cochera(s)" if num(p.get("park")) else "",
                                           "Apto crédito" if p.get("credit") else "",
                                           f"Cód. {p.get('code')}"] if x)
            h.append(f'<li><a href="{url}">{esc(titulo(p))}</a> — {esc(resumen(p))}. {esc(extra)}</li>')
            t.append(f"- {titulo(p)} | {resumen(p)} | {extra} | {url}")
        h.append("</ul>")
        t.append("")
    return pagina(f"Propiedades {OFICINA}", "\n".join(h), f"Listado completo de propiedades de {OFICINA}"), "\n".join(t)


def main():
    site = Path(sys.argv[1] if len(sys.argv) > 1 else "site")
    base = (sys.argv[2] if len(sys.argv) > 2 else "https://remaxpower.github.io/catalogo-power").rstrip("/")
    data = json.loads((site / "propiedades.json").read_text(encoding="utf-8"))
    items = data["items"] if isinstance(data, dict) else data
    updated = data.get("updated", "") if isinstance(data, dict) else ""

    salteadas = feed(items, base, site / "feed.csv")

    fdir = site / "fichas"
    fdir.mkdir(parents=True, exist_ok=True)
    urls = [f"{base}/", f"{base}/listado.html"]
    for p in items:
        (fdir / f"{ficha_id(p)}.html").write_text(ficha_html(p, base), encoding="utf-8")
        urls.append(f"{base}/fichas/{ficha_id(p)}.html")

    lh, lt = listado(items, base, updated)
    (site / "listado.html").write_text(lh, encoding="utf-8")
    (site / "listado.txt").write_text(lt, encoding="utf-8")
    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{esc(u)}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")

    print(f"extras: {len(items)} propiedades · feed con {len(items) - salteadas} (salteadas sin precio/foto: {salteadas}) · {len(items)} fichas")


if __name__ == "__main__":
    main()
