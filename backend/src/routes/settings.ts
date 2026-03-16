import { Router } from "express";
import { prisma } from "../lib/prisma.js";

export const settingsRouter = Router();

// GET /api/settings
settingsRouter.get("/", async (_req, res) => {
  try {
    const session = await prisma.sessionState.findFirst({ where: { id: 1 } });

    if (!session) {
      res.json({ auctionUserId: "", auctionPassword: "", isValid: false });
      return;
    }

    res.json({
      auctionUserId: session.auctionUserId || "",
      auctionPassword: session.auctionPassword ? "••••••••" : "",
      hasPassword: !!session.auctionPassword,
      isValid: session.isValid,
      lastLogin: session.lastLogin?.toISOString() || null,
    });
  } catch (err) {
    console.error("GET /api/settings error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// PUT /api/settings
settingsRouter.put("/", async (req, res) => {
  try {
    const { auctionUserId, auctionPassword } = req.body;

    if (!auctionUserId || typeof auctionUserId !== "string") {
      res.status(400).json({ error: "Auction User ID is required" });
      return;
    }

    const data: Record<string, string | boolean> = {
      auctionUserId: auctionUserId.trim(),
      isValid: false,
    };

    if (auctionPassword && auctionPassword !== "••••••••") {
      data.auctionPassword = auctionPassword;
    }

    await prisma.sessionState.upsert({
      where: { id: 1 },
      update: data,
      create: { id: 1, ...data },
    });

    res.json({ success: true });
  } catch (err) {
    console.error("PUT /api/settings error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
