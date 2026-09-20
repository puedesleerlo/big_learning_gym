// Both real frontends, real API, disposable synthetic databases; no learner profile.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
const root = fileURLToPath(new URL("../../", import.meta.url));
const servers = [];
async function fixture(id, token = "") {
  const proc = spawn(
    `${root}.venv/bin/python`,
    ["tests/experience_server.py", "--id", id, "--token", token],
    {
      cwd: root,
      env: { ...process.env, PYTHONPATH: root },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  servers.push(proc);
  let errors = "";
  proc.stderr.on("data", (d) => (errors += d));
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(Error(errors || "Fixture startup timed out")),
      10000,
    );
    createInterface({ input: proc.stdout }).once("line", (line) => {
      clearTimeout(timer);
      resolve(JSON.parse(line).url);
    });
    proc.once("exit", (code) => {
      clearTimeout(timer);
      reject(Error(`Fixture exited ${code}: ${errors}`));
    });
  });
  for (let i = 0; i < 50; i++) {
    try {
      if ((await fetch(url + "/app-config.json")).ok) return url;
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  throw Error("Fixture unavailable");
}
const browser = await chromium.launch({ headless: true });
const problems = [];
async function page() {
  const p = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  p.setDefaultTimeout(10000);
  p.on("pageerror", (e) => {
    problems.push(e.message);
    console.error(e.message);
  });
  return p;
}
const summary = async (url) => (await fetch(url + "/__fixture/summary")).json();
const btn = (p, name) => p.getByRole("button", { name, exact: true });
const noOverflow = async (p) =>
  assert(
    await p.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
    "Page overflows narrow viewport",
  );
async function narrow(p) {
  await p.setViewportSize({ width: 390, height: 844 });
  await noOverflow(p);
  await p.setViewportSize({ width: 1440, height: 1000 });
}
async function waitSaved(p, url, count) {
  await p.waitForFunction(
    async ({ url, count }) =>
      (await (await fetch(url + "/__fixture/summary")).json()).attempts
        .length === count,
    { url, count },
  );
}
async function nextQuestion(p) {
  const title = await p.locator("article.question h2").textContent();
  await btn(p, "Next question").click();
  await p.waitForFunction(
    (title) =>
      document.querySelector("article.question h2")?.textContent !== title,
    title,
  );
  // The default UI resets answer state in a React effect when the question changes.
  await p.waitForFunction(() =>
    [
      ...document.querySelectorAll(
        "article.question textarea, article.question input[type=radio], article.question select",
      ),
    ].every((el) => (el.type === "radio" ? !el.checked : el.value === "")),
  );
}
async function journey(url, custom) {
  const p = await page();
  await p.goto(url + (custom ? "/experience/makitra/" : "/?page=labs"));
  if (custom) {
    await btn(p, "Open lab")
      .waitFor()
      .catch(async (e) => {
        console.error(await p.locator("body").innerText());
        throw e;
      });
    await p.keyboard.press("Tab");
    assert.equal(await p.locator(":focus").textContent(), "Skip to content");
    await p.keyboard.press("Enter");
    assert.equal(await p.locator(":focus").getAttribute("id"), "main-content");
  }
  await p.getByRole("button", { name: /^Open lab/ }).click();
  await btn(p, custom ? "Start lesson" : "Start learning session").click();
  await btn(p, custom ? "Pause lesson" : "Pause").click();
  await btn(p, custom ? "Resume lesson" : "Resume").click();
  // Both presentations submit the same preparation response and experiment input.
  await p
    .locator("textarea")
    .first()
    .fill(
      "I expect a single changed input to make the comparison interpretable.",
    );
  await btn(p, "Save response").first().click();
  await btn(p, custom ? "Run experiment" : "Run comparison").click();
  await narrow(p);
  await btn(p, custom ? "Start practice" : "Start practice check").click();
  await p.locator("article.question h2").waitFor();
  await btn(p, custom ? "Pause practice" : "Pause session").click();
  await btn(p, custom ? "Resume practice" : "Resume session").click();
  await btn(p, custom ? "Pause practice" : "Pause session").waitFor();
  for (let i = 0; i < 6; i++) {
    const question = p.locator("article.question");
    if (await question.locator("input[type=radio]").count())
      await question.locator("input[type=radio]").first().check();
    else if (await question.locator("textarea").count())
      await question
        .locator("textarea")
        .fill(
          "Hold all other inputs constant and compare the observed outcomes.",
        );
    else {
      const selects = question
        .locator("select")
        .filter({ has: p.locator("option[value=t1]") });
      await selects.nth(0).selectOption("t1");
      await selects.nth(1).selectOption("t2");
    }
    await btn(p, custom ? "Save answer" : "Check my reasoning")
      .click()
      .catch(async (e) => {
        console.error(
          "Failed",
          custom,
          i,
          await p.locator("article.question").innerText(),
          await p
            .locator(
              "article.question input, article.question select, article.question textarea",
            )
            .evaluateAll((els) =>
              els.map((el) => ({
                value: el.value,
                checked: el.checked,
                disabled: el.disabled,
              })),
            ),
        );
        throw e;
      });
    await waitSaved(p, url, i + 1);
    await btn(p, custom ? "Save answer" : "Check my reasoning").waitFor({
      state: "detached",
    });
    if (i < 5) await nextQuestion(p);
  }
  await narrow(p);
  if (custom) {
    await btn(p, "Finish and review").click();
    await btn(p, "Save and finish").click();
    await p
      .getByRole("heading", { name: "Practice, reflected.", exact: true })
      .waitFor();
  } else {
    await btn(p, "Finish session").click();
    await p
      .getByRole("dialog")
      .getByRole("button", { name: "Finish & review", exact: true })
      .click();
    await p.getByRole("heading", { name: "Keep the useful part." }).waitFor();
  }
  const stored = await summary(url);
  assert.equal(stored.attempts.length, 6);
  assert.equal(stored.visits.length, 1);
  assert.equal(stored.visits[0].status, "finished");
  assert.equal(stored.sessions[0].completion, "complete");
  assert(stored.attempts.every((a) => a.assistance.includes("lab_materials")));
  assert.equal(stored.attempts.filter((a) => a.status === "pending").length, 4);
  await p.close();
  return {
    attempts: stored.attempts
      .map((a) => ({
        item_id: a.item_id,
        answer: a.answer,
        score: a.score,
        status: a.status,
        assistance: a.assistance,
      }))
      .sort((a, b) => a.item_id.localeCompare(b.item_id)),
    visits: stored.visits.map((v) => ({
      status: v.status,
      reading_count: v.reading_count,
      experiment_count: v.experiment_count,
      help_count: v.help_count,
      responses: Object.fromEntries(
        Object.entries(v.responses).map(([k, r]) => [k, r.value]),
      ),
      experiment_results: Object.fromEntries(
        Object.entries(v.experiment_results).map(([k, r]) => [
          k,
          { inputs: r.inputs, output: r.output },
        ]),
      ),
    })),
    learners: stored.learners.map((l) => ({
      course_id: l.course_id,
      capability: l.capability,
      dimensions: l.dimensions,
      assisted_attempts: l.assisted_attempts,
      independent_attempts: l.independent_attempts,
    })),
  };
}
try {
  const standard = await fixture("standard"),
    custom = await fixture("makitra"),
    recovery = await fixture("recovery"),
    locked = await fixture("locked", "fixture-token");
  assert.deepEqual(await journey(custom, true), await journey(standard, false));
  console.log(
    "Stored outcomes match through both frontends, including all six question formats.",
  );
  const p = await page();
  await p.goto(recovery + "/experience/makitra/");
  await btn(p, "Open lab").click();
  await btn(p, "Start lesson").click();
  const draft = "A draft survives a refresh in its workspace.";
  await p.locator("textarea").first().fill(draft);
  await p.reload();
  await p.getByRole("button", { name: /^(Resume|Pause) lesson$/ }).waitFor();
  if (await btn(p, "Resume lesson").count())
    await btn(p, "Resume lesson").click();
  assert.equal(await p.locator("textarea").first().inputValue(), draft);
  assert.equal((await summary(recovery)).visits.length, 1);
  // Lose a successful non-idempotent create response. Recovery must find/link it.
  let creates = 0;
  const loseCreate = async (route) => {
    creates++;
    await route.fetch();
    await route.abort("connectionfailed");
  };
  await p.route("**/api/sessions", loseCreate);
  await btn(p, "Start practice").click();
  await p
    .getByText("A practice start needs to be recovered before continuing.")
    .waitFor();
  await p.unroute("**/api/sessions", loseCreate);
  // Switch presentation while creation is ambiguous; the shared intent must survive.
  await p.goto(recovery + "/?page=lab&lab_id=demo-lab");
  await btn(p, "Resume").click();
  await btn(p, "Start practice check").click();
  await btn(p, "Find interrupted practice").click();
  await p.getByRole("button", { name: /^Recover practice from/ }).click();
  await p.locator("article.question h2").waitFor();
  await p.goto(
    recovery +
      "/experience/makitra/#session=" +
      (await summary(recovery)).sessions[0].id,
  );
  await btn(p, "Save answer").waitFor();
  if (await btn(p, "Resume practice").count())
    await btn(p, "Resume practice").click();
  assert.equal(creates, 1);
  assert.equal((await summary(recovery)).sessions.length, 1);
  const liveSession = await (
    await fetch(
      recovery + "/api/sessions/" + (await summary(recovery)).sessions[0].id,
    )
  ).json();
  const mcqIndex = liveSession.items.findIndex((i) => i.type === "mcq");
  for (let i = 0; i < mcqIndex; i++) await nextQuestion(p);
  await p.locator("input[type=radio]").first().check();
  let lostAnswer = 0;
  const loseAnswer = async (route) => {
    lostAnswer++;
    await route.fetch();
    await route.abort("connectionfailed");
  };
  await p.route("**/answers", loseAnswer);
  await btn(p, "Save answer").click();
  await p.getByRole("alert").waitFor();
  await p.unroute("**/answers", loseAnswer);
  await btn(p, "Save answer").click();
  await p.getByText("Answer-key feedback", { exact: true }).waitFor();
  assert.equal(lostAnswer, 1);
  assert.equal((await summary(recovery)).attempts.length, 1);
  // The standard frontend opens the very same session and evidence.
  const sessionId = (await summary(recovery)).sessions[0].id;
  await p.goto(recovery + `/?page=session&session_id=${sessionId}`);
  await p.locator("article.question h2").waitFor();
  assert.equal((await summary(recovery)).sessions.length, 1);
  await p.goto(recovery + "/?page=lab&lab_id=demo-lab&lesson_id=explore");
  await p
    .locator('button[aria-current="step"]')
    .filter({ hasText: "Look, listen, and discuss" })
    .waitFor();
  // Rich activities preserve the shared execution boundary and unavailable-tutor state.
  await p.goto(recovery + "/experience/makitra/#lab=demo-lab&lesson=explore");
  await btn(p, "Start lesson").click();
  const failTutor = (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Tutor is unavailable. Try again later.",
      }),
    });
  await p.route("**/discussion", failTutor);
  await p.getByLabel(/^Message to/).fill("What should stay constant?");
  await btn(p, "Send to tutor").click();
  await p.getByText("Tutor is unavailable. Try again later.").waitFor();
  await p.unroute("**/discussion", failTutor);
  await btn(p, "Send to tutor").click();
  await p
    .getByText("Which comparison keeps the other conditions unchanged?", {
      exact: true,
    })
    .waitFor();
  await btn(p, "Run visualization").click();
  const inner = p
    .frameLocator(".lab-visualization-frame")
    .frameLocator("iframe");
  await inner.locator("body").waitFor();
  assert.equal(
    await inner.locator("body").evaluate(() => {
      try {
        return parent.document.body.textContent;
      } catch {
        return "blocked";
      }
    }),
    "blocked",
  );
  assert(
    (
      await p
        .getByRole("link", { name: "Open coursework" })
        .getAttribute("href")
    ).includes("assignment_id=demo-assignment"),
  );
  await narrow(p);
  await p.screenshot({ path: "/tmp/gym-makitra-lesson.png", fullPage: true });
  await btn(p, "Start practice").click();
  await p.getByText("transfer", { exact: true }).waitFor();
  assert.equal(
    (await summary(recovery)).sessions.filter((s) => s.mode === "transfer")
      .length,
    1,
  );
  await p.goto(recovery + "/experience/makitra/#lab=missing");
  await p.getByRole("alert").waitFor();
  await btn(p, "Try again").click();
  assert(!(await p.getByText("Design preview", { exact: true }).count()));
  // Authentication is recoverable and never invokes synthetic fallback.
  await p.goto(locked + "/experience/makitra/");
  await p.getByLabel("Server access token").fill("fixture-token");
  await btn(p, "Unlock workspace").click();
  await btn(p, "Open lab").waitFor();
  assert.equal((await summary(locked)).attempts.length, 0);
  // Preview runs without *any* API calls and cannot create learner history.
  await p.route("**/api/**", () => {
    throw Error("Preview must not request the API");
  });
  await p.goto(locked + "/experience/makitra/?preview=1");
  await btn(p, "Open lab").click();
  await btn(p, "Start lesson").click();
  await btn(p, "Start practice").click();
  await p.locator("input[type=radio]").first().check();
  await btn(p, "Save answer").click();
  assert.equal((await summary(locked)).visits.length, 0);
  await p.unroute("**/api/**");
  await p.goto(custom + "/experience/makitra/");
  await btn(p, "Open lab").waitFor();
  await p.screenshot({ path: "/tmp/gym-makitra-catalog.png", fullPage: true });
  await p.setViewportSize({ width: 390, height: 844 });
  await noOverflow(p);
  await p.screenshot({ path: "/tmp/gym-makitra-mobile.png", fullPage: true });
  assert.deepEqual(problems, []);
  console.log(
    "Experience browser checks passed: parity, recovery, refresh, auth, transfer, tutor, sandbox, preview, keyboard, narrow screens and shared history.",
  );
} finally {
  await browser.close();
  for (const server of servers) server.kill("SIGTERM");
}
