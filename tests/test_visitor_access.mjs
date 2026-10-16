import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, readdirSync } from 'node:fs';
import { createGateway, hash, safeReturn } from '../website/access/worker.mjs';

const origin = 'https://genealogy.test';
function fixture() {
  const sqlite = new DatabaseSync(':memory:');
  sqlite.exec('PRAGMA foreign_keys=ON');
  for (const file of readdirSync(new URL('../website/access/drizzle/', import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) {
    sqlite.exec(readFileSync(new URL('../website/access/drizzle/' + file, import.meta.url), 'utf8'));
  }
  const DB = { prepare(sql) {
    const build = values => ({
      bind: (...args) => build(args),
      first: async () => sqlite.prepare(sql).get(...values) || null,
      all: async () => ({results: sqlite.prepare(sql).all(...values)}),
      run: async () => sqlite.prepare(sql).run(...values),
    });
    return build([]);
  }, async batch(statements) {
    sqlite.exec('BEGIN');
    try { const results = []; for (const s of statements) results.push(await s.run()); sqlite.exec('COMMIT'); return results; }
    catch (error) { sqlite.exec('ROLLBACK'); throw error; }
  }};
  const objects = new Map();
  const BUCKET = {get: async key => objects.has(key) ? {body:objects.get(key), text:async()=>new TextDecoder().decode(objects.get(key))} : null,
    put: async(key, bytes) => objects.set(key, bytes)};
  const assets = {'/index.html':{hash:'home',type:'text/html'}, '/private.jpg':{hash:'photo',type:'image/jpeg'}, '/download/family.ged':{hash:'ged',type:'text/plain'}};
  for (const path of ['/assets/favicon.svg','/favicon.ico','/apple-touch-icon.png','/apple-touch-icon-precomposed.png']) {
    assets[path] = {hash:'icon', type:path.endsWith('.svg') ? 'image/svg+xml' : path.endsWith('.ico') ? 'image/vnd.microsoft.icon' : 'image/png'};
  }
  assets['/assets/private.jpg'] = {hash:'photo',type:'image/jpeg'};
  objects.set('assets/icon', new TextEncoder().encode('GENERIC ICON'));
  objects.set('assets/home', new TextEncoder().encode('<html><body><main>Family tree</main></body></html>'));
  objects.set('assets/photo', new Uint8Array([1,2,3])); objects.set('assets/ged',new TextEncoder().encode('FAMILY DATA'));
  sqlite.prepare('INSERT INTO approved_visitors VALUES (?,?,1)').run('relative@example.test', 'Józef <Family>');
  const gateway = createGateway(assets, '/* no visitor data */');
  const env = {DB, BUCKET, VISITOR_ADMIN_TOKEN:'owner-secret'};
  const request = (path, opts={}) => gateway.fetch(new Request(origin+path, {...opts,headers:{'CF-Connecting-IP':'203.0.113.10','Accept-Language':'pl-PL,pl;q=0.9',...opts.headers}}),env);
  const enter = async(email='relative@example.test', path='/') => request('/__access/enter', {method:'POST',headers:{Origin:origin},
    body:new URLSearchParams({email,return_to:path,timezone:'Europe/Warsaw',utc_offset_minutes:'120',language:'pl-PL'})});
  return {sqlite, request, enter, objects, env, gateway};
}

test('every static route and spoofed local bypass is protected',async()=>{
  const f=fixture();
  for(const path of ['/','/download/family.ged','/index.html?preview=1']) {
    const r=await f.request(path,{headers:{'X-Local-Preview':'1',Host:'localhost'}});
    assert.equal(r.status,303); assert.match(r.headers.get('Location'),/^\/__access\/entry/);
    assert.equal(await r.text(),'');
  }
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visit_events').get().n,3);
});
test('generic icons are public and cacheable without sessions, redirects or visitor events',async()=>{
  const f=fixture();
  for (const path of ['/assets/favicon.svg','/favicon.ico','/apple-touch-icon.png','/apple-touch-icon-precomposed.png']) {
    const r=await f.request(path+'?v=current');
    assert.equal(r.status,200);assert.equal(await r.text(),'GENERIC ICON');
    assert.equal(r.headers.get('Set-Cookie'),null);assert.equal(r.headers.get('Location'),null);
    assert.match(r.headers.get('Cache-Control'),/^public/);
    assert.equal((await f.request(path,{headers:{'If-None-Match':r.headers.get('ETag')}})).status,304);
    const head=await f.request(path,{method:'HEAD'});assert.equal(head.status,200);assert.equal(await head.text(),'');
  }
  assert.equal((await f.gateway.fetch(new Request(origin+'/favicon.ico'),{BUCKET:f.env.BUCKET})).status,200);
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visit_events').get().n,0);
});
test('protected background requests fail quietly while document navigation still reaches entry',async()=>{
  const f=fixture();
  for (const path of ['/private.jpg','/assets/private.jpg','/assets/missing.css','/assets/missing.js','/missing.png']) {
    const r=await f.request(path);assert.equal(r.status,403);assert.equal(r.headers.get('Location'),null);
    assert.ok(!(await r.text()).includes('Family tree'));
  }
  assert.equal((await f.request('/download/family.ged',{headers:{'Sec-Fetch-Dest':'image'}})).status,403);
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visit_events').get().n,0);
  assert.equal((await f.request('/private.jpg',{headers:{'Sec-Fetch-Dest':'document'}})).status,303);
  const entry=await(await f.request('/__access/entry')).text();
  assert.match(entry,/apple-touch-icon\.png\?v=icon/);
  const cookie=(await f.enter()).headers.get('Set-Cookie').split(';')[0];
  const before=f.sqlite.prepare('SELECT count(*) AS n FROM visit_events').get().n;
  assert.equal((await f.request('/assets/private.jpg',{headers:{Cookie:cookie}})).status,200);
  assert.equal((await f.request('/missing.css',{headers:{Cookie:cookie}})).status,404);
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visit_events').get().n,before);
});
test('recognized visitors get an opaque secure cookie, greeting and logged return visits',async()=>{
  const f=fixture();const login=await f.enter(' RELATIVE@EXAMPLE.TEST ','/download/family.ged');
  assert.equal(login.status,303);assert.equal(login.headers.get('Location'),'/download/family.ged');
  const cookie=login.headers.get('Set-Cookie');
  for(const flag of ['Secure','HttpOnly','SameSite=Lax','Max-Age=15552000']) assert.ok(cookie.includes(flag));
  assert.ok(!cookie.includes('relative'));const headers={Cookie:cookie.split(';')[0]};
  const page=await f.request('/',{headers});const html=await page.text();
  assert.match(html,/Welcome, Józef &lt;Family&gt;/); assert.ok(!html.includes('relative@example.test'));
  assert.match(page.headers.get('Cache-Control'),/no-store/);
  assert.equal((await f.request('/private.jpg',{headers})).status,200);
  assert.equal((await f.request('/download/family.ged',{headers})).status,200);
  const logged=f.sqlite.prepare("SELECT * FROM visit_events WHERE kind='page'").get();
  assert.equal(logged.email,'relative@example.test');assert.equal(logged.timezone,'Europe/Warsaw');
  assert.equal(logged.ip_address,'203.0.113.10'); assert.equal(logged.language,'pl-PL');
  assert.ok(!cookie.includes(f.sqlite.prepare('SELECT token_hash FROM visitor_sessions').get().token_hash));
});
test('unknown emails are rejected and recorded; repeated attempts are limited',async()=>{
  const f=fixture(); const rejection=await f.enter('unknown@example.test');
  assert.equal(rejection.status,403);
  const page = await rejection.text();
  assert.match(page,/couldn’t grant access/);
  assert.match(page,/<a href="mailto:rekarpyrce@gmail\.com">email the archive owner<\/a>/);
  assert.equal(rejection.headers.get('Set-Cookie'),null);
  for(let i=0;i<9;i++) await f.enter('unknown@example.test');
  assert.equal((await f.enter()).status,429);
  assert.equal(f.sqlite.prepare("SELECT count(*) AS n FROM visit_events WHERE outcome='rate_limited'").get().n,1);
});
test('revocation, expiry and forgetting invalidate remembered access',async()=>{
  const f=fixture();const cookie=(await f.enter()).headers.get('Set-Cookie').split(';')[0];const headers={Cookie:cookie};
  f.sqlite.exec('UPDATE approved_visitors SET enabled=0');assert.equal((await f.request('/',{headers})).status,303);
  f.sqlite.exec('UPDATE approved_visitors SET enabled=1; UPDATE visitor_sessions SET expires_at=0');
  assert.equal((await f.request('/',{headers})).status,303);
  const fresh=(await f.enter()).headers.get('Set-Cookie').split(';')[0];
  assert.equal((await f.request('/__access/forget',{method:'POST',headers:{Origin:origin,Cookie:fresh}})).status,303);
  assert.equal((await f.request('/',{headers:{Cookie:fresh}})).status,303);
});
test('context enrichment is bounded, once-only and cannot update other visit records',async()=>{
  const f=fixture();const page=await(await f.request('/__access/entry')).text();
  const id=page.match(/data-event="([^"]+)/)[1],token=page.match(/data-token="([^"]+)/)[1];
  const update=(payload)=>f.request('/__access/context',{method:'POST',headers:{Origin:origin},body:JSON.stringify(payload)});
  await update({id,token:'0'.repeat(64),timezone:'America/Chicago'});
  assert.equal(f.sqlite.prepare('SELECT timezone FROM visit_events WHERE id=?').get(id).timezone,null);
  await update({id,token,timezone:'America/Chicago',language:'en-US',utc_offset_minutes:-300});
  await update({id,token,timezone:'Europe/Warsaw'});
  assert.equal(f.sqlite.prepare('SELECT timezone FROM visit_events WHERE id=?').get(id).timezone,'America/Chicago');
});
test('owner endpoints require their own secret; replacements revoke removed sessions',async()=>{
  const f=fixture();const cookie=(await f.enter()).headers.get('Set-Cookie').split(';')[0];
  assert.equal((await f.request('/__access/admin/events',{headers:{Cookie:cookie}})).status,404);
  const owner={Authorization:'Bearer owner-secret'};
  const replacement=await f.request('/__access/admin/visitors',{method:'POST',headers:owner,body:JSON.stringify({visitors:[{email:'other@example.test',name:'Other'}]})});
  assert.equal(replacement.status,200);assert.equal((await f.request('/',{headers:{Cookie:cookie}})).status,303);
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visitor_sessions').get().n,0);
  const bytes=new TextEncoder().encode('new asset'),digest=await hash(bytes);
  assert.equal((await f.request('/__access/admin/assets/'+digest,{method:'PUT',headers:owner,body:bytes})).status,204);
  assert.equal((await f.request('/__access/admin/assets/'+ 'a'.repeat(64),{method:'PUT',headers:owner,body:bytes})).status,400);
  const csv=await f.request('/__access/admin/events',{headers:owner});assert.equal(csv.status,200);
  assert.match(await csv.text(),/occurred_at_utc,local_date_time,timezone/);
});
test('cross-origin submissions, open redirects and storage outages fail closed',async()=>{
  const f=fixture();assert.equal((await f.request('/__access/enter',{method:'POST',headers:{Origin:'https://evil.test'},body:'email=relative@example.test'})).status,403);
  for(const target of ['//evil.test','/\\evil.test','https://evil.test','/__access/admin/events','/\r\nLocation: bad']) assert.equal(safeReturn(target),'/');
  const out=await f.gateway.fetch(new Request(origin),{});assert.equal(out.status,503);
});
test('automatic cleanup removes expired sessions and year-old visit records',async()=>{
  const f=fixture();await f.request('/__access/entry');
  f.sqlite.exec("UPDATE visit_events SET occurred_at=1; DELETE FROM access_settings");
  await f.request('/__access/entry');
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visit_events WHERE occurred_at=1').get().n,0);
});
test('export filters icons and dates before pagination and preserves database records',async()=>{
  const f=fixture(), owner={Authorization:'Bearer owner-secret'};
  const insert=f.sqlite.prepare('INSERT INTO visit_events (id,occurred_at,kind,outcome,path) VALUES (?,?,?,?,?)');
  insert.run('old',100,'page','allowed','/');
  for(let i=0;i<2004;i++) insert.run('event-'+i,200+i,'page','allowed',i%2===0?'/favicon.ico':'/');
  let cursor='0', count=0, batches=[];
  for(let i=0;i<5;i++) {
    const r=await f.request('/__access/admin/events?since=200&after='+cursor,{headers:owner});
    assert.equal(r.status,200);
    const text=await r.text(), lines=text.split('\r\n');
    assert.ok(!text.includes('/favicon.ico'));assert.ok(!text.includes('"old"'));
    batches.push(lines.length-1);count+=lines.length-1;
    const next=r.headers.get('X-Next-Cursor');if(next===cursor) break;cursor=next;
  }
  assert.deepEqual(batches,[1000,2,0]);assert.equal(count,1002);
  const full=await f.request('/__access/admin/events?include_icons=1',{headers:owner});
  assert.match(await full.text(),/favicon\.ico/);
  const empty=await f.request('/__access/admin/events?since=9999999999',{headers:owner});
  assert.match(await empty.text(),/^cursor,id,email,occurred_at_utc/);
  for (const query of ['since=bad','since=-1','include_icons=bad','after=-1'])
    assert.equal((await f.request('/__access/admin/events?'+query,{headers:owner})).status,400);
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visit_events').get().n,2005);
});

