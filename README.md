# Shakespeare-2025

## Automated production updates

This repo includes a no-billing updater that discovers candidate 2025 Shakespeare productions using the GDELT DOC 2.1 API. It writes to `docs/data/productions.json`, preserving manual fields like `themes`, `synopsis`, and `reviews`.

### Run locally

```bash
python scripts/update_productions.py
```

Optional flags:

```bash
python scripts/update_productions.py --max-articles-per-play 10 --max-records 100
```

### Sources seed list

`data/sources.yaml` contains a starter list of major theatre companies and festivals. Add more by appending entries with `name`, `url`, and optional `region`/`notes`. The file is YAML-compatible JSON, so any standard JSON list entry is valid.

### Editorial review

New entries are marked `needs_editorial: true` and leave `staging_description` blank unless there is source support. Add or edit themes, synopsis, staging details, and review bullets after verification.

### Scheduled updates

GitHub Actions runs the updater weekly and opens a pull request with any changes. Review the PR before merging to main.
