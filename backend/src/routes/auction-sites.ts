import { Router } from "express";
import { prisma } from "../lib/prisma.js";

export const auctionSitesRouter = Router();

// GET /api/auction-sites
auctionSitesRouter.get("/", async (_req, res) => {
  try {
    const sites = await prisma.auctionSite.findMany({ orderBy: { name: "asc" } });

    res.json(sites.map(s => ({
      id: s.id,
      name: s.name,
      url: s.url,
      userId: s.userId || "",
      hasPassword: !!s.password,
      isEnabled: s.isEnabled,
      isConnected: s.isConnected,
      lastLogin: s.lastLogin?.toISOString() || null,
      lastSync: s.lastSync?.toISOString() || null,
    })));
  } catch (err) {
    console.error("GET /api/auction-sites error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// PUT /api/auction-sites
auctionSitesRouter.put("/", async (req, res) => {
  try {
    const { id, userId, password, isEnabled } = req.body;
    if (!id) {
      res.status(400).json({ error: "Site ID is required" });
      return;
    }

    const data: Record<string, unknown> = {};
    if (typeof isEnabled === "boolean") data.isEnabled = isEnabled;
    if (userId !== undefined) data.userId = userId.trim();
    if (password && password !== "••••••••") data.password = password;

    await prisma.auctionSite.update({ where: { id }, data });
    res.json({ success: true });
  } catch (err) {
    console.error("PUT /api/auction-sites error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
