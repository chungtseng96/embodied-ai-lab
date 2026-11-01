import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { spawn, type ChildProcess } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const project = path.resolve(here, "../..");
const fixtureScript = path.join(project, "scripts/e2e_fixture.py");
const frontendDist = path.join(project, "frontend/dist");

type Backend = {
  root: string;
  url: string;
  restart: () => Promise<void>;
  close: () => Promise<void>;
};

async function launch(root: string): Promise<{ child: ChildProcess; url: string }> {
  const child = spawn(process.env.PYTHON ?? "python3", [
    fixtureScript,
    "--outputs-root", root,
    "--frontend-dir", frontendDist,
    "--port", "0",
  ], {
    cwd: project,
    env: {
      ...process.env,
      PYTHONPATH: [path.join(project, "src"), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stderr = "";
  child.stderr?.on("data", (chunk: Buffer) => {
    stderr = `${stderr}${chunk.toString()}`.slice(-4000);
  });
  try {
    const url = await new Promise<string>((resolve, reject) => {
      let output = "";
      const timer = setTimeout(() => {
        reject(new Error(`backend startup timed out; stdout=${output}; stderr=${stderr}`));
      }, 10_000);
      child.stdout?.on("data", (chunk: Buffer) => {
        output = `${output}${chunk.toString()}`;
        const match = output.match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match) {
          clearTimeout(timer);
          resolve(match[0]);
        }
      });
      child.once("error", (error) => {
        clearTimeout(timer);
        reject(new Error(`backend failed to launch: ${error.message}; stderr=${stderr}`));
      });
      child.once("exit", (code) => {
        clearTimeout(timer);
        reject(new Error(`backend exited before startup (${code}); stdout=${output}; stderr=${stderr}`));
      });
    });
    return { child, url };
  } catch (error) {
    await stop(child);
    throw error;
  }
}

async function stop(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) return;
  child.kill("SIGTERM");
  const exited = new Promise<void>((resolve) => child.once("exit", () => resolve()));
  const graceful = await Promise.race([
    exited.then(() => true),
    new Promise<false>((resolve) => setTimeout(() => resolve(false), 2_000)),
  ]);
  if (graceful) return;
  child.kill("SIGKILL");
  await Promise.race([
    exited,
    new Promise<void>((resolve) => setTimeout(resolve, 2_000)),
  ]);
}

const backendTest = test.extend<{ backend: Backend }>({
  backend: async ({}, use) => {
    const root = await mkdtemp(path.join(tmpdir(), "laundrybench-e2e-"));
    let running: Awaited<ReturnType<typeof launch>>;
    try {
      running = await launch(root);
    } catch (error) {
      await rm(root, { recursive: true, force: true });
      throw error;
    }
    const backend: Backend = {
      root,
      get url() { return running.url; },
      restart: async () => {
        await stop(running.child);
        running = await launch(root);
      },
      close: async () => {
        try {
          await stop(running.child);
        } finally {
          await rm(root, { recursive: true, force: true });
        }
      },
    };
    try {
      await use(backend);
    } finally {
      await backend.close();
    }
  },
});

async function openRun(page: Page, baseUrl: string, run = "exp-e2e-alpha") {
  await page.goto(baseUrl);
  const runNavigation = page.getByRole("navigation", { name: "Experiment runs" });
  const runButton = runNavigation.getByRole("button", { name: new RegExp(run) });
  await runButton.click();
  await expect(runButton).toHaveClass(/active/);
  await expect(page.getByRole("heading", { name: "Manual review" })).toBeVisible();
}

async function expectCoverage(page: Page, value: string) {
  const overview = page.locator("details.run-overview");
  if (!(await overview.evaluate((element: HTMLDetailsElement) => element.open))) {
    await overview.locator("summary").click();
  }
  const coverage = overview.locator(".kpi").filter({ hasText: "Decision coverage" });
  await expect(coverage.getByText(value, { exact: true })).toBeVisible();
}

backendTest("review writes real labels, refreshes metrics, and survives server restart and reload", async ({ page, backend }) => {
  await openRun(page, backend.url);
  await page.getByLabel("Review notes").fill("Verified from browser acceptance");
  await page.getByRole("button", { name: "Save review", exact: true }).click();
  await expect(page.getByText("Review saved. Metrics refreshed.")).toBeVisible();
  await expectCoverage(page, "1 reviewed · 2 pending · 0 excluded");
  await backend.restart();
  await page.goto(backend.url);
  await page.getByRole("navigation", { name: "Experiment runs" }).getByRole("button", { name: /exp-e2e-alpha/ }).click();
  await expect(page.getByLabel("Review notes")).toHaveValue("Verified from browser acceptance");
  const detail = await (await page.request.get(`${backend.url}/api/runs/exp-e2e-alpha`)).json();
  expect(detail.revision).toBe(1);
  expect(detail.summary.pending_episodes).toBe(2);
  expect(detail.episodes[0].annotation.notes).toBe("Verified from browser acceptance");
});

backendTest("exclusion removes an episode from metrics and restoring it returns it to reviewed counts", async ({ page, backend }) => {
  await openRun(page, backend.url);
  await page.getByRole("radio", { name: "Success", exact: true }).check();
  await page.getByRole("button", { name: "Save review", exact: true }).click();
  await expectCoverage(page, "1 reviewed · 2 pending · 0 excluded");
  await page.getByRole("radio", { name: "Exclude", exact: true }).check();
  await page.getByLabel("Reason for exclusion").fill("Camera evidence is obstructed");
  await page.getByRole("button", { name: "Save exclusion" }).click();
  await expectCoverage(page, "0 reviewed · 2 pending · 1 excluded");
  await page.getByLabel("Filter episodes").getByRole("button", { name: "Excluded" }).click();
  await page.getByRole("radio", { name: "Failure", exact: true }).check();
  await page.getByRole("button", { name: "Save review", exact: true }).click();
  await expectCoverage(page, "1 reviewed · 2 pending · 0 excluded");
});

backendTest("declining the unsaved-change prompt keeps the draft and selected run", async ({ page, backend }) => {
  await openRun(page, backend.url);
  await page.getByLabel("Review notes").fill("Keep this draft");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("navigation", { name: "Experiment runs" }).getByRole("button", { name: /exp-e2e-beta/ }).click();
  await expect(page.getByLabel("Review notes")).toHaveValue("Keep this draft");
  await expect(page.getByRole("navigation", { name: "Experiment runs" }).getByRole("button", { name: /exp-e2e-alpha/ })).toHaveClass(/active/);
});

backendTest("two tabs loaded at one revision surface a real 409 conflict without losing the draft", async ({ browser, backend }) => {
  const first = await browser.newPage();
  const second = await browser.newPage();
  await openRun(first, backend.url);
  await openRun(second, backend.url);
  await first.getByLabel("Review notes").fill("First reviewer");
  await first.getByRole("button", { name: "Save review", exact: true }).click();
  await expect(first.getByText("Review saved. Metrics refreshed.")).toBeVisible();
  await second.getByLabel("Review notes").fill("Second reviewer draft");
  await second.getByRole("button", { name: "Save review", exact: true }).click();
  await expect(second.getByText("labels changed; reload before saving")).toBeVisible();
  await expect(second.getByLabel("Review notes")).toHaveValue("Second reviewer draft");
  await first.close();
  await second.close();
});

backendTest("experiment comparison withholds incompatible deltas until the API acknowledgment flag is supplied", async ({ page, backend }) => {
  const incompatible = await (await page.request.get(
    `${backend.url}/api/runs/exp-e2e-beta/compare/exp-e2e-alpha`,
  )).json();
  expect(incompatible.compatibility.status).toBe("mismatched");
  expect(incompatible.delta).toBeNull();
  const acknowledged = await (await page.request.get(
    `${backend.url}/api/runs/exp-e2e-beta/compare/exp-e2e-alpha?acknowledge_incompatible=1`,
  )).json();
  expect(acknowledged.compatibility.status).toBe("mismatched");
  expect(acknowledged.delta).not.toBeNull();
});

backendTest("comparison UI shows context, withholds mismatched deltas, and keeps representative evidence independent", async ({ page, backend }) => {
  await openRun(page, backend.url, "exp-e2e-beta");
  await expect(page.getByRole("region", { name: "Current experiment context" })).toContainText("Controlled fixture for browser acceptance");
  await page.locator("details.run-overview > summary").click();
  await page.getByLabel("Baseline experiment").selectOption("exp-e2e-alpha");
  const compatibility = page.getByRole("status").filter({ hasText: "Compatibility: mismatched" });
  await expect(compatibility).toBeVisible();
  await expect(page.getByRole("heading", { name: "Descriptive outcome differences" })).toHaveCount(0);
  await page.getByRole("button", { name: "Acknowledge incompatible comparison and show descriptive delta" }).click();
  await expect(page.getByRole("heading", { name: "Descriptive outcome differences" })).toBeVisible();
  const representative = page.getByRole("region", { name: "Representative episode evidence" });
  await representative.getByLabel("Candidate representative episode").selectOption("episode-001");
  await representative.getByLabel("Baseline representative episode").selectOption("episode-002");
  await expect(representative.locator(".representative-card")).toHaveCount(2);
  await expect(representative).toContainText("episode-001");
  await expect(representative).toContainText("episode-002");
});

backendTest("keyboard-only navigation enters a run, reviews an episode, and advances with focus", async ({ page, backend }) => {
  await page.goto(backend.url);
  const navigation = page.getByRole("navigation", { name: "Experiment runs" });
  const alphaButton = navigation.getByRole("button", { name: /exp-e2e-alpha/ });
  await expect(alphaButton).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator("a.brand")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Refresh experiments" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Search experiments")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(alphaButton).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Manual review" })).toBeVisible();

  const notes = page.getByLabel("Review notes");
  let foundNotes = false;
  for (let index = 0; index < 80 && !foundNotes; index += 1) {
    foundNotes = await notes.evaluate((element) => element === document.activeElement);
    if (!foundNotes) await page.keyboard.press("Tab");
  }
  await expect(notes).toBeFocused();
  await page.keyboard.type("keyboard review");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Save review", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  const saveNext = page.getByRole("button", { name: "Save & next: save review and go to next pending episode" });
  await expect(saveNext).toBeFocused();
  await page.keyboard.press("Enter");
  const nextHeading = page.getByRole("heading", { name: "episode-002" });
  await expect(nextHeading).toBeVisible();
  await expect(nextHeading).toBeFocused();
  await expect(page.getByRole("status").filter({ hasText: "Review saved. Opened the next pending episode." })).toBeVisible();
});

backendTest("a corrupt linked video reports an error while the trace and manual review remain usable", async ({ page, backend }) => {
  await openRun(page, backend.url);
  await page.getByRole("region", { name: "Episode queue" }).getByRole("button", { name: /episode-003/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: /could not (decode|load) this video\/mp4 stream/ })).toBeVisible();
  await expect(page.getByLabel("Review notes")).toBeVisible();
  await page.getByLabel("Review notes").fill("Corrupt media did not block review");
  await page.getByRole("button", { name: "Save review", exact: true }).click();
  await expect(page.getByText("Review saved. Metrics refreshed.")).toBeVisible();
});

