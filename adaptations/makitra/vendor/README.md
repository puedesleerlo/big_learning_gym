# Makitra reference package

`makitra-react-0.1.0.tgz` is the actual built `@makitra/react` 0.1.0 package from the local `kitchen_design_sys/react` design-system project supplied by the user, not a recreation of its components. It contains its React components, CSS tokens, typography, bundled Geologica and Protest Guerrilla fonts, illustrations, TypeScript declarations and usage documentation. `CREDITS.md` preserves the upstream attribution.

Archive SHA-1: `5faa90586d7d93236975db03c2e52876598dfe3e` (also pinned in the frontend lockfile). The upstream documentation marks the design system non-commercial; retain this as the user's personal reference experiment. This archive does not expand those permissions. Review upstream terms before any other distribution/use.

The frontend follows the package's MakitraRoot, semantic color/spacing/type tokens, supplied fonts and components. Its own CSS handles learning layout and styles the shared rich-activity markup. No kitchen product models, recipes, countdown logic or local application state are imported into the Gym integration.

For an authorized update, build the upstream package and use `pnpm pack --pack-destination <this-directory>` from that package, then update the dependency and lockfile and rerun both frontend and browser checks. Keep design-system dependencies out of `gym/` and `packages/gym-frontend/`.
