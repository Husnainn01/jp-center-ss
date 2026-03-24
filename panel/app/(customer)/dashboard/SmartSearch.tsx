"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Search, X, Calendar, Wrench, Building2, Car, Hash } from "lucide-react";

// ── Known data for parser matching ──────────────────────────────────────────

const KNOWN_MAKERS = new Set([
  "TOYOTA", "LEXUS", "NISSAN", "HONDA", "MAZDA", "MITSUBISHI", "SUBARU",
  "DAIHATSU", "SUZUKI", "ISUZU", "HINO", "BMW", "MERCEDES", "MERCEDES-BENZ",
  "AUDI", "VOLKSWAGEN", "PORSCHE", "VOLVO", "MINI", "PEUGEOT", "FIAT",
  "ALFA ROMEO", "CHEVROLET", "FORD", "DODGE", "CHRYSLER", "JEEP", "CADILLAC",
  "JAGUAR", "FERRARI", "MASERATI", "BENTLEY", "TESLA", "RENAULT", "CITROEN",
  "OPEL", "SMART", "ROVER", "LAMBORGHINI", "BYD",
]);

// Auction house prefixes — match "USS" in "USS NAGOYA"
// Backend uses ILIKE so partial matches work (e.g. "USS" matches "USS Tokyo", "USS Nagoya")
// Note: "NISSAN" excluded because it conflicts with the car maker.
const AUCTION_PREFIXES = [
  "Honda AA", "SUZUKI AA",  // two-word prefixes first (greedy match)
  "USS", "TAA", "IAA", "HAA", "JU", "KCAA", "ARAI", "NAA", "LAA", "CAA",
  "ZIP", "AUCNET", "BAYAUC", "MIRIVE", "HERO", "LUM", "Aux",
];

// ── Parser ──────────────────────────────────────────────────────────────────

export interface ParsedFilters {
  chassisCode?: string;
  maker?: string;
  yearFrom?: string;
  yearTo?: string;
  auctionHouse?: string;
  search?: string;
}

export interface ParsedTag {
  type: "chassis" | "maker" | "year" | "auction" | "search";
  label: string;
  value: string;
  key: string; // param key for removal
}

