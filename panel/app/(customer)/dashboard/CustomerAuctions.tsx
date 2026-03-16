"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import Image from "next/image";
import { AuctionSerialized } from "@/lib/types";
import { formatPrice } from "@/lib/format";
import { proxyUrl } from "@/lib/image";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Search, ArrowUpDown, ChevronLeft, ChevronRight,
  SlidersHorizontal, X, Car, LayoutGrid, List,
} from "lucide-react";

interface FilterOption { value: string; count: number }
interface Props {
  auctions: AuctionSerialized[];
  page: number;
  totalPages: number;
  total: number;
  sourceCounts: Record<string, number>;
  filterOptions: {
    makers: FilterOption[];
    locations: FilterOption[];
    auctionHouses: FilterOption[];
  };
}

function Content({ auctions, page, totalPages, total, sourceCounts, filterOptions }: Props) {
  const router = useRouter();
  const sp = useSearchParams();
  const [showFilters, setShowFilters] = useState(true);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [models, setModels] = useState<FilterOption[]>([]);

  const get = useCallback((k: string) => sp.get(k) ?? "", [sp]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function debouncedUpdate(updates: Record<string, string>) {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => update(updates), 400);
  }

  // Fetch models when maker changes
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
    // Clear model when maker changes
    if ("maker" in updates && updates.maker !== get("maker")) {
      params.delete("model");
    }
    params.delete("page");
    router.push(`/dashboard?${params.toString()}`);
  }

  function clearAll() { router.push("/dashboard"); }
  function goPage(p: number) {
    const params = new URLSearchParams(sp.toString());
    params.set("page", String(p));
    router.push(`/dashboard?${params.toString()}`);
  }

  const sel = "h-9 rounded-lg border border-input bg-background px-2.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-ring";
  const activeFilters = ["maker", "model", "location", "auctionHouse", "source", "minPrice", "maxPrice", "rating", "search"].filter(k => get(k)).length;
  const totalAll = Object.values(sourceCounts).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Upcoming Auctions</h1>
          <div className="flex items-center gap-3 mt-1">
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Car className="h-4 w-4" />
              <span className="font-medium text-foreground">{total.toLocaleString()}</span> vehicles
            </div>
            {activeFilters > 0 && (
              <>
                <Separator orientation="vertical" className="h-4" />
                <button onClick={clearAll} className="text-xs text-primary hover:underline">
                  Clear {activeFilters} filter{activeFilters > 1 ? "s" : ""}
                </button>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex border rounded-lg overflow-hidden">
            <button onClick={() => setViewMode("grid")} className={`p-1.5 ${viewMode === "grid" ? "bg-accent" : ""}`}>
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button onClick={() => setViewMode("list")} className={`p-1.5 ${viewMode === "list" ? "bg-accent" : ""}`}>
              <List className="h-4 w-4" />
            </button>
          </div>
          <Button variant="outline" size="sm" onClick={() => setShowFilters(!showFilters)}>
            <SlidersHorizontal className="h-3.5 w-3.5 mr-1.5" />
            Filters
            {activeFilters > 0 && (
              <Badge variant="default" className="ml-1.5 h-4 w-4 p-0 flex items-center justify-center text-[10px] rounded-full">
                {activeFilters}
              </Badge>
            )}
          </Button>
        </div>
      </div>

      {/* Source tabs */}
      <div className="flex gap-1.5 border-b pb-3">
        <button
          onClick={() => update({ source: "" })}
          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${!get("source") ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}
        >
          All Sources ({totalAll.toLocaleString()})
        </button>
        {Object.entries(sourceCounts).map(([src, count]) => (
          <button
            key={src}
            onClick={() => update({ source: src })}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${get("source") === src ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}
          >
            {src.toUpperCase()} ({count.toLocaleString()})
          </button>
        ))}
      </div>

      {/* Filters */}
      {showFilters && (
        <Card className="border-dashed">
          <CardContent className="p-4 space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {/* Search */}
              <div className="sm:col-span-2 space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Search</label>
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <Input placeholder="Maker, model, lot..." defaultValue={get("search")} onChange={e => debouncedUpdate({ search: e.target.value })} className="pl-8 h-9" />
                </div>
              </div>

              {/* Maker */}
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Maker</label>
                <select value={get("maker")} onChange={e => update({ maker: e.target.value })} className={sel}>
                  <option value="">All Makers</option>
                  {filterOptions.makers.map(m => (
                    <option key={m.value} value={m.value}>{m.value} ({m.count})</option>
                  ))}
                </select>
              </div>

              {/* Model — dynamic based on maker */}
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Model</label>
                {models.length > 0 ? (
                  <select value={get("model")} onChange={e => update({ model: e.target.value })} className={sel}>
                    <option value="">All Models</option>
                    {models.map(m => (
                      <option key={m.value} value={m.value}>{m.value} ({m.count})</option>
                    ))}
                  </select>
                ) : (
                  <Input placeholder={get("maker") ? "Loading..." : "Select maker first"} disabled={!get("maker")} defaultValue={get("model")} onChange={e => update({ model: e.target.value })} className="h-9" />
                )}
              </div>

              {/* Auction House */}
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Auction</label>
                <select value={get("auctionHouse")} onChange={e => update({ auctionHouse: e.target.value })} className={sel}>
                  <option value="">All Houses</option>
                  {filterOptions.auctionHouses.map(h => (
                    <option key={h.value} value={h.value}>{h.value} ({h.count})</option>
                  ))}
                </select>
              </div>

              {/* Location */}
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Location</label>
                <select value={get("location")} onChange={e => update({ location: e.target.value })} className={sel}>
                  <option value="">All Locations</option>
                  {filterOptions.locations.map(l => (
                    <option key={l.value} value={l.value}>{l.value} ({l.count})</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Row 2: Price, Rating, Sort */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Min Price (¥)</label>
                <Input type="number" placeholder="0" defaultValue={get("minPrice")} onChange={e => debouncedUpdate({ minPrice: e.target.value })} className="h-9" />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Max Price (¥)</label>
                <Input type="number" placeholder="No limit" defaultValue={get("maxPrice")} onChange={e => debouncedUpdate({ maxPrice: e.target.value })} className="h-9" />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Rating</label>
                <select value={get("rating")} onChange={e => update({ rating: e.target.value })} className={sel}>
                  <option value="">Any</option>
                  <option value="S">S</option>
                  <option value="6">6+</option>
                  <option value="5">5+</option>
                  <option value="4.5">4.5+</option>
                  <option value="4">4+</option>
                  <option value="3.5">3.5+</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Sort By</label>
                <select value={get("sort") || "auctionDate"} onChange={e => update({ sort: e.target.value })} className={sel}>
                  <option value="auctionDate">Auction Date</option>
                  <option value="startPrice">Price</option>
                  <option value="maker">Maker</option>
                  <option value="firstSeen">Recently Added</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Order</label>
                <button onClick={() => update({ order: get("order") === "desc" ? "asc" : "desc" })} className={`${sel} flex items-center gap-2 cursor-pointer`}>
                  <ArrowUpDown className="h-3.5 w-3.5" />
                  {get("order") === "desc" ? "Descending" : "Ascending"}
                </button>
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">&nbsp;</label>
                {activeFilters > 0 && (
                  <Button variant="ghost" size="sm" className="h-9 w-full text-xs" onClick={clearAll}>
                    <X className="h-3 w-3 mr-1" /> Clear All
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {auctions.length === 0 ? (
        <Card>
          <CardContent className="py-20 text-center">
            <Car className="h-12 w-12 mx-auto text-muted-foreground/20 mb-4" />
            <p className="text-lg font-medium text-muted-foreground">No vehicles found</p>
            <p className="text-sm text-muted-foreground mt-1">Try adjusting your filters</p>
            {activeFilters > 0 && (
              <Button variant="outline" size="sm" className="mt-4" onClick={clearAll}>Clear all filters</Button>
            )}
          </CardContent>
        </Card>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {auctions.map(a => (
            <Link key={a.id} href={`/dashboard/${a.id}`} className="group">
              <Card className="overflow-hidden hover:shadow-lg transition-all duration-200 h-full border-transparent hover:border-primary/20">
                <div className="aspect-[4/3] bg-muted relative overflow-hidden">
                  {a.imageUrl ? (
                    <Image src={proxyUrl(a.imageUrl)} alt={`${a.maker} ${a.model}`} fill className="object-cover group-hover:scale-105 transition-transform duration-300" sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw" loading="lazy" unoptimized />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-muted-foreground/40">
                      <Car className="h-10 w-10" />
                    </div>
                  )}
                  <div className="absolute top-2 left-2 right-2 flex justify-between">
                    <Badge className="text-[10px] bg-black/60 text-white border-0 backdrop-blur-sm">
                      {a.source?.toUpperCase()}
                    </Badge>
                    {a.rating && (
                      <Badge variant="outline" className="text-[10px] bg-white/90 backdrop-blur-sm border-0">
                        {a.rating}
                      </Badge>
                    )}
                  </div>
                </div>
                <CardContent className="p-3.5 space-y-2">
                  <div>
                    <h3 className="font-semibold text-sm group-hover:text-primary transition-colors leading-tight">
                      {a.maker} {a.model}
                    </h3>
                    {a.grade && <p className="text-[11px] text-muted-foreground truncate mt-0.5">{a.grade}</p>}
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                    {a.year && <span>{a.year}</span>}
                    {a.mileage && <><span>·</span><span>{a.mileage}</span></>}
                    {a.color && <><span>·</span><span>{a.color}</span></>}
                  </div>
                  <Separator />
                  <div className="flex items-center justify-between">
                    <span className="font-bold">
                      {a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}
                    </span>
                    <div className="text-right">
                      <div className="text-[11px] font-medium">{a.auctionDate}</div>
                      <div className="text-[10px] text-muted-foreground">{a.location}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        /* List view */
        <Card>
          <CardContent className="p-0 divide-y">
            {auctions.map(a => (
              <Link key={a.id} href={`/dashboard/${a.id}`} className="flex items-center gap-4 p-3 hover:bg-accent/50 transition-colors group">
                <div className="w-20 h-14 rounded-md overflow-hidden bg-muted flex-shrink-0 relative">
                  {a.imageUrl ? (
                    <Image src={proxyUrl(a.imageUrl)} alt={`${a.maker} ${a.model}`} fill className="object-cover" sizes="80px" loading="lazy" unoptimized />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-muted-foreground/30"><Car className="h-5 w-5" /></div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-sm group-hover:text-primary transition-colors truncate">{a.maker} {a.model}</h3>
                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground mt-0.5">
                    {a.year && <span>{a.year}</span>}
                    {a.color && <><span>·</span><span>{a.color}</span></>}
                    {a.rating && <><span>·</span><span className="font-medium text-foreground">{a.rating}</span></>}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <span className="font-bold text-sm">{a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}</span>
                  <div className="text-[11px] text-muted-foreground">{a.auctionDate}</div>
                </div>
                <Badge variant="outline" className="text-[10px] flex-shrink-0">{a.source?.toUpperCase()}</Badge>
              </Link>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-sm text-muted-foreground">
            Showing {(page - 1) * 40 + 1}-{Math.min(page * 40, total)} of {total.toLocaleString()}
          </span>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => goPage(page - 1)}>
              <ChevronLeft className="h-4 w-4 mr-1" /> Previous
            </Button>
            <span className="px-3 text-sm text-muted-foreground">
              {page} / {totalPages}
            </span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => goPage(page + 1)}>
              Next <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function CustomerAuctions(props: Props) {
  return (
    <Suspense fallback={<div className="py-10 text-center text-muted-foreground text-sm">Loading...</div>}>
      <Content {...props} />
    </Suspense>
  );
}
