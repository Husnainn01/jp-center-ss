import { Router } from "express";
import { prisma } from "../lib/prisma.js";
import { serializeAuction } from "../lib/serialize.js";
import { Prisma } from "../generated/prisma/client.js";
import { cached } from "../lib/cache.js";

export const auctionsRouter = Router();

const META_TTL = 2 * 60 * 1000; // 2 min — filter options rarely change

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
    if (maker) where.maker = maker;
    if (model) where.model = model;
    if (location) where.location = location;
    if (chassisCode) where.chassisCode = { contains: chassisCode, mode: "insensitive" };
    if (auctionHouse) where.auctionHouse = { contains: auctionHouse, mode: "insensitive" };
    if (source) where.source = source;
    if (status) where.status = status;
    else if (!req.query.status) where.status = undefined; // Allow all statuses by default
    if (rating) {
      if (rating === "S") {
        where.rating = "S";
      } else {
        // rating is a numeric threshold like "4.5" — find >= that value
        // rating field is string, so we use gte which works for numeric-like strings
        where.rating = { gte: rating, not: "S" };
      }
    }
    if (yearFrom || yearTo) {
      where.year = {};
      if (yearFrom) where.year.gte = yearFrom;
      if (yearTo) where.year.lte = yearTo;
    }
    if (auctionDay) {
      where.auctionDateNorm = new Date(auctionDay);
    } else if (status === "upcoming") {
      // For upcoming auctions, only show FUTURE dates (tomorrow onwards)
      // Today's auctions are useless — they've already started
      const tomorrow = new Date(new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Tokyo" }));
      tomorrow.setDate(tomorrow.getDate() + 1);
      where.auctionDateNorm = { gte: tomorrow };
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
        { chassisCode: { contains: search, mode: "insensitive" } },
        { lotNumber: { contains: search, mode: "insensitive" } },
        { grade: { contains: search, mode: "insensitive" } },
        { itemId: { contains: search, mode: "insensitive" } },
        { auctionHouse: { contains: search, mode: "insensitive" } },
      ];
    }

    const allowedSorts = ["auctionDate", "auctionDateNorm", "startPrice", "maker", "firstSeen", "year", "rating"];
    const sortField = allowedSorts.includes(sort) ? sort : "auctionDate";

    // Main data query — not cached (pagination + filters change constantly)
    const [auctions, total] = await Promise.all([
      prisma.auction.findMany({
        where,
        orderBy: { [sortField]: order } as Prisma.AuctionOrderByWithRelationInput,
        skip: (page - 1) * pageSize,
        take: pageSize,
      }),
      prisma.auction.count({ where }),
    ]);

    // Day counts: same filters as main query but WITHOUT auctionDay
    // This ensures day button counts reflect the user's active filters
    const filteredDays = await
      prisma.$queryRaw<{ date: string; cnt: number }[]>`
        SELECT auction_date_norm::text as date, COUNT(*)::int as cnt
        FROM auctions
        WHERE status = 'upcoming'
          AND auction_date_norm IS NOT NULL
          AND auction_date_norm > (NOW() AT TIME ZONE 'Asia/Tokyo')::date
          ${maker ? Prisma.sql`AND maker = ${maker}` : Prisma.empty}
          ${model ? Prisma.sql`AND model = ${model}` : Prisma.empty}
          ${location ? Prisma.sql`AND location = ${location}` : Prisma.empty}
          ${chassisCode ? Prisma.sql`AND chassis_code ILIKE ${'%' + chassisCode + '%'}` : Prisma.empty}
          ${auctionHouse ? Prisma.sql`AND auction_house ILIKE ${'%' + auctionHouse + '%'}` : Prisma.empty}
          ${source ? Prisma.sql`AND source = ${source}` : Prisma.empty}
          ${minPrice ? Prisma.sql`AND start_price >= ${parseFloat(minPrice)}` : Prisma.empty}
          ${maxPrice ? Prisma.sql`AND start_price <= ${parseFloat(maxPrice)}` : Prisma.empty}
          ${yearFrom ? Prisma.sql`AND year >= ${yearFrom}` : Prisma.empty}
          ${yearTo ? Prisma.sql`AND year <= ${yearTo}` : Prisma.empty}
          ${rating === "S" ? Prisma.sql`AND rating = 'S'` : rating ? Prisma.sql`AND rating >= ${rating} AND rating != 'S'` : Prisma.empty}
          ${search ? Prisma.sql`AND (maker ILIKE ${'%' + search + '%'} OR model ILIKE ${'%' + search + '%'} OR lot_number ILIKE ${'%' + search + '%'} OR grade ILIKE ${'%' + search + '%'} OR item_id ILIKE ${'%' + search + '%'})` : Prisma.empty}
        GROUP BY auction_date_norm
        ORDER BY auction_date_norm ASC
      `;

    const response: Record<string, unknown> = {
      auctions: auctions.map(serializeAuction),
      total,
      page,
      pageSize,
      totalPages: Math.ceil(total / pageSize),
      auctionDays: filteredDays.map(d => ({ date: d.date, count: d.cnt })),
    };

    // Meta/filter options — cached (same for all users, only changes on scraper sync)
    if (includeMeta) {
      const meta = await cached("auctions:meta", async () => {
        const [sourceCounts, makers, locations, houses] = await Promise.all([
          prisma.auction.groupBy({ by: ["source"], where: { status: "upcoming" }, _count: true }),
          prisma.$queryRaw<{ maker: string; cnt: number }[]>`SELECT maker, COUNT(*)::int as cnt FROM auctions WHERE status='upcoming' GROUP BY maker ORDER BY cnt DESC LIMIT 30`,
          prisma.$queryRaw<{ location: string; cnt: number }[]>`SELECT location, COUNT(*)::int as cnt FROM auctions WHERE status='upcoming' GROUP BY location ORDER BY cnt DESC LIMIT 20`,
          prisma.$queryRaw<{ auction_house: string; cnt: number }[]>`SELECT auction_house, COUNT(*)::int as cnt FROM auctions WHERE status='upcoming' GROUP BY auction_house ORDER BY cnt DESC`,
        ]);
        return {
          sourceCounts: Object.fromEntries(sourceCounts.map(s => [s.source, s._count])),
          filterOptions: {
            makers: makers.map(m => ({ value: m.maker, count: m.cnt })),
            locations: locations.map(l => ({ value: l.location, count: l.cnt })),
            auctionHouses: houses.map(h => ({ value: h.auction_house, count: h.cnt })),
          },
        };
      }, META_TTL);

      response.sourceCounts = meta.sourceCounts;
      response.filterOptions = meta.filterOptions;
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
