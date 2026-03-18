import { notFound } from "next/navigation";
import Link from "next/link";
import { backendFetch } from "@/lib/api";
import { AuctionSerialized } from "@/lib/types";
import { formatPrice } from "@/lib/format";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft } from "lucide-react";
import { ImageCarousel } from "../../../(admin)/components/ImageCarousel";
import { AddToListButton } from "../../components/AddToListButton";
import { SendForBiddingButton } from "../../components/SendForBiddingButton";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function CustomerVehicleDetail({ params }: Props) {
  const { id } = await params;
  const auctionId = parseInt(id);
  if (isNaN(auctionId)) notFound();

  let auction: AuctionSerialized;
  try {
    auction = await backendFetch<AuctionSerialized>(`/api/auctions/${auctionId}`);
  } catch {
    notFound();
  }

  if (auction.status !== "upcoming") notFound();

  const allImages = auction.images || [];
  const carImages = allImages.filter((url: string) => !url.includes("_exb") && !url.includes("_scan"));
  const exhibitSheetUrl = auction.exhibitSheet || allImages.find((url: string) => url.includes("_exb") || url.includes("_scan")) || null;

  const specs = [
    { label: "Year", value: auction.year },
    { label: "Mileage", value: auction.mileage },
    { label: "Color", value: auction.color },
    { label: "Rating", value: auction.rating },
    { label: "Engine", value: auction.engineSpecs },
    { label: "Chassis", value: auction.chassisCode },
    { label: "Inspection", value: auction.inspectionExpiry },
  ];

  const auctionInfo = [
    { label: "Lot No.", value: auction.lotNumber },
    { label: "Auction", value: auction.auctionHouse },
    { label: "Location", value: auction.location },
    { label: "Date", value: auction.auctionDate },
    { label: "Source", value: auction.source?.toUpperCase() },
  ];

  return (
    <div className="space-y-3 max-w-[1400px]">
      {/* Header row */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 min-w-0">
          <Link href="/dashboard" className="p-1 rounded hover:bg-accent transition-colors flex-shrink-0">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <h1 className="text-base font-bold tracking-tight truncate">{auction.maker} {auction.model}</h1>
          <Badge variant="outline" className="text-[9px] flex-shrink-0">{auction.source?.toUpperCase()}</Badge>
          {auction.grade && <span className="text-xs text-muted-foreground hidden sm:inline">· {auction.grade}</span>}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {auction.startPrice && (
            <span className="text-base font-bold">{formatPrice(Number(auction.startPrice))}</span>
          )}
          <AddToListButton auctionId={auction.id} />
          <SendForBiddingButton auctionId={auction.id} />
        </div>
      </div>

      {/* All in one row: Car Photos | Auction Sheet | Specs | Auction Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        {/* Car Photos — smaller */}
        <Card className="xl:col-span-1">
          <CardContent className="p-2">
            <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">Car Photos</p>
            <ImageCarousel images={carImages} alt={`${auction.maker} ${auction.model}`} />
          </CardContent>
        </Card>

        {/* Auction Sheet */}
        <Card className="xl:col-span-1">
          <CardContent className="p-2">
            <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">Auction Sheet</p>
            {exhibitSheetUrl ? (
              <ImageCarousel images={[exhibitSheetUrl]} alt="Auction sheet" />
            ) : (
              <div className="aspect-[4/3] rounded bg-muted flex items-center justify-center">
                <span className="text-[10px] text-muted-foreground">Not available</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Specifications */}
        <Card className="xl:col-span-1">
          <CardContent className="p-2">
            <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">Specifications</p>
            <div>
              {specs.map((s) => (
                <div key={s.label} className="flex justify-between items-center py-[5px] border-b border-border/40 last:border-0">
                  <span className="text-[10px] text-muted-foreground">{s.label}</span>
                  <span className="text-[11px] font-medium">{s.value || "—"}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Auction Details */}
        <Card className="xl:col-span-1">
          <CardContent className="p-2">
            <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">Auction Details</p>
            <div>
              {auctionInfo.map((a) => (
                <div key={a.label} className="flex justify-between items-center py-[5px] border-b border-border/40 last:border-0">
                  <span className="text-[10px] text-muted-foreground">{a.label}</span>
                  <span className="text-[11px] font-medium text-right max-w-[60%] truncate">{a.value || "—"}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
