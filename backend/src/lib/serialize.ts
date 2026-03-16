import type { Auction, SyncLog } from "../generated/prisma/client.js";

export function serializeAuction(auction: Auction) {
  return {
    id: auction.id,
    itemId: auction.itemId,
    lotNumber: auction.lotNumber,
    maker: auction.maker,
    model: auction.model,
    grade: auction.grade,
    chassisCode: auction.chassisCode,
    engineSpecs: auction.engineSpecs,
    year: auction.year,
    mileage: auction.mileage,
    color: auction.color,
    rating: auction.rating,
    startPrice: auction.startPrice?.toString() ?? null,
    auctionDate: auction.auctionDate,
    auctionHouse: auction.auctionHouse,
    location: auction.location,
    status: auction.status,
    source: auction.source,
    imageUrl: auction.imageUrl,
    images: auction.images,
    exhibitSheet: auction.exhibitSheet,
    inspectionExpiry: auction.inspectionExpiry,
    firstSeen: auction.firstSeen.toISOString(),
    lastUpdated: auction.lastUpdated.toISOString(),
  };
}

export function serializeSyncLog(log: SyncLog) {
  return {
    id: log.id,
    runAt: log.runAt.toISOString(),
    newCount: log.newCount,
    updatedCount: log.updatedCount,
    expiredCount: log.expiredCount,
    totalScraped: log.totalScraped,
    source: log.source,
    error: log.error,
    durationMs: log.durationMs,
  };
}
