# Learning Gym

A single-user learning and research workbench: create practice from course evidence, do real coursework, keep the evidence from that work, and use it to choose the next activity and plan your time.

The implementation follows the shared [AI research assistantships architecture](https://chatgpt.com/share/6aaf4301-d3a4-83e9-a1a4-784dc03dbf33) and the [assessment-profile workflow](https://claude.ai/share/e3ee8d67-b12b-4066-be83-5ba5831457bb). Both reference conversations were accessible and read. The older AI Strategy gym supplies content and interaction examples. **Its imported content supplies no learner history, telemetry, or claims of mastery.**

## Run locally

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 22+, npm.

```sh
uv sync --frozen
npm --prefix web ci
npm --prefix web run build
cp .env.example .env  # Only on a new installation; preserve an existing .env.
# Set the relevant provider key in .env using your editor.
uv run python -m gym.cli init
uv run python -m gym.cli serve
```

Open <http://127.0.0.1:8787>. The local server includes a durable background worker. It runs while the process is alive; this release does not install a system service. For frontend development, run `npm --prefix web run dev` alongside the API; Vite proxies `/api` to port 8787.

The current workspace already has the AI Strategy content imported. To import it into another installation:

```sh
uv run python -m gym.cli import-legacy ../learning_gym
```

The importer preserves 314 practice items, four 16-item / 100-point mock exams, shared cases and tables, matching questions, explanations, hints, plain-English aids, eight guides, and 331 glossary entries. The legacy style specification is imported as a **proposed** assessment profile to review. It does not fabricate practice sessions.

## Reusable labs

Open **Labs** to browse across gyms or filter to one gym. **Create lab** lets you choose a gym, add lessons linked to its topics and reviewed sources, and arrange readings, predictions, worked examples, parameter experiments, reflections, practice checks and coursework. Each gym can have multiple named labs. Validate and preview before publishing; the preview does not record learner activity. Edit a published lab through a new revision; ongoing visits retain their original lesson.

New labs using these activity types need content and configuration, not application code. Parameter experiments currently calculate a weighted sum of bounded inputs; new kinds of simulation need a reviewed component. Research-paper sections are optional. For agents, use the [API workflow](docs/AGENT_API.md) and adapt the [non-causality example](content/examples/general-lab.json) with real course, topic and confirmed source IDs.

## Causality learning gym

The causality curriculum uses the existing workbench, study library, practice sessions, sources, coursework, and rubrics. Open **Labs** and select **Causality: from first questions to frontier research**. Follow modules C01–C12: read the explanation, run a small illustrative experiment, save your reasoning, and start linked practice. The same content is available in the study library. Four longer exercises are in **Coursework & rubrics**.

The guided lab records explicit start/pause/finish events, capped server-measured active time, elapsed time, reading exposure, experiment parameters, and reflections. Hiding the tab pauses its timer. Linked practice uses the existing session, scoring, and learner model; guided exposure is recorded as support before answers are submitted. **Learning evidence** shows preparation beside actual practice outcomes. Study completion earns no mastery, and linked time/outcome observations do not establish a causal teaching effect. The four widgets explain exact toy models; they do not execute causal-learn algorithms or claim real-world causal identification.

Each lesson connects a foundational idea to an inspected paper, with assumptions, limitations, and a suggested reading task. Research includes causal-learn/Tetrad methods, BOSS, latent-variable discovery, causal representation learning, and Aether-linked world-model research. Preprints and company summaries are labeled. Public CMU course materials and an open textbook supplement the lessons. The two books mentioned by the learner have not yet been located; no contents from them are claimed to be included.

To populate another running installation through its HTTP API:

```sh
uv run python scripts/install_causality.py --base-url http://127.0.0.1:8787
```

The importer validates source reconstruction, imports material atomically, and can be repeated with the same content without duplication. It records content provenance, not learner attempts or mastery, and makes no model calls. Source material is original AI-assisted teaching synthesis with links to the external papers. See [research notes](docs/causality-research-notes.md) for checked citations and scientific limits.

## Agent access

Agents use the same authenticated HTTP API as the UI. The live operation catalog is `/api/agent/capabilities`; `/api/agent/schema` exposes its OpenAPI contract. The authoring API adds course/module, guide, glossary, and question management, with revision checks, atomic imports, source references, and preserved historical questions. Existing source, rubric, assignment, practice, research, and planning endpoints remain the workflow authority.

```sh
uv run python -m gym.agent_client capabilities
uv run python -m gym.agent_client GET /api/overview
```

Use the [Learning Gym skill](skills/learning-gym/SKILL.md) and [agent API guide](docs/AGENT_API.md) for authoring and maintenance. `GYM_ACCESS_TOKEN` is read from the server environment or `.env`; the client does not print it.

## Create a gym from a course

1. Choose **Sources & create → New gym**. Upload lectures, slides and readings as instructional sources. Upload official homework, quizzes, labs and worksheets as assessment examples; mark rubrics separately.
2. Open each source. Inspect its page/slide/line anchors, correct damaged extraction, and confirm the reconstruction. Corrections create a new version and preserve the original file.
3. Select reviewed assessment examples and **Infer assessment profile**. Edit and confirm the proposed structure, reasoning demands, scoring rules and uncertainty. This transfers the assessment's style into new practice; raw assessment questions are excluded from the generation content context.
4. Select instructional sources, a topic, formats, optional profile and rubric. Set exact type counts when needed. For a shared-case section, choose the number of trailing items that use one generated case and comparison table.
5. **Generate & verify** runs design and independent verification in bounded batches. Item count, type allocation, source references, keys, matching mappings and rubric weights are checked. Rejected items are quarantined. A fixed simulation is published only when all its items pass.

MCQ, matching, open response, case analysis, counterfactual and coding prompts are supported. Explicit counts and rubric constraints are enforced; nuanced style, section placement and difficulty remain model-reviewed targets, not a guarantee of exam equivalence. Review generated material before using it as consequential assessment.

## Do real coursework

In **Coursework & rubrics**, create a shared rubric or a task-specific rubric. An uploaded, reviewed rubric can be converted into an editable proposal from its source preview. Weights sum to one; anchors state what weak and strong work look like.

Add the homework, practice quiz, lab, essay or project. Attach its source instructions and use **Use selected source instructions** to populate the prompt. Either pin the rubric version or follow future shared revisions. Historical submissions always retain their original prompt, rubric, attachments and AI attribution.

Write in the workbench or attach a file, optionally run the work timer, and record a local submission version. Attached text is included in rubric assessment. Request provisional model feedback; record the instructor's actual grade separately. Low-scoring coursework feeds back into the next-activity recommendation. A holistic course grade is never silently turned into general mastery. Recording a submission **does not submit it to your school**.

## Two feedback loops

The operational loop records attempts, assistance, exposure, confidence, active versus elapsed time, unfinished work, submissions, changes in task scope and calendar revisions. It updates evidence summaries, invalidates affected estimates, and proposes schedule repair. Assistance and repeated exposure reduce the weight of practice evidence. Recommendations show their rationale; estimates carry uncertainty and are open to correction.

The slower adaptation loop evaluates forecasts against later outcomes. It requires at least 12 matched effort outcomes, at least eight training outcomes available before every held-out forecast, and a chronological holdout. Candidates must improve median-effort error without worsening the upper-tail loss. Passing candidates remain in shadow until you activate them; the prior model can be restored. It makes no causal claim about teaching interventions. Disabling adaptation leaves practice, coursework and planning operational.

**Plan my time** is the sole scheduling authority. Define tasks by remaining scope and a completion criterion, dependencies, deadlines, effort and block sizes. Add fixed commitments manually or import ICS. Configure availability, workload and slack, then inspect and accept a proposal. Pins are retained, conflicts are explicit, and stale proposals cannot be accepted. Export accepted blocks as ICS. Academic risk comes first, followed by research bottlenecks, academic/capability work and bounded exploration.

**Research & writing** preserves versioned claims, objections, artifacts and provenance links with an independent critique. Model critique is explicitly not external validation.

## Models and credentials

Edit `config/models.json` to route each role independently: extractor, designer, tutor, verifier, assessor and research coach. The supplied configuration uses `kimi-k3` at different reasoning/token budgets. Providers include Moonshot, OpenAI-compatible endpoints, Google compatibility, a native Anthropic adapter and a local OpenAI-compatible server. Set a compatible model name and parameters for each selected provider; only Kimi K3 was exercised live in this implementation.

Keys are referenced by environment variable and read server-side. `.env`, runtime data and build outputs are ignored; the browser never receives keys. After rotating the test key, replace `MOONSHOT_API_KEY` in `.env` and restart the server/worker. Logs retain model identity, usage and hashes rather than prompt bodies or credentials. Review the call/input/retry limits in the model configuration before large runs. Generated content and submitted work are sent to the provider configured for the invoked role; maintenance itself makes no model calls.

Kimi API integration references: [official API documentation](https://platform.kimi.ai/docs/api/chat), [K3 quickstart](https://platform.kimi.com/docs/guide/kimi-k3-quickstart).

## PostgreSQL and separate workers

```sh
docker compose up --build -d
```

Compose runs PostgreSQL, the API and a separate durable worker, with localhost-only published ports and persistent volumes. This is a separate database from the default local SQLite workspace. Stop a local server using port 8787 before starting the container app. For an existing PostgreSQL instance, set `GYM_DATABASE_URL=postgresql+psycopg://...`; set `GYM_EMBEDDED_WORKER=0` and run `uv run python -m gym.cli worker` separately.

Use `System` to inspect connector freshness, job retries/failures, model versions and configuration. SQLite and PostgreSQL share the same transactional storage interface. PostgreSQL is the deployment path; SQLite is convenient for a local single user.

## Recovery and validation

```sh
uv run python -m gym.cli backup backups/workspace.zip
# Restore to a NEW, empty workspace. Stop its server first.
GYM_DATABASE_URL=sqlite:///data/restored.db GYM_DATA_DIR=data/restored \
  uv run python -m gym.cli restore backups/workspace.zip

uv run pytest -q
uv run ruff check gym tests scripts
npm --prefix web run build
# Optional: isolated schemas in your test PostgreSQL instance.
GYM_TEST_DATABASE_URL=postgresql+psycopg://gym:gym-local-only@127.0.0.1:55432/gym uv run pytest -q
# Optional, explicitly makes paid model calls using synthetic material only:
uv run python scripts/live_smoke.py
```

Portable backups contain the database records and referenced originals with checksums; they exclude provider credentials. Keep backups private because they contain your coursework. Restore refuses a nonempty workspace and makes interrupted job leases reclaimable. The test suite includes a restore drill and corruption rejection.

See [architecture](docs/ARCHITECTURE.md) for module boundaries and [validation](docs/VALIDATION.md) for what was exercised and the remaining limits.
