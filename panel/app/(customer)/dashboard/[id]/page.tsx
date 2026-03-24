import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/api";
import { AuctionSerialized } from "@/lib/types";
import { formatPrice } from "@/lib/format";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar, MapPin, Hash, Gauge, Palette, Star, Fuel, Shield, Clock } from "lucide-react";
import { VehicleNavigation } from "./VehicleNavigation";
import { StickyHeader } from "./StickyHeader";
import { MobileBottomBar } from "./MobileBottomBar";
import { ImageCarousel } from "../../../(admin)/components/ImageCarousel";
import { AddToListButton } from "../../components/AddToListButton";
import { SendForBiddingButton } from "../../components/SendForBiddingButton";

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
    <div className="max-w-[1400px] mx-auto space-y-5 pb-20 md:pb-0">

      {/* ──── Sticky Header (desktop, appears on scroll) ──── */}
      <StickyHeader
        auctionId={auction.id}
        title={`${auction.maker || ""} ${auction.model || "Vehicle"}`.trim()}
        price={auction.startPrice ? Number(auction.startPrice) : null}
      />

      {/* ──── Navigation Bar ──── */}
      <VehicleNavigation auctionId={auction.id} />

      {/* ──── Title Bar ──── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold tracking-tight text-zinc-50">
              {auction.maker} {auction.model}
            </h1>
            <Badge variant="outline" className="text-[9px] font-mono border-zinc-700 text-zinc-400">{auction.source?.toUpperCase()}</Badge>
          </div>
          {auction.grade && (
            <p className="text-sm text-zinc-500 mt-0.5">{auction.grade}</p>
          )}
        </div>

        <div className="text-right space-y-2 flex-shrink-0 pt-4">
          {auction.startPrice && (
            <p className="text-2xl font-mono font-bold text-blue-400">{formatPrice(Number(auction.startPrice))}</p>
          )}
          <div className="flex items-center gap-2 justify-end">
            <AddToListButton auctionId={auction.id} />
            <SendForBiddingButton auctionId={auction.id} />
          </div>
        </div>
      </div>

      {/* ──── Quick Specs Strip ──── */}
      <div className="flex flex-wrap gap-1.5">
        {auction.year && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-zinc-700 bg-zinc-800/50 text-xs text-zinc-300">
            <Calendar className="h-3 w-3 text-zinc-500" />
            {auction.year}
          </span>
        )}
        {auction.mileage && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-zinc-700 bg-zinc-800/50 text-xs text-zinc-300">
            <Gauge className="h-3 w-3 text-zinc-500" />
            {auction.mileage}
          </span>
        )}
        {auction.color && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-zinc-700 bg-zinc-800/50 text-xs text-zinc-300">
            <Palette className="h-3 w-3 text-zinc-500" />
            {auction.color}
          </span>
        )}
        {auction.rating && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-blue-500/30 bg-blue-500/10 text-xs font-mono font-bold text-blue-400">
            <Star className="h-3 w-3" />
            {auction.rating}
          </span>
        )}
        {auction.engineSpecs && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-zinc-700 bg-zinc-800/50 text-xs text-zinc-300">
            <Fuel className="h-3 w-3 text-zinc-500" />
            {auction.engineSpecs}
          </span>
        )}
      </div>

      {/* ──── Car Photos ──── */}
      <div className="bg-zinc-900 border border-zinc-800 rounded overflow-hidden p-3">
        <div className="max-w-[600px] mx-auto">
          <ImageCarousel images={carImages} alt={`${auction.maker} ${auction.model}`} />
        </div>
      </div>

      {/* ──── Two-Column: Auction Sheet + Details ──── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

        {/* Auction Sheet — wider */}
        <div className="lg:col-span-3">
          <div className="bg-zinc-900 border border-zinc-800 rounded p-4">
            <h2 className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500 mb-3">
              Inspection Sheet
            </h2>
            {exhibitSheetUrl ? (
              <ImageCarousel images={[exhibitSheetUrl]} alt="Auction sheet" />
            ) : (
              <div className="aspect-[4/3] rounded bg-zinc-800/50 border border-dashed border-zinc-700 flex items-center justify-center">
                <div className="text-center">
                  <Shield className="h-6 w-6 mx-auto text-zinc-700 mb-2" />
                  <p className="text-xs text-zinc-600">Not available</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Vehicle + Auction Info */}
        <div className="lg:col-span-2 space-y-3">

          {/* Specifications */}
          <div className="bg-zinc-900 border border-zinc-800 rounded p-4">
            <h2 className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500 mb-3">
              Specifications
            </h2>
            <div className="divide-y divide-zinc-800">
              {[
                { icon: Calendar, label: "Year", value: auction.year },
                { icon: Gauge, label: "Mileage", value: auction.mileage },
                { icon: Palette, label: "Color", value: auction.color },
                { icon: Star, label: "Rating", value: auction.rating },
                { icon: Fuel, label: "Engine", value: auction.engineSpecs },
                { icon: Shield, label: "Chassis", value: auction.chassisCode },
                { icon: Clock, label: "Inspection", value: auction.inspectionExpiry },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between py-2">
                  <span className="flex items-center gap-2 text-xs text-zinc-500">
                    <item.icon className="h-3 w-3" />
                    {item.label}
                  </span>
                  <span className="text-xs font-medium text-zinc-200">{item.value || "—"}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Auction Details */}
          <div className="bg-zinc-900 border border-zinc-800 rounded p-4">
            <h2 className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500 mb-3">
              Auction Info
            </h2>
            <div className="divide-y divide-zinc-800">
              {[
                { icon: Hash, label: "Lot No.", value: auction.lotNumber },
                { icon: Shield, label: "House", value: auction.auctionHouse },
                { icon: MapPin, label: "Location", value: auction.location },
                { icon: Calendar, label: "Date", value: auction.auctionDate },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between py-2">
                  <span className="flex items-center gap-2 text-xs text-zinc-500">
                    <item.icon className="h-3 w-3" />
                    {item.label}
                  </span>
                  <span className="text-xs font-medium text-zinc-200 text-right max-w-[55%]">{item.value || "—"}</span>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>

      {/* ──── Mobile Bottom Bar (prev/next) ──── */}
      <MobileBottomBar auctionId={auction.id} />
    </div>
  );
}
