"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import Image from "next/image";
import { AuctionSerialized } from "@/lib/types";
import { formatPrice } from "@/lib/format";
import { proxyUrl } from "@/lib/image";
import { Button } from "@/components/ui/button";
import {
  Search, ChevronLeft, ChevronRight, Car, LayoutGrid, AlignJustify, X, SlidersHorizontal,
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

const dd = "h-[30px] rounded border border-input bg-card px-2 text-[11px] w-full focus:outline-none focus:ring-1 focus:ring-primary/40 focus:border-primary cursor-pointer appearance-none";

function Content({ auctions, page, totalPages, total, filterOptions }: Props) {
  const router = useRouter();
  const sp = useSearchParams();
  const [viewMode, setViewMode] = useState<"grid" | "list">("list");
  const [models, setModels] = useState<FilterOption[]>([]);
  const [showFilters, setShowFilters] = useState(true);
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
    } else { setModels([]); }
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

  const filterKeys = ["maker", "model", "location", "auctionHouse", "minPrice", "maxPrice", "rating", "search"];
  const activeFilters = filterKeys.filter(k => get(k)).length;

  return (
    <div className="space-y-2">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h1 className="text-base font-bold tracking-tight">Vehicles</h1>
          <span className="text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full font-medium">
            {total.toLocaleString()}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant={showFilters ? "default" : "outline"}
            size="sm"
            className="h-7 text-[11px] gap-1"
            onClick={() => setShowFilters(!showFilters)}
          >
            <SlidersHorizontal className="h-3 w-3" />
            Filters
            {activeFilters > 0 && (
              <span className="bg-background/20 text-[9px] px-1 rounded-full">{activeFilters}</span>
            )}
          </Button>
          <div className="flex border rounded overflow-hidden h-7">
            <button onClick={() => setViewMode("grid")} className={`px-2 transition-colors ${viewMode === "grid" ? "bg-foreground text-background" : "hover:bg-accent"}`}>
              <LayoutGrid className="h-3 w-3" />
            </button>
            <button onClick={() => setViewMode("list")} className={`px-2 transition-colors ${viewMode === "list" ? "bg-foreground text-background" : "hover:bg-accent"}`}>
              <AlignJustify className="h-3 w-3" />
            </button>
          </div>
        </div>
      </div>

      {/* Filter bar — single row */}
      {showFilters && (
        <div className="bg-card border rounded-lg px-3 py-2 flex items-center gap-2 overflow-x-auto">
          <div className="relative flex-shrink-0">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
            <input
              ref={searchRef}
              type="text"
              placeholder="Search..."
              defaultValue={get("search")}
              onChange={e => debouncedUpdate({ search: e.target.value })}
              className="h-[32px] w-[160px] rounded border border-input bg-background pl-7 pr-2 text-[11px] focus:outline-none focus:ring-1 focus:ring-primary/40"
            />
          </div>

          <select value={get("maker")} onChange={e => update({ maker: e.target.value })} className={`${dd} !w-auto min-w-[100px]`}>
            <option value="">Maker</option>
            {filterOptions.makers.map(m => <option key={m.value} value={m.value}>{m.value} ({m.count})</option>)}
          </select>

          {(models.length > 0 || get("maker")) && (
            <select value={get("model")} onChange={e => update({ model: e.target.value })} className={`${dd} !w-auto min-w-[90px]`} disabled={models.length === 0}>
              <option value="">{models.length ? "Model" : "..."}</option>
              {models.map(m => <option key={m.value} value={m.value}>{m.value} ({m.count})</option>)}
            </select>
          )}

          <select value={get("auctionHouse")} onChange={e => update({ auctionHouse: e.target.value })} className={`${dd} !w-auto min-w-[110px]`}>
            <option value="">Auction</option>
            {filterOptions.auctionHouses.map(h => <option key={h.value} value={h.value}>{h.value} ({h.count})</option>)}
          </select>

          <select value={get("location")} onChange={e => update({ location: e.target.value })} className={`${dd} !w-auto min-w-[90px]`}>
            <option value="">Location</option>
            {filterOptions.locations.map(l => <option key={l.value} value={l.value}>{l.value} ({l.count})</option>)}
          </select>

          <select value={get("rating")} onChange={e => update({ rating: e.target.value })} className={`${dd} !w-auto min-w-[70px]`}>
            <option value="">Rating</option>
            <option value="S">S</option><option value="6">6+</option><option value="5">5+</option>
            <option value="4.5">4.5+</option><option value="4">4+</option><option value="3.5">3.5+</option>
          </select>

          <select value={get("minPrice")} onChange={e => update({ minPrice: e.target.value })} className={`${dd} !w-auto min-w-[80px]`}>
            <option value="">Min ¥</option>
            <option value="10000">¥10K+</option><option value="50000">¥50K+</option><option value="100000">¥100K+</option>
            <option value="300000">¥300K+</option><option value="500000">¥500K+</option><option value="1000000">¥1M+</option>
          </select>

          <select value={get("maxPrice")} onChange={e => update({ maxPrice: e.target.value })} className={`${dd} !w-auto min-w-[80px]`}>
            <option value="">Max ¥</option>
            <option value="50000">~¥50K</option><option value="100000">~¥100K</option><option value="300000">~¥300K</option>
            <option value="500000">~¥500K</option><option value="1000000">~¥1M</option><option value="3000000">~¥3M</option>
          </select>

          <select value={get("sort") || "firstSeen"} onChange={e => update({ sort: e.target.value })} className={`${dd} !w-auto min-w-[80px]`}>
            <option value="firstSeen">Newest</option><option value="auctionDate">Date</option>
            <option value="startPrice">Price</option><option value="maker">Maker</option>
          </select>

          {activeFilters > 0 && (
            <button onClick={clearAll} className="h-[32px] px-2.5 rounded border border-destructive/30 text-destructive text-[10px] font-medium hover:bg-destructive/5 transition-colors flex items-center gap-1 flex-shrink-0">
              <X className="h-2.5 w-2.5" /> Clear
            </button>
          )}
        </div>
      )}

      {/* Empty state */}
      {auctions.length === 0 ? (
        <div className="py-20 text-center">
          <Car className="h-8 w-8 mx-auto text-muted-foreground/20 mb-2" />
          <p className="text-xs text-muted-foreground">No vehicles match your filters</p>
          {activeFilters > 0 && (
            <button onClick={clearAll} className="text-[11px] text-primary hover:underline mt-1">Clear filters</button>
          )}
        </div>
      ) : viewMode === "grid" ? (
        /* Grid */
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
          {auctions.map(a => (
            <Link key={a.id} href={`/dashboard/${a.id}`} className="group">
              <div className="bg-card border rounded-lg overflow-hidden hover:shadow-md hover:border-primary/20 transition-all duration-150">
                <div className="aspect-[16/10] bg-muted relative overflow-hidden">
                  {a.imageUrl ? (
                    <Image src={proxyUrl(a.imageUrl)} alt="" fill className="object-cover group-hover:scale-[1.03] transition-transform duration-200" sizes="(max-width: 640px) 50vw, 20vw" loading="lazy" unoptimized />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-muted-foreground/20"><Car className="h-5 w-5" /></div>
                  )}
                  {a.rating && (
                    <span className="absolute top-1 right-1 text-[8px] font-bold bg-black/60 text-white px-1 py-0.5 rounded">
                      {a.rating}
                    </span>
                  )}
                </div>
                <div className="p-2.5 space-y-1">
                  <p className="text-xs font-semibold truncate leading-tight group-hover:text-primary transition-colors">
                    {a.maker} {a.model}
                  </p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    {[a.year, a.mileage, a.color].filter(Boolean).join(" · ")}
                  </p>
                  <div className="flex items-center justify-between pt-0.5">
                    <span className="text-xs font-bold">
                      {a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}
                    </span>
                    {a.rating && <span className="text-[9px] font-bold bg-muted px-1 py-0.5 rounded">{a.rating}</span>}
                  </div>
                  <p className="text-[9px] text-muted-foreground truncate">{a.auctionHouse} · {a.auctionDate}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        /* List — data-dense table */
        <div className="bg-card border rounded-lg overflow-hidden">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="text-left font-medium text-muted-foreground px-3 py-2 w-[50px]"></th>
                <th className="text-left font-medium text-muted-foreground px-2 py-2">Vehicle</th>
                <th className="text-left font-medium text-muted-foreground px-2 py-2 hidden md:table-cell">Auction</th>
                <th className="text-left font-medium text-muted-foreground px-2 py-2 hidden lg:table-cell">Specs</th>
                <th className="text-center font-medium text-muted-foreground px-2 py-2 hidden sm:table-cell w-[50px]">Score</th>
                <th className="text-left font-medium text-muted-foreground px-2 py-2 hidden lg:table-cell">Date</th>
                <th className="text-right font-medium text-muted-foreground px-3 py-2">Price</th>
              </tr>
            </thead>
            <tbody>
              {auctions.map(a => (
                <tr key={a.id} className="border-b last:border-0 hover:bg-accent/40 transition-colors cursor-pointer group" onClick={() => router.push(`/dashboard/${a.id}`)}>
                  <td className="px-3 py-1.5">
                    <div className="w-[42px] h-[30px] rounded overflow-hidden bg-muted relative">
                      {a.imageUrl ? (
                        <Image src={proxyUrl(a.imageUrl)} alt="" fill className="object-cover" sizes="42px" loading="lazy" unoptimized />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-muted-foreground/20"><Car className="h-3 w-3" /></div>
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-1.5">
                    <p className="font-medium truncate max-w-[200px] group-hover:text-primary transition-colors">{a.maker} {a.model}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{a.grade || ""}</p>
                  </td>
                  <td className="px-2 py-1.5 hidden md:table-cell">
                    <p className="truncate max-w-[150px]">{a.auctionHouse}</p>
                    <p className="text-[10px] text-muted-foreground">{a.location}</p>
                  </td>
                  <td className="px-2 py-1.5 hidden lg:table-cell text-muted-foreground">
                    {[a.year, a.mileage, a.color].filter(Boolean).join(" · ")}
                  </td>
                  <td className="px-2 py-1.5 text-center hidden sm:table-cell">
                    {a.rating && <span className="text-[10px] font-bold bg-muted px-1.5 py-0.5 rounded">{a.rating}</span>}
                  </td>
                  <td className="px-2 py-1.5 hidden lg:table-cell text-muted-foreground text-[10px]">
                    {a.auctionDate}
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <span className="font-bold">{a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-muted-foreground">
            {(page - 1) * 40 + 1}–{Math.min(page * 40, total)} of {total.toLocaleString()}
          </span>
          <div className="flex items-center gap-0.5">
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" disabled={page <= 1} onClick={() => goPage(page - 1)}>
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = page <= 3 ? i + 1 : page + i - 2;
              if (p < 1 || p > totalPages) return null;
              return (
                <Button key={p} variant={p === page ? "default" : "ghost"} size="sm" className="h-7 w-7 p-0 text-[10px]" onClick={() => goPage(p)}>
                  {p}
                </Button>
              );
            })}
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" disabled={page >= totalPages} onClick={() => goPage(page + 1)}>
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function CustomerAuctions(props: Props) {
  return (
    <Suspense fallback={
      <div className="space-y-3">
        <div className="h-7 w-32 bg-muted animate-pulse rounded" />
        <div className="h-[30px] bg-muted animate-pulse rounded-lg" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="bg-card border rounded-lg overflow-hidden">
              <div className="aspect-[16/10] bg-muted animate-pulse" />
              <div className="p-2 space-y-1">
                <div className="h-3 bg-muted animate-pulse rounded w-3/4" />
                <div className="h-2.5 bg-muted animate-pulse rounded w-1/2" />
                <div className="h-3 bg-muted animate-pulse rounded w-1/3" />
              </div>
            </div>
          ))}
        </div>
      </div>
    }>
      <Content {...props} />
    </Suspense>
  );
}
