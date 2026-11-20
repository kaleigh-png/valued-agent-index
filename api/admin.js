// Admin actions, used by /admin with the ADMIN_KEY. Every action is a human
// decision: approve or reject a story, add a reply under a story, publish a
// correction, close a report.
import { db, json, adminOk, str, parse } from './_store.js';
import { PENDING, APPROVED } from './stories.js';

export async function POST(request) {
  const auth = adminOk(request);
  if (!auth.ok) return auth.res;
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Bad request' }, 400); }
  const store = db();
  const id = str(body.id, 32);
  try {
    switch (body.action) {
      case 'approve_story': {
        const raw = await store.hget(PENDING, id);
        if (!raw) return json({ error: 'No pending story with that id' }, 404);
        const s = parse(raw);
        s.status = 'approved'; s.approved_at = new Date().toISOString();
        if (str(body.note, 300)) s.editor_note = str(body.note, 300);
        await store.hset(APPROVED, { [id]: JSON.stringify(s) });
        await store.hdel(PENDING, id);
        return json({ ok: true });
      }
      case 'reject_story': {
        await store.hdel(PENDING, id);
        return json({ ok: true });
      }
      case 'unpublish_story': {
        await store.hdel(APPROVED, id);
        return json({ ok: true });
      }
      case 'add_reply': {
        const raw = await store.hget(APPROVED, id);
        if (!raw) return json({ error: 'No approved story with that id' }, 404);
        const s = parse(raw);
        const who = str(body.who, 80), text = str(body.text, 1000);
        if (!who || !text) return json({ error: 'Reply needs who and text' }, 422);
        s.replies = [...(s.replies || []), { who, text, ts: new Date().toISOString() }];
        await store.hset(APPROVED, { [id]: JSON.stringify(s) });
        return json({ ok: true });
      }
      case 'add_correction': {
        const agent = str(body.agent, 80), note = str(body.note, 600);
        if (!note) return json({ error: 'Correction needs a note' }, 422);
        await store.lpush('corrections', JSON.stringify({ ts: new Date().toISOString(), agent, note }));
        return json({ ok: true });
      }
      case 'close_report': {
        // Reports are a list; mark closed by rewriting the matching entry.
        const ts = str(body.ts, 40);
        const raw = await store.lrange('reports', 0, -1);
        const idx = raw.findIndex(r => (parse(r) || {}).ts === ts);
        if (idx < 0) return json({ error: 'No report with that timestamp' }, 404);
        const r = parse(raw[idx]); r.status = 'closed';
        await store.lset('reports', idx, JSON.stringify(r));
        return json({ ok: true });
      }
      default:
        return json({ error: 'Unknown action' }, 400);
    }
  } catch (err) {
    console.error('admin action failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}
