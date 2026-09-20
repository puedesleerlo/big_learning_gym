---
name: build-gym-frontend
description: Build or redesign an independent company frontend for the Learning Gym using its exported integration kit and a supplied design system. Use for experience adaptation code, not curriculum authoring, assessment changes, or backend algorithms.
---

# Build a Gym frontend

Start from the bundle's `START_HERE.md` and `starter/`. Select the requested company design system. You own screens, navigation, components, spacing, type, and assets. Do not copy the Gym backend or import its source into the frontend.

The supported contract is 1.0. Discover the client's TypeScript declarations in `packages/gym-frontend/index.d.ts` and `react.d.ts`; then read only the required journey:

- [Browse and study](references/labs.md): catalog, pinned lessons, activity blocks, timers, drafts, and rich content.
- [Practice](references/practice.md): session linking, answers, assistance, feedback, and interrupted requests.
- [Runtime and installation](references/runtime.md): auth, workspace storage, manifests, preview/live modes, deep links, design-system dependencies.
- [Verify](references/verification.md): build, functional checks, recovery, and handoff.

Use `@learning-gym/frontend` and its headless hooks for supported workflows. API names and payloads come from the declarations and exported `contracts/`, not guesses. The shared package must remain free of company dependencies. Extend only the company's frontend for visual changes; requests for a new backend capability should be identified explicitly.

Preserve learner meaning in the interface: preparation is not mastery; model judgments are provisional; hints are attributed assistance; unfinished work remains unfinished. Display server results rather than calculating grades or time worked. Render errors and pending states honestly.

Keep preview conspicuous and synthetic. Use no learner history, credentials, or company documents as design fixtures. A live API failure must never switch to preview data.

Use the shared rich-activity renderer for media and visualization behavior. Its browser sandbox is separate from the trusted frontend package. Never lift authored visualization code into the application document.

Finish by running the build and verification steps, identifying the installed route and remaining limitations. Do not claim compatibility from a screenshot or a manifest check alone.
