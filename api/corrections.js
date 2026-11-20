// Public corrections log. Every fix a person makes after a report is listed
// here with the date, so anyone can see what changed and why.
import { db, json, parse } from './_store.js';

export async function GET() {
  try {
    const raw = await db().lrange('corrections', 0, 199);
    return json({ corrections: raw.map(parse).filter(Boolean) });
  } catch (err) {
    console.error('corrections GET failed', err);
    return json({ error: 'unavailable' }, 503);
  }
}
