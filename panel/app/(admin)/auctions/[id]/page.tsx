import { notFound } from "next/navigation";
import Link from "next/link";
import { backendFetch } from "@/lib/api";
import { AuctionSerialized } from "@/lib/types";
import { formatPrice, formatDate } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft } from "lucide-react";
import { ImageCarousel } from "../../components/ImageCarousel";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function AuctionDetailPage({ params }: Props) {
  const { id } = await params;
  const auctionId = parseInt(id);
  if (isNaN(auctionId)) notFound();

  let auction: AuctionSerialized;
  try {
    auction = await backendFetch<AuctionSerialized>(`/api/auctions/${auctionId}`);
  } catch {
    notFound();
  }

  const allImages = auction.images || [];
  const carImages = allImages.filter((url: string) => !url.includes("_exb"));
  const exhibitSheetUrl = auction.exhibitSheet || allImages.find((url: string) => url.includes("_exb")) || null;
  const variant = auction.status === "upcoming" ? "default" as const : auction.status === "sold" ? "secondary" as const : "destructive" as const;

  const specs = [
    { label: "Chassis Code", value: auction.chassisCode },
    { label: "Engine", value: auction.engineSpecs },
    { label: "Mileage", value: auction.mileage },
    { label: "Color", value: auction.color },
    { label: "Rating", value: auction.rating },
    { label: "Year", value: auction.year },
    { label: "Inspection", value: auction.inspectionExpiry },
  ];

  const auctionInfo = [
    { label: "Lot Number", value: auction.lotNumber },
    { label: "Auction House", value: auction.auctionHouse },
    { label: "Location", value: auction.location },
    { label: "Auction Date", value: auction.auctionDate },
    { label: "First Seen", value: formatDate(auction.firstSeen) },
  ];

  return (
    <div className="space-y-4">
      <Link href="/auctions" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="h-4 w-4" /> Back
      </Link>

      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant={variant} className="capitalize text-xs">{auction.status}</Badge>
            <span className="font-mono text-xs text-muted-foreground">{auction.lotNumber}</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">{auction.maker} {auction.model}</h1>
          {auction.grade && <p className="text-sm text-muted-foreground mt-0.5">{auction.grade}</p>}
        </div>
        <div className="text-right">
          {auction.startPrice && (
            <p className="text-2xl font-bold">{formatPrice(Number(auction.startPrice))}</p>
          )}
          <p className="text-xs text-muted-foreground mt-1">
            {auction.auctionDate} · {auction.auctionHouse}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 space-y-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Car Photos</CardTitle></CardHeader>
            <CardContent className="pt-0">
              <ImageCarousel images={carImages} alt={`${auction.maker} ${auction.model}`} />
            </CardContent>
          </Card>
          {exhibitSheetUrl && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Auction Sheet</CardTitle></CardHeader>
              <CardContent className="pt-0">
                <ImageCarousel images={[exhibitSheetUrl]} alt="Auction sheet" />
              </CardContent>
            </Card>
          )}
        </div>

        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Specifications</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {specs.map((s) => (
                <div key={s.label} className="flex justify-between items-center">
                  <span className="text-xs text-muted-foreground">{s.label}</span>
                  <span className="text-sm font-medium">{s.value || "—"}</span>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Auction Info</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {auctionInfo.map((a) => (
                <div key={a.label} className="flex justify-between items-center">
                  <span className="text-xs text-muted-foreground">{a.label}</span>
                  <span className="text-sm font-medium">{a.value || "—"}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
