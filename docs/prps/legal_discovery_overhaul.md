name: "PRP Entry — Legal Discovery UI/UX Overhaul & Qdrant Fix"
description: |
  Detailed notes capturing the work performed to stabilize the Legal Discovery app
  and dramatically improve its user experience. These notes serve as a
  contextual memory bank for future developers or autonomous agents tasked
  with continuing this project. Follow this guide to understand the
  motivations behind each change, how to reproduce the environment locally,
  and what remains to be done.

Goals

Resolve persistent vector database failures during bulk uploads. The original
stack used Qdrant backed by Postgres; misconfigurations caused the service
to crash when Postgres was slow or unavailable. As an interim fix the
service was pointed at DuckDB, and this update migrates to Qdrant, a
dedicated vector database designed for high‑throughput ingestion and
similarity search.

Elevate the UI/UX from a cramped, low‑fidelity webapp to a polished, luxury
dashboard that feels worthy of a premium subscription. Key objectives
include adding a dedicated sidebar, increasing spacing, adopting a dark
navy + cyan color palette, and making the interface more intuitive for
power users on desktop.

Document every significant change and provide a self‑contained roadmap so
the next agent can hit the ground running without rediscovering context.

Why

The application previously relied on Qdrant plus PostgreSQL for vector storage.
Misconfigured database credentials caused Qdrant to hang on startup, which
cascaded into a full stack crash. We first experimented with an embedded
DuckDB backend to eliminate the Postgres dependency, but found that a
dedicated vector database would better support high‑volume ingestion. The
current solution uses Qdrant, which isolates vector storage from the SQL
database entirely and offers superior throughput and resilience.

The existing dashboard was cluttered: all tabs were squeezed into a
horizontally scrolling list and the content area lacked breathing room.
Users need to juggle dozens of tools—from timeline and vector management to
legal theory and document drafting—so a more structured layout with a
persistent navigation sidebar improves orientation and reduces cognitive
load.

A robust PRP entry acts as a “knowledge checkpoint.” Without it, future
maintainers must trawl commit history or Slack threads to understand why
certain decisions were made. Capturing context here accelerates velocity
and prevents regressions.

Current State (Key Changes)
Infrastructure

Vector database — The stack now ships with Qdrant instead of relying on
Qdrant backed by Postgres. A new qdrant service has been added to
docker-compose.yml, exposing port 6333 and persisting data under
./docker_volumes/qdrant. The legal_discovery service declares
QDRANT_HOST/QDRANT_PORT environment variables and depends on qdrant
instead of Qdrant. Qdrant collections are created at runtime for legal
documents, chat messages, and conversation summaries. The Python code
automatically falls back to Qdrant or an in‑memory store if Qdrant is
unavailable, but production deployments should run with Qdrant for high
throughput ingestion.

Frontend

