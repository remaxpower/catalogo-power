# Catálogo de propiedades REMAX Power

Página interna con todas las propiedades publicadas por REMAX Power en remax.com.ar.
Se actualiza sola todos los días a las 07:00 (hora Argentina) con GitHub Actions.

- `build.py`: descarga listado y fichas desde la API pública de remax.com.ar y arma el HTML.
- `template.html`: diseño de la página.
- `.github/workflows/actualizar.yml`: la tarea diaria.

Actualizar a mano: pestaña **Actions** → "Actualizar catálogo" → **Run workflow**.
Cambiar horario: editar la línea `cron` (está en UTC; 10:00 UTC = 07:00 ART).
