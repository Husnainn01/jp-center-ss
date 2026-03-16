import { Router } from "express";
import { prisma } from "../lib/prisma.js";

export const statsRouter = Router();

// GET /api/stats
statsRouter.get("/", async (req, res) => {
  try {
    const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const extended = req.query.extended === "true";

    const baseQueries = [
      prisma.auction.count({ where: { status: "upcoming" } }),
      prisma.auction.count({ where: { status: "sold" } }),
      prisma.auction.count({ where: { firstSeen: { gte: oneDayAgo } } }),
      prisma.auction.count({ where: { status: "expired" } }),
      prisma.syncLog.findFirst({ orderBy: { runAt: "desc" } }),
    ];

    if (extended) {
      baseQueries.push(
        prisma.auction.count() as unknown as typeof baseQueries[0],
        prisma.auction.groupBy({ by: ["source"], _count: true }) as unknown as typeof baseQueries[0],
      );
    }

    const results = await Promise.all(baseQueries);

    const response: Record<string, unknown> = {
      totalUpcoming: results[0],
      totalSold: results[1],
      recentlyAdded: results[2],
      totalExpired: results[3],
      lastSyncAt: (results[4] as { runAt: Date } | null)?.runAt.toISOString() ?? null,
      lastSyncTotal: (results[4] as { totalScraped: number } | null)?.totalScraped ?? 0,
    };

    if (extended) {
      response.totalAll = results[5];
      response.sourceCounts = results[6];
    }

    res.json(response);
  } catch (err) {
    console.error("GET /api/stats error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
