"""Stage the production visitor gateway and manage its private data over HTTPS.

Local website previews always serve the plain static bundle and never use this gateway.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

import duckdb

from scripts.lib.genealogy_data import ROOT

ACCESS = ROOT / "website/access"


def asset_manifest(directory: Path) -> dict[str, dict[str, str]]:
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Website assets must not contain symlinks.")
        if not path.is_file():
            continue
        relative = path.relative_to(directory).as_posix()
        if any(part.startswith(".") for part in Path(relative).parts):
            raise ValueError("Hidden files must not be published as website assets.")
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            media_type = "text/javascript"
        if media_type.startswith("text/") or media_type == "application/json":
            media_type += "; charset=utf-8"
        result["/" + relative] = {"hash": hashlib.sha256(path.read_bytes()).hexdigest(), "type": media_type}
    if "/index.html" not in result:
        raise ValueError("Website is missing index.html.")
    return result


def stage_gateway(checkout: Path, static: Path, hosting: dict) -> None:
    """Package only executable code; content bytes go into private R2 storage."""
    asset_manifest(static)
    for name in ["dist", "archive-assets", "access", "drizzle"]:
        if (checkout / name).is_symlink():
            raise ValueError(f"Destination {name} must not be a symlink.")
    # All validation above precedes replacing the deployment copy.
    for name in ["dist", "archive-assets", "access", "drizzle"]:
        if (checkout / name).exists():
            shutil.rmtree(checkout / name)
    shutil.copytree(static, checkout / "archive-assets")
    # Keep the source and open local preview intact; use the configured owner contact in production.
    for page in (checkout / "archive-assets").rglob("*.html"):
        content = page.read_text(encoding="utf-8")
        content = re.sub(r'<a\b[^>]*href=["\']mailto:[^"\']*["\'][^>]*>.*?</a>',
                         '<a href="mailto:rekarpyrce@gmail.com">Contact the archive owner</a>',
                         content, flags=re.IGNORECASE | re.DOTALL)
        page.write_text(content, encoding="utf-8")
    assets = asset_manifest(checkout / "archive-assets")
    shutil.copytree(ACCESS, checkout / "access", ignore=shutil.ignore_patterns("node_modules", "drizzle"))
    shutil.copytree(ACCESS / "drizzle", checkout / "drizzle")
    dist = checkout / "dist"
    (dist / "server").mkdir(parents=True)
    (dist / ".openai").mkdir()
    worker = (ACCESS / "worker.mjs").read_text(encoding="utf-8")
    client = (ACCESS / "client.js").read_text(encoding="utf-8")
    (dist / "server/index.js").write_text(
        worker + "\nexport default createGateway(" + json.dumps(assets, ensure_ascii=True)
        + "," + json.dumps(client) + ");\n", encoding="utf-8")
    hosting = {key: value for key, value in hosting.items() if key != "static"}
    hosting.update(d1="DB", r2="BUCKET")
    for target in [checkout / ".openai/hosting.json", dist / ".openai/hosting.json"]:
        target.write_text(json.dumps(hosting, indent=2) + "\n", encoding="utf-8")
    (checkout / "asset-manifest.json").write_text(json.dumps(assets, indent=2) + "\n", encoding="utf-8")


def load_visitors(path: Path) -> list[dict[str, str]]:
    """Accept Name/Email Address or name/email headers without echoing private rows."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = {key.strip().lower(): key for key in reader.fieldnames or []}
        email_key = fields.get("email") or fields.get("email address")
        name_key = fields.get("name")
        if not email_key or not name_key:
            raise ValueError("Visitor CSV requires Name and Email Address (or name and email) columns.")
        visitors = []
        seen = set()
        for number, row in enumerate(reader, 2):
            if not any(row.values()):
                continue
            email = (row.get(email_key) or "").strip().lower()
            name = (row.get(name_key) or "").strip()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254 or not name or len(name) > 120:
                raise ValueError(f"Invalid visitor CSV row {number}; correct its email and name.")
            if email in seen:
                raise ValueError(f"Duplicate email at visitor CSV row {number}.")
            seen.add(email)
            visitors.append({"email": email, "name": name})
    if not 1 <= len(visitors) <= 250:
        raise ValueError("Visitor CSV must contain 1–250 unique visitors.")
    return visitors


