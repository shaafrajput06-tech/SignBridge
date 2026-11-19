# SignBridge website (GitHub Pages)

**Address:** <https://shaafrajput06-tech.github.io/SignBridge/>

Open it on any phone, tablet or computer with a camera, in Chrome, Edge or Safari. It is served over
HTTPS, so browsers allow the camera. The website is built and published automatically by
`.github/workflows/website.yml` every time something is pushed to the `main` branch.

## One-time setting [ME]

GitHub only publishes the site after this is switched on once:

1. Open <https://github.com/shaafrajput06-tech/SignBridge/settings/pages> (signed in to GitHub).
2. Under **Build and deployment**, set **Source** to **GitHub Actions**. There is no Save button; the
   choice is stored straight away.
3. Open the **Actions** tab, click **Website and checks**, then **Run workflow** > **Run workflow**.
   After about 5-10 minutes the run turns green and the address above works.

## What works on the website

| Feature | Website | Laptop with `start_signbridge.bat` |
|---|---|---|
| PSL mode (Phase 0 demo hand shapes, vocabulary, Urdu/English text, speech) | yes | yes |
| ASL mode (250 ASL words) | yes, in the browser (LiteRT.js, signs resampled to 32 frames) | yes, through the local server (each sign's real length) |
| Saving training samples, training report, CSV download | no (needs the server) | yes |

The header says **"Website version"** when there is no server. Everything runs on the device:
camera frames never leave the browser, and the website has no server that could receive them.

## The first visit downloads the models

The landmark and ASL models are about 29 MB together (hand 7.8 MB, pose 5.8 MB, face 3.8 MB, ASL
11.2 MB), plus the browser runtimes. On a phone, open the site on Wi-Fi the first time. The browser
caches the files after that.

## Check results

Each build runs every test and a real-browser ASL check, and publishes the results with the site:

- <https://shaafrajput06-tech.github.io/SignBridge/ci/status.json>: pass or fail for each check, the
  commit and a link to the run;
- `ci/tests.txt`, `ci/licences-release.txt`, `ci/asl-selftest.json`: the full output.

A failing check does not stop the website from being published; it shows up here instead.

## If something goes wrong

| Problem | What to do |
|---|---|
| 404 at the address | Do the one-time setting above, then run the workflow again. |
| The Actions run is red | Open it, click the red step and send a screenshot of the error. |
| "Camera permission was declined" | Allow the camera for the site in the browser's settings, then reload. |
| ASL mode says the model file was not found | The build could not download it; run the workflow again. |
