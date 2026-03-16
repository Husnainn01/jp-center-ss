const CRM_API_URL = process.env.CRM_API_URL || "http://localhost:5000";

interface CrmBidPayload {
  customerId: string;
  auctionHouse: string;
  lotNumber: string;
  maker: string;
  model: string;
  year: string;
  color: string;
  maxBidPrice: number | null;
  bidDate: string;
  exhibitSheetUrl: string | null;
  vehicleImages: string[];
  chassisCode: string | null;
  mileage: string | null;
  rating: string | null;
  startPrice: number | null;
  auctionSource: string;
  note?: string;
}

interface CrmBidResponse {
  id: string;
  referenceCode: string;
}

async function crmFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${CRM_API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`CRM API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function crmCreateBid(payload: CrmBidPayload, crmToken: string): Promise<CrmBidResponse> {
  return crmFetch<CrmBidResponse>("/api/bids", {
    method: "POST",
    headers: { Authorization: `Bearer ${crmToken}` },
    body: JSON.stringify(payload),
  });
}

export type { CrmBidPayload, CrmBidResponse };
