# Updating the family website

The website is generated from this repository. Its layout and mapping are saved
here; publishing does not require interpreting documents or manually arranging
pages.

## Everyday use

1. Edit the appropriate Markdown document or registry, or add an image to a photo
   folder.
2. Run `./preview_site.sh` from the repository. It opens
   <http://127.0.0.1:4176/> in your default browser. Stop the preview with
   Ctrl-C.
3. Ask Codex to **publish the latest site** when the preview is ready.

Preview builds and checks the site but does not publish it. To build without
starting a server, use `./preview_site.sh --build-only`. To use another port,
run `./preview_site.sh --port 4177`.

The footer date is set automatically when staging each publication, using the
America/Chicago calendar date. Local previews show their build date. Republishing
an older saved version retains that version's original publication date.

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

The Muszyna collection's `first_photo` setting selects the first gallery image;
the remaining images keep their filename order. `photo_credits` records linked
source credits shown in the gallery and on each credited image's detail page.

The Sophie and Joseph directory currently links to Google Drive. The linked
folder must be locally available before building. Missing media or unreadable
images stop the build instead of silently disappearing from the published site.
Supported images are JPG, JPEG, PNG, GIF, TIFF and WebP. Matching PDFs alongside
Muszyna images appear as downloads. Research Markdown notes are not gallery images.
Synced `.gvid` references in the Sophie and Joseph folder appear as video panels
among the photographs in filename order; viewers may need Google Drive permission
to open them.

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

Our Polish Family History uses the existing Site. Its ID and URL are in
`site.json`. Production uses the visitor gateway described below. Local previews
remain open and do not collect visitor information.

1. Use the Sites hosting skill to open the existing Site's source checkout and
   retain the returned `source` result. Do not create another Site.
2. Build with `./preview_site.sh --build-only` if content changed since preview.
3. Run `uv run python -m scripts.website stage --checkout /absolute/site/checkout`.
   This checks the Site identity and build fingerprints, then copies the exact
   reviewed static output and gateway into that checkout. Stale or modified builds
   are rejected. Static content is held in `archive-assets/`, outside the executable
   deployment archive; production serves it from private R2 storage.
   Upload new content objects **before** deploying an updated gateway:

   ```sh
   uv run python -m scripts.visitor_access --env-file .env.visitor-access upload --checkout /absolute/site/checkout
   ```

   On the initial migration, publish the gateway under the existing Sites account
   access policy first, then bootstrap objects and approved visitors using a
   request-scoped Sites service credential. Open the outer Sites entry policy only
   after verifying that the gateway protects every content route. The gateway
   remains responsible for the private email list and sessions on every hostname.
4. Run the Sites workflow with the retained `source` result and an archive path.
   It commits and pushes the staged output, then packages it. No further content
   mapping or build in the Sites checkout is needed.
5. Save and deploy the returned commit and archive using Sites, preserving
   access. Confirm deployment succeeded. The outer Sites policy permits reaching
   the email entry form; the application gateway authorizes all archive content.

The genealogy repository owns `scripts/build_website.py`, `scripts/website.py`,
this configuration, and templates. The Sites repository is a deployment copy of
the production Worker, a static content snapshot, its hosting manifest, and
`genealogy-build.json`. Do not maintain a second
builder there. The build fingerprint includes the linked photo files even though
those originals are outside this Git repository. Committing genealogy changes
and publishing to Sites remain separate operations.

## Visitor access in production

`website/access/worker.mjs` is the production-only serverless gateway. It serves
the generated static website from a private R2 binding named `BUCKET`; no public
asset directory is packaged in the deployment. D1 (`DB`) stores approved visitors,
hashed session tokens, and visit events. Schema-only migrations are generated
from `website/access/schema.js` using `npm run db:generate` in that directory.
Tests use the generated SQL against SQLite: `node --test tests/test_visitor_access.mjs`.

The approved list is `data/email.csv` with `Name,Email Address` columns (or
`name,email`). This file is ignored by Git and is never copied into the website,
source deployment checkout, or deployment archive. Changing the list requires an
owner import, not a site rebuild:

```sh
uv run python -m scripts.visitor_access validate data/email.csv
uv run python -m scripts.visitor_access --env-file .env.visitor-access import data/email.csv
```

Imports replace the active list. Removed addresses are disabled and their sessions
deleted. Emails are trimmed and compared without case; provider-specific aliases
are not guessed. Names preserve their spelling and diacritics.

Production requires the Sites secret `VISITOR_ADMIN_TOKEN`. The corresponding
local owner credential is `GENEALOGY_VISITOR_ADMIN_TOKEN` in the ignored,
permission-0600 `.env.visitor-access` file. Keep this file private and out of the
Sites checkout. Owner APIs accept that bearer token, never browser sessions.
Owner operations require HTTPS and refuse redirects to avoid forwarding secrets.
Sites service credentials used during initial bootstrap stay in session memory.