test('archive includes icons, raw values and a stable high-water cursor',async()=>{
  const f=fixture(), owner={Authorization:'Bearer owner-secret'};
  await f.enter();
  const record=f.sqlite.prepare('SELECT * FROM visit_events').get();
  f.sqlite.prepare('UPDATE visit_events SET email=?,path=? WHERE id=?').run('=raw@example.test','/favicon.ico',record.id);
  const first=await(await f.request('/__access/admin/events/archive',{headers:owner})).json();
  assert.equal(first.version,1);assert.equal(first.events.length,1);
  assert.equal(first.events[0].email,'=raw@example.test');assert.equal(first.events[0].path,'/favicon.ico');
  assert.equal(first.events[0].context_hash,undefined);assert.match(first.events[0].receipt,/^[a-f0-9]{64}$/);
  await f.request('/__access/entry'); // Created after the export boundary.
  const next=await(await f.request(`/__access/admin/events/archive?after=${first.next_cursor}&through=${first.through}`,{headers:owner})).json();
  assert.deepEqual(next.events,[]);assert.equal(next.through,first.through);
});

test('archive pages through more than 1000 events without filtering icons',async()=>{
  const f=fixture(), owner={Authorization:'Bearer owner-secret'};
  const insert=f.sqlite.prepare('INSERT INTO visit_events (id,occurred_at,kind,outcome,path) VALUES (?,?,?,?,?)');
  for(let i=0;i<1003;i++) insert.run(crypto.randomUUID(),200+i,'challenge','denied',i%2?'/favicon.ico':'/');
  let after=0,through,ids=new Set(),sizes=[];
  for(let i=0;i<4;i++) {
    const page=await(await f.request(`/__access/admin/events/archive?after=${after}${through===undefined?'':'&through='+through}`,{headers:owner})).json();
    through=page.through;sizes.push(page.events.length);
    for(const row of page.events) { assert.ok(!ids.has(row.id));ids.add(row.id); }
    if(page.next_cursor===after)break;
    after=page.next_cursor;
  }
  assert.deepEqual(sizes,[1000,3,0]);assert.equal(ids.size,1003);
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visit_events').get().n,1003);
});

