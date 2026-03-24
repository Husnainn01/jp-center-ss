import { Router } from "express";
import { prisma } from "../lib/prisma.js";
import { serializeAuction } from "../lib/serialize.js";
import { requireAuth } from "../middleware/auth.js";

export const listsRouter = Router();

// All list routes require auth
listsRouter.use(requireAuth);

// GET /api/lists
listsRouter.get("/", async (req, res) => {
  try {
    const userId = req.user!.id;
    const lists = await prisma.carList.findMany({
      where: { userId },
      orderBy: { createdAt: "desc" },
      include: { _count: { select: { items: true } } },
    });

    res.json(lists.map(l => ({
      id: l.id,
      name: l.name,
      itemCount: l._count.items,
      createdAt: l.createdAt.toISOString(),
    })));
  } catch (err) {
    console.error("GET /api/lists error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /api/lists
listsRouter.post("/", async (req, res) => {
  try {
    const userId = req.user!.id;
    const { name } = req.body;
    const safeName = String(name || "").replace(/<[^>]*>/g, "").trim().slice(0, 100);
    if (!safeName) {
      res.status(400).json({ error: "List name is required" });
      return;
    }

    const list = await prisma.carList.create({
      data: { name: safeName, userId },
    });

    res.status(201).json({
      id: list.id,
      name: list.name,
      itemCount: 0,
      createdAt: list.createdAt.toISOString(),
    });
  } catch (err) {
    console.error("POST /api/lists error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// GET /api/lists/:id
listsRouter.get("/:id", async (req, res) => {
  try {
    const userId = req.user!.id;
    const listId = parseInt(req.params.id);

    const list = await prisma.carList.findFirst({
      where: { id: listId, userId },
      include: { items: { orderBy: { addedAt: "desc" } } },
    });

    if (!list) {
      res.status(404).json({ error: "Not found" });
      return;
    }

    const auctionIds = list.items.map(i => i.auctionId);
    const auctions = await prisma.auction.findMany({
      where: { id: { in: auctionIds } },
    });
    const auctionMap = Object.fromEntries(auctions.map(a => [a.id, a]));

    res.json({
      id: list.id,
      name: list.name,
      createdAt: list.createdAt.toISOString(),
      items: list.items.map(item => ({
        id: item.id,
        auctionId: item.auctionId,
        note: item.note,
        addedAt: item.addedAt.toISOString(),
        auction: auctionMap[item.auctionId] ? serializeAuction(auctionMap[item.auctionId]) : null,
      })),
    });
  } catch (err) {
    console.error("GET /api/lists/:id error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// DELETE /api/lists/:id
listsRouter.delete("/:id", async (req, res) => {
  try {
    const userId = req.user!.id;
    const listId = parseInt(req.params.id);

    const list = await prisma.carList.findFirst({ where: { id: listId, userId } });
    if (!list) {
      res.status(404).json({ error: "Not found" });
      return;
    }

    await prisma.carList.delete({ where: { id: listId } });
    res.json({ success: true });
  } catch (err) {
    console.error("DELETE /api/lists/:id error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /api/lists/:id/items
listsRouter.post("/:id/items", async (req, res) => {
  try {
    const userId = req.user!.id;
    const listId = parseInt(req.params.id);
    const auctionId = parseInt(String(req.body.auctionId));
    const note = req.body.note ? String(req.body.note).replace(/<[^>]*>/g, "").trim().slice(0, 500) : null;

    if (isNaN(listId) || isNaN(auctionId)) {
      res.status(400).json({ error: "Invalid ID" });
      return;
    }

    const list = await prisma.carList.findFirst({ where: { id: listId, userId } });
    if (!list) {
      res.status(404).json({ error: "List not found" });
      return;
    }

    const auction = await prisma.auction.findUnique({ where: { id: auctionId } });
    if (!auction) {
      res.status(404).json({ error: "Auction not found" });
      return;
    }

    try {
      const item = await prisma.carListItem.create({
        data: { listId, auctionId, note },
      });
      res.status(201).json({ id: item.id, auctionId: item.auctionId });
    } catch {
      res.status(409).json({ error: "Already in this list" });
    }
  } catch (err) {
    console.error("POST /api/lists/:id/items error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// DELETE /api/lists/:id/items
listsRouter.delete("/:id/items", async (req, res) => {
  try {
    const userId = req.user!.id;
    const listId = parseInt(req.params.id);
    const { auctionId } = req.body;

    const list = await prisma.carList.findFirst({ where: { id: listId, userId } });
    if (!list) {
      res.status(404).json({ error: "Not found" });
      return;
    }

    await prisma.carListItem.deleteMany({ where: { listId, auctionId } });
    res.json({ success: true });
  } catch (err) {
    console.error("DELETE /api/lists/:id/items error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
