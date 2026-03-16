import { backendFetch } from "@/lib/api";
import { AuctionSerialized } from "@/lib/types";
import { AuctionsClient } from "./AuctionsClient";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | undefined>>;
}

interface AuctionsResponse {
  auctions: AuctionSerialized[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

interface FilterResponse {
  makers: { value: string; count: number }[];
  locations: { value: string; count: number }[];
  auctionHouses: { value: string; count: number }[];
  sources?: { value: string; count: number }[];
  statuses?: { value: string; count: number }[];
}

export default async function AuctionsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const page = Math.max(1, parseInt(sp.page || "1"));

  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("pageSize", "25");

  const passthrough = ["maker", "model", "location", "auctionHouse", "source", "status", "search", "sort", "order", "yearFrom", "yearTo", "minPrice", "maxPrice"];
  for (const key of passthrough) {
    if (sp[key]) params.set(key, sp[key]!);
  }
  if (!sp.sort) params.set("sort", "firstSeen");
  if (!sp.order) params.set("order", "desc");

  const [auctionData, filterData] = await Promise.all([
    backendFetch<AuctionsResponse>(`/api/auctions?${params}`),
    backendFetch<FilterResponse>("/api/filter-options?includeAll=true"),
  ]);

  return (
    <AuctionsClient
      auctions={auctionData.auctions}
      page={auctionData.page}
      totalPages={auctionData.totalPages}
      total={auctionData.total}
      filterOptions={{
        makers: filterData.makers,
        locations: filterData.locations,
        auctionHouses: filterData.auctionHouses,
        sources: filterData.sources || [],
        statuses: filterData.statuses || [],
      }}
    />
  );
}
