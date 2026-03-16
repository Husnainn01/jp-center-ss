import { AuctionSerialized, SyncLogSerialized } from "./types";

/**
 * These functions are kept for backward compatibility but with the backend
 * separation, they're mainly used by components that receive pre-serialized data.
 * The backend handles the actual Prisma→JSON serialization now.
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function serializeAuction(auction: any): AuctionSerialized {
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
    startPrice: typeof auction.startPrice === "object" ? auction.startPrice?.toString() ?? null : auction.startPrice ?? null,
    auctionDate: auction.auctionDate,
    auctionHouse: auction.auctionHouse,
    location: auction.location,
    status: auction.status,
    source: auction.source,
    imageUrl: auction.imageUrl,
    images: auction.images ?? null,
    exhibitSheet: auction.exhibitSheet,
    inspectionExpiry: auction.inspectionExpiry,
    firstSeen: typeof auction.firstSeen === "string" ? auction.firstSeen : auction.firstSeen?.toISOString?.() ?? "",
    lastUpdated: typeof auction.lastUpdated === "string" ? auction.lastUpdated : auction.lastUpdated?.toISOString?.() ?? "",
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function serializeSyncLog(log: any): SyncLogSerialized {
  return {
    id: log.id,
    runAt: typeof log.runAt === "string" ? log.runAt : log.runAt?.toISOString?.() ?? "",
    newCount: log.newCount,
    updatedCount: log.updatedCount,
    expiredCount: log.expiredCount,
    totalScraped: log.totalScraped,
    error: log.error,
    durationMs: log.durationMs,
  };
}
