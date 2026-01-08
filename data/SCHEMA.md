# Productions JSON Schema (human-readable)

`/data/productions.json` contains an array of production objects.

## Production object

- `id` (string, required): Stable slug-like identifier.
- `sample` (boolean, required): `true` for sample/demo entries.
- `play` (string, required): Play title (e.g., "Hamlet").
- `production_title` (string, required): Display title for the production.
- `company` (string, required): Producing company or presenter.
- `venue` (string, required): Primary venue or presenting organization.
- `city` (string, required)
- `country` (string, required)
- `start_date` (string, required): ISO date (`YYYY-MM-DD`).
- `end_date` (string, required): ISO date (`YYYY-MM-DD`).
- `is_tour` (boolean, required): `true` if this entry represents a tour (single entry only).
- `themes` (array of strings, required): Curated themes for filtering.
- `synopsis` (string, required): Short factual summary; avoid unsupported staging claims.
- `image_url` (string or null, required): Hotlinked image URL when available.
- `reviews` (array, required): Up to 2–3 review bullets.
  - `outlet` (string, required)
  - `quote` (string, required): Review bullet text (English).
  - `url` (string, required)
  - `language` (string, required)
- `sources` (array of strings, required): All source URLs referenced for the production.
