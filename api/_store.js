// Shared storage helpers for the API functions. Files starting with "_" are not routes.
import { Redis } from '@upstash/redis';
import { Ratelimit } from '@upstash/ratelimit';

let redis;
const limiters = {};
export function db() {
  if (!redis) redis = Redis.fromEnv();
  return redis;
}
export function limiter(name, n, window) {
  if (!limiters[name]) limiters[name] = new Ratelimit({ redis: db(), limiter: Ratelimit.slidingWindow(n, window), prefix: 'rl:' + name });
  return limiters[name];
}
export const json = (body, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } });
export const ipOf = request => (request.headers.get('x-forwarded-for') || 'unknown').split(',')[0].trim();
export const str = (v, max) => (typeof v === 'string' ? v.trim().slice(0, max) : '');
export const isEmail = v => /^\S+@\S+\.\S+$/.test(v);
