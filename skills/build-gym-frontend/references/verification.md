# Verify the experience

1. Run the frontend's type check/build and `pnpm run check`. Confirm the built entry and assets are served under its manifest ID. Run the shared client tests using `pnpm --dir ../packages/gym-frontend test` in an exported bundle.
2. In explicit preview mode: open a lab, start/pause/resume a lesson, save a reflection, run an experiment, link practice, answer each supported format, and finish. Refresh a live visit separately: preview memory is intentionally ephemeral.
3. Repeat in an isolated local Gym workspace with synthetic material. Verify read-only browsing creates no attempts/visits; reading becomes preparation; linked attempts retain assistance; open answers remain pending rather than inventing model feedback.
4. Interrupt an answer response, retry, and verify only one attempt exists. Interrupt practice creation and verify the frontend offers recovery without creating a second session. Check auth failure, missing lab, missing tutor, and stale/finished visit handling.
5. Open the full Gym and verify the same session and saved responses are present. Switch between two named workspaces and confirm drafts, credentials, content, and practice references do not cross.
6. Exercise rich blocks. Media loads only on user action. Pausing unloads it. Visualization code cannot fetch external data or call the Gym. Preview/discussion failures never fabricate evidence.
7. Check keyboard focus, form labels, headings, and layouts at 390px and desktop widths. Test light/dark themes supplied by the company system.

The repository maintains automated browser/API journey tests and backend behavior tests. The exported starter and client tests are portable; live checks require an actual Gym installation. Do not claim all invariants are verified by the static package checker.
