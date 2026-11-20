// "Report an error" on agent pages and "Reply" on stories. Both land in one
// list for a person to act on. Corrections that come out of it are published
// through /api/corrections.
import { db, limiter, json, ipOf, str, isEmail, pick } from './_store.js';

const KINDS = ['error', 'reply'];

export async function POST(request) {
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Bad request' }, 400); }
  if (body.hp_url) return json({ ok: true });
  const r = {
    ts: new Date().toISOString(), kind: pick(body.kind, KINDS) || 'error',
    agent: str(body.agent, 80), story: str(body.story, 32), what: str(body.what, 1500),
    name: str(body.name, 80), email: str(body.email, 200), status: 'open',
  };
  if (r.what.length < 5) return json({ error: 'Say what is wrong.' }, 422);
  if (r.email && !isEmail(r.email)) return json({ error: 'Enter a valid email address, or leave it blank.' }, 422);
  if (r.kind === 'reply' && !r.name) return json({ error: 'Say who is replying.' }, 422);
  try {
    const { success } = await limiter('report', 10, '1 h').limit(ipOf(request));
    if (!success) return json({ error: 'Too many reports from this connection. Try again in an hour.' }, 429);
    await db().lpush('reports', JSON.stringify(r));
    return json({ ok: true });
  } catch (err) {
    console.error('report POST failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}
