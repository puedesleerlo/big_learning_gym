# Runtime, company styling, and installation

Each experience is an independent React/Vite app. Use the actual company package and its documented provider/root, tokens, fonts, and assets. Do not import the default Gym CSS or force the company design into a universal widget catalog. Keep React deduplicated when linking local packages.

Use `connectGym()` after page load. It reads safe public bootstrap metadata and supplies same-origin `/api`. Handle 401 with a token entry form, `client.setToken(token)`, and retry; never put provider credentials in the browser. `client.storage` prefixes drafts, token, session IDs, and pending actions by workspace ID. The original default workspace migrates its prior browser keys on access.

Named workspaces are local process configurations, not tenant authorization. One process serves one database and upload root. The standard Gym at `/` and experiences at `/experience/<id>/` share that workspace. Use `standardGymLink()` for labs, coursework, planning, authoring, progress, research, system, and sessions; never include tokens in links.

Manifest `experience.json`:

```json
{"id":"company-name","version":"0.1.0","contract_version":"1.0","capabilities":["labs","practice","transfer"],"entry":"dist/index.html"}
```

Keep the Vite base `/experience/<id>/`; the starter derives it from this manifest. Build assets must be self-contained and use this base. Test deep routes and missing assets. A compatible manifest is a declaration, not proof of workflow correctness.

The dev proxy defaults to localhost:8787. For another running workspace, set `GYM_DEV_ORIGIN=http://127.0.0.1:PORT` when starting Vite. This changes only the development proxy; installed frontends use same-origin APIs.

`?preview=1` explicitly selects the synthetic in-memory transport. Display a permanent preview notice; illustrative scores are not assessments. Without that parameter, real errors stay real errors. No mode silently falls back to the other.

After functional verification, in the Gym checkout run:

```sh
python -m gym.cli --workspace /absolute/company.json frontend install /absolute/frontend
python -m gym.cli --workspace /absolute/company.json serve
```

Restart after installation. Installed frontends are trusted application code and can access that workspace as the signed-in user; the integration kit does not sandbox them. Keep company data and local configuration outside commits. Upgrades require explicit compatible builds; rollback selects the full Gym at `/`.
