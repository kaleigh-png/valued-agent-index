// Private read of every form submission. Needs the ADMIN_KEY env var,
// sent as ?key=... or an x-admin-key header. Used by /admin.
import { db, json } from './_store.js';

export async function GET(request) {
  const key = process.env.ADMIN_KEY;
  if (!key) return json({ error: 'ADMIN_KEY is not set on the project' }, 503);
  const url = new URL(request.url);
  const given = request.headers.get('x-admin-key') || url.searchParams.get('key') || '';
  if (given.length !== key.length || given !== key) return json({ error: 'Not allowed' }, 401);
  try {
    const store = db();
    const out = {};
    for (const kind of ['claim', 'manage', 'pulse']) {
      const raw = await store.lrange(`submissions:${kind}`, 0, -1);
      out[kind] = raw.map(r => (typeof r === 'string' ? JSON.parse(r) : r));
    }
    return json(out);
  } catch (err) {
    console.error('submissions failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}
