/* Production-only gateway. The staging command appends the static asset manifest. */
const PREFIX = '/__access';
const COOKIE = '__Host-genealogy_visitor';
const SESSION_SECONDS = 180 * 24 * 60 * 60;
const RETENTION_SECONDS = 365 * 24 * 60 * 60;
const ICON_PATHS = ['/assets/favicon.svg', '/favicon.ico', '/apple-touch-icon.png', '/apple-touch-icon-precomposed.png'];
const ARCHIVE_FIELDS = ['id','email','occurred_at','kind','outcome','path','timezone','utc_offset_minutes','language','accept_language','ip_address'];
const archiveReceipt = row => hash(JSON.stringify(ARCHIVE_FIELDS.map(field => row[field] ?? null)));
const encoder = new TextEncoder();
const seconds = () => Math.floor(Date.now() / 1000);
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
export async function hash(value) {
  const bytes = typeof value === 'string' ? encoder.encode(value) : value;
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(x => x.toString(16).padStart(2, '0')).join('');
}
function token() {
  return [...crypto.getRandomValues(new Uint8Array(32))].map(x => x.toString(16).padStart(2, '0')).join('');
}
export function safeReturn(value) {
  try {
    const url = new URL(value || '/', 'https://archive.invalid');
    if (!value?.startsWith('/') || url.origin !== 'https://archive.invalid' || url.pathname.startsWith(PREFIX) || /[\r\n\\]/.test(value)) return '/';
    return url.pathname + url.search + url.hash;
  } catch { return '/'; }
}
function contextValues(data = {}) {
  let timezone = null;
  try {
    if (typeof data.timezone === 'string' && data.timezone.length < 100) {
      new Intl.DateTimeFormat('en', {timeZone: data.timezone});
      timezone = data.timezone;
    }
  } catch {}
  const offset = data.utc_offset_minutes === '' || data.utc_offset_minutes == null ? NaN : Number(data.utc_offset_minutes);
  return {timezone, utc_offset_minutes: Number.isInteger(offset) && Math.abs(offset) <= 840 ? offset : null,
    language: typeof data.language === 'string' ? data.language.slice(0, 100) || null : null};
}
function statement(db, sql, ...values) { return db.prepare(sql).bind(...values); }
function response(body, status = 200, type = 'text/html; charset=utf-8', extra = {}) {
  return new Response(body, { status, headers: {
    'Content-Type': type, 'Cache-Control': 'private, no-store', 'Referrer-Policy': 'same-origin',
    'X-Content-Type-Options': 'nosniff', 'X-Robots-Tag': 'noindex, nofollow', ...extra,
  }});
}
function redirect(path, cookie) {
  return response(null, 303, 'text/plain', {Location: path, ...(cookie ? {'Set-Cookie': cookie} : {})});
}
function backgroundRequest(request, path, asset) {
  const destination = request.headers.get('Sec-Fetch-Dest');
  if (['document', 'iframe'].includes(destination)) return false;
  if (destination && destination !== 'empty') return true;
  return path.startsWith('/assets/')
    || /\.(?:css|m?js|png|jpe?g|gif|webp|svg|ico|woff2?|ttf|mp[34]|webm)$/i.test(path)
    || /^(?:image\/|audio\/|video\/|font\/|text\/css|(?:text|application)\/javascript)/.test(asset?.type || '');
}
function sameOrigin(request) {
  return request.headers.get('Origin') === new URL(request.url).origin && request.headers.get('Sec-Fetch-Site') !== 'cross-site';
}
async function bodyBytes(request, limit = 65536) {
  if (Number(request.headers.get('Content-Length')) > limit) throw new Error('invalid input');
  // Bound streamed bodies too, rather than trusting Content-Length.
  const reader = request.body?.getReader();
  if (!reader) throw new Error('invalid input');
  const chunks = []; let size = 0;
  for (;;) {
    const {done, value} = await reader.read(); if (done) break;
    size += value.byteLength;
    if (size > limit) { await reader.cancel(); throw new Error('invalid input'); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return bytes;
}
async function bodyJson(request, limit = 65536) {
  return JSON.parse(new TextDecoder().decode(await bodyBytes(request, limit)));
}
async function cleanup(db) {
  await db.batch([
    statement(db, 'DELETE FROM visit_events WHERE occurred_at<?', seconds() - RETENTION_SECONDS),
    statement(db, 'DELETE FROM visitor_sessions WHERE expires_at<=?', seconds()),
    statement(db, 'DELETE FROM visitor_rate_events WHERE occurred_at<=?', seconds() - 600),
  ]);
}
async function dailyCleanup(db) {
  const day = String(Math.floor(seconds()/86400));
  const claimed = await statement(db, `INSERT INTO access_settings (key,value) VALUES ('cleanup_day',?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value WHERE value<>excluded.value RETURNING value`, day).first();
  if (claimed) await cleanup(db);
}
async function event(db, request, kind, outcome, email = null, context = {}) {
  const id = crypto.randomUUID(), nonce = token();
  const values = contextValues(context);
  // Query strings are deliberately excluded: they can contain personal information.
  const insert = statement(db, `INSERT INTO visit_events
    (id,email,occurred_at,kind,outcome,path,timezone,utc_offset_minutes,language,accept_language,ip_address,context_hash)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`, id, email, seconds(), kind, outcome,
    new URL(request.url).pathname.slice(0, 2048), values.timezone, values.utc_offset_minutes, values.language,
    request.headers.get('Accept-Language')?.slice(0, 512) || null,
    request.headers.get('CF-Connecting-IP') || null, await hash(nonce));
  if (kind === 'access_attempt') {
    await db.batch([insert, statement(db, 'INSERT INTO visitor_rate_events (id,occurred_at,ip_address) VALUES (?,?,?)',
      id, seconds(), request.headers.get('CF-Connecting-IP') || null)]);
  } else await insert.run();
  return {id, nonce};
}
function trackingScript(record) {
  return `<script src="${PREFIX}/client.js" data-event="${record.id}" data-token="${record.nonce}" defer></script>`;
}
function entry(returnTo, record, rejected = false, iconVersion = '') {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Welcome · Muszyna Family Archive</title>
    <link rel="icon" type="image/svg+xml" href="/assets/favicon.svg?v=${iconVersion}">
    <link rel="icon" type="image/x-icon" href="/favicon.ico?v=${iconVersion}">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png?v=${iconVersion}"><style>
    :root{font-family:system-ui,sans-serif;color:#20312a;background:#f4f1e8}body{margin:0;padding:24px;min-height:90vh;display:grid;place-items:center}
    main{max-width:440px;padding:clamp(24px,5vw,48px);background:#fffdf7;border:1px solid #d9dfd2;border-radius:16px;box-shadow:0 12px 40px #20312a12}
    h1{font-family:Georgia,serif;font-size:2rem}p{line-height:1.6}label{display:block;font-weight:600;margin-top:24px}
    input,button{font:inherit;box-sizing:border-box;border-radius:6px;padding:12px;width:100%;margin-top:8px}input{border:1px solid #758575}
    button{background:#284e3a;color:white;border:0;cursor:pointer;margin-top:16px}button:hover{background:#1a3627}input:focus-visible,button:focus-visible{outline:3px solid #bd8b32;outline-offset:3px}
    .notice{color:#8b3026}small{display:block;margin-top:24px;line-height:1.5;color:#526254}</style></head><body><main>
    <p>Muszyna Family Archive</p><h1>Welcome to the archive</h1><p>Please enter your email address to continue.</p>
    ${rejected ? '<p class="notice" role="alert">Sorry, we couldn’t grant access with that email address. Please check the address you entered or <a href="mailto:rekarpyrce@gmail.com">email the archive owner</a>.</p>' : ''}
    <form method="post" action="${PREFIX}/enter"><label for="email">Email address</label><input id="email" name="email" type="email" autocomplete="email" required maxlength="254">
    <input type="hidden" name="return_to" value="${escapeHtml(safeReturn(returnTo))}"><input type="hidden" name="timezone"><input type="hidden" name="utc_offset_minutes"><input type="hidden" name="language">
    <button type="submit">Enter the archive</button></form>
    <small>Recognized visitors are remembered on this browser for 180 days.</small>
    </main>${trackingScript(record)}</body></html>`;
}
async function session(db, request) {
  const cookies = (request.headers.get('Cookie') || '').split(';').map(s => s.trim());
  const value = cookies.find(s => s.startsWith(COOKIE + '='))?.slice(COOKIE.length + 1);
  if (!/^[a-f0-9]{64}$/.test(value || '')) return null;
  return statement(db, `SELECT s.*, v.name FROM visitor_sessions s JOIN approved_visitors v ON v.email=s.email
    WHERE s.token_hash=? AND s.expires_at>? AND v.enabled=1`, await hash(value), seconds()).first();
}
function csvCell(value) {
  let text = value == null ? '' : String(value);
  // Spreadsheet formula injection is possible even in rejected email/path fields.
  if (/^[=+\-@\t\r]/.test(text)) text = "'" + text;
  return '"' + text.replace(/"/g, '""') + '"';
}
async function admin(request, env, url) {
  const supplied = request.headers.get('Authorization') || '';
  if (!env.VISITOR_ADMIN_TOKEN || await hash(supplied) !== await hash('Bearer ' + env.VISITOR_ADMIN_TOKEN)) return response('Not found', 404, 'text/plain');
  if (url.pathname === PREFIX + '/admin/visitors' && request.method === 'POST') {
    const data = await bodyJson(request);
    if (!Array.isArray(data.visitors) || !data.visitors.length || data.visitors.length > 250) return response('Expected 1–250 visitors.', 400, 'text/plain');
    const seen = new Set();
    const visitors = data.visitors.map(v => {
      const email = typeof v.email === 'string' ? v.email.trim().toLowerCase() : '';
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254 || typeof v.name !== 'string' || !v.name.trim() || v.name.length > 120 || seen.has(email)) throw new Error('invalid input');
      seen.add(email); return {email, name: v.name.trim()};
    });
    // Replacing the list disables removed visitors; existing tokens cannot regain access later.
    await env.DB.batch([
      statement(env.DB, 'UPDATE approved_visitors SET enabled=0'),
      ...visitors.map(v => statement(env.DB, `INSERT INTO approved_visitors (email,name,enabled) VALUES (?,?,1)
        ON CONFLICT(email) DO UPDATE SET name=excluded.name,enabled=1`, v.email, v.name)),
      statement(env.DB, 'DELETE FROM visitor_sessions WHERE email IN (SELECT email FROM approved_visitors WHERE enabled=0)'),
    ]);
    return response(JSON.stringify({imported: visitors.length}), 200, 'application/json');
  }
  const assetMatch = url.pathname.match(/^\/__access\/admin\/assets\/([a-f0-9]{64})$/);
  if (assetMatch && request.method === 'PUT') {
    // Only the owner can upload; bytes must match their content-addressed key.
    const bytes = await bodyBytes(request, 25 * 1024 * 1024);
    if (await hash(bytes) !== assetMatch[1]) return response('Invalid asset', 400, 'text/plain');
    await env.BUCKET.put('assets/' + assetMatch[1], bytes);
    return response(null, 204);
  }
  if (url.pathname === PREFIX + '/admin/events' && request.method === 'GET') {
    const after = Number(url.searchParams.get('after') || '0');
    const since = url.searchParams.get('since');
    const includeIcons = url.searchParams.get('include_icons');
    if (!Number.isSafeInteger(after) || after < 0
      || (since !== null && (!/^\d+$/.test(since) || !Number.isSafeInteger(Number(since))))
      || (includeIcons !== null && !['0', '1'].includes(includeIcons))) return response('Invalid export filter', 400, 'text/plain');
    const predicates = ['rowid>?'], values = [after];
    if (since !== null) { predicates.push('occurred_at>=?'); values.push(Number(since)); }
    if (includeIcons !== '1') {
      predicates.push(`path NOT IN (${ICON_PATHS.map(() => '?').join(',')})`);
      values.push(...ICON_PATHS);
    }
    const rows = (await statement(env.DB, `SELECT rowid AS cursor,* FROM visit_events WHERE ${predicates.join(' AND ')} ORDER BY rowid LIMIT 1000`, ...values).all()).results;
    const fields = ['cursor','id','email','occurred_at_utc','local_date_time','timezone','utc_offset_minutes','language','accept_language','ip_address','kind','outcome','path'];
    const records = rows.map(row => {
      const date = new Date(row.occurred_at * 1000);
      return {...row, occurred_at_utc: date.toISOString(), local_date_time: row.timezone ? new Intl.DateTimeFormat('sv-SE', {timeZone:row.timezone, dateStyle:'short', timeStyle:'medium'}).format(date) : null};
    });
    return response([fields.join(','), ...records.map(row => fields.map(f => csvCell(row[f])).join(','))].join('\r\n'), 200, 'text/csv; charset=utf-8', {'X-Next-Cursor': String(rows.at(-1)?.cursor || after)});
  }
  if (url.pathname === PREFIX + '/admin/events/archive' && request.method === 'GET') {
    const after = Number(url.searchParams.get('after') || '0');
    const through = url.searchParams.has('through') ? Number(url.searchParams.get('through'))
      : (await statement(env.DB, 'SELECT COALESCE(MAX(rowid),0) AS n FROM visit_events').first()).n;
    if (!Number.isSafeInteger(after) || !Number.isSafeInteger(through) || after < 0 || through < after)
      return response('Invalid archive cursor', 400, 'text/plain');
    const rows = (await statement(env.DB, `SELECT rowid AS cursor,${ARCHIVE_FIELDS.join(',')} FROM visit_events
      WHERE rowid>? AND rowid<=? ORDER BY rowid LIMIT 1000`, after, through).all()).results;
    const events = await Promise.all(rows.map(async row => ({...row, receipt:await archiveReceipt(row)})));
    return response(JSON.stringify({version:1, through, next_cursor:rows.at(-1)?.cursor || after, events}), 200, 'application/json');
  }
  if (url.pathname === PREFIX + '/admin/events/archive/ack' && request.method === 'POST') {
    const data = await bodyJson(request);
    if (!Array.isArray(data.events) || !data.events.length || data.events.length > 50
      || new Set(data.events.map(row => row?.id)).size !== data.events.length
      || data.events.some(row => !/^[a-f0-9-]{36}$/.test(row?.id || '') || !/^[a-f0-9]{64}$/.test(row?.receipt || '')))
      return response('Expected 1–50 unique event receipts', 400, 'text/plain');
    let deleted = 0, missing = 0;
    for (const item of data.events) {
      const row = await statement(env.DB, `SELECT ${ARCHIVE_FIELDS.join(',')},context_hash FROM visit_events WHERE id=?`, item.id).first();
      if (!row) { missing++; continue; }
      if (await archiveReceipt(row) !== item.receipt) continue;
      const canEnrich = ['page','entry'].includes(row.kind) || (row.kind === 'access_attempt' && row.outcome === 'rejected');
      // Keep the short browser-enrichment window open before removing its target row.
      if (canEnrich && row.context_hash && row.occurred_at > seconds() - 300) continue;
      const operations = [];
      // Preserve legacy rate-limit history before deleting an access attempt.
      if (row.kind === 'access_attempt' && row.occurred_at > seconds() - 600)
        operations.push(statement(env.DB, 'INSERT OR IGNORE INTO visitor_rate_events (id,occurred_at,ip_address) VALUES (?,?,?)', row.id, row.occurred_at, row.ip_address));
      // Compare every exported value atomically, including nullable browser context.
      operations.push(statement(env.DB, `DELETE FROM visit_events WHERE ${ARCHIVE_FIELDS.map(field => field + ' IS ?').join(' AND ')}
        ${canEnrich ? 'AND (context_hash IS NULL OR occurred_at<=?)' : ''}`,
        ...ARCHIVE_FIELDS.map(field => row[field] ?? null), ...(canEnrich ? [seconds() - 300] : [])));
      const results = await env.DB.batch(operations), result = results.at(-1);
      deleted += Number(result.meta?.changes ?? result.changes);
    }
    return response(JSON.stringify({deleted, missing, retained:data.events.length - deleted - missing}), 200, 'application/json');
  }
  if (url.pathname === PREFIX + '/admin/cleanup' && request.method === 'POST') {
    await cleanup(env.DB);
    return response(null, 204);
  }
  return response('Not found', 404, 'text/plain');
}

export function createGateway(assets, clientScript) {
  const iconVersion = assets['/assets/favicon.svg']?.hash.slice(0, 12) || '';
  return {async fetch(request, env, execution) {
    try {
      const url = new URL(request.url);
      // There is deliberately no localhost, query parameter, or header bypass.
      // The separate Python preview server never invokes this Worker.
      if (url.pathname.startsWith(PREFIX + '/admin/')) return await admin(request, env, url);
      // Only these generic site icons are public. Archive assets still require a session.
      if (ICON_PATHS.includes(url.pathname)) {
        if (!['GET', 'HEAD'].includes(request.method)) return response('Method not allowed', 405, 'text/plain', {Allow:'GET, HEAD'});
        const icon = assets[url.pathname];
        if (!icon) return response('Not found', 404, 'text/plain');
        if (!env.BUCKET) return response('Icon unavailable', 503, 'text/plain');
        const headers = {'Cache-Control':'public, max-age=86400', ETag:`"${icon.hash}"`};
        if (request.headers.get('If-None-Match') === headers.ETag) return response(null, 304, icon.type, headers);
        const object = await env.BUCKET.get('assets/' + icon.hash);
        if (!object) return response('Icon unavailable', 503, 'text/plain');
        return response(request.method === 'HEAD' ? null : object.body, 200, icon.type, headers);
      }
      if (!env.DB || !env.BUCKET) return response('The archive is temporarily unavailable. Please try again later.', 503);
      if (url.pathname === PREFIX + '/client.js' && request.method === 'GET') return response(clientScript, 200, 'text/javascript; charset=utf-8');
      await dailyCleanup(env.DB);
      if (url.pathname === PREFIX + '/context' && request.method === 'POST') {
        if (!sameOrigin(request)) return response('Forbidden', 403, 'text/plain');
        const data = await bodyJson(request, 2048), values = contextValues(data);
        if (typeof data.id !== 'string' || !/^[a-f0-9]{64}$/.test(data.token || '')) return response('Invalid context', 400, 'text/plain');
        const recorded = await statement(env.DB, 'SELECT * FROM visit_events WHERE id=? AND context_hash=? AND occurred_at>?', data.id, await hash(data.token), seconds()-300).first();
        if (!recorded) return response(null, 204);
        await statement(env.DB, 'UPDATE visit_events SET timezone=?,utc_offset_minutes=?,language=?,context_hash=NULL WHERE id=? AND context_hash=?',
          values.timezone, values.utc_offset_minutes, values.language, data.id, await hash(data.token)).run();
        const visitor = await session(env.DB, request);
        if (visitor && visitor.email === recorded.email) await statement(env.DB, 'UPDATE visitor_sessions SET timezone=?,utc_offset_minutes=?,language=? WHERE token_hash=?',
          values.timezone, values.utc_offset_minutes, values.language, visitor.token_hash).run();
        return response(null, 204);
      }
      if (url.pathname === PREFIX + '/enter' && request.method === 'POST') {
        if (!sameOrigin(request)) {
          await event(env.DB, request, 'access_attempt', 'forbidden');
          return response('Please return to the archive entry page.', 403);
        }
        let raw;
        try { raw = new TextDecoder().decode(await bodyBytes(request, 4096)); }
        catch {
          await event(env.DB, request, 'access_attempt', 'invalid_input');
          return response('Form too large or invalid', 413);
        }
        const form = Object.fromEntries(new URLSearchParams(raw));
        const email = (form.email || '').trim().toLowerCase().slice(0, 254), values = contextValues(form);
        const ip = request.headers.get('CF-Connecting-IP');
        const attempts = await statement(env.DB, `SELECT COUNT(*) AS count FROM (
          SELECT id FROM visitor_rate_events WHERE ip_address IS ? AND occurred_at>?
          UNION SELECT id FROM visit_events WHERE kind='access_attempt' AND ip_address IS ? AND occurred_at>?
        )`, ip, seconds()-600, ip, seconds()-600).first();
        if (attempts.count >= 10) {
          await event(env.DB, request, 'access_attempt', 'rate_limited', email || null, values);
          return response('Too many attempts. Please try again in ten minutes.', 429, 'text/plain', {'Retry-After':'600'});
        }
        const visitor = await statement(env.DB, 'SELECT * FROM approved_visitors WHERE email=? AND enabled=1', email).first();
        if (!visitor) {
          const record = await event(env.DB, request, 'access_attempt', 'rejected', email || null, values);
          return response(entry(form.return_to, record, true, iconVersion), 403);
        }
        const value = token();
        await statement(env.DB, `INSERT INTO visitor_sessions (token_hash,email,created_at,expires_at,timezone,utc_offset_minutes,language)
          VALUES (?,?,?,?,?,?,?)`, await hash(value), visitor.email, seconds(), seconds()+SESSION_SECONDS,
          values.timezone, values.utc_offset_minutes, values.language).run();
        await event(env.DB, request, 'access_attempt', 'allowed', visitor.email, values);
        return redirect(safeReturn(form.return_to), `${COOKIE}=${value}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${SESSION_SECONDS}`);
      }
      const visitor = await session(env.DB, request);
      if (url.pathname === PREFIX + '/forget' && request.method === 'POST') {
        if (!sameOrigin(request)) return response('Forbidden', 403, 'text/plain');
        if (visitor) await statement(env.DB, 'DELETE FROM visitor_sessions WHERE token_hash=?', visitor.token_hash).run();
        return redirect(PREFIX + '/entry', `${COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0`);
      }
      if (url.pathname === PREFIX + '/entry' && request.method === 'GET') {
        if (visitor) return redirect(safeReturn(url.searchParams.get('return_to')));
        const record = await event(env.DB, request, 'entry', 'anonymous');
        return response(entry(url.searchParams.get('return_to'), record, false, iconVersion));
      }
      let path;
      try { path = decodeURIComponent(url.pathname); } catch { return response('Not found', 404, 'text/plain'); }
      const asset = assets[path] || assets[path.endsWith('/') ? path + 'index.html' : path + '/index.html'];
      const background = backgroundRequest(request, path, asset);
      if (!visitor) {
        if (background) return response('Access required', 403, 'text/plain');
        await event(env.DB, request, 'challenge', 'denied');
        return redirect(PREFIX + '/entry?return_to=' + encodeURIComponent(safeReturn(url.pathname + url.search)));
      }
      if (!['GET','HEAD'].includes(request.method)) return response('Method not allowed', 405, 'text/plain', {Allow:'GET, HEAD'});
      if (!asset) {
        if (!background) await event(env.DB, request, 'request', 'not_found', visitor.email, visitor);
        return response('Not found', 404, 'text/plain');
      }
      const html = asset.type.startsWith('text/html');
      const download = !html && !background && !/^\/(assets|analytics\/app)\//.test(path);
      const record = request.method === 'GET' && (html || download) ? await event(env.DB, request, html ? 'page' : 'download', 'allowed', visitor.email, visitor) : null;
      const object = await env.BUCKET.get('assets/' + asset.hash);
      if (!object) return response('The archive is being updated. Please try again shortly.', 503);
      let body = request.method === 'HEAD' ? null : object.body;
      if (html && request.method === 'GET') {
        const greeting = `<aside aria-label="Visitor" style="padding:8px 20px;background:#e8eee6;color:#20312a;display:flex;gap:16px;align-items:center;flex-wrap:wrap;font:14px system-ui"><span>Welcome, ${escapeHtml(visitor.name)}</span><form method="post" action="${PREFIX}/forget"><button type="submit">Forget this browser</button></form></aside>`;
        const content = await object.text();
        body = content.replace(/<body([^>]*)>/i, '<body$1>' + greeting).replace(/<\/body>/i, trackingScript(record) + '</body>');
      }
      // Private, no-store prevents personalized pages and protected bytes leaking through caches.
      return response(body, 200, asset.type);
    } catch {
      // Fail closed without exposing request bodies, database errors, or credentials in logs.
      return response('The archive is temporarily unavailable. Please try again later.', 503);
    }
  }};
}
