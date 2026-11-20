// Private read of everything people sent in. Needs the ADMIN_KEY env var,
// sent as ?key=... or an x-admin-key header. Used by /admin.
import { db, json, adminOk, parse } from './_store.js';
import { PENDING } from './stories.js';

export async function GET(request) {
  const auth = adminOk(request);
  if (!auth.ok) return auth.res;
  try {
    const store = db();
    const out = {};
    for (const kind of ['claim', 'manage', 'pulse']) {
      out[kind] = (await store.lrange(`submissions:${kind}`, 0, -1)).map(parse);
    }
    out.stories_pending = Object.values((await store.hgetall(PENDING)) || {}).map(parse).filter(Boolean)
      .sort((x, y) => String(y.ts).localeCompare(String(x.ts)));
    out.reports = (await store.lrange('reports', 0, -1)).map(parse).filter(Boolean);
    out.jobs_named = (await store.lrange('jobs:named', 0, 999)).map(parse).filter(Boolean);
    out.corrections = (await store.lrange('corrections', 0, 199)).map(parse).filter(Boolean);
    return json(out);
  } catch (err) {
    console.error('submissions failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}