test('archive receipts match the Python protocol for Unicode and raw fields',async()=>{
  const f=fixture(),owner={Authorization:'Bearer owner-secret'};
  f.sqlite.prepare('INSERT INTO visit_events (id,email,occurred_at,kind,outcome,path,language,accept_language,ip_address) VALUES (?,?,?,?,?,?,?,?,?)')
    .run('00000000-0000-4000-8000-000000000001','=raw@example.test',1792022400,'page','allowed','/Józef/','pl-PL','pl-PL','203.0.113.1');
  const page=await(await f.request('/__access/admin/events/archive',{headers:owner})).json();
  assert.equal(page.events[0].receipt,'280a9f867e5b4268caa078117760e623ebb82cafb3c5ed90bf92095c145809a6');
});

test('archive acknowledgements delete only unchanged exact IDs and are idempotent',async()=>{
  const f=fixture(),owner={Authorization:'Bearer owner-secret'};
  const batch=f.env.DB.batch;
  f.env.DB.batch=async operations=>(await batch(operations)).map(result=>({meta:{changes:Number(result.changes)}}));
  await f.enter();await f.request('/__access/entry');
  const snapshot=await(await f.request('/__access/admin/events/archive',{headers:owner})).json();
  const [unchanged,changed]=snapshot.events;
  f.sqlite.prepare('UPDATE visit_events SET timezone=? WHERE id=?').run('America/Chicago',changed.id);
  await f.request('/__access/entry');
  const ack=async events=>f.request('/__access/admin/events/archive/ack',{method:'POST',headers:owner,body:JSON.stringify({events})});
  const receipts=snapshot.events.map(({id,receipt})=>({id,receipt}));
  assert.equal((await f.request('/__access/admin/events/archive/ack',{method:'POST',body:JSON.stringify({events:receipts})})).status,404);
  assert.deepEqual(await(await ack(receipts)).json(),{deleted:1,missing:0,retained:1});
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visit_events').get().n,2);
  assert.deepEqual(await(await ack([receipts[0]])).json(),{deleted:0,missing:1,retained:0});
  assert.equal((await ack([{id:unchanged.id,receipt:'bad'}])).status,400);
  assert.equal((await ack([receipts[1],receipts[1]])).status,400);
});

