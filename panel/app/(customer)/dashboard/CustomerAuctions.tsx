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
  ChevronLeft, ChevronRight, Car, LayoutGrid, AlignJustify, Loader2,
} from "lucide-react";
import { useNavigationContext } from "../components/NavigationContext";
import { SmartSearch } from "./SmartSearch";

interface DayOption { date: string; count: number }
interface FilterOptions {
  auctionDays?: DayOption[];
}


const PASSTHROUGH_KEYS = ["maker", "model", "chassisCode", "location", "auctionHouse", "source", "search", "sort", "order", "minPrice", "maxPrice", "rating", "yearFrom", "yearTo", "auctionDay", "pageSize"];

const PAGE_SIZE_OPTIONS = [20, 40, 80, 100];
const DEFAULT_PAGE_SIZE = 40;

function buildQueryString(sp: URLSearchParams, includeMeta: boolean): string {
  const params = new URLSearchParams();
  const page = Math.max(1, parseInt(sp.get("page") || "1"));
  const pageSize = parseInt(sp.get("pageSize") || String(DEFAULT_PAGE_SIZE));
  params.set("page", String(page));
  params.set("pageSize", String(pageSize));
  if (includeMeta) params.set("includeMeta", "true");
  if (!sp.get("status")) params.set("status", "upcoming");

  for (const key of PASSTHROUGH_KEYS) {
    const val = sp.get(key);
    if (val) params.set(key, val);
  }
  if (!sp.get("sort")) params.set("sort", "firstSeen");
  if (!sp.get("order")) params.set("order", "desc");

  return params.toString();
}

