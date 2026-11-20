// Customer stories: the job someone automated, with which agent, how, and who ran it.
// POST puts a story in the pending hash. A person approves it on /admin before it
// shows. GET returns approved stories only, never the author's email.
import { db, limiter, json, ipOf, str, isEmail, pick, parse, newId } from './_store.js';

export const RUNS = ['We run it ourselves', "The maker's hosted version", 'A provider runs it for us'];
export const AUTHORS = ['A customer who uses it', 'The maker of the agent', 'A consultant who set it up'];
export const PENDING = 'stories:pending';
export const APPROVED = 'stories';

export const publicStory = s => { const { email, ip, ...rest } = s; return rest; };

export async function GET() {
  try {
    const all = (await db().hgetall(APPROVED)) || {};
    const stories = Object.values(all).map(parse).filter(s => s && typeof s === 'object').map(publicStory);
    stories.sort((x, y) => String(y.approved_at || y.ts).localeCompare(String(x.approved_at || x.ts)));
    return json({ stories });
  } catch (err) {
    console.error('stories GET failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}

export async function POST(request) {
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Bad request' }, 400); }
  if (body.hp_url) return json({ ok: true }); // honeypot
  const s = {
    id: newId(), ts: new Date().toISOString(), status: 'pending',
    job: str(body.job, 80), job_text: str(body.job_text, 160),
    agent: str(body.agent, 80), agent_name: str(body.agent_name, 80), agent_url: str(body.agent_url, 300),
    before: str(body.before, 400), workflow: str(body.workflow, 1500), outcome: str(body.outcome, 300),
    runs: pick(body.runs, RUNS), provider: str(body.provider, 80),
    author: pick(body.author, AUTHORS), company: str(body.company, 120), role: str(body.role, 80),
    industry: str(body.industry, 80), email: str(body.email, 200),
  };
  if (!s.job_text && !s.job) return json({ error: 'Name the job.' }, 422);
  if (!s.agent_name && !s.agent) return json({ error: 'Name the agent.' }, 422);
  if (!s.workflow) return json({ error: 'Describe how it runs.' }, 422);
  if (!s.runs || !s.author) return json({ error: 'Choose where it runs and who you are.' }, 422);
  if (!isEmail(s.email)) return json({ error: 'Enter a valid email address so we can confirm the story.' }, 422);
  if (s.agent_url && !/^https?:\/\//i.test(s.agent_url)) return json({ error: 'The agent link must start with http.' }, 422);
  try {
    const ip = ipOf(request);
    const { success } = await limiter('stories', 5, '1 h').limit(ip);
    if (!success) return json({ error: 'Too many stories from this connection. Try again in an hour.' }, 429);
    await db().hset(PENDING, { [s.id]: JSON.stringify({ ...s, ip }) });
    return json({ ok: true, id: s.id });
  } catch (err) {
    console.error('stories POST failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}