test('context changes between acknowledgement read and delete retain the online event',async()=>{
  const f=fixture(),owner={Authorization:'Bearer owner-secret'};
  await f.request('/__access/entry');
  f.sqlite.exec('UPDATE visit_events SET context_hash=NULL');
  const record=(await(await f.request('/__access/admin/events/archive',{headers:owner})).json()).events[0];
  const batch=f.env.DB.batch;
  f.env.DB.batch=async operations=>{
    f.sqlite.prepare('UPDATE visit_events SET language=? WHERE id=?').run('pl-PL',record.id);
    return batch(operations);
  };
  const result=await(await f.request('/__access/admin/events/archive/ack',{method:'POST',headers:owner,
    body:JSON.stringify({events:[{id:record.id,receipt:record.receipt}]})})).json();
  assert.deepEqual(result,{deleted:0,missing:0,retained:1});
  assert.equal(f.sqlite.prepare('SELECT language FROM visit_events WHERE id=?').get(record.id).language,'pl-PL');
});

test('export deletion preserves recent throttling, including legacy attempts',async()=>{
  const f=fixture(),owner={Authorization:'Bearer owner-secret'};
  for(let i=0;i<10;i++) await f.enter('unknown@example.test');
  // Simulate records collected by the old gateway, before independent counters existed.
  f.sqlite.exec('DELETE FROM visitor_rate_events');
  f.sqlite.exec('UPDATE visit_events SET context_hash=NULL');
  const snapshot=await(await f.request('/__access/admin/events/archive',{headers:owner})).json();
  const result=await(await f.request('/__access/admin/events/archive/ack',{method:'POST',headers:owner,
    body:JSON.stringify({events:snapshot.events.map(({id,receipt})=>({id,receipt}))})})).json();
  assert.equal(result.deleted,10);assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visit_events').get().n,0);
  assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM visitor_rate_events').get().n,10);
  assert.equal((await f.enter()).status,429);
});

test('archive keeps recent context targets until enrichment completes or expires',async()=>{
  const f=fixture(),owner={Authorization:'Bearer owner-secret'};
  await f.request('/__access/entry');
  const record=(await(await f.request('/__access/admin/events/archive',{headers:owner})).json()).events[0];
  const ack=()=>f.request('/__access/admin/events/archive/ack',{method:'POST',headers:owner,
    body:JSON.stringify({events:[{id:record.id,receipt:record.receipt}]})});
  assert.deepEqual(await(await ack()).json(),{deleted:0,missing:0,retained:1});
  f.sqlite.exec('UPDATE visit_events SET context_hash=NULL');
  assert.deepEqual(await(await ack()).json(),{deleted:1,missing:0,retained:0});
});
