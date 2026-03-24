/**
 * Simple in-memory rate limiter. No external dependencies.
 * Limits requests per IP within a time window.
 */

import type { Request, Response, NextFunction } from "express";

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

const store = new Map<string, RateLimitEntry>();

// Cleanup stale entries every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of store) {
    if (entry.resetAt < now) store.delete(key);
  }
}, 5 * 60 * 1000);

/**
 * Creates a rate limiter middleware.
 * @param maxRequests Max requests allowed in the window
 * @param windowMs Time window in milliseconds
 */
export function rateLimit(maxRequests: number, windowMs: number) {
  return (req: Request, res: Response, next: NextFunction) => {
    const ip = req.ip || req.headers["x-forwarded-for"] as string || "unknown";
    const key = `${ip}:${req.path}`;
    const now = Date.now();

    let entry = store.get(key);
    if (!entry || entry.resetAt < now) {
      entry = { count: 0, resetAt: now + windowMs };
      store.set(key, entry);
    }

    entry.count++;

    res.setHeader("X-RateLimit-Limit", String(maxRequests));
    res.setHeader("X-RateLimit-Remaining", String(Math.max(0, maxRequests - entry.count)));
    res.setHeader("X-RateLimit-Reset", String(Math.ceil(entry.resetAt / 1000)));

    if (entry.count > maxRequests) {
      res.status(429).json({ error: "Too many requests. Please try again later." });
      return;
    }

    next();
  };
}
