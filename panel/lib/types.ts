export interface AuctionSerialized {
  id: number;
  itemId: string;
  lotNumber: string;
  maker: string;
  model: string;
  grade: string | null;
  chassisCode: string | null;
  engineSpecs: string | null;
  year: string | null;
  mileage: string | null;
  color: string | null;
  rating: string | null;
  startPrice: string | null;
  auctionDate: string;
  auctionHouse: string;
  location: string;
  status: string;
  source: string;
  imageUrl: string | null;
  images: string[] | null;
  exhibitSheet: string | null;
  inspectionExpiry: string | null;
  firstSeen: string;
  lastUpdated: string;
}

export interface AuctionsResponse {
  auctions: AuctionSerialized[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface DashboardStats {
  totalActive: number;
  endingSoon: number;
  recentlyAdded: number;
  totalExpired: number;
  lastSyncAt: string | null;
}

export interface FilterState {
  search: string;
  maker: string;
  location: string;
  status: string;
  minPrice: string;
  maxPrice: string;
  sort: string;
  order: "asc" | "desc";
  page: number;
}

export interface SyncLogSerialized {
  id: number;
  runAt: string;
  newCount: number;
  updatedCount: number;
  expiredCount: number;
  totalScraped: number;
  error: string | null;
  durationMs: number | null;
}
