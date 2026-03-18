import { Router } from "express";
import { prisma } from "../lib/prisma.js";
import { serializeAuction } from "../lib/serialize.js";
import type { Prisma } from "../generated/prisma/client.js";

export const auctionsRouter = Router();

// GET /api/auctions — paginated list with filters
auctionsRouter.get("/", async (req, res) => {
  try {
    const page = Math.max(1, parseInt(req.query.page as string) || 1);
    const pageSize = Math.min(100, Math.max(1, parseInt(req.query.pageSize as string) || 25));
    const maker = req.query.maker as string | undefined;
    const model = req.query.model as string | undefined;
    const location = req.query.location as string | undefined;
    const auctionHouse = req.query.auctionHouse as string | undefined;
    const chassisCode = req.query.chassisCode as string | undefined;
    const source = req.query.source as string | undefined;
    const status = req.query.status as string | undefined;
    const search = req.query.search as string | undefined;
    const sort = (req.query.sort as string) || "auctionDate";
    const order = req.query.order === "desc" ? "desc" : "asc";
    const minPrice = req.query.minPrice as string | undefined;
    const maxPrice = req.query.maxPrice as string | undefined;
    const rating = req.query.rating as string | undefined;
    const yearFrom = req.query.yearFrom as string | undefined;
    const yearTo = req.query.yearTo as string | undefined;
    const auctionDay = req.query.auctionDay as string | undefined;
    const includeMeta = req.query.includeMeta === "true";

    const where: Prisma.AuctionWhereInput = {};
    if (maker) where.maker = { contains: maker };
    if (model) where.model = { contains: model };
    if (location) where.location = { contains: location };
    if (chassisCode) where.chassisCode = { contains: chassisCode };
    if (auctionHouse) where.auctionHouse = { contains: auctionHouse };
    if (source) where.source = source;
    if (status) where.status = status;
    else if (!req.query.status) where.status = undefined; // Allow all statuses by default
    if (rating) where.rating = { contains: rating };
    if (yearFrom || yearTo) {
      where.year = {};
      if (yearFrom) where.year.gte = yearFrom;
      if (yearTo) where.year.lte = yearTo;
    }
    if (auctionDay) {
      where.auctionDateNorm = new Date(auctionDay);
    }
    if (minPrice || maxPrice) {
      where.startPrice = {};
      if (minPrice) where.startPrice.gte = parseFloat(minPrice);
      if (maxPrice) where.startPrice.lte = parseFloat(maxPrice);
    }
    if (search) {
      where.OR = [
        { maker: { contains: search, mode: "insensitive" } },
        { model: { contains: search, mode: "insensitive" } },
        { lotNumber: { contains: search, mode: "insensitive" } },
        { grade: { contains: search, mode: "insensitive" } },
        { itemId: { contains: search, mode: "insensitive" } },
      ];
    }

    const allowedSorts = ["auctionDate", "auctionDateNorm", "startPrice", "maker", "firstSeen", "year", "rating"];
    const sortField = allowedSorts.includes(sort) ? sort : "auctionDate";

    const queries: Promise<unknown>[] = [
      prisma.auction.findMany({
        where,
        orderBy: { [sortField]: order } as Prisma.AuctionOrderByWithRelationInput,
        skip: (page - 1) * pageSize,
        take: pageSize,
      }),
      prisma.auction.count({ where }),
    ];

    // Optionally include source counts + filter options for server component use
    if (includeMeta) {
      queries.push(
        prisma.auction.groupBy({ by: ["source"], where: { status: "upcoming" }, _count: true }),
        prisma.$queryRaw`SELECT maker, COUNT(*)::int as cnt FROM auctions WHERE status='upcoming' GROUP BY maker ORDER BY cnt DESC LIMIT 30`,
        prisma.$queryRaw`SELECT location, COUNT(*)::int as cnt FROM auctions WHERE status='upcoming' GROUP BY location ORDER BY cnt DESC LIMIT 20`,
        prisma.$queryRaw`SELECT auction_house, COUNT(*)::int as cnt FROM auctions WHERE status='upcoming' GROUP BY auction_house ORDER BY cnt DESC`,
        prisma.$queryRaw`SELECT auction_date_norm::text as date, COUNT(*)::int as cnt FROM auctions WHERE status='upcoming' AND auction_date_norm IS NOT NULL AND auction_date_norm >= (NOW() AT TIME ZONE 'Asia/Tokyo')::date GROUP BY auction_date_norm ORDER BY auction_date_norm ASC`,
      );
    }

    const results = await Promise.all(queries);
    const auctions = results[0] as Awaited<ReturnType<typeof prisma.auction.findMany>>;
    const total = results[1] as number;

    const response: Record<string, unknown> = {
      auctions: auctions.map(serializeAuction),
      total,
      page,
      pageSize,
      totalPages: Math.ceil(total / pageSize),
    };

    if (includeMeta) {
      const sourceCounts = results[2] as { source: string; _count: number }[];
      const makers = results[3] as { maker: string; cnt: number }[];
      const locations = results[4] as { location: string; cnt: number }[];
      const houses = results[5] as { auction_house: string; cnt: number }[];
      const days = results[6] as { date: string; cnt: number }[];
      response.sourceCounts = Object.fromEntries(sourceCounts.map(s => [s.source, s._count]));
      response.filterOptions = {
        makers: makers.map(m => ({ value: m.maker, count: m.cnt })),
        locations: locations.map(l => ({ value: l.location, count: l.cnt })),
        auctionHouses: houses.map(h => ({ value: h.auction_house, count: h.cnt })),
        auctionDays: days.map(d => ({ date: d.date, count: d.cnt })),
      };
    }

    res.json(response);
  } catch (err) {
    console.error("GET /api/auctions error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// GET /api/auctions/:id — single auction
auctionsRouter.get("/:id", async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) {
      res.status(400).json({ error: "Invalid ID" });
      return;
    }

    const auction = await prisma.auction.findUnique({ where: { id } });
    if (!auction) {
      res.status(404).json({ error: "Auction not found" });
      return;
    }

    res.json(serializeAuction(auction));
  } catch (err) {
    console.error("GET /api/auctions/:id error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
