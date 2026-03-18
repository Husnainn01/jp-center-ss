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
import { Button } from "@/components/ui/button";
import {
  Search, ChevronLeft, ChevronRight, Car, LayoutGrid, List, X,
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

const sel = "h-8 rounded-md border border-input bg-background px-2 text-xs w-full focus:outline-none focus:ring-1 focus:ring-ring/30 cursor-pointer";

function Content({ auctions, page, totalPages, total, filterOptions }: Props) {
  const router = useRouter();
  const sp = useSearchParams();
  const [viewMode, setViewMode] = useState<"grid" | "list">("list");
  const [models, setModels] = useState<FilterOption[]>([]);
  const searchRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    router.push(`/dashboard?${params.toString()}`);
  }

  function debouncedUpdate(updates: Record<string, string>) {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => update(updates), 400);
  }

  function clearAll() { router.push("/dashboard"); }
  function goPage(p: number) {
    const params = new URLSearchParams(sp.toString());
    params.set("page", String(p));
    router.push(`/dashboard?${params.toString()}`);
  }

  const activeFilters = ["maker", "model", "location", "auctionHouse", "minPrice", "maxPrice", "rating", "search", "auctionDate"].filter(k => get(k)).length;

  return (
    <div className="space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold tracking-tight">Upcoming Auctions</h1>
          <p className="text-xs text-muted-foreground">
            {total.toLocaleString()} vehicles found
            {activeFilters > 0 && (
              <button onClick={clearAll} className="ml-2 text-primary hover:underline">
                Clear {activeFilters} filter{activeFilters > 1 ? "s" : ""}
              </button>
            )}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="flex border rounded overflow-hidden">
            <button onClick={() => setViewMode("grid")} className={`p-1.5 ${viewMode === "grid" ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}>
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button onClick={() => setViewMode("list")} className={`p-1.5 ${viewMode === "list" ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}>
              <List className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Compact filters — all dropdowns in one row */}
      <div className="flex flex-wrap gap-2 items-end">
        {/* Search */}
        <div className="relative w-44">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            ref={searchRef}
            type="text"
            placeholder="Search..."
            defaultValue={get("search")}
            onChange={e => debouncedUpdate({ search: e.target.value })}
            className="h-8 w-full rounded-md border border-input bg-background pl-7 pr-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring/30"
          />
        </div>

        {/* Maker */}
        <select value={get("maker")} onChange={e => update({ maker: e.target.value })} className={`${sel} w-32`}>
          <option value="">All Makers</option>
          {filterOptions.makers.map(m => (
            <option key={m.value} value={m.value}>{m.value} ({m.count})</option>
          ))}
        </select>

        {/* Model */}
        {models.length > 0 ? (
          <select value={get("model")} onChange={e => update({ model: e.target.value })} className={`${sel} w-32`}>
            <option value="">All Models</option>
            {models.map(m => (
              <option key={m.value} value={m.value}>{m.value} ({m.count})</option>
            ))}
          </select>
        ) : get("maker") ? (
          <select disabled className={`${sel} w-32 opacity-50`}><option>Loading...</option></select>
        ) : null}

        {/* Auction House */}
        <select value={get("auctionHouse")} onChange={e => update({ auctionHouse: e.target.value })} className={`${sel} w-36`}>
          <option value="">All Auctions</option>
          {filterOptions.auctionHouses.map(h => (
            <option key={h.value} value={h.value}>{h.value} ({h.count})</option>
          ))}
        </select>

        {/* Location */}
        <select value={get("location")} onChange={e => update({ location: e.target.value })} className={`${sel} w-32`}>
          <option value="">All Locations</option>
          {filterOptions.locations.map(l => (
            <option key={l.value} value={l.value}>{l.value} ({l.count})</option>
          ))}
        </select>

        {/* Rating */}
        <select value={get("rating")} onChange={e => update({ rating: e.target.value })} className={`${sel} w-24`}>
          <option value="">Rating</option>
          <option value="S">S</option>
          <option value="6">6+</option>
          <option value="5">5+</option>
          <option value="4.5">4.5+</option>
          <option value="4">4+</option>
          <option value="3.5">3.5+</option>
        </select>

        {/* Price Range */}
        <select value={get("minPrice")} onChange={e => update({ minPrice: e.target.value })} className={`${sel} w-28`}>
          <option value="">Min Price</option>
          <option value="10000">¥10,000+</option>
          <option value="50000">¥50,000+</option>
          <option value="100000">¥100,000+</option>
          <option value="300000">¥300,000+</option>
          <option value="500000">¥500,000+</option>
          <option value="1000000">¥1,000,000+</option>
        </select>

        <select value={get("maxPrice")} onChange={e => update({ maxPrice: e.target.value })} className={`${sel} w-28`}>
          <option value="">Max Price</option>
          <option value="50000">~¥50,000</option>
          <option value="100000">~¥100,000</option>
          <option value="300000">~¥300,000</option>
          <option value="500000">~¥500,000</option>
          <option value="1000000">~¥1,000,000</option>
          <option value="3000000">~¥3,000,000</option>
        </select>

        {/* Sort */}
        <select value={get("sort") || "firstSeen"} onChange={e => update({ sort: e.target.value })} className={`${sel} w-28`}>
          <option value="firstSeen">Newest</option>
          <option value="auctionDate">Date</option>
          <option value="startPrice">Price</option>
          <option value="maker">Maker</option>
        </select>

        {/* Clear */}
        {activeFilters > 0 && (
          <Button variant="ghost" size="sm" className="h-8 px-2 text-xs" onClick={clearAll}>
            <X className="h-3 w-3 mr-1" /> Clear
          </Button>
        )}
      </div>

      {/* Results */}
      {auctions.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <Car className="h-10 w-10 mx-auto text-muted-foreground/20 mb-3" />
            <p className="text-sm font-medium text-muted-foreground">No vehicles found</p>
            {activeFilters > 0 && (
              <Button variant="outline" size="sm" className="mt-3" onClick={clearAll}>Clear filters</Button>
            )}
          </CardContent>
        </Card>
      ) : viewMode === "grid" ? (
        /* Compact grid — 5 columns on xl, smaller cards */
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {auctions.map(a => (
            <Link key={a.id} href={`/dashboard/${a.id}`} className="group">
              <Card className="overflow-hidden hover:shadow-md transition-all duration-150 h-full">
                <div className="aspect-[16/10] bg-muted relative overflow-hidden">
                  {a.imageUrl ? (
                    <Image src={proxyUrl(a.imageUrl)} alt="" fill className="object-cover group-hover:scale-105 transition-transform duration-200" sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw" loading="lazy" unoptimized />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-muted-foreground/30"><Car className="h-6 w-6" /></div>
                  )}
                  {a.rating && (
                    <Badge variant="outline" className="absolute top-1.5 right-1.5 text-[9px] bg-white/90 border-0 px-1 py-0 h-4">
                      {a.rating}
                    </Badge>
                  )}
                </div>
                <CardContent className="p-2.5 space-y-1">
                  <h3 className="font-semibold text-xs leading-tight truncate group-hover:text-primary transition-colors">
                    {a.maker} {a.model}
                  </h3>
                  <p className="text-[10px] text-muted-foreground truncate">
                    {[a.year, a.mileage, a.color].filter(Boolean).join(" · ")}
                  </p>
                  <div className="flex items-center justify-between pt-1">
                    <span className="font-bold text-xs">
                      {a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}
                    </span>
                    <span className="text-[9px] text-muted-foreground truncate max-w-[60%] text-right">
                      {a.auctionHouse}
                    </span>
                  </div>
                  <div className="text-[9px] text-muted-foreground">{a.auctionDate}</div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        /* Compact list view */
        <Card>
          <CardContent className="p-0">
            {/* Header */}
            <div className="grid grid-cols-12 gap-2 px-3 py-2 border-b bg-muted/50 text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
              <div className="col-span-1">Image</div>
              <div className="col-span-3">Vehicle</div>
              <div className="col-span-2">Auction</div>
              <div className="col-span-2">Details</div>
              <div className="col-span-1">Rating</div>
              <div className="col-span-1">Date</div>
              <div className="col-span-2 text-right">Price</div>
            </div>
            {auctions.map(a => (
              <Link key={a.id} href={`/dashboard/${a.id}`} className="grid grid-cols-12 gap-2 px-3 py-2 items-center hover:bg-accent/50 transition-colors border-b last:border-0 group">
                <div className="col-span-1">
                  <div className="w-14 h-10 rounded overflow-hidden bg-muted relative">
                    {a.imageUrl ? (
                      <Image src={proxyUrl(a.imageUrl)} alt="" fill className="object-cover" sizes="56px" loading="lazy" unoptimized />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-muted-foreground/30"><Car className="h-3 w-3" /></div>
                    )}
                  </div>
                </div>
                <div className="col-span-3 min-w-0">
                  <p className="text-xs font-medium truncate group-hover:text-primary transition-colors">{a.maker} {a.model}</p>
                  {a.grade && <p className="text-[10px] text-muted-foreground truncate">{a.grade}</p>}
                </div>
                <div className="col-span-2 min-w-0">
                  <p className="text-[11px] truncate">{a.auctionHouse}</p>
                  <p className="text-[10px] text-muted-foreground truncate">{a.location}</p>
                </div>
                <div className="col-span-2">
                  <p className="text-[10px] text-muted-foreground">
                    {[a.year, a.mileage].filter(Boolean).join(" · ")}
                  </p>
                  {a.color && <p className="text-[10px] text-muted-foreground">{a.color}</p>}
                </div>
                <div className="col-span-1">
                  {a.rating && <Badge variant="outline" className="text-[9px] px-1 py-0 h-4">{a.rating}</Badge>}
                </div>
                <div className="col-span-1">
                  <p className="text-[10px] text-muted-foreground">{a.auctionDate}</p>
                </div>
                <div className="col-span-2 text-right">
                  <span className="font-bold text-xs">{a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}</span>
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {(page - 1) * 40 + 1}-{Math.min(page * 40, total)} of {total.toLocaleString()}
          </span>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="sm" className="h-7 text-xs" disabled={page <= 1} onClick={() => goPage(page - 1)}>
              <ChevronLeft className="h-3 w-3" />
            </Button>
            <span className="px-2 text-xs text-muted-foreground">{page}/{totalPages}</span>
            <Button variant="outline" size="sm" className="h-7 text-xs" disabled={page >= totalPages} onClick={() => goPage(page + 1)}>
              <ChevronRight className="h-3 w-3" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function CustomerAuctions(props: Props) {
  return (
    <Suspense fallback={<div className="py-10 text-center text-xs text-muted-foreground">Loading vehicles...</div>}>
      <Content {...props} />
    </Suspense>
  );
}
