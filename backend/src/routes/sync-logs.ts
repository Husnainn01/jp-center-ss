import { Router } from "express";
import { prisma } from "../lib/prisma.js";
import { serializeSyncLog } from "../lib/serialize.js";

export const syncLogsRouter = Router();

// GET /api/sync-logs
syncLogsRouter.get("/", async (req, res) => {
  try {
    const limit = Math.min(100, parseInt(req.query.limit as string) || 10);
    const includeSession = req.query.includeSession === "true";

    const queries: Promise<unknown>[] = [
      prisma.syncLog.findMany({ orderBy: { runAt: "desc" }, take: limit }),
    ];

    if (includeSession) {
      queries.push(prisma.sessionState.findFirst({ where: { id: 1 } }));
    }

    const results = await Promise.all(queries);
    const logs = results[0] as Awaited<ReturnType<typeof prisma.syncLog.findMany>>;

    const response: Record<string, unknown> = {
      logs: logs.map(serializeSyncLog),
    };

    if (includeSession && results[1]) {
      const session = results[1] as { lastLogin: Date | null; isValid: boolean };
      response.session = {
        lastLogin: session.lastLogin?.toISOString() || null,
        isValid: session.isValid,
      };
    }

    res.json(response);
  } catch (err) {
    console.error("GET /api/sync-logs error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