export function parseSearchInput(text: string): { filters: ParsedFilters; tags: ParsedTag[] } {
  const filters: ParsedFilters = {};
  const tags: ParsedTag[] = [];
  if (!text.trim()) return { filters, tags };

  let remaining = text.trim();

  // 1. Year range: 2015-2020
  const yearRangeMatch = remaining.match(/\b((?:19|20)\d{2})\s*[-–]\s*((?:19|20)\d{2})\b/);
  if (yearRangeMatch) {
    filters.yearFrom = yearRangeMatch[1];
    filters.yearTo = yearRangeMatch[2];
    tags.push({ type: "year", label: `${yearRangeMatch[1]}–${yearRangeMatch[2]}`, value: `${yearRangeMatch[1]}-${yearRangeMatch[2]}`, key: "year" });
    remaining = remaining.replace(yearRangeMatch[0], " ").trim();
  }

  // 2. Auction house: match known prefixes
  // Backend uses ILIKE so "USS Nagoya" matches even if user types "USS NAGOYA"
  const upperRemaining = remaining.toUpperCase();
  for (const prefix of AUCTION_PREFIXES) {
    const prefixUpper = prefix.toUpperCase();
    const idx = upperRemaining.indexOf(prefixUpper);
    if (idx !== -1) {
      // Extract prefix + next word as the auction house name
      const afterPrefix = remaining.substring(idx + prefix.length).trim();
      const nextWord = afterPrefix.match(/^([A-Za-z]\S*)/); // next word starting with letter
      let auctionName = prefix;
      let matchLen = prefix.length;

      if (nextWord && nextWord[1].length > 1) {
        auctionName = prefix + " " + nextWord[1];
        matchLen = prefix.length + 1 + nextWord[1].length;
      }

      filters.auctionHouse = auctionName.trim();
      tags.push({ type: "auction", label: auctionName.trim(), value: auctionName.trim(), key: "auctionHouse" });
      remaining = (remaining.substring(0, idx) + remaining.substring(idx + matchLen)).trim();
      break;
    }
  }
  remaining = remaining.trim();

  // 3. Single year (if no range was found): standalone 19XX or 20XX
  if (!filters.yearFrom) {
    const singleYear = remaining.match(/\b((?:19|20)\d{2})\b/);
    if (singleYear) {
      filters.yearFrom = singleYear[1];
      filters.yearTo = singleYear[1];
      tags.push({ type: "year", label: singleYear[1], value: singleYear[1], key: "year" });
      remaining = remaining.replace(singleYear[0], " ").trim();
    }
  }

  // 4. Chassis code: patterns like DBA-GP5, GP5, ZVW30, DAA-ZE4
  const chassisMatch = remaining.match(/\b([A-Z]{2,4}-[A-Z0-9]{2,}(?:-\d+)?)\b/i)
    || remaining.match(/\b([A-Z]{1,4}\d{2,}[A-Z]?)\b/); // ZVW30, GP5, GK3
  if (chassisMatch) {
    const code = chassisMatch[1].toUpperCase();
    // Make sure it's not a maker we already matched
    if (!KNOWN_MAKERS.has(code)) {
      filters.chassisCode = code;
      tags.push({ type: "chassis", label: code, value: code, key: "chassisCode" });
      remaining = remaining.replace(chassisMatch[0], " ").trim();
    }
  }

  // 5. Known maker
  const words = remaining.toUpperCase().split(/\s+/);
  for (const word of words) {
    if (KNOWN_MAKERS.has(word)) {
      filters.maker = word;
      tags.push({ type: "maker", label: word, value: word, key: "maker" });
      remaining = remaining.replace(new RegExp(`\\b${word}\\b`, "i"), " ").trim();
      break;
    }
  }
  // Also check two-word makers
  const twoWordMakers = ["ALFA ROMEO", "MERCEDES BENZ", "MERCEDES-BENZ"];
  for (const m of twoWordMakers) {
    if (remaining.toUpperCase().includes(m)) {
      filters.maker = m;
      tags.push({ type: "maker", label: m, value: m, key: "maker" });
      remaining = remaining.replace(new RegExp(m, "i"), " ").trim();
      break;
    }
  }

  // 6. Everything left = free text search
  remaining = remaining.replace(/\s+/g, " ").trim();
  if (remaining) {
    filters.search = remaining;
    tags.push({ type: "search", label: remaining, value: remaining, key: "search" });
  }

  return { filters, tags };
}

// ── Hint texts (rotate in placeholder) ──────────────────────────────────────

const HINT_EXAMPLES = [
  "GP5 USS NAGOYA 2015-2020",
  "TOYOTA Prius",
  "DBA-ZVW30 2018",
  "HONDA Fit 2015-2020",
  "TAA KANTO",
  "SUZUKI Swift 2020",
];

// ── Component ───────────────────────────────────────────────────────────────

interface DayOption { date: string; count: number }

interface Props {
  onFiltersChange: (params: Record<string, string>) => void;
  auctionDays: DayOption[];
  selectedDay: string;
  onDaySelect: (day: string) => void;
  sort: string;
  onSortChange: (sort: string) => void;
  total: number;
  activeFilters: Record<string, string>; // current filters from URL params
}

