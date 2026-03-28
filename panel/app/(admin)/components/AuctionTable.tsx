"use client";

import Link from "next/link";
import Image from "next/image";
import { AuctionSerialized } from "@/lib/types";
import { formatPrice } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { proxyUrl } from "@/lib/image";

interface AuctionTableProps {
  auctions: AuctionSerialized[];
  compact?: boolean;
}

function statusVariant(status: string) {
  switch (status) {
    case "upcoming": return "default" as const;
    case "sold": return "secondary" as const;
    case "expired": return "destructive" as const;
    default: return "outline" as const;
  }
}

export function AuctionTable({ auctions, compact = false }: AuctionTableProps) {
  if (auctions.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground text-sm">
        No auctions found
      </div>
    );
  }

  if (compact) {
    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Vehicle</TableHead>
            <TableHead>Rating</TableHead>
            <TableHead className="text-right">Price</TableHead>
            <TableHead>Auction</TableHead>
            <TableHead className="text-right">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {auctions.map((a) => (
            <TableRow key={a.id}>
              <TableCell className="py-2 max-w-[180px]">
                <Link href={`/auctions/${a.id}`} className="font-medium hover:text-primary transition-colors truncate block">
                  {`${a.maker} ${a.model}`.slice(0, 24)}{`${a.maker} ${a.model}`.length > 24 ? "…" : ""}
                </Link>
              </TableCell>
              <TableCell className="py-2 text-xs text-muted-foreground">{a.rating || "—"}</TableCell>
              <TableCell className="py-2 text-right font-mono text-xs">
                {a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}
              </TableCell>
              <TableCell className="py-2">
                <div className="text-xs">{a.auctionDate}</div>
                <div className="text-[11px] text-muted-foreground">{a.location}</div>
              </TableCell>
              <TableCell className="py-2 text-right">
                <Badge variant={statusVariant(a.status)} className="text-[10px] capitalize whitespace-nowrap">
                  {a.status}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-16">Image</TableHead>
          <TableHead>Vehicle</TableHead>
          <TableHead>Year</TableHead>
          <TableHead>Color</TableHead>
          <TableHead>Rating</TableHead>
          <TableHead className="text-right">Price</TableHead>
          <TableHead>Auction</TableHead>
          <TableHead className="text-right">Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {auctions.map((a) => (
          <TableRow key={a.id} className="group">
            <TableCell className="py-2">
              {a.imageUrl ? (
                <Image src={proxyUrl(a.imageUrl)} alt="" width={64} height={40} className="h-10 w-16 rounded object-cover bg-muted" />
              ) : (
                <div className="h-10 w-16 rounded bg-muted" />
              )}
            </TableCell>
            <TableCell className="py-2">
              <Link href={`/auctions/${a.id}`} className="font-medium group-hover:text-primary transition-colors">
                {a.maker} {a.model}
              </Link>
              {a.grade && (
                <p className="text-[11px] text-muted-foreground truncate max-w-[220px]">{a.grade}</p>
              )}
            </TableCell>
            <TableCell className="text-xs text-muted-foreground">{a.year || "—"}</TableCell>
            <TableCell className="text-xs text-muted-foreground">{a.color || "—"}</TableCell>
            <TableCell className="text-xs font-medium">{a.rating || "—"}</TableCell>
            <TableCell className="text-right font-mono text-xs font-medium">
              {a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}
            </TableCell>
            <TableCell>
              <div className="text-xs">{a.auctionDate}</div>
              <div className="text-[11px] text-muted-foreground">{a.location}</div>
            </TableCell>
            <TableCell className="text-right">
              <Badge variant={statusVariant(a.status)} className="text-[10px] capitalize whitespace-nowrap">
                {a.status}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