class NoRedirect(HTTPRedirectHandler):
    """Never forward owner credentials to a redirect target."""
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def credentials(env_file: Path | None) -> dict[str, str]:
    values = dict(os.environ)
    if env_file:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def api(url: str, route: str, values: dict, method="GET", body: bytes | None = None, media_type="application/json"):
    if urlsplit(url).scheme != "https" or urlsplit(url).username or urlsplit(url).password:
        raise ValueError("Owner operations require an HTTPS site URL without credentials.")
    secret = values.get("GENEALOGY_VISITOR_ADMIN_TOKEN")
    if not secret:
        raise ValueError("Set GENEALOGY_VISITOR_ADMIN_TOKEN or use --env-file with an ignored private file.")
    headers = {"Authorization": f"Bearer {secret}", "Content-Type": media_type,
               "User-Agent": "GenealogyOwnerTools/1.0"}
    if values.get("SITES_SERVICE_TOKEN"):
        headers["OAI-Sites-Authorization"] = "Bearer " + values["SITES_SERVICE_TOKEN"]
    request = Request(url.rstrip("/") + "/__access/admin/" + route, data=body, headers=headers, method=method)
    return build_opener(NoRedirect).open(request, timeout=60)


def upload_assets(checkout: Path, url: str, values: dict) -> None:
    expected = json.loads((checkout / "asset-manifest.json").read_text(encoding="utf-8"))
    actual = asset_manifest(checkout / "archive-assets")
    if actual != expected:
        raise ValueError("Staged static assets have changed. Rebuild and stage before uploading.")
    unique = {}
    for route, asset in actual.items():
        unique.setdefault(asset["hash"], (route, asset))

    def upload(item):
        route, asset = item
        content = (checkout / "archive-assets" / route.lstrip("/")).read_bytes()
        with api(url, "assets/" + asset["hash"], values, "PUT", content, "application/octet-stream"):
            pass

    with ThreadPoolExecutor(max_workers=4) as executor:
        for _ in executor.map(upload, unique.values()):
            pass
    print(f"Uploaded {len(unique)} protected content objects.")


ARCHIVE_FIELDS = ("id", "email", "occurred_at", "kind", "outcome", "path", "timezone",
                  "utc_offset_minutes", "language", "accept_language", "ip_address")
ARCHIVE_TYPES = ("VARCHAR PRIMARY KEY", "VARCHAR", "BIGINT NOT NULL", "VARCHAR NOT NULL",
                 "VARCHAR NOT NULL", "VARCHAR NOT NULL", "VARCHAR", "BIGINT", "VARCHAR", "VARCHAR", "VARCHAR")
DEFAULT_ARCHIVE = ROOT / "artifacts/visitor-access/visits.duckdb"


