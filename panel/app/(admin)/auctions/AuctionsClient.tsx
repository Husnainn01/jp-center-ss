"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { AuctionSerialized } from "@/lib/types";
import { formatPrice } from "@/lib/format";
import { proxyUrl } from "@/lib/image";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import { Search, ArrowUpDown, ChevronLeft, ChevronRight, SlidersHorizontal, X, Download } from "lucide-react";

interface FilterOption { value: string; count: number }
interface Props {
  auctions: AuctionSerialized[];
  page: number;
  totalPages: number;
  total: number;
  filterOptions: {
    makers: FilterOption[];
    locations: FilterOption[];
    auctionHouses: FilterOption[];
    sources: FilterOption[];
    statuses: FilterOption[];
  };
}

function Content({ auctions, page, totalPages, total, filterOptions }: Props) {
  const router = useRouter();
  const sp = useSearchParams();
  const [showFilters, setShowFilters] = useState(true);
  const [models, setModels] = useState<FilterOption[]>([]);

  const get = useCallback((k: string) => sp.get(k) ?? "", [sp]);

  useEffect(() => {
    const maker = get("maker");
    if (maker) {
      fetch(`/api/filter-options?maker=${encodeURIComponent(maker)}`)
        .then(r => r.json())
        .then(d => setModels(d.models || []))
        .catch(() => setModels([]));
    } else {
      setModels([]);
    }
  }, [get]);

  function update(updates: Record<string, string>) {
    const params = new URLSearchParams(sp.toString());
    Object.entries(updates).forEach(([k, v]) => {
      if (v) params.set(k, v); else params.delete(k);
    });
    if ("maker" in updates && updates.maker !== get("maker")) params.delete("model");
    params.delete("page");
    router.push(`/auctions?${params.toString()}`);
  }
  function clearAll() { router.push("/auctions"); }
  function goPage(p: number) {
    const params = new URLSearchParams(sp.toString());
    params.set("page", String(p));
    router.push(`/auctions?${params.toString()}`);
  }

  const sel = "h-8 rounded-md border border-input bg-background px-2 text-xs w-full focus:outline-none focus:ring-2 focus:ring-ring/30";
  const activeFilters = ["maker","model","location","auctionHouse","source","status","minPrice","maxPrice","yearFrom","yearTo","search"].filter(k => get(k)).length;

  function statusVariant(s: string) {
    return s === "upcoming" ? "default" as const : s === "sold" ? "secondary" as const : "destructive" as const;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">All Auctions</h1>
          <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{total.toLocaleString()}</span> vehicles
            {activeFilters > 0 && (
              <>
                <span>·</span>
                <button onClick={clearAll} className="text-primary hover:underline">{activeFilters} filter{activeFilters > 1 ? "s" : ""} active</button>
              </>
            )}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => setShowFilters(!showFilters)}>
          <SlidersHorizontal className="h-3.5 w-3.5 mr-1.5" />
          {showFilters ? "Hide" : "Show"} Filters
          {activeFilters > 0 && <Badge variant="default" className="ml-1.5 h-4 min-w-4 p-0 flex items-center justify-center text-[10px] rounded-full">{activeFilters}</Badge>}
        </Button>
      </div>

      {/* Source + Status pills */}
      <div className="flex flex-wrap gap-1.5">
        <button onClick={() => update({ source: "" })} className={`px-2.5 py-1 rounded-full text-[11px] font-medium ${!get("source") ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}>
          All ({filterOptions.sources.reduce((a,b) => a + b.count, 0).toLocaleString()})
        </button>
        {filterOptions.sources.map(s => (
          <button key={s.value} onClick={() => update({ source: s.value })} className={`px-2.5 py-1 rounded-full text-[11px] font-medium ${get("source") === s.value ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}>
            {s.value.toUpperCase()} ({s.count.toLocaleString()})
          </button>
        ))}
        <Separator orientation="vertical" className="h-6 mx-1" />
        {filterOptions.statuses.map(s => (
          <button key={s.value} onClick={() => update({ status: get("status") === s.value ? "" : s.value })} className={`px-2.5 py-1 rounded-full text-[11px] font-medium capitalize ${get("status") === s.value ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}>
            {s.value} ({s.count.toLocaleString()})
          </button>
        ))}
      </div>

      {/* Filters */}
      {showFilters && (
        <Card className="border-dashed">
          <CardContent className="p-3">
            <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-8 gap-2">
              <div className="col-span-2 space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Search</label>
                <div className="relative">
                  <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                  <Input placeholder="Maker, model, lot..." defaultValue={get("search")} onChange={e => update({ search: e.target.value })} className="pl-7 h-8 text-xs" />
                </div>
              </div>
              <div className="space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Maker</label>
                <select value={get("maker")} onChange={e => update({ maker: e.target.value })} className={sel}>
                  <option value="">All</option>
                  {filterOptions.makers.map(m => <option key={m.value} value={m.value}>{m.value} ({m.count})</option>)}
                </select>
              </div>
              <div className="space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Model</label>
                {models.length > 0 ? (
                  <select value={get("model")} onChange={e => update({ model: e.target.value })} className={sel}>
                    <option value="">All</option>
                    {models.map(m => <option key={m.value} value={m.value}>{m.value} ({m.count})</option>)}
                  </select>
                ) : (
                  <Input placeholder={get("maker") ? "Loading..." : "Select maker"} disabled={!get("maker")} defaultValue={get("model")} onChange={e => update({ model: e.target.value })} className="h-8 text-xs" />
                )}
              </div>
              <div className="space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Auction</label>
                <select value={get("auctionHouse")} onChange={e => update({ auctionHouse: e.target.value })} className={sel}>
                  <option value="">All</option>
                  {filterOptions.auctionHouses.map(h => <option key={h.value} value={h.value}>{h.value}</option>)}
                </select>
              </div>
              <div className="space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Location</label>
                <select value={get("location")} onChange={e => update({ location: e.target.value })} className={sel}>
                  <option value="">All</option>
                  {filterOptions.locations.map(l => <option key={l.value} value={l.value}>{l.value} ({l.count})</option>)}
                </select>
              </div>
              <div className="space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Sort</label>
                <select value={get("sort") || "firstSeen"} onChange={e => update({ sort: e.target.value })} className={sel}>
                  <option value="firstSeen">Date Added</option>
                  <option value="auctionDate">Auction Date</option>
                  <option value="startPrice">Price</option>
                  <option value="maker">Maker</option>
                  <option value="year">Year</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-8 gap-2 mt-2">
              <div className="space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Year From</label>
                <Input placeholder="2020" defaultValue={get("yearFrom")} onChange={e => update({ yearFrom: e.target.value })} className="h-8 text-xs" />
              </div>
              <div className="space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Year To</label>
                <Input placeholder="2026" defaultValue={get("yearTo")} onChange={e => update({ yearTo: e.target.value })} className="h-8 text-xs" />
              </div>
              <div className="space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Min Price</label>
                <Input type="number" placeholder="¥0" defaultValue={get("minPrice")} onChange={e => update({ minPrice: e.target.value })} className="h-8 text-xs" />
              </div>
              <div className="space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Max Price</label>
                <Input type="number" placeholder="No limit" defaultValue={get("maxPrice")} onChange={e => update({ maxPrice: e.target.value })} className="h-8 text-xs" />
              </div>
              <div className="space-y-0.5">
                <label className="text-[10px] font-medium text-muted-foreground uppercase">Order</label>
                <button onClick={() => update({ order: get("order") === "asc" ? "desc" : "asc" })} className={`${sel} flex items-center gap-1 cursor-pointer`}>
                  <ArrowUpDown className="h-3 w-3" />
                  {(get("order") || "desc") === "desc" ? "Newest" : "Oldest"}
                </button>
              </div>
              {activeFilters > 0 && (
                <div className="space-y-0.5 col-span-2 flex items-end">
                  <Button variant="ghost" size="sm" className="h-8 text-xs w-full" onClick={clearAll}>
                    <X className="h-3 w-3 mr-1" /> Clear All Filters
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {auctions.length === 0 ? (
            <div className="py-16 text-center text-muted-foreground text-sm">No auctions found</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="text-[11px]">
                  <TableHead className="w-14">Img</TableHead>
                  <TableHead>Vehicle</TableHead>
                  <TableHead>Year</TableHead>
                  <TableHead>Rating</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead>Auction</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {auctions.map(a => (
                  <TableRow key={a.id} className="group text-xs">
                    <TableCell className="py-1.5">
                      {a.imageUrl ? (
                        <Image src={proxyUrl(a.imageUrl)} alt="" width={56} height={36} className="h-9 w-14 rounded object-cover bg-muted" />
                      ) : (
                        <div className="h-9 w-14 rounded bg-muted" />
                      )}
                    </TableCell>
                    <TableCell className="py-1.5">
                      <Link href={`/auctions/${a.id}`} className="font-medium group-hover:text-primary transition-colors">
                        {a.maker} {a.model}
                      </Link>
                      {a.grade && <p className="text-[10px] text-muted-foreground truncate max-w-[180px]">{a.grade}</p>}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{a.year || "—"}</TableCell>
                    <TableCell>{a.rating || "—"}</TableCell>
                    <TableCell className="text-right font-mono font-medium">
                      {a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}
                    </TableCell>
                    <TableCell>
                      <div>{a.auctionDate}</div>
                      <div className="text-[10px] text-muted-foreground">{a.location}</div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[9px]">{a.source?.toUpperCase()}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(a.status)} className="text-[9px] capitalize">{a.status}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t">
              <span className="text-xs text-muted-foreground">
                {(page - 1) * 25 + 1}–{Math.min(page * 25, total)} of {total.toLocaleString()}
              </span>
              <div className="flex items-center gap-1">
                <Button variant="outline" size="sm" className="h-7 text-xs" disabled={page <= 1} onClick={() => goPage(page - 1)}>
                  <ChevronLeft className="h-3.5 w-3.5 mr-0.5" /> Prev
                </Button>
                <span className="px-2 text-xs text-muted-foreground">{page}/{totalPages}</span>
                <Button variant="outline" size="sm" className="h-7 text-xs" disabled={page >= totalPages} onClick={() => goPage(page + 1)}>
                  Next <ChevronRight className="h-3.5 w-3.5 ml-0.5" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function AuctionsClient(props: Props) {
  return (
    <Suspense fallback={<div className="py-10 text-center text-muted-foreground text-sm">Loading...</div>}>
      <Content {...props} />
    </Suspense>
  );
}
