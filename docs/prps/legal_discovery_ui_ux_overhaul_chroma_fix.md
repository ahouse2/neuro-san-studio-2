name: "PRP Entry — Legal Discovery UI/UX Overhaul & Chroma Fix"
description: |
  Detailed notes capturing the work performed to stabilize the Legal Discovery app
  and dramatically improve its user experience. These notes serve as a
  contextual memory bank for future developers or autonomous agents tasked
  with continuing this project. Follow this guide to understand the
  motivations behind each change, how to reproduce the environment locally,
  and what remains to be done.

---

## Goals

- Resolve the persistent ChromaDB startup/connection issue that caused the entire
  stack to crash during document ingestion and vector operations.
- Elevate the UI/UX from a cramped, low‑fidelity webapp to a polished, luxury
  dashboard with a dedicated sidebar, increased spacing, and a dark navy + cyan palette.
- Document every significant change and provide a self‑contained roadmap for future work.

## Why

- ChromaDB previously depended on a PostgreSQL backend via environment variables in `docker-compose.yml`.
  Startup would fail when the Postgres instance was unavailable, crashing the app. Switching to an embedded
  DuckDB backend eliminates this brittleness and simplifies local development.
- The existing dashboard was cluttered: tabs were squeezed into a scrolling list and the content area lacked breathing room.
  Power users juggle many tools, so a structured layout with a persistent navigation sidebar improves orientation
  and reduces cognitive load.
- Capturing context in this PRP entry accelerates velocity and prevents regressions by giving future maintainers
  immediate insight into the motivations behind these changes.

## Current State (Key Changes)

### Infrastructure
- ChromaDB backend updated to use `CHROMA_DB_IMPL=duckdb` with a local `PERSIST_DIRECTORY`.
  Postgres environment variables were removed from the Chroma service.
- The `legal_discovery` service still references `CHROMA_HOST` and `CHROMA_PORT`, which now point at the standalone Chroma container.

### Frontend
- Design tokens in `apps/legal_discovery/src/tokens.css` replaced with a richer palette and typographic scale
  using deep navy backgrounds, translucent surfaces, and vibrant cyan accents.
- Dashboard layout reworked with `.dashboard-grid`, `.dashboard-sidebar`, and `.tab-panels` classes.
  The sidebar hosts vertically stacked navigation buttons while the right panel scrolls independently.
- `apps/legal_discovery/src/Dashboard.jsx` now wraps navigation in an `<aside>` element and keeps content panels within `<main>`.

## Limitations

- This environment lacks Docker and a Node.js toolchain, so the app was not fully built or run.
  Future developers must validate by running `npm ci && npm run build` under `apps/legal_discovery`
  and spinning up the stack with `docker compose up -d`.
- Only high‑level dashboard styles were updated. Individual sections may need further polish to conform
  to the new design language.

## Setup and Reproduction

1. Clone or download the repository.
2. Install dependencies:
   ```bash
   cd apps/legal_discovery
   npm ci
   ```
3. Run the backend:
   ```bash
   docker compose build
   docker compose up -d
   ```
4. Verify services are healthy via `docker compose ps` or by hitting `http://localhost:5001/api/health`.
5. Start the frontend:
   ```bash
   npm run dev
   ```
6. Navigate to `http://localhost:8080` and confirm the sidebar layout loads.

## Next Steps

- Validate Chroma via DuckDB by running ingestion workflows and ensuring data persists under `/data`.
- Harmonize card components and tables with the new color palette and spacing.
- Replace `<select>` drop‑downs with custom styled components where appropriate.
- Ensure accessibility and test responsiveness at common widths (1440 px, 1920 px).
- Engage stakeholders to collect feedback before rolling out to production.

## Open Questions

- Do downstream systems assume Chroma uses a Postgres backend?
- Should theming support allow toggling between light and dark modes?
- Does the new layout need to account for extremely long tab lists or is vertical scrolling sufficient?

## TL;DR

This entry records the initial overhaul of the Legal Discovery app: switching ChromaDB to DuckDB for stability,
applying a luxurious dark theme with a fixed navigation sidebar, and documenting how to reproduce and extend the work.
Follow the next steps above to validate, refine, and deploy these improvements.

