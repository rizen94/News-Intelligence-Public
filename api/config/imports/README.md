# Optional CSV imports for longitudinal macro indices (Phase 2)

Drop vendor exports here (not committed — large files):

- `gpr_export.csv` — Caldara-Iacoviello GPR (columns: month, GPR)
- `epu_export.csv` — Baker-Bloom-Davis EPU (columns: month, EPU)
- `vdem_export.csv` — V-Dem polyarchy (columns: year, country, v2x_polyarchy)
- `freedom_house_export.csv` — Freedom House scores (columns: year, country, score)

Override paths via `GPR_CSV_PATH`, `EPU_CSV_PATH`, `VDEM_CSV_PATH`, and `FREEDOM_HOUSE_CSV_PATH` in `.env`.

FRED/ALFRED series refresh runs via `macro_series_refresh` automation when `FRED_API_KEY` is set.

Tier A trade/resource imports (EIA, Federal Register sample) run when `TRADE_RESOURCES_IMPORT_ENABLED=true` and `EIA_API_KEY` is set (optional).
