# Decision Support — Integration Plan

## Target structure

```text
apps/
  web/                         # Next.js UI and feature modules
  api/src/removebg/
    api.py                      # App composition and existing media API
    modules/decision_support/   # New analytics feature, kept independent of media workflows
      presentation/             # FastAPI router and request/response contracts
      application/              # CSV import and review analysis
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
- CSV category values define the catalog categories, allowing products with different specifications to remain separate.
- SQLite stores imported source observations locally. CSV import validates and previews rows before committing them.
- The initial UI supports catalog analysis and evidence comparison; preference-based ranking is deferred until category-specific criteria are defined.
- IndoBERT inference currently uses a TWS aspect taxonomy only. Other categories need their own labeled data and model before AI analysis is enabled.
- Data collection currently uses user-provided CSV. Scraping requires a selected source and review of its allowed access and terms.

## Current entry points

- UI: `apps/web/app/decision-support/page.tsx`
- UI feature: `apps/web/features/decision-support/`
- API router: `apps/api/src/removebg/modules/decision_support/presentation/router.py`
- Data schema/repository: `apps/api/src/removebg/modules/decision_support/infrastructure/`
- Training: `ml/src/decision_support_ml/training/train_absa.py`
- Local database: `data/decision-support.sqlite3`
