// Disposable browser integration; creates no real learner records and calls no model provider.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
const root = fileURLToPath(new URL("../../", import.meta.url));
const server = spawn(`${root}.venv/bin/python`, ["tests/authoring_server.py"], {
  cwd: root,
  env: { ...process.env, PYTHONPATH: root },
  stdio: ["ignore", "pipe", "pipe"],
});
let stderr = "";
server.stderr.on("data", (c) => (stderr += c));
const browser = await chromium.launch({ headless: true });
try {
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(stderr || "Fixture timed out")),
      10000,
    );
    createInterface({ input: server.stdout }).once("line", (l) => {
      clearTimeout(timer);
      resolve(JSON.parse(l).url);
    });
    server.once("exit", () => {
      clearTimeout(timer);
      reject(new Error(stderr));
    });
  });
  for (let i = 0; i < 50; i++) {
    try {
      if ((await fetch(`${url}/api/overview`)).ok) break;
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  const page = await browser.newPage({
    viewport: { width: 1450, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(url);
  await page.getByRole("button", { name: "Authoring", exact: true }).click();
  await page.getByLabel("Select Prior lecture.md", { exact: true }).check();
  await page
    .getByLabel("Profile title", { exact: true })
    .fill("Future Quiz 2 preparation");
  await page
    .getByLabel("Specific assessment target", { exact: true })
    .fill("Prepare for Quiz 2 causal inference and uncertainty");
  await page
    .getByLabel("Intended coursework (optional)", { exact: true })
    .selectOption({ label: "Future Quiz 2 · open" });
  await page
    .getByRole("checkbox", { name: /Prior Quiz 1 · coursework/ })
    .check();
  await page
    .getByRole("checkbox", { name: /Write and review a profile manually/ })
    .check();
  await page
    .getByRole("button", { name: "Create profile proposal", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Review & edit", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm this profile", exact: true })
    .click();
  const get = async (path) => (await fetch(url + "/api" + path)).json();
  let cw = await get("/coursework");
  const original = cw.assessment_profile[0];
  assert.equal(original.status, "confirmed");
  assert.equal(original.assignment_ids.length, 1);
  assert.ok(original.target_assignment_id);
  await page
    .getByRole("button", { name: "Evidence, versions & rerun", exact: true })
    .click();
  const sources = await get("/sources");
  const newSource = sources.find((s) => s.name === "New clarification.md");
  await page
    .getByLabel("New information about the task", { exact: true })
    .selectOption([newSource.id]);
  await page
    .getByRole("button", {
      name: "Rerun profile with updated evidence",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Review & edit", exact: true })
    .waitFor({ timeout: 15000 });
  await page
    .getByRole("button", { name: "Review & edit", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm this profile", exact: true })
    .click();
  cw = await get("/coursework");
  const evolved = cw.assessment_profile[0];
  assert.equal(evolved.run_version, 2);
  assert.deepEqual(evolved.emergent_source_ids, [newSource.id]);
  const history = await get(`/profiles/${original.id}/versions`);
  assert.equal(
    history.versions.filter((v) => v.status === "confirmed").length,
    2,
  );
  await page
    .getByLabel("Reviewed assessment profile", { exact: true })
    .selectOption(evolved.id);
  await page.getByLabel("Items", { exact: true }).fill("2");
  await page
    .getByRole("button", { name: "Generate & verify", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Practice", exact: true })
    .last()
    .waitFor({ timeout: 15000 });
  let runs = await get("/generations");
  assert.equal(runs[0].status, "ready");
  assert.equal(runs[0].counterfactual_count, 1);
  await page
    .getByText("Regenerate practice questions", { exact: true })
    .click();
  await page
    .getByRole("button", { name: "Generate a new question set", exact: true })
    .click();
  await page.waitForFunction(
    async () =>
      (await (await fetch("/api/generations")).json()).filter(
        (g) => g.status === "ready",
      ).length === 2,
  );
  runs = await get("/generations");
  assert.equal(runs[1].parent_blueprint_id, runs[0].id);
  await page
    .getByRole("button", { name: "Coursework & rubrics", exact: true })
    .click();
  await page.getByRole("button", { name: /Prior Quiz 1.*completed/ }).click();
  await page
    .getByRole("button", { name: "Record instructor outcome", exact: true })
    .click();
  await page
    .getByLabel("Grade (out of 100; leave blank for feedback only)", {
      exact: true,
    })
    .fill("91");
  await page
    .getByLabel("Instructor / TA feedback", { exact: true })
    .fill("Observed TA comment from a synthetic course record.");
  await page
    .getByRole("button", { name: "Save instructor outcome", exact: true })
    .click();
  await page.getByText("Instructor grade: 91 / 100", { exact: true }).waitFor();
  cw = await get("/coursework");
  assert.equal(cw.submission.length, 0);
  assert.equal(cw.coursework_outcome.length, 1);
  await page.screenshot({
    path: "/tmp/gym-authoring-coursework.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth + 2,
    ),
    false,
  );
  assert.deepEqual(errors, []);
  console.log(
    "Authoring browser journey passed: goal, prior/emergent evidence, profile versions/rerun, practice regeneration, external outcome, narrow screen.",
  );
} finally {
  await browser.close();
  server.kill("SIGTERM");
}
