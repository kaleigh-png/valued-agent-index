// Reviews API. Anonymous yes/no reviews, one per browser per agent.
// Storage: one Redis hash, field "<agent>:<uid>" -> review JSON.
import { Redis } from '@upstash/redis';
import { Ratelimit } from '@upstash/ratelimit';

const ROLES = ['Executive','Operations','IT / Security','Engineering','Sales / Marketing','Finance / Legal','Other'];
const SIZES = ['1–49','50–249','250–999','1,000–4,999','5,000+'];
const RUNS = ['I run it myself',"The maker's hosted version",'Managed by a provider','Bought through a reseller'];
const QS = ['did_job','production','recommend','fast_setup','cost_ok'];
const HASH = 'reviews';

let redis, limiter;
function db() {
  if (!redis) {
    redis = Redis.fromEnv();
    limiter = new Ratelimit({ redis, limiter: Ratelimit.slidingWindow(5, '1 h'), prefix: 'rl:reviews' });
  }
  return redis;
}
const json = (body, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } });
const pick = (v, list) => (list.includes(v) ? v : null);
const str = (v, max) => (typeof v === 'string' ? v.trim().slice(0, max) : '');

export async function GET() {
  try {
    const all = (await db().hgetall(HASH)) || {};
    const byAgent = {};
    for (const [field, raw] of Object.entries(all)) {
      const i = field.lastIndexOf(':');
      if (i < 1) continue;
      const agent = field.slice(0, i), uid = field.slice(i + 1);
      const r = typeof raw === 'string' ? JSON.parse(raw) : raw;
      if (r && typeof r === 'object') (byAgent[agent] = byAgent[agent] || []).push({ ...r, uid });
    }
    for (const l of Object.values(byAgent)) l.sort((x, y) => String(y.ts).localeCompare(String(x.ts)));
    return json({ byAgent });
  } catch (err) {
    console.error('reviews GET failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}

export async function POST(request) {
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Bad request' }, 400); }
  if (body.website) return json({ ok: true }); // honeypot: bots fill it, people never see it

  const agent = str(body.agent, 80), uid = str(body.uid, 40);
  if (!/^[a-z0-9][a-z0-9-]{0,79}$/.test(agent) || !/^[a-f0-9]{32}$/.test(uid)) return json({ error: 'Bad request' }, 400);

  const r = {
    role: pick(body.role, ROLES), size: pick(body.size, SIZES), run: pick(body.run, RUNS),
    job: str(body.job, 120), comment: str(body.comment, 600), ts: new Date().toISOString(),
  };
  for (const k of QS) r[k] = body[k] === 'yes' ? 'yes' : body[k] === 'no' ? 'no' : null;
  if (!r.role || !r.size || !r.run) return json({ error: 'Choose your role, company size and how you use it.' }, 422);
  if (QS.some(k => !r[k])) return json({ error: 'Answer all five yes/no questions.' }, 422);

  try {
    const store = db();
    const ip = (request.headers.get('x-forwarded-for') || 'unknown').split(',')[0].trim();
    const { success } = await limiter.limit(ip);
    if (!success) return json({ error: 'Too many reviews from this connection. Try again in an hour.' }, 429);
    await store.hset(HASH, { [`${agent}:${uid}`]: JSON.stringify(r) });
    return json({ review: { ...r, uid } });
  } catch (err) {
    console.error('reviews POST failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}
