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
  ChevronLeft, ChevronRight, Car, LayoutGrid, AlignJustify, X, Calendar, Loader2,
} from "lucide-react";

interface FilterOption { value: string; count: number }
interface DayOption { date: string; count: number }
interface FilterOptions {
  makers: FilterOption[];
  locations: FilterOption[];
  auctionHouses: FilterOption[];
  auctionDays?: DayOption[];
}

const sel = "h-9 rounded-md border border-input bg-card px-3 text-xs w-full focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary cursor-pointer appearance-none";

function formatDayLabel(dateStr: string): { label: string; day: string; weekday: string } {
  const d = new Date(dateStr + "T00:00:00");
  const jstNow = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Tokyo" }));
  const today = new Date(jstNow.getFullYear(), jstNow.getMonth(), jstNow.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const day = d.getDate().toString();
  const weekday = d.toLocaleDateString("en", { weekday: "short" });

  if (d.getTime() === today.getTime()) return { label: "Today", day, weekday: "" };
  if (d.getTime() === tomorrow.getTime()) return { label: "Tomorrow", day, weekday: "" };
  return { label: weekday, day, weekday };
}

const YEARS = Array.from({ length: 30 }, (_, i) => (2026 - i).toString());

const PASSTHROUGH_KEYS = ["maker", "model", "chassisCode", "location", "auctionHouse", "source", "search", "sort", "order", "minPrice", "maxPrice", "rating", "yearFrom", "yearTo", "auctionDay"];

function buildQueryString(sp: URLSearchParams, includeMeta: boolean): string {
  const params = new URLSearchParams();
  const page = Math.max(1, parseInt(sp.get("page") || "1"));
  params.set("page", String(page));
  params.set("pageSize", "40");
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
  const [viewMode, setViewMode] = useState<"grid" | "list">("list");
  const [models, setModels] = useState<FilterOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [chassisCodes, setChassisCodes] = useState<FilterOption[]>([]);

  // Client-side data state
  const [auctions, setAuctions] = useState<AuctionSerialized[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({ makers: [], locations: [], auctionHouses: [] });
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
  useEffect(() => {
    try {
      const params = new URLSearchParams(sp.toString());
      params.delete("page");
      if (params.toString()) {
        localStorage.setItem("auction-filters", params.toString());
      }
    } catch {}
  }, [sp]);

  useEffect(() => {
    const maker = get("maker");
    const model = get("model");
    if (maker) {
      setModelsLoading(true);
      const params = new URLSearchParams({ maker });
      if (model) params.set("model", model);
      fetch(`/api/filter-options?${params}`)
        .then(r => {
          if (!r.ok) throw new Error(`filter-options ${r.status}`);
          return r.json();
        })
        .then(d => {
          setModels(d.models || []);
          setChassisCodes(d.chassisCodes || []);
        })
        .catch(() => {
          setModels([]);
          setChassisCodes([]);
        })
        .finally(() => setModelsLoading(false));
    } else { setModels([]); setChassisCodes([]); setModelsLoading(false); }
  }, [get]);

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

  const filterKeys = ["auctionDay", "maker", "model", "chassisCode", "location", "auctionHouse", "minPrice", "maxPrice", "rating", "yearFrom", "yearTo"];
  const activeFilters = filterKeys.filter(k => get(k)).length;
  const auctionDays = filterOptions.auctionDays || [];

  // Skeleton for initial load
  if (initialLoad) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-6 w-36 bg-muted animate-pulse rounded" />
            <div className="h-6 w-20 bg-muted animate-pulse rounded-full" />
          </div>
        </div>
        <div className="flex gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 w-20 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
        <div className="h-24 bg-muted animate-pulse rounded-lg" />
        <div className="space-y-1">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-12 bg-muted/50 animate-pulse rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold tracking-tight">Auction Vehicles</h1>
          <span className="text-xs text-muted-foreground bg-muted px-2.5 py-1 rounded-full font-medium">
            {total.toLocaleString()} vehicles
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex border rounded-md overflow-hidden h-8">
            <button onClick={() => setViewMode("grid")} className={`px-2.5 transition-colors ${viewMode === "grid" ? "bg-foreground text-background" : "hover:bg-accent"}`}>
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button onClick={() => setViewMode("list")} className={`px-2.5 transition-colors ${viewMode === "list" ? "bg-foreground text-background" : "hover:bg-accent"}`}>
              <AlignJustify className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Auction Day Picker */}
      {auctionDays.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Auction Days</span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            <button
              onClick={() => update({ auctionDay: "" })}
              className={`flex-shrink-0 px-4 py-2.5 rounded-lg border text-xs font-medium transition-all ${
                !get("auctionDay")
                  ? "bg-primary text-primary-foreground border-primary shadow-sm"
                  : "bg-card hover:bg-accent border-input"
              }`}
            >
              All Days
            </button>
            {auctionDays.map(d => {
              const { label, day } = formatDayLabel(d.date);
              const isSelected = get("auctionDay") === d.date;
              return (
                <button
                  key={d.date}
                  onClick={() => update({ auctionDay: isSelected ? "" : d.date })}
                  className={`flex-shrink-0 min-w-[80px] px-3 py-2 rounded-lg border text-center transition-all ${
                    isSelected
                      ? "bg-primary text-primary-foreground border-primary shadow-sm"
                      : "bg-card hover:bg-accent border-input"
                  }`}
                >
                  <div className="text-[10px] font-medium opacity-70">{label}</div>
                  <div className="text-lg font-bold leading-tight">{day}</div>
                  <div className="text-[10px] opacity-60">{d.count.toLocaleString()}</div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-card border rounded-lg p-4 space-y-3">
        {/* Row 1: Make, Model, Chassis Code, Year range */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <select value={get("maker")} onChange={e => update({ maker: e.target.value })} className={sel}>
            <option value="">All Makes</option>
            {filterOptions.makers.map(m => <option key={m.value} value={m.value}>{m.value} ({m.count})</option>)}
          </select>

          <select value={get("model")} onChange={e => update({ model: e.target.value })} className={sel} disabled={!get("maker") || modelsLoading}>
            <option value="">{get("maker") ? (modelsLoading ? "Loading..." : models.length ? "All Models" : "No models found") : "Select Make first"}</option>
            {models.map(m => <option key={m.value} value={m.value}>{m.value} ({m.count})</option>)}
          </select>

          <select value={get("chassisCode")} onChange={e => update({ chassisCode: e.target.value })} className={sel} disabled={chassisCodes.length === 0 && !get("model")}>
            <option value="">{get("model") ? (chassisCodes.length ? "All Chassis" : "No chassis data") : "Select Model first"}</option>
            {chassisCodes.map(c => <option key={c.value} value={c.value}>{c.value} ({c.count})</option>)}
          </select>

          <select value={get("yearFrom")} onChange={e => update({ yearFrom: e.target.value })} className={sel}>
            <option value="">Year From</option>
            {YEARS.slice().reverse().map(y => <option key={y} value={y}>{y}</option>)}
          </select>

          <select value={get("yearTo")} onChange={e => update({ yearTo: e.target.value })} className={sel}>
            <option value="">Year To</option>
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>

        {/* Row 2: Auction House, Price, Rating, Sort */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <select value={get("auctionHouse")} onChange={e => update({ auctionHouse: e.target.value })} className={sel}>
            <option value="">All Auctions</option>
            {filterOptions.auctionHouses.map(h => <option key={h.value} value={h.value}>{h.value}</option>)}
          </select>

          <select value={get("minPrice")} onChange={e => update({ minPrice: e.target.value })} className={sel}>
            <option value="">Min Price</option>
            <option value="10000">¥10,000+</option>
            <option value="50000">¥50,000+</option>
            <option value="100000">¥100,000+</option>
            <option value="300000">¥300,000+</option>
            <option value="500000">¥500,000+</option>
            <option value="1000000">¥1,000,000+</option>
            <option value="3000000">¥3,000,000+</option>
            <option value="5000000">¥5,000,000+</option>
          </select>

          <select value={get("maxPrice")} onChange={e => update({ maxPrice: e.target.value })} className={sel}>
            <option value="">Max Price</option>
            <option value="50000">~¥50,000</option>
            <option value="100000">~¥100,000</option>
            <option value="300000">~¥300,000</option>
            <option value="500000">~¥500,000</option>
            <option value="1000000">~¥1,000,000</option>
            <option value="3000000">~¥3,000,000</option>
            <option value="5000000">~¥5,000,000</option>
            <option value="10000000">~¥10,000,000</option>
          </select>

          <select value={get("rating")} onChange={e => update({ rating: e.target.value })} className={sel}>
            <option value="">Any Rating</option>
            <option value="S">S</option>
            <option value="6">6+</option>
            <option value="5">5+</option>
            <option value="4.5">4.5+</option>
            <option value="4">4+</option>
            <option value="3.5">3.5+</option>
          </select>

          <select value={get("sort") || "firstSeen"} onChange={e => update({ sort: e.target.value })} className={sel}>
            <option value="firstSeen">Sort: Newest</option>
            <option value="auctionDateNorm">Sort: Auction Date</option>
            <option value="startPrice">Sort: Price</option>
            <option value="maker">Sort: Maker</option>
            <option value="year">Sort: Year</option>
          </select>
        </div>

        {/* Clear filters */}
        {activeFilters > 0 && (
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-muted-foreground">{activeFilters} filter{activeFilters > 1 ? "s" : ""} active</span>
            <button onClick={clearAll} className="h-8 px-3 rounded-md border border-destructive/30 text-destructive text-xs font-medium hover:bg-destructive/5 transition-colors flex items-center gap-1.5">
              <X className="h-3 w-3" /> Clear All Filters
            </button>
          </div>
        )}
      </div>

      {/* Table/Grid with loading overlay */}
      <div className="relative">
        {/* Loading overlay — shown over existing data during refetch */}
        {loading && !initialLoad && (
          <div className="absolute inset-0 bg-background/60 z-10 flex items-center justify-center rounded-lg">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Empty state */}
        {auctions.length === 0 && !loading ? (
          <div className="py-20 text-center">
            <Car className="h-10 w-10 mx-auto text-muted-foreground/20 mb-3" />
            <p className="text-sm text-muted-foreground">No vehicles match your filters</p>
            {activeFilters > 0 && (
              <button onClick={clearAll} className="text-xs text-primary hover:underline mt-2">Clear all filters</button>
            )}
          </div>
        ) : viewMode === "grid" ? (
          /* Grid */
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {auctions.map(a => (
              <Link key={a.id} href={`/dashboard/${a.id}`} className="group">
                <div className="bg-card border rounded-lg overflow-hidden hover:shadow-md hover:border-primary/20 transition-all duration-150">
                  <div className="aspect-[16/10] bg-muted relative overflow-hidden">
                    {a.imageUrl ? (
                      <Image src={proxyUrl(a.imageUrl)} alt="" fill className="object-cover group-hover:scale-[1.03] transition-transform duration-200" sizes="(max-width: 640px) 50vw, 25vw" loading="lazy" unoptimized />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-muted-foreground/20"><Car className="h-6 w-6" /></div>
                    )}
                    {a.rating && (
                      <span className="absolute top-1.5 right-1.5 text-[9px] font-bold bg-black/60 text-white px-1.5 py-0.5 rounded">
                        {a.rating}
                      </span>
                    )}
                  </div>
                  <div className="p-3 space-y-1.5">
                    <p className="text-sm font-semibold truncate leading-tight group-hover:text-primary transition-colors">
                      {a.maker || "Unknown"} {a.model || "Vehicle"}
                    </p>
                    <p className="text-xs text-muted-foreground truncate">
                      {[a.year, a.mileage, a.color].filter(Boolean).join(" · ")}
                    </p>
                    <div className="flex items-center justify-between pt-0.5">
                      <span className="text-sm font-bold">
                        {a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}
                      </span>
                    </div>
                    <p className="text-[10px] text-muted-foreground truncate">{a.auctionHouse} · {a.auctionDate}</p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          /* List — data-dense table */
          <div className="bg-card border rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="text-left font-medium text-muted-foreground px-3 py-2.5 w-[56px]"></th>
                  <th className="text-left font-medium text-muted-foreground px-2 py-2.5">Vehicle</th>
                  <th className="text-left font-medium text-muted-foreground px-2 py-2.5 hidden md:table-cell">Auction</th>
                  <th className="text-left font-medium text-muted-foreground px-2 py-2.5 hidden lg:table-cell">Specs</th>
                  <th className="text-center font-medium text-muted-foreground px-2 py-2.5 hidden sm:table-cell w-[60px]">Score</th>
                  <th className="text-left font-medium text-muted-foreground px-2 py-2.5 hidden lg:table-cell">Date</th>
                  <th className="text-right font-medium text-muted-foreground px-3 py-2.5">Price</th>
                </tr>
              </thead>
              <tbody>
                {auctions.map(a => (
                  <tr key={a.id} className="border-b last:border-0 hover:bg-accent/40 transition-colors cursor-pointer group relative" onClick={() => router.push(`/dashboard/${a.id}`)}>
                    <td className="px-3 py-2">
                      <Link href={`/dashboard/${a.id}`} className="absolute inset-0 z-[1]" aria-label={`${a.maker || ""} ${a.model || "Vehicle"}`} />
                      <div className="w-[48px] h-[34px] rounded overflow-hidden bg-muted relative">
                        {a.imageUrl ? (
                          <Image src={proxyUrl(a.imageUrl)} alt="" fill className="object-cover" sizes="48px" loading="lazy" unoptimized />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-muted-foreground/20"><Car className="h-3.5 w-3.5" /></div>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-2">
                      <p className="font-medium truncate max-w-[220px] group-hover:text-primary transition-colors">{a.maker || "Unknown"} {a.model || "Vehicle"}</p>
                      <p className="text-[10px] text-muted-foreground truncate">{a.grade || ""}</p>
                    </td>
                    <td className="px-2 py-2 hidden md:table-cell">
                      <p className="truncate max-w-[160px]">{a.auctionHouse}</p>
                      <p className="text-[10px] text-muted-foreground">{a.location}</p>
                    </td>
                    <td className="px-2 py-2 hidden lg:table-cell text-muted-foreground">
                      {[a.year, a.mileage, a.color].filter(Boolean).join(" · ")}
                    </td>
                    <td className="px-2 py-2 text-center hidden sm:table-cell">
                      {a.rating && <span className="text-[10px] font-bold bg-muted px-1.5 py-0.5 rounded">{a.rating}</span>}
                    </td>
                    <td className="px-2 py-2 hidden lg:table-cell text-muted-foreground text-[10px]">
                      {a.auctionDate}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span className="font-bold">{a.startPrice ? formatPrice(parseFloat(a.startPrice)) : "—"}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {(page - 1) * 40 + 1}–{Math.min(page * 40, total)} of {total.toLocaleString()}
          </span>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" disabled={page <= 1} onClick={() => goPage(page - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = page <= 3 ? i + 1 : page + i - 2;
              if (p < 1 || p > totalPages) return null;
              return (
                <Button key={p} variant={p === page ? "default" : "ghost"} size="sm" className="h-8 w-8 p-0 text-xs" onClick={() => goPage(p)}>
                  {p}
                </Button>
              );
            })}
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" disabled={page >= totalPages} onClick={() => goPage(page + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function CustomerAuctions() {
  return (
    <Suspense fallback={
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-6 w-36 bg-muted animate-pulse rounded" />
            <div className="h-6 w-20 bg-muted animate-pulse rounded-full" />
          </div>
        </div>
        <div className="flex gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 w-20 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
        <div className="h-24 bg-muted animate-pulse rounded-lg" />
        <div className="space-y-1">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-12 bg-muted/50 animate-pulse rounded" />
          ))}
        </div>
      </div>
    }>
      <Content />
    </Suspense>
  );
}
