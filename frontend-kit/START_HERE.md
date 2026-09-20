# Build a company learning experience

You are building a frontend for an existing Learning Gym. Own the complete visual experience. Use the supplied company design system for components, typography, layout, assets, and interaction presentation.

The platform already owns lessons, attempts, evidence, assessment, timers, and scheduling. Connect those capabilities through the supplied client. Do not implement a second learning engine.

## Start in five minutes

1. Read `skill/SKILL.md`. For this version, choose labs, practice, and/or transfer practice.
2. Work inside `starter/`. Run `pnpm install`, then `pnpm run dev`. Open the printed local URL with `?preview=1` for explicit synthetic data.
3. Add the company's design-system package and redesign the frontend. Keep the client and workflow hooks. Read only the journey reference you need.
4. Run `pnpm run build` and `pnpm run check`. Exercise `skill/references/verification.md` against an isolated Gym workspace.
5. In the Gym repository, install using `python -m gym.cli --workspace /absolute/company.json frontend install /absolute/frontend`. Restart that workspace; open `/experience/<id>/`.

The export is self-contained: `packages/` is the client and hooks; `starter/` is the runnable app; `contracts/` contains live-generated OpenAPI, activity schemas, and synthetic response examples. No backend source, credentials, company documents, or learner history is needed to design it.

In this repository before export, the skill lives at `skills/build-gym-frontend/` and the client at `packages/gym-frontend/`. Use `python -m gym.cli frontend export-kit /absolute/new-directory` to produce the portable layout described above.

## One connection, two explicit modes

```tsx
import { connectGym } from '@learning-gym/frontend';
import { createPreviewClient } from '@learning-gym/frontend/preview';
const client = preview ? createPreviewClient() : await connectGym();
const labs = await client.labs();
```

Live mode loads `/app-config.json`, checks contract compatibility, and uses same-origin `/api`. A live failure stays a visible error. Preview never contacts the backend; its feedback is illustrative, not assessment.

Claude Design can use the company system and this specification to explore screens. Hand the exported design and this bundle to Claude Code or another local coding agent for implementation and compatibility checks. A design preview is not an installed application.
