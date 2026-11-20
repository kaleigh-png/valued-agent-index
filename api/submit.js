// Form submissions: claim a listing, get help with an agent, Agent Pulse.
// Each kind is a Redis list (newest first). Pulse emails also go in a set.
// A help request names the providers it goes to; there is no default provider.
import { db, limiter, json, ipOf, str, isEmail } from './_store.js';

const KINDS = {
  claim:  { fields: { role: 80, agent: 80, co: 120, em: 200, web: 300, about: 600, ev: 2000, run_ok: 10 }, required: ['co', 'em'], email: 'em' },
  manage: { fields: { magent: 80, mjob: 1000, mco: 120, mem: 200, providers: 300 }, required: ['mjob', 'mco', 'mem', 'providers'], email: 'mem' },
  pulse:  { fields: { pem: 200, pind: 80 }, required: ['pem'], email: 'pem' },
};

export async function POST(request) {
  let body;
  try { body = await request.json(); } catch { return json({ error: 'Bad request' }, 400); }
  if (body.hp_url) return json({ ok: true }); // honeypot
  const spec = KINDS[body.kind];
  if (!spec) return json({ error: 'Bad request' }, 400);

  const fields = {};
  for (const [k, max] of Object.entries(spec.fields)) fields[k] = str(body[k], max);
  if (spec.required.some(k => !fields[k])) return json({ error: 'Fill in every required field.' }, 422);
  if (!isEmail(fields[spec.email])) return json({ error: 'Enter a valid email address.' }, 422);

  try {
    const ip = ipOf(request);
    const { success } = await limiter('submit', 10, '1 h').limit(ip);
    if (!success) return json({ error: 'Too many submissions from this connection. Try again in an hour.' }, 429);
    const rec = { kind: body.kind, ts: new Date().toISOString(), ...fields };
    const store = db();
    await store.lpush(`submissions:${body.kind}`, JSON.stringify(rec));
    if (body.kind === 'pulse') await store.sadd('pulse:emails', fields.pem.toLowerCase());
    return json({ ok: true });
  } catch (err) {
    console.error('submit failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}
