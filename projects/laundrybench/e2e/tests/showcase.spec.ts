import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { cp, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { spawn, type ChildProcess } from "node:child_process";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const project = path.resolve(here, "../..");
const frontend = path.join(project, "frontend");
const dist = process.env.SHOWCASE_DIST ?? path.join(frontend, "dist");
const fixtureServer = path.join(project, "scripts/showcase_fixture_server.py");

test.use({ video: { mode: "on", size: { width: 1280, height: 900 } }, trace: "off" });

type StaticServer = { url: string; close: () => Promise<void> };

async function launchStaticServer(distRoot: string = dist): Promise<StaticServer> {
  const child = spawn(process.env.PYTHON ?? "python3", [fixtureServer, "--dist", distRoot, "--port", "0"], {
    cwd: project,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stderr = "";
  child.stderr?.on("data", (chunk: Buffer) => {
    stderr = `${stderr}${chunk.toString()}`.slice(-4000);
  });
  let output = "";
  let startupTimer: NodeJS.Timeout;
  try {
    const url = await new Promise<string>((resolve, reject) => {
      startupTimer = setTimeout(() => reject(new Error(`static fixture startup timed out; stdout=${output}; stderr=${stderr}`)), 10_000);
      child.stdout?.on("data", (chunk: Buffer) => {
        output = `${output}${chunk.toString()}`;
        const match = output.match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match) resolve(match[0]);
      });
      child.once("error", (error) => reject(new Error(`static fixture failed to launch: ${error.message}; stderr=${stderr}`)));
      child.once("exit", (code) => reject(new Error(`static fixture exited before startup (${code}); stdout=${output}; stderr=${stderr}`)));
    });
    clearTimeout(startupTimer!);
    return {
      url,
      close: async () => {
        if (child.exitCode !== null || child.signalCode !== null) return;
        child.kill("SIGTERM");
        await Promise.race([
          new Promise<void>((resolve) => child.once("exit", () => resolve())),
          new Promise<void>((resolve) => setTimeout(resolve, 2_000)),
        ]);
        if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL");
      },
    };
  } catch (error) {
    clearTimeout(startupTimer!);
    child.kill("SIGTERM");
    throw error;
  }
}

async function inspectNoLabelingControls(page: Page) {
  const reviewRecord = page.getByRole("region", { name: "Review record" });
  await expect(reviewRecord).toBeVisible();
  await expect(reviewRecord).toContainText(/read\s+only/i);
  await expect(page.getByLabel("Review notes")).toHaveCount(0);
  await expect(reviewRecord.locator("textarea")).toHaveCount(0);
  await expect(page.locator("form.label-form")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /save (review|label|exclusion)/i })).toHaveCount(0);
  await expect(reviewRecord.getByRole("radio")).toHaveCount(0);
}

