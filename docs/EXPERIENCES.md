# Local company experiences

Keep the original Gym running exactly as before with `uv run python -m gym.cli serve`. It uses the existing database and uploads. JavaScript commands use pnpm 10.7.1 (recorded in each `package.json`). The new configuration is optional.

## Try the Makitra personal reference

```sh
pnpm --dir web install --frozen-lockfile
pnpm --dir web run build
pnpm --dir adaptations/makitra install --frozen-lockfile
pnpm --dir adaptations/makitra run build
pnpm --dir adaptations/makitra run check
uv run python -m gym.cli --workspace config/workspaces/makitra.example.json serve
```

Open `http://127.0.0.1:8791/experience/makitra/`. This example creates a separate local directory under ignored `workspaces.local/makitra`; it does not copy your existing history. Add company content through the existing document/course/lab authoring workflows at `http://127.0.0.1:8791/`. Once content exists, both frontends show that same workspace and history.

For a synthetic design preview, append `?preview=1`. It displays a permanent preview notice and keeps illustrative responses in memory. It does not create learner history or contact the API. Refresh resets synthetic data. Live mode never substitutes these examples for failed requests. Media only loads on explicit action, and synthetic media URLs are placeholders.

Makitra is a personal, non-commercial reference, using the actual React package, tokens, fonts and guidelines. See [vendor provenance](../adaptations/makitra/vendor/README.md). Its kitchen-specific product logic is not imported into the platform.

## Add another workspace and frontend

Create a local JSON configuration (outside version control), with a unique identity, port and data directory:

```json
{
  "id": "company-two",
  "port": 8792,
  "data_dir": "./company-two-data",
  "frontends": []
}
```

Paths resolve relative to this file, not your terminal. Without `database_url`, the database is `data_dir/gym.db`. An optional explicit SQLite or PostgreSQL URL selects another database; use distinct databases and original-file directories for separate companies. A process does not enforce separation between mistakenly reused configurations. Tokens and provider settings retain the existing server environment behavior; run processes with different environment settings when needed.

Build an independent frontend package with its own company design-system dependencies and `experience.json`. Install its already verified build:

```sh
uv run python -m gym.cli --workspace /absolute/company-two.json frontend install /absolute/company-two-frontend
uv run python -m gym.cli --workspace /absolute/company-two.json serve
# If running a separate worker, use the same configuration:
uv run python -m gym.cli --workspace /absolute/company-two.json worker
```

Installation updates only that file's frontend list; restart its server. One process serves one workspace. The original Gym remains `/`, with installed frontends under `/experience/<id>/`. Browser drafts, credentials and session references are namespaced by workspace identity. Changing frontend within a workspace does not create another learner or rewrite evidence.

Installed frontend code is trusted application code. Keep it local and review its dependencies. Rich lesson visualization code remains separately sandboxed by the existing shared renderer. This experiment adds no hosted multi-user access or live company synchronization.

## Give an agent the integration bundle

```sh
uv run python -m gym.cli frontend export-kit /absolute/new-gym-frontend-kit
```

The destination must be new. Export creates a disposable application instance for live OpenAPI/registry snapshots and synthetic examples. It never exports local documents, history or credentials. Hand the directory, the company's design system and the requested experience to a local coding agent. It starts at `START_HERE.md`, selects a journey, reads exact contracts as needed, builds the frontend and runs the verification guide before installing.

The minimal starter is runnable; its neutral screens demonstrate a connection and linked practice. It intentionally delegates richer block presentation to the generating agent through explicit full-Gym links. The Makitra reference supplies the complete experimental journey. Generated code may need agent-led corrections to pass the acceptance scenarios; the user should not manually wire API calls.

[Claude Design documentation](https://support.claude.com/en/articles/14604416-get-started-with-claude-design) describes design-system import and local coding-agent handoff. A cloud design preview is separate from the local installed app; it cannot be assumed to reach your localhost service. Our compatibility checks exercise locally generated code and exported artifacts, not an actual Claude Design session.

For live Vite development, start the workspace server, then use `GYM_DEV_ORIGIN=http://127.0.0.1:8791 pnpm --dir adaptations/makitra run dev`. Open the printed frontend URL. Its `/api` and bootstrap requests proxy to that workspace; installed builds use the same origin directly.

## Verification and rollback

```sh
uv run pytest -q
python scripts/check_architecture.py
pnpm --dir packages/gym-frontend test
pnpm --dir web run build
pnpm --dir adaptations/makitra run build
pnpm --dir adaptations/makitra run check
pnpm --dir frontend-kit/starter run build
pnpm --dir frontend-kit/starter run check
pnpm --dir web exec playwright install chromium
pnpm --dir web run test:rich-labs
pnpm --dir web run test:experiences
# After committing, inspect the real branch diff:
python scripts/check_architecture.py --base <base-commit>
```

Browser tests create temporary databases with synthetic fixtures. They compare all six question formats across both frontends; check attributed preparation, interrupted requests, live errors, preview isolation, keyboard access and narrow screens. Open answers remain pending without an assessment worker, exactly as the backend reports. Existing backend tests cover scoring and simulation feedback sealing.

Build the exported starter in a fresh directory using only its bundled package and lockfile. For another company, keep design-system dependencies in that frontend and run its full journey verification; a manifest check alone proves only selected static compatibility.

Rollback by opening `/`, or removing a frontend from the workspace configuration and restarting. Keep the database and uploads: content, preparation, practice, assessment and plans require no rewrite.
