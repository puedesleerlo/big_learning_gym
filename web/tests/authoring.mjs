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
  page.on("response", async (response) => {
    if (response.status() >= 400 && response.url().includes("/api/")) {
      console.error(
        "Fixture API failure",
        response.status(),
        response.url(),
        await response.text(),
      );
    }
  });
  await page.goto(url);
  await page.getByRole("button", { name: "Authoring", exact: true }).click();
  const pick = async (label, query, name) => {
    await page.getByRole("combobox", { name: label, exact: true }).fill(query);
    await page.getByRole("option", { name, exact: false }).click();
  };
  assert.equal(
    await page
      .getByRole("button", { name: "Create profile proposal", exact: true })
      .isEnabled(),
    false,
  );
  assert.equal(
    await page.getByText("Emergent evidence", { exact: true }).count(),
    0,
  );
  // Large libraries are searchable and bounded, with no ambiguous selection checkboxes.
  await page.getByRole("button", { name: /Material library Upload/ }).click();
  assert.equal(await page.locator(".source-list .source-row").count(), 8);
  assert.equal(
    await page.locator(".source-list input[type=checkbox]").count(),
    0,
  );
  await page.getByRole("button", { name: "Next files", exact: true }).click();
  await page
    .getByLabel("Search material", { exact: true })
    .fill("Prior lecture");
  assert.equal(await page.locator(".source-list .source-row").count(), 1);
  await page
    .getByRole("button", { name: "Return to profile", exact: true })
    .click();
  await pick("Coursework to prepare for", "Future Quiz", "Future Quiz 2");
  // Keyboard selection works and file selection lives in the profile.
  const material = page.getByRole("combobox", {
    name: "Course material",
    exact: true,
  });
  await material.fill("Prior lecture");
  await material.press("ArrowDown");
  await material.press("Enter");
  await pick("Earlier coursework (optional)", "Prior Quiz", "Prior Quiz 1");
  // Creating coursework here requires a deadline and time estimate.
  await page
    .getByRole("button", { name: "Add coursework here", exact: true })
    .click();
  await page
    .getByLabel("Coursework title", { exact: true })
    .fill("Inline Quiz 3");
  await page
    .getByLabel("Assignment instructions", { exact: true })
    .fill("Explain causal inference and uncertainty.");
  const saveInline = page.getByRole("button", {
    name: "Save coursework and select it",
    exact: true,
  });
  assert.equal(await saveInline.isEnabled(), false);
  await page
    .getByLabel("Deadline (required)", { exact: true })
    .fill("2026-10-03T17:00");
  assert.equal(await saveInline.isEnabled(), false);
  await page
    .getByLabel("Estimated time in minutes (required)", { exact: true })
    .fill("45");
  await saveInline.click();
  await saveInline.waitFor({ state: "hidden" });
  await page
    .getByRole("button", { name: "Remove Inline Quiz 3", exact: true })
    .click();
  await pick("Coursework to prepare for", "Future Quiz", "Future Quiz 2");
  await page
    .getByLabel("Profile title", { exact: true })
    .fill("Future Quiz 2 preparation");
  await page
    .getByLabel("What should your practice focus on?", { exact: true })
    .fill("Prepare for Quiz 2 causal inference and uncertainty");
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    ),
    false,
  );
  await page.screenshot({
    path: "/tmp/gym-guided-authoring-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1450, height: 1000 });
  await page.screenshot({
    path: "/tmp/gym-guided-authoring-desktop.png",
    fullPage: true,
  });
  await page
    .getByText("Prepare a proposal without a model", { exact: true })
    .click();
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
  await page.getByRole("heading", { name: "Make your practice set", exact: true }).waitFor();
  const get = async (path) => (await fetch(url + "/api" + path)).json();
  let cw = await get("/coursework");
  const original = cw.assessment_profile[0];
  assert.equal(original.status, "confirmed");
  assert.equal(original.assignment_ids.length, 1);
  assert.ok(original.target_assignment_id);
  await page.getByRole("button", { name: /2. Review profiles/ }).click();
  await page
    .getByText(`Run 1 · r${original.revision} · confirmed`, { exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Update evidence", exact: true })
    .click();
  const sources = await get("/sources");
  const newSource = sources.find((s) => s.name === "New clarification.md");
  await pick(
    "New information about the task",
    "New clarification",
    "New clarification.md",
  );
  await page
    .getByRole("button", {
      name: "Rerun profile with updated evidence",
      exact: true,
    })
    .click();
  await page.locator(".modal-shade").waitFor({ state: "hidden" });
  await page
    .getByText(/Run 2 · r\d+ · needs_review/, { exact: true })
    .waitFor({ timeout: 15000 });
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
  await page
    .getByLabel("Filter by gym", { exact: true })
    .selectOption("other-course");
  await page.getByRole("button", { name: /Writing task/ }).waitFor();
  assert.equal(
    await page.getByRole("button", { name: /Prior Quiz 1.*completed/ }).count(),
    0,
  );
  assert.equal(
    await page.getByRole("button", { name: /Writing task/ }).count(),
    1,
  );
  assert.equal(
    await page
      .getByRole("heading", { name: "Reusable rubrics", exact: true })
      .count(),
    0,
  );
  await page.getByLabel("Filter by gym", { exact: true }).selectOption("");
  await page.getByRole("button", { name: /Prior Quiz 1.*completed/ }).waitFor();
  assert.equal(
    await page.getByRole("button", { name: /Prior Quiz 1.*completed/ }).count(),
    1,
  );
  assert.equal(
    await page.getByRole("button", { name: /Writing task/ }).count(),
    1,
  );
  await page
    .getByLabel("Filter by gym", { exact: true })
    .selectOption("course");
  await page.getByRole("button", { name: /Prior Quiz 1.*completed/ }).click();
  assert.equal(
    await page.getByLabel("Assignment draft", { exact: true }).isVisible(),
    false,
  );
  await page
    .getByRole("button", { name: "Add grade or feedback", exact: true })
    .click();
  await page
    .getByLabel("Upload instructor feedback or grade file", { exact: true })
    .setInputFiles({
      name: "Quiz 1 instructor feedback.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "Synthetic TA record: 91/100. Explain the assumption more precisely.",
      ),
    });
  await page
    .getByLabel("Saved feedback file (optional)", { exact: true })
    .waitFor();
  await page
    .getByLabel("Grade (out of 100; leave blank for feedback only)", {
      exact: true,
    })
    .fill("91");
  await page
    .getByLabel("Instructor / TA feedback", { exact: true })
    .fill("Observed TA comment from a synthetic course record.");
  await page
    .getByRole("button", { name: "Save grade & feedback", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save grade & feedback", exact: true })
    .waitFor({ state: "hidden" });
  await page.getByText("Instructor grade: 91 / 100", { exact: true }).waitFor();
  cw = await get("/coursework");
  assert.equal(cw.submission.length, 0);
  assert.equal(cw.assignment_draft.length, 0);
  assert.equal(cw.coursework_outcome.length, 1);
  const feedbackSource = (await get("/sources")).find(
    (s) => s.name === "Quiz 1 instructor feedback.txt",
  );
  assert.equal(feedbackSource.role, "feedback");
  assert.equal(cw.coursework_outcome[0].source_id, feedbackSource.id);
  assert.deepEqual(
    cw.assignment.find((a) => a.title === "Prior Quiz 1").source_ids,
    [],
  );
  await page.getByText("Record details & history", { exact: true }).click();
  await page.getByText(feedbackSource.name, { exact: true }).click();
  await page
    .getByRole("button", { name: "Read document text", exact: true })
    .click();
  await page
    .getByText(
      "Synthetic TA record: 91/100. Explain the assumption more precisely.",
      { exact: true },
    )
    .waitFor();
  await page
    .getByRole("button", {
      name: "Edit grade & feedback",
      exact: true,
    })
    .click();
  assert.equal(
    await page
      .getByLabel("Saved feedback file (optional)", { exact: true })
      .inputValue(),
    feedbackSource.id,
  );
  await page
    .getByLabel("Instructor / TA feedback", { exact: true })
    .fill("Corrected transcription of the synthetic TA comment.");
  await page
    .getByRole("button", { name: "Save grade & feedback", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save grade & feedback", exact: true })
    .waitFor({ state: "hidden" });
  await page
    .getByText("Corrected transcription of the synthetic TA comment.", {
      exact: true,
    })
    .waitFor();
  cw = await get("/coursework");
  assert.equal(cw.coursework_outcome.length, 2);
  const correction = cw.coursework_outcome.find((o) => o.supersedes);
  assert.equal(correction.source_id, feedbackSource.id);
  assert.equal(
    cw.coursework_outcome.find((o) => o.id === correction.supersedes).feedback,
    "Observed TA comment from a synthetic course record.",
  );
  assert.equal(
    await page
      .getByText("Observed TA comment from a synthetic course record.", {
        exact: true,
      })
      .isVisible(),
    false,
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Add grade or feedback", exact: true })
      .count(),
    0,
  );
  assert.equal(await page.locator(".official-grade > strong").count(), 1);
  assert.equal(
    await page
      .getByRole("button", { name: "Edit assignment details", exact: true })
      .isVisible(),
    true,
  );
  const order = await page.locator("main").evaluate((main) => {
    const instructions = [...main.querySelectorAll("summary")].find(
      (e) => e.textContent === "Assignment instructions & rubric",
    );
    const feedback = main.querySelector(
      '[aria-label="Instructor grades and feedback"]',
    );
    return !!(
      instructions.compareDocumentPosition(feedback) &
      Node.DOCUMENT_POSITION_FOLLOWING
    );
  });
  assert.equal(order, true);
  await page
    .getByRole("button", { name: "Edit assignment details", exact: true })
    .click();
  await page.getByText(/Supporting assignment documents \(optional\)/).click();
  const modal = page.locator(".modal");
  const rubricOptions = await modal
    .getByLabel("Rubric", { exact: true })
    .locator("option")
    .allTextContents();
  assert.ok(rubricOptions.some((name) => name.startsWith("Statistics rubric")));
  assert.ok(
    rubricOptions.some((name) => name.startsWith("Shared reasoning rubric")),
  );
  assert.ok(!rubricOptions.some((name) => name.startsWith("Writing rubric")));
  const due = page.getByLabel("Coursework deadline", { exact: true });
  const originalDeadline = await due.inputValue();
  assert.ok(originalDeadline);
  await due.fill("");
  assert.equal(
    await modal
      .getByRole("button", { name: "Save coursework revision", exact: true })
      .isEnabled(),
    false,
  );
  await due.fill(originalDeadline);
  const estimate = page.getByLabel("Estimated time (minutes, required)", {
    exact: true,
  });
  await estimate.fill("");
  assert.equal(
    await modal
      .getByRole("button", { name: "Save coursework revision", exact: true })
      .isEnabled(),
    false,
  );
  await estimate.fill("75");

  assert.equal(
    await modal.getByText(feedbackSource.name, { exact: true }).count(),
    0,
  );
  assert.equal(
    await modal.getByRole("checkbox", { name: /Prior lecture.md/ }).count(),
    1,
  );
  await modal
    .getByRole("button", { name: "Save coursework revision", exact: true })
    .click();
  await page
    .getByText("Corrected transcription of the synthetic TA comment.", {
      exact: true,
    })
    .waitFor();
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
    "Authoring browser journey passed: goal, prior/emergent evidence, profile versions/rerun, practice regeneration, feedback upload and correction, completed coursework, narrow screen.",
  );
} catch (error) {
  const page = browser.contexts()[0]?.pages()[0];
  if (page) {
    await page.screenshot({
      path: "/tmp/gym-authoring-failure.png",
      fullPage: true,
    });
    console.error(await page.locator("main").innerText());
  }
  throw error;
} finally {
  await browser.close();
  server.kill("SIGTERM");
}
