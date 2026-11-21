# Moving SignBridge to https://signmate-pk.github.io/

**Status: done on 2026-11-21.** The organisation `signmate-pk` was created, the repository was moved
into it and renamed `signmate-pk.github.io` in the same transfer, Pages kept its "GitHub Actions"
source, and <https://signmate-pk.github.io/> serves the site (checked in a browser: "SignMate",
"69 PSL signs · suggestions", "Community dataset — not yet validated"). The owner also chose a new
name, **SignMate** (PR #4). The steps below are kept as the record of how it was done.

**Old address switched off (2026-11-21).** At first the old address forwarded to the new one (step 6).
The owner then asked for the old website to disappear, so the forwarding pages were removed:
`https://shaafrajput06-tech.github.io/SignBridge/` now shows GitHub's 404 page. Only
`SignBridge/sw.js` is left there, to delete the old offline copy from browsers that saved it
(`tools/old_address_cleanup/README.md`).

Chosen by the owner on 2026-11-20 (master-v3.md section 3, Stage 7 B.4, free option).

**Why not `signbridge.github.io`?** That address belongs to whoever owns the GitHub name `signbridge`.
On 2026-11-20 that name is taken by another organisation (a 2023 student project), and GitHub does not
hand over names that are in use. `signmate-pk` keeps the SignBridge brand, says "Pakistan", and is free.

**What stays the same:** the app, the branding (SignBridge everywhere), the workflow that builds and
publishes the site, and all branches. The website already uses relative paths (`base: "./"` in
`web/vite.config.js`, `web/src/paths.js`), so it works at the new address without being rebuilt
differently. The address lives in one place: `shared_data/site.json`.

## Steps for you [ME] (about 15 minutes, all on github.com)

### 1. Create the free organisation `signmate-pk`
1. Sign in to GitHub as `shaafrajput06-tech`.
2. Open <https://github.com/account/organizations/new?plan=free>.
3. **Organization name:** `signmate-pk`. **Contact email:** yours. **This organization belongs to:**
   *My personal account*. Tick the terms box, then **Next**, then **Complete setup** (you can skip
   inviting people).
   - If GitHub says the name is taken, stop and tell me; I'll suggest the next name.

### 2. Move the repository into the organisation
1. Open <https://github.com/shaafrajput06-tech/SignBridge/settings> and scroll to the **Danger Zone**.
2. Click **Transfer**, choose **Specify an organization or user**, type `signmate-pk`, type the
   repository name to confirm, and click **I understand, transfer this repository**.
3. The repository is now at `https://github.com/signmate-pk/SignBridge`. GitHub forwards the old
   repository address, old git links and old download links there automatically.

### 3. Rename it so it becomes the organisation's main website
GitHub serves `https://signmate-pk.github.io/` from a repository named exactly
`signmate-pk.github.io`.
1. Open <https://github.com/signmate-pk/SignBridge/settings>.
2. Under **Repository name**, type `signmate-pk.github.io` and click **Rename**.

### 4. Check Pages and publish once
1. Open <https://github.com/signmate-pk/signmate-pk.github.io/settings/pages>.
   **Source** must say **GitHub Actions** (it moves with the repository; set it again if not).
2. Open the **Actions** tab. If GitHub asks whether to enable workflows, click **I understand my
   workflows, go ahead and enable them**.
3. Click **Website and checks** > **Run workflow** > **Run workflow** (branch `main`). This rebuilds the
   site that is already live; it does not publish any of the v3 work (that waits for Stage 7).
4. After about 5 minutes, open <https://signmate-pk.github.io/>. You should see SignBridge.

### 5. Let Claude back in
After the move, the repository has a new name, so Claude needs permission again:
- Tell Claude: *"The repo moved to signmate-pk/signmate-pk.github.io, connect it with push access."*
- If GitHub asks you to **install or approve the Claude app for the `signmate-pk` organisation**,
  choose the organisation and allow access to the `signmate-pk.github.io` repository.

### 6. Make the old address forward to the new one (later switched off, see the top)
GitHub only forwards the old *repository* address, not the old *website* address
(`shaafrajput06-tech.github.io/SignBridge/`), so a tiny forwarding site does that:
1. Open <https://github.com/new> (still as `shaafrajput06-tech`). **Repository name:**
   `shaafrajput06-tech.github.io`, **Public**, tick **Add a README file**, click **Create repository**.
2. In the new repository click **Add file** > **Upload files** and drag in the three files from the
   SignBridge folder `tools/old_address_redirect/` (now `tools/old_address_cleanup/`): `404.html`, `.nojekyll`
   and the folder `SignBridge` (it held `index.html`). Windows hides files starting with a dot: if `.nojekyll` does not show, skip
   it, it is optional here. Click **Commit changes**.
3. Open its **Settings** > **Pages**: **Source** = *Deploy from a branch*, **Branch** = `main`, folder
   `/ (root)`, **Save**.
4. After about 2 minutes, open <https://shaafrajput06-tech.github.io/SignBridge/>: it should jump to
   <https://signmate-pk.github.io/>.

### 7. On each computer where you have a copy of the code
In the SignBridge folder, run once (Command Prompt):

```
git remote set-url origin https://github.com/signmate-pk/signmate-pk.github.io.git
```

(Old links keep working because GitHub forwards them, but this avoids surprises later.)

## What Claude does (already done on branch `v3/master` unless marked)

- `shared_data/site.json` holds the new address, the new repository and the old ones.
- README, `docs/WEBSITE.md` and the baseline download tool use the new address, falling back to the
  old one until the move is finished.
- `tools/old_address_cleanup/`: what is left at the old address (no pages; a worker that clears old offline copies).
- `tests/test_site_address.py` fails if any file gives an address that disagrees with `site.json`.
- Later stages (PWA manifest, service-worker scope, `sitemap.xml`, `robots.txt`, Open Graph tags,
  Flutter links) read the address from `site.json` when they are added.
- Stage 7: check the live site at the new address and record the result in `reports/release_v3.md`.

## Optional later: your own domain

If you buy a domain later (for example `signbridge.pk`), the site can move again without changing the
code: add the domain under Settings > Pages > Custom domain, create the DNS records GitHub shows, tick
**Enforce HTTPS**, and change `site_url` in `shared_data/site.json`. GitHub then forwards
`signmate-pk.github.io` to the domain by itself, because both are on the same account.
