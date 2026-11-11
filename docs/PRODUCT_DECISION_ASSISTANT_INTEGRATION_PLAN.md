# Decision Support — Integration Plan

## Target structure

```text
apps/
  web/                         # Next.js UI and feature modules
  api/src/removebg/
    api.py                      # App composition and existing media API
    modules/decision_support/   # New analytics feature, kept independent of media workflows
      presentation/             # FastAPI router and request/response contracts
      application/              # CSV import, review analysis, recommendations
      domain/                   # Taxonomy and text rules
      infrastructure/           # SQLite schema and repositories
      integrations/ml/          # Local model adapter
ml/
  src/decision_support_ml/training/
  data/{raw,interim,processed}/
  artifacts/
  reports/
```

`apps/api/src/removebg/api.py` stays the composition root. It registers the `/api/v1/decision-support` router; business rules and data access live in the `decision_support` module. The frontend route is `/decision-support`, with UI and API client under `apps/web/features/decision-support`. ML training code and generated artifacts live under `ml/`.

## Boundaries

- Keep the existing media tools in their current backend and UI flows; the new feature has its own route, API prefix, database, and feature UI.
- The first category is TWS, but code and route names describe the capability rather than a specific catalog entity.
- SQLite stores imported source observations locally. CSV import validates and previews rows before committing them.
- SAW recommendation logic is in the application layer and reports criterion contributions and evidence coverage.
- IndoBERT inference is behind an ML adapter. The model is unavailable until the user supplies a labeled dataset and trains it; no predictions are fabricated.

## Current entry points

- UI: `apps/web/app/decision-support/page.tsx`
- UI feature: `apps/web/features/decision-support/`
- API router: `apps/api/src/removebg/modules/decision_support/presentation/router.py`
- Data schema/repository: `apps/api/src/removebg/modules/decision_support/infrastructure/`
- Training: `ml/src/decision_support_ml/training/train_absa.py`
- Local database: `data/decision-support.sqlite3`
