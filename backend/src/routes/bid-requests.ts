import { Router } from "express";
import { prisma } from "../lib/prisma.js";
import { requireAuth, requireAdmin } from "../middleware/auth.js";

export const bidRequestsRouter = Router();

bidRequestsRouter.use(requireAuth);

// GET /api/bid-requests
bidRequestsRouter.get("/", async (req, res) => {
  try {
    const { id, role } = req.user!;
    const where = role === "admin" ? {} : { userId: id };

    const requests = await prisma.bidRequest.findMany({
      where,
      orderBy: { createdAt: "desc" },
      include: { user: { select: { name: true, email: true } } },
    });

    const auctionIds = requests.map(r => r.auctionId);
    const auctions = await prisma.auction.findMany({
      where: { id: { in: auctionIds } },
    });
    const auctionMap = Object.fromEntries(auctions.map(a => [a.id, a]));

    res.json(requests.map(r => {
      const a = auctionMap[r.auctionId];
      return {
        id: r.id,
        userId: r.userId,
        userName: r.user.name,
        userEmail: r.user.email,
        auctionId: r.auctionId,
        vehicle: a ? `${a.maker} ${a.model}` : "Unknown",
        lotNumber: a?.lotNumber || "",
        auctionDate: a?.auctionDate || "",
        auctionHouse: a?.auctionHouse || "",
        startPrice: a?.startPrice?.toString() || null,
        maxBid: r.maxBid?.toString() || null,
        note: r.note,
        status: r.status,
        crmBidRefCode: r.crmBidRefCode,
        sentToCrm: r.sentToCrm,
        createdAt: r.createdAt.toISOString(),
        reviewedAt: r.reviewedAt?.toISOString() || null,
      };
    }));
  } catch (err) {
    console.error("GET /api/bid-requests error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /api/bid-requests
bidRequestsRouter.post("/", async (req, res) => {
  try {
    const userId = req.user!.id;
    const body = req.body;
    const items: { auctionId: number; maxBid?: string; note?: string }[] =
      Array.isArray(body) ? body : [body];

    const results = [];
    for (const item of items) {
      if (!item.auctionId) continue;
      try {
        const bid = await prisma.bidRequest.create({
          data: {
            userId,
            auctionId: item.auctionId,
            maxBid: item.maxBid ? parseFloat(item.maxBid) : null,
            note: item.note || null,
          },
        });
        results.push({ auctionId: item.auctionId, status: "created", id: bid.id });
      } catch {
        results.push({ auctionId: item.auctionId, status: "already_sent" });
      }
    }

    res.status(201).json(results);
  } catch (err) {
    console.error("POST /api/bid-requests error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// PUT /api/bid-requests — admin only
bidRequestsRouter.put("/", requireAdmin, async (req, res) => {
  try {
    const { id, status } = req.body;
    const validStatuses = ["pending", "approved", "rejected", "completed"];
    if (!validStatuses.includes(status)) {
      res.status(400).json({ error: "Invalid status" });
      return;
    }

    await prisma.bidRequest.update({
      where: { id },
      data: { status, reviewedAt: new Date() },
    });

    res.json({ success: true });
  } catch (err) {
    console.error("PUT /api/bid-requests error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
