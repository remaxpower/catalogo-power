# Catálogo de propiedades REMAX Power

Página interna con todas las propiedades publicadas por REMAX Power en remax.com.ar.
Se actualiza sola todos los días a las 07:00 (hora Argentina) con GitHub Actions.

- `build.py`: descarga listado y fichas desde la API pública de remax.com.ar y arma el HTML.
- `template.html`: diseño de la página.
- `.github/workflows/actualizar.yml`: la tarea diaria.

Actualizar a mano: pestaña **Actions** → "Actualizar catálogo" → **Run workflow**.
Cambiar horario: editar la línea `cron` (está en UTC; 10:00 UTC = 07:00 ART).

## Todo RE/MAX (sección /remax)

Página aparte, vinculada desde el catálogo de Power (botón "Todo REMAX"), con las ~70.000 propiedades activas de toda la red en remax.com.ar.

build_remax.py: baja el listado completo, lo divide en un archivo por provincia (site/remax/data) y copia template_remax.html. La descripción y todas las fotos de cada propiedad se traen en vivo al abrir la ficha. Si la descarga falla, se vuelve a publicar la versión anterior.
template_remax.html: diseño de la página (mismo estilo que el de Power).

