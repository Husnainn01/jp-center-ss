"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AuctionSerialized } from "@/lib/types";
import { formatPrice } from "@/lib/format";
import { proxyUrl } from "@/lib/image";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, Trash2, Calendar } from "lucide-react";
import { SendForBiddingButton, BulkSendForBidding } from "../../components/SendForBiddingButton";

interface ListItem {
  id: number;
  auctionId: number;
  note: string | null;
  addedAt: string;
  auction: AuctionSerialized | null;
}

interface ListDetail {
  id: number;
  name: string;
  createdAt: string;
  items: ListItem[];
}

export default function ListDetailPage() {
  const params = useParams();
  const [list, setList] = useState<ListDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/lists/${params.id}`)
      .then(r => r.json())
      .then(setList)
      .finally(() => setLoading(false));
  }, [params.id]);

  async function removeItem(auctionId: number) {
    await fetch(`/api/lists/${params.id}/items`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auctionId }),
    });
    setList(prev => prev ? { ...prev, items: prev.items.filter(i => i.auctionId !== auctionId) } : null);
  }

  if (loading) return <div className="text-center py-10 text-muted-foreground text-sm">Loading...</div>;
  if (!list) return <div className="text-center py-10 text-muted-foreground">List not found</div>;

  const allAuctionIds = list.items.map(i => i.auctionId).filter(Boolean);

  // Group items by date added
  const grouped = list.items.reduce<Record<string, ListItem[]>>((acc, item) => {
    const d = new Date(item.addedAt);
    const key = d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    (acc[key] ||= []).push(item);
    return acc;
  }, {});

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Link href="/lists" className="text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{list.name}</h1>
          <p className="text-sm text-muted-foreground">
            {list.items.length} vehicles · Created {new Date(list.createdAt).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
          </p>
        </div>
        {/* Bulk send for bidding */}
        {allAuctionIds.length > 0 && (
          <BulkSendForBidding auctionIds={allAuctionIds} />
        )}
      </div>

      {list.items.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <p className="text-muted-foreground">This list is empty</p>
            <Link href="/dashboard">
              <Button variant="outline" size="sm" className="mt-3">Browse upcoming auctions</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        Object.entries(grouped).map(([date, items]) => (
          <div key={date} className="space-y-2">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Calendar className="h-3 w-3" />
              <span>Added {date}</span>
              <Badge variant="secondary" className="text-[10px]">{items.length}</Badge>
            </div>
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">Image</TableHead>
                      <TableHead>Vehicle</TableHead>
                      <TableHead>Rating</TableHead>
                      <TableHead className="text-right">Price</TableHead>
                      <TableHead>Auction</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map(item => {
                      const a = item.auction;
                      if (!a) return null;
                      return (
                        <TableRow key={item.id}>
                          <TableCell className="py-2">
                            {a.imageUrl ? (
                              /* eslint-disable-next-line @next/next/no-img-element */
                              <img src={proxyUrl(a.imageUrl)} alt="" className="h-10 w-16 rounded object-cover bg-muted" loading="lazy" />
                            ) : (
                              <div className="h-10 w-16 rounded bg-muted" />
                            )}
                          </TableCell>
                          <TableCell>
                            <Link href={`/dashboard/${a.id}`} className="font-medium hover:text-primary transition-colors">
                              {a.maker} {a.model}
                            </Link>
                            {a.grade && <p className="text-[11px] text-muted-foreground truncate max-w-[200px]">{a.grade}</p>}
                          </TableCell>
                          <TableCell className="text-xs">{a.rating || "—"}</TableCell>
                          <TableCell className="text-right font-mono text-xs font-medium">
                            {a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}
                          </TableCell>
                          <TableCell>
                            <div className="text-xs">{a.auctionDate}</div>
                            <div className="text-[11px] text-muted-foreground">{a.location}</div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-[10px]">{a.source?.toUpperCase()}</Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <SendForBiddingButton auctionId={a.id} variant="compact" />
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeItem(a.id)}>
                                <Trash2 className="h-3 w-3 text-muted-foreground" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        ))
      )}
    </div>
  );
}