function formatDayLabel(dateStr: string): { label: string; day: string } {
  const d = new Date(dateStr + "T00:00:00");
  const jstNow = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Tokyo" }));
  const today = new Date(jstNow.getFullYear(), jstNow.getMonth(), jstNow.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const day = d.getDate().toString();
  if (d.getTime() === today.getTime()) return { label: "Today", day };
  if (d.getTime() === tomorrow.getTime()) return { label: "Tmrw", day };
  return { label: d.toLocaleDateString("en", { weekday: "short" }), day };
}

// Build tags from active URL filter params (for display when page loads with saved filters)
function tagsFromParams(params: Record<string, string>): ParsedTag[] {
  const tags: ParsedTag[] = [];
  if (params.chassisCode) tags.push({ type: "chassis", label: params.chassisCode, value: params.chassisCode, key: "chassisCode" });
  if (params.maker) tags.push({ type: "maker", label: params.maker, value: params.maker, key: "maker" });
  if (params.yearFrom && params.yearTo && params.yearFrom !== params.yearTo) {
    tags.push({ type: "year", label: `${params.yearFrom}–${params.yearTo}`, value: `${params.yearFrom}-${params.yearTo}`, key: "year" });
  } else if (params.yearFrom) {
    tags.push({ type: "year", label: params.yearFrom, value: params.yearFrom, key: "year" });
  }
  if (params.auctionHouse) tags.push({ type: "auction", label: params.auctionHouse, value: params.auctionHouse, key: "auctionHouse" });
  if (params.search) tags.push({ type: "search", label: params.search, value: params.search, key: "search" });
  return tags;
}

export function SmartSearch({ onFiltersChange, auctionDays, selectedDay, onDaySelect, sort, onSortChange, total, activeFilters }: Props) {
  const [inputValue, setInputValue] = useState("");
  const [tags, setTags] = useState<ParsedTag[]>([]);
  const [hintIdx, setHintIdx] = useState(0);
  const [initialized, setInitialized] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Initialize tags from URL params (restored from localStorage or direct URL)
  useEffect(() => {
    if (initialized) return;
    const hasActiveFilters = Object.values(activeFilters).some(v => v);
    if (hasActiveFilters) {
      const restoredTags = tagsFromParams(activeFilters);
      setTags(restoredTags);
      // Reconstruct input text from active filters
      const parts: string[] = [];
      if (activeFilters.maker) parts.push(activeFilters.maker);
      if (activeFilters.search) parts.push(activeFilters.search);
      if (activeFilters.chassisCode) parts.push(activeFilters.chassisCode);
      if (activeFilters.auctionHouse) parts.push(activeFilters.auctionHouse);
      if (activeFilters.yearFrom && activeFilters.yearTo && activeFilters.yearFrom !== activeFilters.yearTo) {
        parts.push(`${activeFilters.yearFrom}-${activeFilters.yearTo}`);
      } else if (activeFilters.yearFrom) {
        parts.push(activeFilters.yearFrom);
      }
      setInputValue(parts.join(" "));
    }
    setInitialized(true);
  }, [activeFilters, initialized]);

  // Rotate placeholder hints
  useEffect(() => {
    const interval = setInterval(() => {
      setHintIdx(i => (i + 1) % HINT_EXAMPLES.length);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  // Parse and emit filters (debounced)
  const emitFilters = useCallback((text: string) => {
    const { filters, tags: newTags } = parseSearchInput(text);
    setTags(newTags);

    const params: Record<string, string> = {};
    if (filters.chassisCode) params.chassisCode = filters.chassisCode;
    if (filters.maker) params.maker = filters.maker;
    if (filters.yearFrom) params.yearFrom = filters.yearFrom;
    if (filters.yearTo) params.yearTo = filters.yearTo;
    if (filters.auctionHouse) params.auctionHouse = filters.auctionHouse;
    if (filters.search) params.search = filters.search;

    onFiltersChange(params);
  }, [onFiltersChange]);

  function handleInputChange(text: string) {
    setInputValue(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => emitFilters(text), 300);
  }

  function removeTag(key: string) {
    // Rebuild input without the removed tag's value
    const tag = tags.find(t => t.key === key);
    if (!tag) return;
    let newInput = inputValue;
    // Try to remove the tag's original text from input
    if (tag.type === "year" && tag.value.includes("-")) {
      newInput = newInput.replace(/\b\d{4}\s*[-–]\s*\d{4}\b/, "").trim();
    } else if (tag.type === "year") {
      newInput = newInput.replace(new RegExp(`\\b${tag.value}\\b`), "").trim();
    } else {
      newInput = newInput.replace(new RegExp(tag.value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"), "").trim();
    }
    setInputValue(newInput);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => emitFilters(newInput), 100);
  }

  function clearAll() {
    setInputValue("");
    setTags([]);
    onFiltersChange({});
    onDaySelect("");
    inputRef.current?.focus();
  }

  const tagColors: Record<string, string> = {
    chassis: "bg-orange-500/15 text-orange-400 border-orange-500/20",
    maker: "bg-blue-500/15 text-blue-400 border-blue-500/20",
    year: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
    auction: "bg-purple-500/15 text-purple-400 border-purple-500/20",
    search: "bg-muted text-muted-foreground border-border",
  };

  const tagIcons: Record<string, typeof Search> = {
    chassis: Wrench,
    maker: Car,
    year: Calendar,
    auction: Building2,
    search: Hash,
  };

  const hasFilters = tags.length > 0 || selectedDay;

  return (
    <div className="space-y-2">
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={e => handleInputChange(e.target.value)}
          placeholder={`Search: ${HINT_EXAMPLES[hintIdx]}`}
          className="w-full h-10 pl-10 pr-20 rounded border border-border bg-card text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-blue-500/40 focus:border-blue-500/40 transition-colors"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {hasFilters && (
            <button onClick={clearAll} className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors" title="Clear all">
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <span className="text-[10px] font-mono text-muted-foreground/50 px-1">
            {total.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Parsed tags */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map(tag => {
            const Icon = tagIcons[tag.type] || Hash;
            return (
              <span
                key={tag.key}
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-medium ${tagColors[tag.type] || tagColors.search}`}
              >
                <Icon className="h-3 w-3" />
                {tag.type !== "search" && <span className="opacity-60">{tag.type}:</span>}
                {tag.label}
                <button onClick={() => removeTag(tag.key)} className="ml-0.5 opacity-50 hover:opacity-100">
                  <X className="h-2.5 w-2.5" />
                </button>
              </span>
            );
          })}
        </div>
      )}

      {/* Day picker + Sort row */}
      <div className="flex items-center gap-2 overflow-x-auto">
        <div className="flex gap-1 flex-shrink-0">
          <button
            onClick={() => onDaySelect("")}
            className={`px-2 py-1 rounded border text-[11px] font-medium transition-colors ${
              !selectedDay
                ? "bg-blue-500 text-white border-blue-500"
                : "bg-card text-muted-foreground border-border hover:text-foreground hover:border-ring/30"
            }`}
          >
            All
          </button>
          {auctionDays.slice(0, 7).map(d => {
            const { label, day } = formatDayLabel(d.date);
            const isSelected = selectedDay === d.date;
            return (
              <button
                key={d.date}
                onClick={() => onDaySelect(isSelected ? "" : d.date)}
                className={`px-2 py-1 rounded border text-center transition-colors min-w-[44px] ${
                  isSelected
                    ? "bg-blue-500 text-white border-blue-500"
                    : "bg-card text-muted-foreground border-border hover:text-foreground hover:border-ring/30"
                }`}
              >
                <div className="text-[9px] opacity-60">{label}</div>
                <div className="text-xs font-bold leading-tight">{day}</div>
              </button>
            );
          })}
        </div>

        <div className="ml-auto flex-shrink-0">
          <select
            value={sort}
            onChange={e => onSortChange(e.target.value)}
            className="h-7 rounded border border-border bg-card px-2 text-[11px] text-muted-foreground focus:outline-none focus:ring-1 focus:ring-blue-500/40 cursor-pointer appearance-none"
          >
            <option value="firstSeen">Newest</option>
            <option value="auctionDateNorm">Auction Date</option>
            <option value="startPrice">Price</option>
            <option value="maker">Maker</option>
            <option value="year">Year</option>
          </select>
        </div>
      </div>
    </div>
  );
}
