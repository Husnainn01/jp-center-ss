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
    <div className="space-y-3 max-w-[1200px]">
      {/* Back + title row */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <Link href="/dashboard" className="p-1 rounded hover:bg-accent transition-colors flex-shrink-0">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight truncate">{auction.maker} {auction.model}</h1>
              <Badge variant="outline" className="text-[9px] flex-shrink-0">{auction.source?.toUpperCase()}</Badge>
            </div>
            <p className="text-xs text-muted-foreground truncate">
              {auction.grade && `${auction.grade} · `}{auction.auctionHouse} · {auction.auctionDate}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {auction.startPrice && (
            <span className="text-lg font-bold">{formatPrice(Number(auction.startPrice))}</span>
          )}
          <AddToListButton auctionId={auction.id} />
          <SendForBiddingButton auctionId={auction.id} />
        </div>
      </div>

      {/* Content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Images */}
        <div className="lg:col-span-2 space-y-3">
          <Card>
            <CardContent className="p-3">
              <ImageCarousel images={carImages} alt={`${auction.maker} ${auction.model}`} />
            </CardContent>
          </Card>
          {exhibitSheetUrl && (
            <Card>
              <CardContent className="p-3">
                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-2">Auction Sheet</p>
                <ImageCarousel images={[exhibitSheetUrl]} alt="Auction sheet" />
              </CardContent>
            </Card>
          )}
        </div>

        {/* Specs + Info */}
        <div className="space-y-3">
          <Card>
            <CardContent className="p-3">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-2">Specifications</p>
              <div className="space-y-0">
                {specs.map((s) => (
                  <div key={s.label} className="flex justify-between items-center py-1.5 border-b border-border/50 last:border-0">
                    <span className="text-[11px] text-muted-foreground">{s.label}</span>
                    <span className="text-[11px] font-medium text-right">{s.value || "—"}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-3">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-2">Auction Details</p>
              <div className="space-y-0">
                {auctionInfo.map((a) => (
                  <div key={a.label} className="flex justify-between items-center py-1.5 border-b border-border/50 last:border-0">
                    <span className="text-[11px] text-muted-foreground">{a.label}</span>
                    <span className="text-[11px] font-medium text-right">{a.value || "—"}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