```sh
uv run python -m scripts.visitor_access --env-file .env.visitor-access export
uv run python -m scripts.visitor_access --env-file .env.visitor-access export --database /absolute/path/to/existing.duckdb
uv run python -m scripts.visitor_access --env-file .env.visitor-access cleanup
```

`export` moves all current visit events into the persistent DuckDB archive at
`artifacts/visitor-access/visits.duckdb`, creating it on the first run. Use
`--database` to merge into another existing DuckDB file. The `visitor_events`
table uses the event UUID as its primary key; unrelated tables are preserved.
Identical events are skipped, and changed browser context for an existing ID
is refreshed. Raw email/IP values and all other recorded visit fields are
preserved, with an additional `occurred_at_utc` timestamp. Historical icon
records are included. The former CSV output, date and icon CLI filters have
been replaced by this complete archive operation.

Generate and open the full-history visitor report from the local archive with
`./visit_report.sh`. Use `./visit_report.sh --export` to archive new online
events first, or `./visit_report.sh --no-open` to generate without opening a
browser. The script executes `scripts/templates/visit_analysis.ipynb` and saves
the executed notebook and HTML report under `artifacts/visitor-access/`.
Network registrations use the local `network_sources.json` evidence cache;
addresses without cached evidence are shown as unclassified.

The command downloads a bounded set of current records, commits the local
transaction, checkpoints and flushes the database, then verifies its saved
receipts before acknowledging online deletion in batches. Each acknowledgement
identifies exact event IDs and checks all exported values. Records changed
since download and new arrivals remain online for the next export. Recent
records awaiting browser metadata also stay online until their update completes
or the five-minute enrichment window expires. Interrupted
runs can safely be repeated using the same database: committed rows are
recognized and remaining online copies are removed. Local download or storage
failures cause no acknowledgement; deletion failures leave the committed
archive available for retry. Database files use owner-only permissions.

Keep this archive in a persistent location. The command rejects the generated
`artifacts/analytics/genealogy_analytics.duckdb`, which ordinary builds replace.
The visitor archive is ignored by Git and excluded from website deployment.
Approved visitors and remembered sessions are not part of visit exports.
Independent, short-lived rate-limit records preserve the login throttle even
when recent visit events have been removed.

Visitor sessions last 180 days. Cookies are host-only, Secure, HttpOnly and
SameSite=Lax, and contain random tokens rather than emails. Every protected
request rechecks that the email remains enabled. “Forget this browser” deletes
the server session and cookie. There is no production preview-header, hostname,
or query-string bypass. The separate local Python preview server never invokes
the gateway, displays its greeting, or writes visitor logs.
Existing mailto contact links are replaced in the production copy with the
archive owner contact at `rekarpyrce@gmail.com`. Source documents and local
preview retain their original contact links.

Logging records HTML page entries, downloads, entry challenges, and access
attempts (including failures and rate limiting). Supporting images/scripts/styles
require authorization without counting as extra visits. Unauthenticated background
requests receive a direct 403 instead of redirecting to the entry page; missing
background assets return 404 to authorized visitors without adding visit records.
Explicit document navigation still follows the normal entry flow. UTC timestamps
come from the gateway; browser time zone, offset and language are supplied by
JavaScript and may be unknown or inaccurate. The trusted connecting IP can be a
VPN or shared address. Anonymous requests have no email until one is submitted.
Queries are excluded from recorded paths. The DuckDB archive preserves raw recorded values and a UTC timestamp; browser
local time can be derived from the stored timezone. The diagnostic owner CSV
endpoint remains read-only and neutralizes spreadsheet formula prefixes.
Expired sessions and records older than 365 days are deleted on the next daily
gateway activity, or immediately by the owner cleanup command. Rate-limit records are eligible
for removal after ten minutes; their counts always use that rolling window. Private content
and personalized responses use `Cache-Control: private, no-store`.

Only the generic site icons at `/assets/favicon.svg`, `/favicon.ico`,
`/apple-touch-icon.png`, and `/apple-touch-icon-precomposed.png` are public.
These exact paths require no visitor session and create no visit records.
The builder generates ICO and PNG fallbacks from the existing favicon artwork.
Page and entry-screen icon links carry an artwork version, and icon responses
support ETags and one-day public caching. Family photographs and other archive
assets remain protected.

Email-only entry identifies a claimed address; it does not verify ownership.
Someone who knows an approved address can use it. An emailed verification link
would be a separate enhancement.
