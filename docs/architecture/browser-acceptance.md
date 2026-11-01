# LaundryBench browser acceptance

The browser suite in `projects/laundrybench/e2e` runs the built operator UI
against the installed Python package and its real loopback review server. It
does not replace API responses or use the frontend unit-test mocks. The one
Playwright route delay test pauses a genuine same-origin API request, then lets
that request reach the backend unchanged.

Each test starts a fresh Python server process on an ephemeral port with a
private temporary outputs root. The fixture contains deterministic run,
episode, label, and trace artifacts plus an ffmpeg-generated, short MP4. One
episode has no linked media. Tests can restart the process over the same root
to verify that persisted labels survive server restarts. The videos and run
artifacts stay in temporary directories and are not committed.

The acceptance flows cover review persistence and refreshed metrics, exclude
and restore behavior, declined unsaved navigation, concurrent-tab revision
conflicts, incompatible-context acknowledgment behavior, keyboard save-and-next
with focus movement, mobile viewport layout, video-to-trace clock offset and
missing/corrupt-media states with review continuity, a delayed real-network
response race, and axe WCAG A/AA checks on the review workspace. Playwright
retains traces, screenshots, and video for failing CI tests.

Run the suite from the repository root after installing the project and
building the frontend:

```bash
python -m pip install -e projects/laundrybench
npm --prefix projects/laundrybench/frontend ci
npm --prefix projects/laundrybench/frontend run build
npm --prefix projects/laundrybench/e2e ci
cd projects/laundrybench/e2e
npx playwright install chromium
npm test
```

The GitHub Actions workflow installs ffmpeg and the official Playwright
Chromium dependencies on its runner. Running browsers locally is optional; the
suite can also be typechecked and discovered without installing a browser.
