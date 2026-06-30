# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Static single-page landing site for Salem Hills (Skyhawk) Lacrosse. There is no build system, package manager, framework, or tests — the entire site is `index.html` with inline `<style>` and local PNG assets. Nothing is compiled; the file served is the file edited.

## Running locally

Open `index.html` directly in a browser, or serve the directory:

```
python3 -m http.server 8000   # then visit http://localhost:8000
```

## Conventions

- **All CSS lives inline** in the `<style>` block of `index.html`. The brand palette is defined as CSS custom properties on `:root`: `--navy #0C2340`, `--sky #7BA4DB`, `--white`, `--gold #B3A369`. Reuse these variables rather than hardcoding hex values.
- **Image assets are versioned by filename, not by cache headers.** The favicon went through `favicon.png` → `skyhawk-favicon-v2.png` → `skyhawk-favicon-v3.png` to force cache-busting on update. When replacing an asset that may be cached, add a new `-vN` file and update the reference rather than overwriting in place. `banner-logo.png` is the main hero logo.
- Asset paths are relative (`./...`) so the site works from any subpath.

## Deployment

Deployed via **Cloudflare Pages** connected to GitHub (`bkimber99/skyhawklacrosse`). Every push to `main` auto-deploys — there is no build step (output directory is the repo root, no build command). The integration runs through the Cloudflare GitHub App at the account level, so there is no workflow, webhook, or deploy config committed to the repo; nothing here needs editing to deploy.

Live at `https://skyhawklacrosse.com` (custom domain) and `https://skyhawklacrosse.pages.dev` (Pages default). GitHub Pages is not used. Build/branch settings live in the Cloudflare dashboard, not in the repo.
