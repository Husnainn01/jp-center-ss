import { Router } from "express";
import { prisma } from "../lib/prisma.js";

export const scraperStatusRouter = Router();

// GET /api/scraper-status — per-scraper health
scraperStatusRouter.get("/", async (_req, res) => {
  try {
    const sources = ["aucnet", "ninja", "taa"];
    const result: Record<string, unknown> = {};

    const latestLogs = await Promise.all(
      sources.map((source) =>
        prisma.syncLog.findFirst({
          where: { source },
          orderBy: { runAt: "desc" },
        })
      )
    );

    for (let i = 0; i < sources.length; i++) {
      const source = sources[i];
      const log = latestLogs[i];

      if (!log) {
        result[source] = { lastRun: null, status: "unknown" };
        continue;
      }

      result[source] = {
        lastRun: log.runAt.toISOString(),
        status: log.error ? "error" : "ok",
        totalScraped: log.totalScraped,
        durationMs: log.durationMs,
        ...(log.error && { error: log.error }),
      };
    }

    res.json(result);
  } catch (err) {
    console.error("GET /api/scraper-status error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
