import { Router } from "express";
import { prisma } from "../lib/prisma.js";
import { requireAuth } from "../middleware/auth.js";
import { crmCreateBid } from "../lib/crm-client.js";
import { proxyUrl } from "../lib/image.js";

export const bidToCrmRouter = Router();

bidToCrmRouter.use(requireAuth);

// POST /api/bid-to-crm
bidToCrmRouter.post("/", async (req, res) => {
  try {
    const user = req.user!;

    if (!user.crmCustomerId) {
      res.status(400).json({ error: "No CRM customer linked to this account" });
      return;
    }

    if (!user.crmToken) {
      res.status(401).json({ error: "CRM session expired. Please log in again." });
      return;
    }

    const { auctionId, maxBidPrice, note } = req.body;

    if (!auctionId) {
      res.status(400).json({ error: "auctionId is required" });
      return;
    }

    const auction = await prisma.auction.findUnique({ where: { id: auctionId } });
    if (!auction) {
      res.status(404).json({ error: "Auction not found" });
      return;
    }

    // Build absolute image URLs
    const images = (auction.images as string[] | null) || [];
    const vehicleImages = images
      .filter((img: string) => !img.includes("_exb"))
      .map((img: string) => proxyUrl(img));

    const exhibitSheetUrl = auction.exhibitSheet
      ? proxyUrl(auction.exhibitSheet)
      : images.find((img: string) => img.includes("_exb"))
        ? proxyUrl(images.find((img: string) => img.includes("_exb"))!)
        : null;

    // Extract year number from auction year string (e.g. "27 December 2016" → 2016)
    const yearMatch = (auction.year || "").match(/\b(19|20)\d{2}\b/);
    const yearNum = yearMatch ? parseInt(yearMatch[0], 10) : new Date().getFullYear();

    // Model may be empty if maker contains full name (e.g. "Honda Fit GP5")
    const modelStr = auction.model || auction.maker.split(" ").slice(1).join(" ") || "Unknown";

    const crmResponse = await crmCreateBid(
      {
        customerId: user.crmCustomerId,
        auctionHouse: auction.auctionHouse,
        lotNumber: auction.lotNumber,
        maker: auction.maker,
        model: modelStr,
        year: String(yearNum),
        color: auction.color || "",
        maxBidPrice: maxBidPrice ? Number(maxBidPrice) : null,
        bidDate: auction.auctionDate,
        exhibitSheetUrl,
        vehicleImages,
        chassisCode: auction.chassisCode || null,
        mileage: auction.mileage || null,
        rating: auction.rating || null,
        startPrice: auction.startPrice ? Number(auction.startPrice) : null,
        auctionSource: auction.source,
        note: note || undefined,
      },
      user.crmToken
    );

    // Save/update local bid request record
    const existingBid = await prisma.bidRequest.findUnique({
      where: { userId_auctionId: { userId: user.id, auctionId } },
    });

    if (existingBid) {
      await prisma.bidRequest.update({
        where: { id: existingBid.id },
        data: {
          maxBid: maxBidPrice ? parseFloat(maxBidPrice) : existingBid.maxBid,
          note: note || existingBid.note,
          crmBidRefCode: crmResponse.referenceCode,
          sentToCrm: true,
        },
      });
    } else {
      await prisma.bidRequest.create({
        data: {
          userId: user.id,
          auctionId,
          maxBid: maxBidPrice ? parseFloat(maxBidPrice) : null,
          note: note || null,
          crmBidRefCode: crmResponse.referenceCode,
          sentToCrm: true,
        },
      });
    }

    res.status(201).json({
      success: true,
      referenceCode: crmResponse.referenceCode,
      crmBidId: crmResponse.id,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to send bid to CRM";
    console.error("POST /api/bid-to-crm error:", message);
    res.status(502).json({ error: message });
  }
});
