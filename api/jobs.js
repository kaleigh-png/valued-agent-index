// The job box: "What one repetitive job would you hand to an agent?"
// POST stores the answer. No email is needed; one is kept only when the person
// asks to be told when an agent for that job appears. GET returns totals only,
// never the text or anyone's address.
import jobsMap from '../data/jobs.json' with { type: 'json' };
import { db, limiter, json, ipOf, str, isEmail } from './_store.js';

const LIST = 'jobs:named';
const RX = jobsMap.jobs.map(j => ({ id: j.id, rx: new RegExp('\\b(?:' + j.match + ')\\b', 'i') }));
export const matchJobs = text => RX.filter(j => j.rx.test(text || '')).map(j => j.id).slice(0, 3);

export async function GET() {
  try {
    const raw = await db().lrange(LIST, 0, 4999);
    const by = {};
    let n = 0;
    for (const r of raw) {
      const j = typeof r === 'string' ? JSON.parse(r) : r;
      if (!j) continue;
      n++;
      for (const id of j.matched || []) by[id] = (by[id] || 0) + 1;
    }
    const top = Object.entries(by).sort((a, b) => b[1] - a[1]).map(([id, count]) => ({ id, count }));
    return json({ count: n, top });
  } catch (err) {
    console.error('jobs GET failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}

export async function POST(request) {
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Bad request' }, 400); }
  if (body.hp_url) return json({ ok: true });
  const job = str(body.job, 200), industry = str(body.industry, 80), email = str(body.email, 200);
  const notify = !!body.notify && !!email;
  if (job.length < 4) return json({ error: 'Describe the job in a few words.' }, 422);
  if (email && !isEmail(email)) return json({ error: 'Enter a valid email address, or leave it blank.' }, 422);
  try {
    const { success } = await limiter('jobs', 20, '1 h').limit(ipOf(request));
    if (!success) return json({ error: 'Too many from this connection. Try again in an hour.' }, 429);
    const rec = { ts: new Date().toISOString(), job, industry, matched: matchJobs(job), notify, ...(notify ? { email } : {}) };
    await db().lpush(LIST, JSON.stringify(rec));
    return json({ ok: true, matched: rec.matched });
  } catch (err) {
    console.error('jobs POST failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}
