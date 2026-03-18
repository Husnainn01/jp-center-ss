import { Router } from "express";
import { prisma } from "../lib/prisma.js";

export const filterOptionsRouter = Router();

// GET /api/filter-options
filterOptionsRouter.get("/", async (req, res) => {
  try {
    const maker = req.query.maker as string | undefined;
    const includeAll = req.query.includeAll === "true";

    const model = req.query.model as string | undefined;

    if (maker) {
      const models = await prisma.$queryRaw<{ model: string; cnt: number }[]>`
        SELECT model, COUNT(*)::int as cnt FROM auctions
        WHERE status = 'upcoming' AND maker = ${maker} AND model != ''
        GROUP BY model ORDER BY cnt DESC LIMIT 50
      `;

      // If model is also provided, return chassis codes for that maker+model
      let chassisCodes: { value: string; count: number }[] = [];
      if (model) {
        const codes = await prisma.$queryRaw<{ chassis_code: string; cnt: number }[]>`
          SELECT chassis_code, COUNT(*)::int as cnt FROM auctions
          WHERE status = 'upcoming' AND maker = ${maker} AND model = ${model}
            AND chassis_code IS NOT NULL AND chassis_code != ''
          GROUP BY chassis_code ORDER BY cnt DESC LIMIT 30
        `;
        chassisCodes = codes.map(c => ({ value: c.chassis_code, count: c.cnt }));
      }

      res.json({
        models: models.map(m => ({ value: m.model, count: m.cnt })),
        chassisCodes,
      });
      return;
    }

    const queries: Promise<unknown>[] = [
      prisma.$queryRaw`SELECT maker, COUNT(*)::int as cnt FROM auctions WHERE status='upcoming' GROUP BY maker ORDER BY cnt DESC LIMIT 40`,
      prisma.$queryRaw`SELECT location, COUNT(*)::int as cnt FROM auctions WHERE status='upcoming' GROUP BY location ORDER BY cnt DESC LIMIT 25`,
      prisma.$queryRaw`SELECT auction_house, COUNT(*)::int as cnt FROM auctions WHERE status='upcoming' GROUP BY auction_house ORDER BY cnt DESC`,
    ];

    if (includeAll) {
      queries.push(
        prisma.auction.groupBy({ by: ["source"], _count: true }),
        prisma.auction.groupBy({ by: ["status"], _count: true }),
      );
    }

    const results = await Promise.all(queries);
    const makers = results[0] as { maker: string; cnt: number }[];
    const locations = results[1] as { location: string; cnt: number }[];
    const houses = results[2] as { auction_house: string; cnt: number }[];

    const response: Record<string, unknown> = {
      makers: makers.map(m => ({ value: m.maker, count: m.cnt })),
      locations: locations.map(l => ({ value: l.location, count: l.cnt })),
      auctionHouses: houses.map(h => ({ value: h.auction_house, count: h.cnt })),
    };

    if (includeAll) {
      const sources = results[3] as { source: string; _count: number }[];
      const statuses = results[4] as { status: string; _count: number }[];
      response.sources = sources.map(s => ({ value: s.source, count: s._count }));
      response.statuses = statuses.map(s => ({ value: s.status, count: s._count }));
    }

    res.json(response);
  } catch (err) {
    console.error("GET /api/filter-options error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
