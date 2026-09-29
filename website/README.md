# Updating the family website

The website is generated from this repository. Its layout and mapping are saved
here; publishing does not require interpreting documents or manually arranging
pages.

## Everyday use

1. Edit the appropriate Markdown document or registry, or add an image to a photo
   folder.
2. Run `./preview_site.sh` from the repository. Open
   <http://127.0.0.1:4176/>. Stop the preview with Ctrl-C.
3. Ask Codex to **publish the latest site** when the preview is ready.

Preview builds and checks the site but does not publish it. To build without
starting a server, use `./preview_site.sh --build-only`. To use another port,
run `./preview_site.sh --port 4177`.

## Content mapping

Edit `website/site.json` to select page source documents and their output paths,
choose the timeline SVG, or change a photo collection's directory. Output paths
are relative to the generated website. For example, `america/index.html` is the
`/america/` page. Update navigation links too when changing a page's route.

| Content | Source |
| --- | --- |
| Homepage, family names, introductions | Markdown files selected in `documents` |
| America history | `docs/sections/pyrce_history.md` |
| Timeline | SVG selected in `timeline`; use the same filename in the history document |
| Muszyna photos | Directory selected in `collections.muszyna.directory` |
| Sophie and Joseph photos | Directory selected in `collections.america.directory` |
| Trees, GEDCOM, analytics | Generated from the authoritative registries |
| Page frame and styling | `website/templates/` |

The Sophie and Joseph directory currently links to Google Drive. The linked
folder must be locally available before building. Missing media or unreadable
images stop the build instead of silently disappearing from the published site.
Supported images are JPG, JPEG, PNG, GIF, TIFF and WebP. Matching PDFs alongside
Muszyna images appear as downloads. Research Markdown notes are not gallery images.

Each Sophie and Joseph image gets a URL derived from its filename, independent
of its position in the gallery. Adding a new image preserves existing URLs;
renaming an image changes its URL. `legacy_photo_urls` preserves the numbered
links from published version 23. Keep those entries; an intentionally removed or
renamed photo requires explicitly updating the corresponding mapping.

## Build and validation

`./preview_site.sh` validates registries, rebuilds the trees/export/analytics,
builds the dashboard with the installed Data plugin, generates the website, and
checks internal HTML file links. It does not check remote URLs, page fragments,
or links created at runtime by JavaScript. A successful build replaces
`artifacts/website/dist/` and writes `artifacts/website/build.json`. A failed
website generation or link check preserves the previous website output.

The Data builder is discovered from installed plugin versions; the scripts no
longer depend on a fixed plugin version. Optional overrides:

- `DATA_ANALYTICS_PLUGIN`: installed Data plugin directory.
- `CODEX_NODE`: absolute Node executable path.

No app dependency installation or protected runtime replacement is performed.
Regenerated tracked outputs, including the dashboard snapshot timestamp, may
appear in Git after a build. Review them with the source changes.

## Publishing with Codex / Sites

This is still the existing Muszyna Family Archive Site. Its ID and URL are in
`site.json`. Keep its existing audience unless a sharing change is requested.

1. Use the Sites hosting skill to open the existing Site's source checkout and
   retain the returned `source` result. Do not create another Site.
2. Build with `./preview_site.sh --build-only` if content changed since preview.
3. Run `uv run python -m scripts.website stage --checkout /absolute/site/checkout`.
   This checks the Site identity and build fingerprints, then copies the exact
   reviewed static output into that checkout. Stale or modified builds are rejected.
4. Run the Sites workflow with the retained `source` result and an archive path.
   It commits and pushes the staged output, then packages it. No further content
   mapping or build in the Sites checkout is needed.
5. Save and deploy the returned commit and archive using Sites, preserving
   access. Confirm deployment succeeded.

The genealogy repository owns `scripts/build_website.py`, `scripts/website.py`,
this configuration, and templates. The Sites repository is a deployment copy of
`dist/`, its hosting manifest, and `genealogy-build.json`. Do not maintain a second
builder there. The build fingerprint includes the linked photo files even though
those originals are outside this Git repository. Committing genealogy changes
and publishing to Sites remain separate operations.