backendTest("review workspace remains usable at a mobile viewport", async ({ page, backend }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openRun(page, backend.url);
  await expect(page.getByLabel("Review notes")).toBeVisible();
  const saveNext = page.getByRole("button", { name: "Save & next: save review and go to next pending episode" });
  await expect(saveNext).toBeVisible();
  const dimensions = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    documentWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
  const buttonBounds = await saveNext.boundingBox();
  expect(buttonBounds).not.toBeNull();
  expect(buttonBounds!.x).toBeGreaterThanOrEqual(0);
  expect(buttonBounds!.x + buttonBounds!.width).toBeLessThanOrEqual(390);
});

backendTest("the rendered review workspace has no axe WCAG A/AA violations", async ({ page, backend }) => {
  await openRun(page, backend.url, "exp-e2e-beta");
  await page.locator("details.run-overview > summary").click();
  await page.getByLabel("Baseline experiment").selectOption("exp-e2e-alpha");
  await expect(page.getByRole("status").filter({ hasText: "Compatibility: mismatched" })).toBeVisible();
  await page.getByRole("button", { name: "Acknowledge incompatible comparison and show descriptive delta" }).click();
  await expect(page.getByRole("heading", { name: "Descriptive outcome differences" })).toBeVisible();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

backendTest("video event seeking honors the recorded clock offset and missing media is explicit", async ({ page, backend }) => {
  await openRun(page, backend.url);
  const video = page.getByLabel("Episode video", { exact: true });
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.readyState)).toBeGreaterThanOrEqual(1);
  await page.getByRole("button", { name: "Seek to recorded event grasp at 0.50 seconds" }).click();
  await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(0.5, 1);
  await expect(page.getByLabel("Seek video from trace")).toHaveValue("100");
  await page.getByRole("region", { name: "Episode queue" }).getByRole("button", { name: /episode-002/ }).click();
  await expect(page.getByText("No media linked to this episode")).toBeVisible();
});