function Content() {
  const router = useRouter();
  const sp = useSearchParams();
  const navCtx = useNavigationContext();
  const [viewMode, setViewMode] = useState<"grid" | "list">("list");

  // Client-side data state
  const [auctions, setAuctions] = useState<AuctionSerialized[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({});
  const [loading, setLoading] = useState(true);
  const [initialLoad, setInitialLoad] = useState(true);

  // Track whether dropdown meta (makers, locations, houses) has been fetched
  const dropdownMetaLoaded = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const get = useCallback((k: string) => sp.get(k) ?? "", [sp]);

  // Fetch auctions from API (client-side)
  const fetchAuctions = useCallback((searchParams: URLSearchParams) => {
    // Cancel any in-flight request
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    // Always request meta for dropdowns on first load; auctionDays come in every response
    const includeMeta = !dropdownMetaLoaded.current;
    const qs = buildQueryString(searchParams, includeMeta);

    setLoading(true);

    fetch(`/api/auctions?${qs}`, { signal: controller.signal })
      .then(r => r.json())
      .then(data => {
        setAuctions(data.auctions || []);
        setTotal(data.total || 0);
        setPage(data.page || 1);
        setTotalPages(data.totalPages || 0);

        // auctionDays now comes in every response (filter-aware counts)
        if (data.auctionDays) {
          setFilterOptions(prev => ({ ...prev, auctionDays: data.auctionDays }));
        }

        // Dropdown options (makers, locations, houses) only on first load
        if (includeMeta && data.filterOptions) {
          setFilterOptions(prev => ({ ...prev, ...data.filterOptions }));
          dropdownMetaLoaded.current = true;
        }

        // Populate navigation context for prev/next on detail pages
        if (data.auctions?.length && navCtx) {
          navCtx.setVehicleList(
            data.auctions.map((a: AuctionSerialized) => a.id),
            searchParams.toString(),
            data.page || 1,
            data.total || 0,
          );
        }

        setLoading(false);
        setInitialLoad(false);
      })
      .catch(err => {
        if (err.name !== "AbortError") {
          setLoading(false);
          setInitialLoad(false);
        }
      });
  }, []);

  // Fetch on mount and when search params change (debounced)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchAuctions(sp);
    }, initialLoad ? 0 : 150);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [sp, fetchAuctions, initialLoad]);

  // Cleanup abort on unmount
  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  // Restore saved filters on first load if no URL params
  useEffect(() => {
    if (sp.toString() === "" || sp.toString() === "page=1") {
      try {
        const saved = localStorage.getItem("auction-filters");
        if (saved) {
          const params = new URLSearchParams(saved);
          params.delete("page");
          const savedDay = params.get("auctionDay");
          if (savedDay) {
            const jstNow = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Tokyo" }));
            const todayStr = `${jstNow.getFullYear()}-${String(jstNow.getMonth() + 1).padStart(2, "0")}-${String(jstNow.getDate()).padStart(2, "0")}`;
            if (savedDay < todayStr) params.delete("auctionDay");
          }
          if (params.toString()) {
            router.replace(`/dashboard?${params.toString()}`);
          }
        }
      } catch {}
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Save filters to localStorage whenever they change
  // Only save actual filter params, not sort/order/pageSize (those are preferences, not filters)
  const FILTER_KEYS = ["maker", "model", "chassisCode", "location", "auctionHouse", "source", "search", "minPrice", "maxPrice", "rating", "yearFrom", "yearTo", "auctionDay"];
  useEffect(() => {
    try {
      const params = new URLSearchParams();
      for (const key of FILTER_KEYS) {
        const val = sp.get(key);
        if (val) params.set(key, val);
      }
      if (params.toString()) {
        localStorage.setItem("auction-filters", params.toString());
      } else {
        localStorage.removeItem("auction-filters");
      }
    } catch {}
  }, [sp]);

  function handleSmartSearch(filters: Record<string, string>) {
    const hasFilters = Object.values(filters).some(v => v);
    if (!hasFilters) {
      // Full clear — remove everything including localStorage
      try { localStorage.removeItem("auction-filters"); } catch {}
      router.replace("/dashboard");
      return;
    }
    // Build fresh params — only include non-empty filter values
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    // Preserve sort, order, auctionDay, pageSize from current URL
    const currentSort = sp.get("sort");
    const currentOrder = sp.get("order");
    const currentDay = sp.get("auctionDay");
    const currentPageSize = sp.get("pageSize");
    if (currentSort) params.set("sort", currentSort);
    if (currentOrder) params.set("order", currentOrder);
    if (currentDay) params.set("auctionDay", currentDay);
    if (currentPageSize) params.set("pageSize", currentPageSize);
    router.replace(`/dashboard?${params.toString()}`);
  }

  function update(updates: Record<string, string>) {
    const params = new URLSearchParams(sp.toString());
    Object.entries(updates).forEach(([k, v]) => {
      if (v) params.set(k, v); else params.delete(k);
    });
    if ("maker" in updates && updates.maker !== get("maker")) { params.delete("model"); params.delete("chassisCode"); }
    if ("model" in updates && updates.model !== get("model")) params.delete("chassisCode");
    params.delete("page");
    router.replace(`/dashboard?${params.toString()}`);
  }

  function clearAll() {
    try { localStorage.removeItem("auction-filters"); } catch {}
    router.replace("/dashboard");
  }
  function goPage(p: number) {
    const params = new URLSearchParams(sp.toString());
    params.set("page", String(p));
    router.replace(`/dashboard?${params.toString()}`);
  }

  const auctionDays = filterOptions.auctionDays || [];

  // Skeleton for initial load
  if (initialLoad) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="h-5 w-32 bg-muted animate-pulse rounded" />
          <div className="h-5 w-16 bg-muted animate-pulse rounded" />
        </div>
        <div className="flex gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-14 w-16 bg-muted animate-pulse rounded" />
          ))}
        </div>
        <div className="h-20 bg-muted/50 animate-pulse rounded" />
        <div className="space-y-px">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="h-10 bg-card animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header + Smart Search */}
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-base font-bold tracking-tight text-foreground">Vehicles</h1>
        <div className="flex items-center gap-1">
          <div className="flex border border-border rounded overflow-hidden h-7">
            <button onClick={() => setViewMode("grid")} className={`px-2 transition-colors ${viewMode === "grid" ? "bg-accent text-foreground" : "text-muted-foreground/70 hover:text-foreground/80 hover:bg-muted"}`}>
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button onClick={() => setViewMode("list")} className={`px-2 transition-colors ${viewMode === "list" ? "bg-accent text-foreground" : "text-muted-foreground/70 hover:text-foreground/80 hover:bg-muted"}`}>
              <AlignJustify className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      <SmartSearch
        onFiltersChange={handleSmartSearch}
        auctionDays={auctionDays}
        selectedDay={get("auctionDay")}
        onDaySelect={(day) => update({ auctionDay: day })}
        sort={get("sort") || "firstSeen"}
        onSortChange={(s) => update({ sort: s })}
        total={total}
        activeFilters={{
          maker: get("maker"),
          search: get("search"),
          chassisCode: get("chassisCode"),
          auctionHouse: get("auctionHouse"),
          yearFrom: get("yearFrom"),
          yearTo: get("yearTo"),
        }}
      />

      {/* Table/Grid with loading overlay */}
      <div className="relative">
        {/* Loading overlay */}
        {loading && !initialLoad && (
          <div className="absolute inset-0 bg-background/60 z-10 flex items-center justify-center rounded">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground/70" />
          </div>
        )}

        {/* Empty state */}
        {auctions.length === 0 && !loading ? (
          <div className="py-16 text-center">
            <Car className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
            <p className="text-sm text-muted-foreground/70">No vehicles match your filters</p>
            <button onClick={clearAll} className="text-xs text-blue-400 hover:text-blue-300 mt-2">Clear all filters</button>
          </div>
        ) : viewMode === "grid" ? (
          /* Grid */
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {auctions.map(a => (
              <Link key={a.id} href={`/dashboard/${a.id}`} className="group">
                <div className="bg-card border border-border rounded overflow-hidden hover:border-ring/30 transition-all duration-100">
                  <div className="aspect-[16/10] bg-muted relative overflow-hidden">
                    {a.imageUrl ? (
                      <Image src={proxyUrl(a.imageUrl)} alt="" fill className="object-cover" sizes="(max-width: 640px) 50vw, 25vw" loading="lazy" unoptimized />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-muted-foreground/30"><Car className="h-5 w-5" /></div>
                    )}
                    {a.rating && (
                      <span className="absolute top-1 right-1 text-[9px] font-mono font-bold bg-blue-500/90 text-white px-1.5 py-0.5 rounded-sm">
                        {a.rating}
                      </span>
                    )}
                  </div>
                  <div className="p-2.5 space-y-1">
                    <p className="text-xs font-semibold truncate text-foreground group-hover:text-blue-400 transition-colors">
                      {a.maker || "Unknown"} {a.model || "Vehicle"}
                    </p>
                    <p className="text-[10px] text-muted-foreground/70 truncate">
                      {[a.year, a.mileage, a.color].filter(Boolean).join(" · ")}
                    </p>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-foreground">
                        {a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}
                      </span>
                    </div>
                    <p className="text-[9px] text-muted-foreground/50 truncate">{a.auctionHouse} · {a.auctionDate}</p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          /* List — dark dense table */
          <div className="bg-card border border-border rounded overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-card">
                  <th className="text-left font-medium text-muted-foreground/70 uppercase text-[10px] tracking-wider px-3 py-2 w-[50px]"></th>
                  <th className="text-left font-medium text-muted-foreground/70 uppercase text-[10px] tracking-wider px-2 py-2">Vehicle</th>
                  <th className="text-left font-medium text-muted-foreground/70 uppercase text-[10px] tracking-wider px-2 py-2 hidden md:table-cell">Auction</th>
                  <th className="text-left font-medium text-muted-foreground/70 uppercase text-[10px] tracking-wider px-2 py-2 hidden lg:table-cell">Specs</th>
                  <th className="text-center font-medium text-muted-foreground/70 uppercase text-[10px] tracking-wider px-2 py-2 hidden sm:table-cell w-[52px]">Score</th>
                  <th className="text-left font-medium text-muted-foreground/70 uppercase text-[10px] tracking-wider px-2 py-2 hidden lg:table-cell">Date</th>
                  <th className="text-right font-medium text-muted-foreground/70 uppercase text-[10px] tracking-wider px-3 py-2">Price</th>
                </tr>
              </thead>
              <tbody>
                {auctions.map(a => (
                  <tr key={a.id} className="border-b border-border/50 last:border-0 hover:bg-muted/40 transition-colors cursor-pointer group relative">
                    <td className="px-3 py-1.5">
                      <Link href={`/dashboard/${a.id}`} className="absolute inset-0 z-[1]" aria-label={`${a.maker || ""} ${a.model || "Vehicle"}`} />
                      <div className="w-[44px] h-[32px] rounded-sm overflow-hidden bg-muted relative">
                        {a.imageUrl ? (
                          <Image src={proxyUrl(a.imageUrl)} alt="" fill className="object-cover" sizes="44px" loading="lazy" unoptimized />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-muted-foreground/30"><Car className="h-3 w-3" /></div>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-1.5">
                      <p className="font-medium truncate max-w-[220px] text-foreground group-hover:text-blue-400 transition-colors">{a.maker || "—"} {a.model || ""}</p>
                      <p className="text-[10px] text-muted-foreground/50 truncate">{a.grade || ""}</p>
                    </td>
                    <td className="px-2 py-1.5 hidden md:table-cell">
                      <p className="truncate max-w-[140px] text-foreground/80">{a.auctionHouse}</p>
                      <p className="text-[10px] text-muted-foreground/50">{a.location}</p>
                    </td>
                    <td className="px-2 py-1.5 hidden lg:table-cell text-muted-foreground/70 text-[11px]">
                      {[a.year, a.mileage, a.color].filter(Boolean).join(" · ")}
                    </td>
                    <td className="px-2 py-1.5 text-center hidden sm:table-cell">
                      {a.rating && <span className="text-[10px] font-mono font-bold bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded-sm">{a.rating}</span>}
                    </td>
                    <td className="px-2 py-1.5 hidden lg:table-cell text-muted-foreground/70 text-[10px] font-mono">
                      {a.auctionDate}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      <span className="font-mono font-bold text-foreground">{a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > 0 && (() => {
        const ps = parseInt(get("pageSize") || String(DEFAULT_PAGE_SIZE));
        return (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-muted-foreground/70 font-mono">
                {(page - 1) * ps + 1}–{Math.min(page * ps, total)} of {total.toLocaleString()}
              </span>
              <select
                value={ps}
                onChange={e => {
                  const params = new URLSearchParams(sp.toString());
                  params.set("pageSize", e.target.value);
                  params.delete("page");
                  router.replace(`/dashboard?${params.toString()}`);
                }}
                className="h-6 rounded border border-border bg-card px-1.5 text-[10px] text-muted-foreground focus:outline-none cursor-pointer appearance-none"
              >
                {PAGE_SIZE_OPTIONS.map(s => (
                  <option key={s} value={s}>{s}/page</option>
                ))}
              </select>
            </div>
            {totalPages > 1 && (
              <div className="flex items-center gap-0.5">
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground/90 hover:bg-muted" disabled={page <= 1} onClick={() => goPage(page - 1)}>
                  <ChevronLeft className="h-3.5 w-3.5" />
                </Button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const p = page <= 3 ? i + 1 : page + i - 2;
                  if (p < 1 || p > totalPages) return null;
                  return (
                    <Button key={p} variant={p === page ? "default" : "ghost"} size="sm" className={`h-7 w-7 p-0 text-[11px] font-mono ${p === page ? "bg-blue-500 text-white hover:bg-blue-600" : "text-muted-foreground hover:text-foreground/90 hover:bg-muted"}`} onClick={() => goPage(p)}>
                      {p}
                    </Button>
                  );
                })}
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground/90 hover:bg-muted" disabled={page >= totalPages} onClick={() => goPage(page + 1)}>
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}

export function CustomerAuctions() {
  return (
    <Suspense fallback={
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="h-5 w-32 bg-muted animate-pulse rounded" />
          <div className="h-5 w-16 bg-muted animate-pulse rounded" />
        </div>
        <div className="flex gap-1.5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-12 w-14 bg-muted animate-pulse rounded" />
          ))}
        </div>
        <div className="h-16 bg-muted/50 animate-pulse rounded" />
        <div className="space-y-px">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="h-10 bg-card animate-pulse" />
          ))}
        </div>
      </div>
    }>
      <Content />
    </Suspense>
  );
}
