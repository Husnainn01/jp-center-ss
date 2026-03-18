import { Router } from "express";
import { cacheInvalidate } from "../lib/cache.js";

export const cacheRouter = Router();

// POST /api/cache/invalidate — called by scraper after sync to clear stale cache
cacheRouter.post("/invalidate", (req, res) => {
  const count = cacheInvalidate();
  console.log(`[cache] Invalidated ${count} cached entries`);
  res.json({ cleared: count });
});