backendTest("delaying the real response for an older run does not replace the newer selection", async ({ page, backend }) => {
  let release!: () => void;
  const paused = new Promise<void>((resolve) => { release = resolve; });
  let started!: () => void;
  const intercepted = new Promise<void>((resolve) => { started = resolve; });
  await page.route("**/api/runs/exp-e2e-alpha", async (route) => {
    started();
    await paused;
    await route.continue();
  });
  await page.goto(backend.url);
  await intercepted;
  const runNavigation = page.getByRole("navigation", { name: "Experiment runs" });
  const betaButton = runNavigation.getByRole("button", { name: /exp-e2e-beta/ });
  await betaButton.click();
  await expect(betaButton).toHaveClass(/active/);
  const lateAlphaResponse = page.waitForResponse((response) =>
    response.url().endsWith("/api/runs/exp-e2e-alpha"),
  );
  release();
  expect((await lateAlphaResponse).ok()).toBeTruthy();
  await page.unroute("**/api/runs/exp-e2e-alpha");
  await expect(betaButton).toHaveClass(/active/);
  const currentContext = page.getByRole("region", { name: "Current experiment context" });
  await expect(currentContext).toContainText("exp-e2e-beta");
  await expect(currentContext).toContainText("Controlled fixture for browser acceptance");
});