def archive_receipt(row: dict) -> str:
    encoded = json.dumps([row[field] for field in ARCHIVE_FIELDS], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_archive_row(row: dict) -> None:
    if not isinstance(row, dict) or any(field not in row for field in ARCHIVE_FIELDS):
        raise ValueError("Archive response is missing event fields.")
    if not isinstance(row["id"], str) or not re.fullmatch(r"[a-f0-9-]{36}", row["id"]):
        raise ValueError("Archive response has an invalid event ID.")
    for field in ARCHIVE_FIELDS:
        value = row[field]
        if field in {"occurred_at", "utc_offset_minutes"}:
            if (value is None and field != "occurred_at") or type(value) is int:
                continue
        elif value is None or isinstance(value, str):
            continue
        raise ValueError(f"Archive response has an invalid {field} value.")
    if row["occurred_at"] < 0 or any(row[field] is None for field in ("id", "kind", "outcome", "path")):
        raise ValueError("Archive response has invalid required values.")
    if row.get("receipt") != archive_receipt(row):
        raise ValueError("Archive response checksum does not match its event data.")


def export_events(database: Path, url: str, values: dict) -> None:
    """Durably merge all current events, then acknowledge exact saved copies for deletion."""
    database = database.resolve()
    if database == (ROOT / "artifacts/analytics/genealogy_analytics.duckdb").resolve():
        raise ValueError("Choose a persistent visitor archive; the genealogy analytics database is replaced by builds.")
    database.parent.mkdir(parents=True, exist_ok=True)
    previous_umask = os.umask(0o077)
    connection = None
    committed = False
    try:
        connection = duckdb.connect(str(database))
        os.chmod(database, 0o600)
        connection.execute("BEGIN TRANSACTION")
        columns = ",".join(f"{name} {kind}" for name, kind in zip(ARCHIVE_FIELDS, ARCHIVE_TYPES))
        connection.execute(f"""CREATE TABLE IF NOT EXISTS visitor_events (
            {columns}, source_url VARCHAR NOT NULL, occurred_at_utc TIMESTAMPTZ NOT NULL,
            receipt VARCHAR NOT NULL, archived_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        constraints = connection.execute("SELECT constraint_column_names FROM duckdb_constraints() WHERE schema_name='main' AND table_name='visitor_events' AND constraint_type='PRIMARY KEY'").fetchall()
        if constraints != [(['id'],)]:
            raise ValueError("Existing visitor_events table must have a primary key on id.")
        cursor, through, pending, seen = 0, None, [], set()
        inserted = updated = duplicates = 0
        while True:
            query = {"after": str(cursor)}
            if through is not None:
                query["through"] = str(through)
            with api(url, "events/archive?" + urlencode(query), values) as result:
                page = json.load(result)
            if not isinstance(page, dict) or page.get("version") != 1 or not isinstance(page.get("events"), list):
                raise ValueError("The online gateway does not support the archive protocol.")
            next_cursor = page.get("next_cursor")
            if (type(page.get("through")) is not int or type(next_cursor) is not int
                    or (through is not None and through != page["through"])
                    or not cursor <= next_cursor <= page["through"]):
                raise ValueError("Archive pagination is inconsistent.")
            through = page["through"]
            if len(page["events"]) > 1000 or (bool(page["events"]) != (next_cursor > cursor)):
                raise ValueError("Archive page has an invalid cursor or size.")
            last_cursor = cursor
            for row in page["events"]:
                validate_archive_row(row)
                if type(row.get("cursor")) is not int or not last_cursor < row["cursor"] <= next_cursor or row["id"] in seen:
                    raise ValueError("Archive event sequence is inconsistent.")
                last_cursor = row["cursor"]
                seen.add(row["id"])
                old = connection.execute(f"SELECT {','.join(ARCHIVE_FIELDS)} FROM visitor_events WHERE id=?", [row["id"]]).fetchone()
                payload = [row[field] for field in ARCHIVE_FIELDS]
                if old is None:
                    connection.execute(f"INSERT INTO visitor_events ({','.join(ARCHIVE_FIELDS)},source_url,occurred_at_utc,receipt) VALUES ({','.join('?' for _ in range(len(payload) + 3))})",
                                       payload + [url.rstrip('/'), datetime.fromtimestamp(row['occurred_at'], timezone.utc), row['receipt']])
                    inserted += 1
                elif archive_receipt(dict(zip(ARCHIVE_FIELDS, old))) == row["receipt"]:
                    # Validate existing data, rather than trusting a stored checksum alone.
                    connection.execute("UPDATE visitor_events SET receipt=? WHERE id=?", [row["receipt"], row["id"]])
                    duplicates += 1
                else:
                    connection.execute(f"UPDATE visitor_events SET {','.join(field + '=?' for field in ARCHIVE_FIELDS)},source_url=?,occurred_at_utc=?,receipt=?,archived_at=CURRENT_TIMESTAMP WHERE id=?",
                                       payload + [url.rstrip('/'), datetime.fromtimestamp(row['occurred_at'], timezone.utc), row['receipt'], row['id']])
                    updated += 1
                pending.append({"id": row["id"], "receipt": row["receipt"]})
            if page["events"] and last_cursor != next_cursor:
                raise ValueError("Archive page does not end at its advertised cursor.")
            if next_cursor == cursor:
                break
            cursor = next_cursor
        connection.execute("COMMIT")
        connection.execute("CHECKPOINT")
        # Flush the checkpointed database and its directory before any remote deletion.
        for path in (database, database.parent):
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        for item in pending:
            saved = connection.execute("SELECT receipt FROM visitor_events WHERE id=?", [item["id"]]).fetchone()
            if saved != (item["receipt"],):
                raise ValueError("Local archive verification failed; online records were retained.")
        committed = True
        deleted = missing = retained = 0
        for offset in range(0, len(pending), 50):
            batch = pending[offset:offset + 50]
            with api(url, "events/archive/ack", values, "POST", json.dumps({"events": batch}).encode()) as result:
                counts = json.load(result)
            if any(type(counts.get(key)) is not int or counts[key] < 0 for key in ("deleted", "missing", "retained")) or sum(counts[key] for key in ("deleted", "missing", "retained")) != len(batch):
                raise ValueError("Invalid archive acknowledgement response.")
            deleted += counts["deleted"]
            missing += counts["missing"]
            retained += counts["retained"]
        print(f"Archived {len(pending)} events in {database}: {inserted} new, {updated} updated, {duplicates} duplicates skipped.")
        print(f"Online: {deleted} removed, {missing} already absent, {retained} changed or awaiting browser context and retained for the next export.")
    except Exception as error:
        if committed:
            raise ValueError(f"Local archive is saved in {database}; online deletion was incomplete. Rerun export with the same database. {error}") from error
        raise
    finally:
        try:
            if connection is not None:
                connection.close()
        finally:
            os.umask(previous_umask)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and administer the genealogy website's visitor access gateway.",
        epilog=(
            "Owner commands (import, upload, export, cleanup) need the admin token, "
            "provided through GENEALOGY_VISITOR_ADMIN_TOKEN or --env-file. "
            "Use export to archive all visit activity in DuckDB and remove the saved online records; use cleanup to immediately "
            "remove expired sessions and visit records older than 365 days."
        ),
    )
    parser.add_argument(
        "--url",
        default=json.loads((ROOT / "website/site.json").read_text(encoding="utf-8"))["url"],
        help="HTTPS site URL for owner operations (default: configured website URL).",
    )
    parser.add_argument(
        "--env-file", type=Path,
        help="Read the private owner credential from this file, e.g. .env.visitor-access.",
    )
    parser.add_argument("--credentials-stdin", action="store_true", help=argparse.SUPPRESS)
    commands = parser.add_subparsers(
        dest="command", required=True,
        title="commands",
        description="Choose a local validation/build task or a production owner operation.",
    )
    commands.add_parser(
        "validate", help="Check an approved-visitor CSV locally without contacting the site.",
        description="Validate CSV headers, names, email addresses, duplicates, and row count without importing anything.",
    ).add_argument("csv", type=Path, help="CSV with Name and Email Address columns (or name,email).")
    commands.add_parser(
        "import", help="Replace the production approved-visitor list from a CSV.",
        description="Upload the CSV as the complete active allowlist. Addresses removed from the file are disabled and their sessions are deleted.",
    ).add_argument("csv", type=Path, help="CSV with Name and Email Address columns (or name,email).")
    commands.add_parser(
        "upload", help="Upload staged protected website files to production storage.",
        description="Upload the archive-assets from a staged Site checkout to private R2 storage before deploying that Site version.",
    ).add_argument("--checkout", type=Path, required=True, help="Staged Site checkout containing archive-assets and asset-manifest.json.")
    export = commands.add_parser(
        "export", help="Merge all online visit events into DuckDB, then remove confirmed online copies.",
        description="Archive all current visit events, including historical icons, in a persistent DuckDB visitor_events table. Existing event IDs are deduplicated and changed browser context is refreshed. Records are removed online only after the local transaction is committed, checkpointed and verified. An interrupted run can safely be repeated with the same database. Approved visitors and remembered sessions remain operational.",
    )
    export.add_argument("--database", type=Path, default=DEFAULT_ARCHIVE,
                        help="Existing DuckDB file to merge into, or a new file to create (default: artifacts/visitor-access/visits.duckdb). Use a persistent file, not the regenerated genealogy analytics database.")
    commands.add_parser(
        "cleanup", help="Immediately purge expired sessions and old visit records.",
        description="Run the same retention cleanup as the gateway's daily maintenance: delete expired sessions and visit records older than 365 days. Use this to remove eligible records now instead of waiting for daily gateway activity. Local DuckDB archives are unaffected.",
    )
    args = parser.parse_args()
    try:
        if args.command == "validate":
            print(f"Validated {len(load_visitors(args.csv))} approved visitors.")
            return
        values = credentials(args.env_file)
        if args.credentials_stdin:
            values.update(json.load(sys.stdin))
        if args.command == "import":
            visitors = load_visitors(args.csv)
            with api(args.url, "visitors", values, "POST", json.dumps({"visitors": visitors}).encode()) as result:
                count = json.load(result)["imported"]
            print(f"Imported {count} approved visitors. Removed addresses are disabled.")
        elif args.command == "upload":
            upload_assets(args.checkout, args.url, values)
        elif args.command == "cleanup":
            with api(args.url, "cleanup", values, "POST", b"{}"):
                pass
            print("Expired sessions and visit records removed.")
        elif args.command == "export":
            export_events(args.database, args.url, values)
    except (ValueError, OSError, HTTPError, KeyError, duckdb.Error) as error:
        # HTTPError.__str__ contains the URL/status, never the submitted body or credentials.
        parser.exit(1, f"Visitor access: {error}\n")


if __name__ == "__main__":
    main()