test("read-only Showcase walkthrough works on desktop and mobile and records a demo", async ({ page, context, request }, testInfo) => {
  test.setTimeout(45_000);
  const server = await launchStaticServer();
  const video = page.video();
  let traceStopped = false;
  try {
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(server.url);

    const showcaseManifestResponse = await request.get(`${server.url}/showcase.json`);
    expect(showcaseManifestResponse.ok()).toBeTruthy();
    const manifest = await showcaseManifestResponse.json();
    expect(manifest.schema_version).toBe(1);
    expect(manifest.source_commit).toMatch(/^[a-f0-9]{40}$/);
    expect(manifest.source_repository).toBeTruthy();
    expect(manifest.evidence_kind).toBe("synthetic");
    expect(manifest.limitations).toBeTruthy();
    expect(manifest.walkthrough_video_url).toBeNull();

    await expect(page.getByRole("heading", { name: "Can a robot sort socks from the rest of the laundry?" })).toBeVisible();
    await expect(page.getByRole("note")).toContainText("All experiment outcomes shown here are synthetic.");
    await page.waitForTimeout(2_000);
    await page.getByRole("button", { name: "Open the evidence explorer" }).click();
    await expect(page.getByRole("heading", { name: "The real experiment workspace" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Episode workspace" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Episode queue" })).toBeVisible();
    await inspectNoLabelingControls(page);
    await page.waitForTimeout(2_000);

    const manifestText = JSON.stringify(manifest);
    await expect(page.getByText(manifest.source_commit, { exact: false }).first()).toBeVisible();
    for (const limitation of Array.isArray(manifest.limitations) ? manifest.limitations : [manifest.limitations]) {
      if (typeof limitation === "string") await expect(page.getByText(limitation, { exact: false }).first()).toBeVisible();
    }
    expect(manifestText).toContain(manifest.candidate_id);
    expect(manifestText).toContain(manifest.baseline_id);
    await expect(page.getByRole("link", { name: new RegExp(manifest.candidate_id) })).toBeVisible();
    await expect(page.getByRole("link", { name: new RegExp(manifest.baseline_id) })).toBeVisible();
    await page.waitForTimeout(2_000);

    await expect(page.getByText("MOCK DATA", { exact: true }).first()).toBeVisible();
    const comparison = page.getByRole("region", { name: "Baseline comparison" });
    const overview = page.locator("details.run-overview");
    if (!(await overview.evaluate((element: HTMLDetailsElement) => element.open))) {
      await overview.locator("summary").click();
    }
    await expect(comparison).toBeVisible();
    await expect(page.getByRole("region", { name: "Baseline experiment context" })).toContainText(manifest.baseline_id);
    await page.waitForTimeout(2_000);

    const desktopAxe = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(desktopAxe.violations, JSON.stringify(desktopAxe.violations, null, 2)).toEqual([]);

    const videoElement = page.getByLabel("Episode video", { exact: true });
    await expect.poll(() => videoElement.evaluate((element: HTMLVideoElement) => element.readyState)).toBeGreaterThanOrEqual(1);
    const traceSeek = page.getByLabel("Seek video from trace");
    await expect(traceSeek).toBeVisible();
    const traceChart = page.getByRole("img", { name: "Recorded joint position and target over elapsed time" });
    await expect(traceChart).toBeVisible();
    const traceCursor = page.getByTestId("trace-cursor");
    await expect(traceCursor).toHaveCount(1);
    await expect(traceCursor).toHaveAttribute("stroke", "#c16646");
    await expect(traceCursor).toHaveAttribute("stroke-width", "2");
    const initialCursorX = Number(await traceCursor.getAttribute("x1"));
    expect(Number.isFinite(initialCursorX)).toBe(true);
    await traceSeek.focus();
    await traceSeek.press("ArrowRight");
    await expect.poll(() => videoElement.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeGreaterThan(0);
    await expect.poll(async () => Number(await traceCursor.getAttribute("x1"))).toBeGreaterThan(initialCursorX);
    await page.waitForTimeout(2_000);

    const candidateBefore = await (await request.get(`${server.url}/api/runs/${manifest.candidate_id}`)).json();
    const writeResponse = await request.put(
      `${server.url}/api/runs/${manifest.candidate_id}/episodes/episode-001/label`,
      { data: { success: false, intervention: false, failure_category: "timeout", notes: "attempted mutation" } },
    );
    expect([405, 501]).toContain(writeResponse.status());
    const candidateAfter = await (await request.get(`${server.url}/api/runs/${manifest.candidate_id}`)).json();
    expect(candidateAfter).toEqual(candidateBefore);

    await page.setViewportSize({ width: 390, height: 844 });
    await inspectNoLabelingControls(page);
    const dimensions = await page.evaluate(() => ({
      viewportWidth: document.documentElement.clientWidth,
      documentWidth: document.documentElement.scrollWidth,
    }));
    expect(dimensions.documentWidth).toBeLessThanOrEqual(dimensions.viewportWidth);
    const mobileAxe = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(mobileAxe.violations, JSON.stringify(mobileAxe.violations, null, 2)).toEqual([]);
    await page.waitForTimeout(2_000);
  } finally {
    if (!traceStopped) {
      await context.tracing.stop({ path: testInfo.outputPath("showcase-trace.zip") });
      traceStopped = true;
    }
    await page.close();
    if (video) await video.saveAs(testInfo.outputPath("showcase-demo.webm"));
    await server.close();
  }
});

test("a curated non-null walkthrough URL renders a labeled video player", async ({ page }) => {
  const original = JSON.parse(await readFile(path.join(dist, "showcase.json"), "utf8"));
  expect(original.walkthrough_video_url).toBeNull();
  const mediaUrl = Object.keys(original.assets).find((url) => url.endsWith(".mp4"));
  expect(mediaUrl).toBeTruthy();

  const fixtureRoot = await mkdtemp(path.join(tmpdir(), "laundrybench-showcase-video-case-"));
  const fixtureDist = path.join(fixtureRoot, "dist");
  await cp(dist, fixtureDist, { recursive: true });
  await writeFile(
    path.join(fixtureDist, "showcase.json"),
    `${JSON.stringify({ ...original, walkthrough_video_url: mediaUrl }, null, 2)}\n`,
    "utf8",
  );
  let server: StaticServer | undefined;
  try {
    server = await launchStaticServer(fixtureDist);
    await page.goto(server.url);
    const walkthrough = page.getByLabel("LaundryBench software walkthrough recording", { exact: true });
    await expect(walkthrough).toBeVisible();
    await expect(walkthrough).toHaveAttribute("src", mediaUrl!);
    await expect.poll(() => walkthrough.evaluate((element: HTMLVideoElement) => element.readyState)).toBeGreaterThanOrEqual(1);
  } finally {
    await server?.close();
    await rm(fixtureRoot, { recursive: true, force: true });
  }
});
