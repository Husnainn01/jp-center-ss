import { notFound } from "next/navigation";
import Link from "next/link";
import { backendFetch } from "@/lib/api";
import { AuctionSerialized } from "@/lib/types";
import { formatPrice } from "@/lib/format";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Calendar, MapPin, Hash, Gauge, Palette, Star, Fuel, Shield, Clock } from "lucide-react";
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

  return (
    <div className="max-w-[1400px] mx-auto space-y-5">

      {/* ──── Navigation + Title Bar ──── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-3"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to listings
          </Link>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold tracking-tight">
              {auction.maker} {auction.model}
            </h1>
            <Badge variant="outline" className="text-[10px] font-mono">{auction.source?.toUpperCase()}</Badge>
          </div>
          {auction.grade && (
            <p className="text-sm text-muted-foreground mt-0.5">{auction.grade}</p>
          )}
        </div>

        <div className="text-right space-y-2 flex-shrink-0 pt-6">
          {auction.startPrice && (
            <p className="text-2xl font-bold tracking-tight">{formatPrice(Number(auction.startPrice))}</p>
          )}
          <div className="flex items-center gap-2 justify-end">
            <AddToListButton auctionId={auction.id} />
            <SendForBiddingButton auctionId={auction.id} />
          </div>
        </div>
      </div>

      {/* ──── Quick Specs Strip ──── */}
      <div className="flex flex-wrap gap-2">
        {auction.year && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-muted text-xs font-medium">
            <Calendar className="h-3 w-3 text-muted-foreground" />
            {auction.year}
          </span>
        )}
        {auction.mileage && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-muted text-xs font-medium">
            <Gauge className="h-3 w-3 text-muted-foreground" />
            {auction.mileage}
          </span>
        )}
        {auction.color && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-muted text-xs font-medium">
            <Palette className="h-3 w-3 text-muted-foreground" />
            {auction.color}
          </span>
        )}
        {auction.rating && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-foreground text-background text-xs font-bold">
            <Star className="h-3 w-3" />
            {auction.rating}
          </span>
        )}
        {auction.engineSpecs && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-muted text-xs font-medium">
            <Fuel className="h-3 w-3 text-muted-foreground" />
            {auction.engineSpecs}
          </span>
        )}
      </div>

      {/* ──── Car Photos ──── */}
      <Card className="overflow-hidden">
        <CardContent className="p-3">
          <div className="max-w-[600px] mx-auto">
            <ImageCarousel images={carImages} alt={`${auction.maker} ${auction.model}`} />
          </div>
        </CardContent>
      </Card>

      {/* ──── Two-Column: Auction Sheet + Details ──── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">

        {/* Auction Sheet — wider */}
        <div className="lg:col-span-3">
          <Card>
            <CardContent className="p-4">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Auction Inspection Sheet
              </h2>
              {exhibitSheetUrl ? (
                <ImageCarousel images={[exhibitSheetUrl]} alt="Auction sheet" />
              ) : (
                <div className="aspect-[4/3] rounded-lg bg-muted/50 border-2 border-dashed border-border flex items-center justify-center">
                  <div className="text-center">
                    <Shield className="h-8 w-8 mx-auto text-muted-foreground/30 mb-2" />
                    <p className="text-sm text-muted-foreground">Inspection sheet not available</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Vehicle + Auction Info */}
        <div className="lg:col-span-2 space-y-4">

          {/* Specifications */}
          <Card>
            <CardContent className="p-4">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Vehicle Specifications
              </h2>
              <div className="divide-y divide-border/60">
                {[
                  { icon: Calendar, label: "Year", value: auction.year },
                  { icon: Gauge, label: "Mileage", value: auction.mileage },
                  { icon: Palette, label: "Color", value: auction.color },
                  { icon: Star, label: "Rating", value: auction.rating },
                  { icon: Fuel, label: "Engine", value: auction.engineSpecs },
                  { icon: Shield, label: "Chassis Code", value: auction.chassisCode },
                  { icon: Clock, label: "Inspection Expiry", value: auction.inspectionExpiry },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between py-2.5">
                    <span className="flex items-center gap-2 text-sm text-muted-foreground">
                      <item.icon className="h-3.5 w-3.5" />
                      {item.label}
                    </span>
                    <span className="text-sm font-medium">{item.value || "—"}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Auction Details */}
          <Card>
            <CardContent className="p-4">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Auction Details
              </h2>
              <div className="divide-y divide-border/60">
                {[
                  { icon: Hash, label: "Lot Number", value: auction.lotNumber },
                  { icon: Shield, label: "Auction House", value: auction.auctionHouse },
                  { icon: MapPin, label: "Location", value: auction.location },
                  { icon: Calendar, label: "Auction Date", value: auction.auctionDate },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between py-2.5">
                    <span className="flex items-center gap-2 text-sm text-muted-foreground">
                      <item.icon className="h-3.5 w-3.5" />
                      {item.label}
                    </span>
                    <span className="text-sm font-medium text-right max-w-[55%]">{item.value || "—"}</span>
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