Design Tokens — Overwrote the fallback definitions in
apps/legal_discovery/src/tokens.css with a richer palette and typographic
scale: deep navy backgrounds (#0a0e23/#101a36), translucent surfaces,
vibrant cyan accents (#4dc9ff), and increased spacing units. These
variables cascade across the app via CSS custom properties.

Dashboard Layout — Added new CSS classes in tokens.css (.dashboard-grid,
.dashboard-sidebar, .tab-panels) to implement a two‑column grid. The
sidebar occupies a fixed width (≈260 px) and hosts vertically stacked
navigation buttons, while the right panel scrolls independently. Tab
buttons now span the full sidebar width and align their icons and labels to
the left for improved scanability.

React Structure — Modified apps/legal_discovery/src/Dashboard.jsx to wrap
the navigation in an <aside> element using the new classes. The
<main> element exclusively contains the content panels. Theme toggle and
settings button remain within the sidebar. A tour overlay and settings
modal still mount at the root of the grid.

Limitations

The environment here does not include Docker or a Node.js toolchain, so the
app could not be fully built or run. All code changes compile in theory,
but future developers must validate by running npm ci && npm run build under
apps/legal_discovery and spinning up the stack with docker compose up -d.
Ensure vite and other dev dependencies are installed.

Only the high‑level dashboard styles were updated. Individual sections
(Timeline, Graph, Vector, etc.) may need further polish to conform to the
new design language. Consider auditing all components for spacing,
typography, and consistent use of the new variables.

Setup and Reproduction

Clone or download the neuro-san-studio-2 repository. In this
environment we could not perform a git clone due to network restrictions,
so we downloaded the zip manually. Future work should use the GitHub
connector or a proper clone on a machine with internet access.

Install dependencies:

cd apps/legal_discovery
npm ci         # ensure vite and other dev packages are present


If your machine is air‑gapped, copy a pre‑built node_modules from
another environment.

Run the backend:

docker compose build
docker compose up -d


Verify the legal_discovery, Qdrant, postgres, neo4j and redis
services are healthy via docker compose ps or by hitting
http://localhost:5001/api/health.

Start the frontend:

npm run dev


Navigate to http://localhost:8080 and confirm the sidebar layout loads.

Next Steps

Validate Qdrant integration — Run ingestion workflows (upload thousands of
documents, chat messages, and conversation summaries) to confirm that
Qdrant persists data under ./docker_volumes/qdrant and maintains
responsive query performance. Monitor the qdrant container’s logs for
errors, and consider adding a health endpoint that performs a heartbeat
search to detect vector store issues early.

Global UI Audit — The dashboard overhaul improved the skeleton, but
additional work is needed:

Harmonize card components and tables with the new color palette and
spacing. Introduce consistent card elevation and hover states.

Replace <select> drop‑downs with custom styled components where
appropriate.

Ensure accessibility (contrast ratios, keyboard navigation) remains high
despite the darker palette.

Performance and Responsiveness — While the app targets desktop users,
it should gracefully handle window resizing. Test the grid at common
widths (1440 px, 1920 px) and refine breakpoints if necessary.

Merge and Deployment — After local validation, commit these changes and
open a pull request. Include screenshots of the new UI and a summary
linking back to this PRP entry. Engage stakeholders to collect feedback
before rolling out to production.

Open Questions

Are there any downstream systems (e.g., analytics pipelines) that
assume vectors live in Qdrant/Postgres? If so, we must update
configuration or build adapters to read from Qdrant instead.

Should we invest in theming support so users can toggle between light and
dark modes, or is a single polished dark theme sufficient for our target
audience?

Does the new layout need to account for extremely long tab lists, or can we
allow vertical scrolling in the sidebar indefinitely? A nested grouping of
related tools might improve discoverability further.

TL;DR

This PRP entry records the initial overhaul of the Legal Discovery app:
adopting Qdrant as the vector store (superseding Qdrant/Postgres), applying a
luxurious dark theme with a fixed navigation sidebar, and documenting how to
reproduce and extend the work. Follow the next steps above to validate,
refine, and eventually deploy these improvements.

Next Steps

Because the GitHub connector available in this environment only supports read operations, I cannot push these changes directly to your ahouse2/neuro-san-studio-2 repository. Please apply the following patch manually on your side and commit it:

docker-compose.yml
  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
    volumes:
      - ./docker_volumes/qdrant:/qdrant/storage
    restart: unless-stopped
  # Qdrant: (commented out; see file for optional configuration)

  # Added QDRANT vars and dependency; removed Qdrant dependency for legal_discovery
   environment:
      - QDRANT_HOST=${QDRANT_HOST:-qdrant}
      - QDRANT_PORT=${QDRANT_PORT:-6333}
   depends_on:
      qdrant:
        condition: service_started

requirements.in / requirements.txt
qdrant-client
qdrant-client==1.6.0  # in requirements.txt only

config/config.py
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

vector_database_manager.py
from qdrant_client.http.models import VectorParams, Distance, PointStruct, PointIdsList
    # instantiate embedder fallback logic (GenerativeAI, HuggingFace, hashed)
    # create collections for legal_documents, chat_messages, conversations
    # implement add/query/delete using Qdrant search/upsert/delete

# tokens.css and Dashboard.jsx
 Added luxury dark theme variables and layout classes
 Converted dashboard layout to use grid with sidebar

Once you pull these changes into your own environment, run docker compose up -d and npm run dev to verify that Qdrant is serving vector queries correctly and that the new dashboard layout looks and feels premium. If everything works as intended, commit the patch to your repository.
