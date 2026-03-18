import { backendFetch } from "@/lib/api";
import { AuctionSerialized } from "@/lib/types";
import { CustomerAuctions } from "./CustomerAuctions";

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
  sourceCounts: Record<string, number>;
  filterOptions: {
    makers: { value: string; count: number }[];
    locations: { value: string; count: number }[];
    auctionHouses: { value: string; count: number }[];
  };
}

export default async function CustomerDashboard({ searchParams }: Props) {
  const sp = await searchParams;
  const page = Math.max(1, parseInt(sp.page || "1"));

  // Build query string for the backend
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("pageSize", "40");
  params.set("includeMeta", "true");
  if (!sp.status) params.set("status", "upcoming");

  const passthrough = ["maker", "model", "location", "auctionHouse", "source", "search", "sort", "order", "minPrice", "maxPrice", "rating", "yearFrom", "yearTo", "auctionDay"];
  for (const key of passthrough) {
    if (sp[key]) params.set(key, sp[key]!);
  }
  if (!sp.sort) params.set("sort", "firstSeen");
  if (!sp.order) params.set("order", "desc");

  const data = await backendFetch<AuctionsResponse>(`/api/auctions?${params}`);

  return (
    <CustomerAuctions
      auctions={data.auctions}
      page={data.page}
      totalPages={data.totalPages}
      total={data.total}
      sourceCounts={data.sourceCounts || {}}
      filterOptions={data.filterOptions || { makers: [], locations: [], auctionHouses: [] }}
    />
  );
}
