import Link from "next/link";
import { backendFetch } from "@/lib/api";
import { AuctionSerialized } from "@/lib/types";
import { timeAgo } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Car, Clock, TrendingUp, XCircle, RefreshCw, ArrowRight, Database } from "lucide-react";

export const dynamic = "force-dynamic";

interface StatsResponse {
  totalUpcoming: number;
  totalSold: number;
  recentlyAdded: number;
  totalExpired: number;
  totalAll: number;
  lastSyncAt: string | null;
  lastSyncTotal: number;
  sourceCounts: { source: string; _count: number }[];
}

export default async function AdminDashboard() {
  const [statsData, recentData] = await Promise.all([
    backendFetch<StatsResponse>("/api/stats?extended=true"),
    backendFetch<{ auctions: AuctionSerialized[] }>("/api/auctions?sort=firstSeen&order=desc&pageSize=10"),
  ]);

  const stats = [
    { label: "Total Listings", value: statsData.totalAll, icon: Database, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "Upcoming", value: statsData.totalUpcoming, icon: Clock, color: "text-emerald-600", bg: "bg-emerald-50" },
    { label: "Added Today", value: statsData.recentlyAdded, icon: TrendingUp, color: "text-amber-600", bg: "bg-amber-50" },
    { label: "Expired", value: statsData.totalExpired, icon: XCircle, color: "text-red-500", bg: "bg-red-50" },
  ];

  const sourceCounts = statsData.sourceCounts || [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {statsData.lastSyncAt ? (
              <span className="flex items-center gap-1"><RefreshCw className="h-3 w-3" /> Synced {timeAgo(statsData.lastSyncAt)}</span>
            ) : "No sync data"}
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {stats.map(s => (
          <Card key={s.label}>
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-medium text-muted-foreground">{s.label}</p>
                <p className="text-2xl font-bold mt-0.5">{s.value.toLocaleString()}</p>
              </div>
              <div className={`h-9 w-9 rounded-lg ${s.bg} flex items-center justify-center`}>
                <s.icon className={`h-4 w-4 ${s.color}`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Source breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {sourceCounts.map(s => (
          <Card key={s.source}>
            <CardContent className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Badge variant="outline" className="text-xs font-bold">{s.source.toUpperCase()}</Badge>
                <span className="text-sm font-medium">{s._count.toLocaleString()} vehicles</span>
              </div>
              <Link href={`/auctions?source=${s.source}`} className="text-xs text-primary hover:underline flex items-center gap-0.5">
                View <ArrowRight className="h-3 w-3" />
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Recent */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">Recently Added</CardTitle>
            <Link href="/auctions?sort=firstSeen&order=desc" className="text-xs text-primary hover:underline flex items-center gap-0.5">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="text-[11px]">
                <TableHead>Vehicle</TableHead>
                <TableHead>Year</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead>Auction</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentData.auctions.map(a => (
                <TableRow key={a.id} className="text-xs">
                  <TableCell className="py-1.5">
                    <Link href={`/auctions/${a.id}`} className="font-medium hover:text-primary">{a.maker} {a.model}</Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{a.year || "—"}</TableCell>
                  <TableCell className="text-right font-mono">{a.startPrice ? `¥${Number(a.startPrice).toLocaleString()}` : "—"}</TableCell>
                  <TableCell>
                    <div>{a.auctionDate}</div>
                    <div className="text-[10px] text-muted-foreground">{a.location}</div>
                  </TableCell>
                  <TableCell><Badge variant="outline" className="text-[9px]">{a.source.toUpperCase()}</Badge></TableCell>
                  <TableCell>
                    <Badge variant={a.status === "upcoming" ? "default" : a.status === "sold" ? "secondary" : "destructive"} className="text-[9px] capitalize">{a.status}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
