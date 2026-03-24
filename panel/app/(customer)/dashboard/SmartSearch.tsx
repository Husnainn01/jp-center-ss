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
// Note: "NISSAN" excluded because it conflicts with the car maker.
// Auction house "NISSAN Osaka" will be matched via "search" instead.
const AUCTION_PREFIXES = [
  "USS", "TAA", "IAA", "HAA", "JU", "KCAA", "ARAI", "Honda AA", "NAA",
  "ZIP", "AUCNET", "Aux", "SUZUKI AA", "LUM",
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

  // 2. Auction house: match known prefixes (must check before maker since "NISSAN" could be both)
  const upperRemaining = remaining.toUpperCase();
  for (const prefix of AUCTION_PREFIXES) {
    const prefixUpper = prefix.toUpperCase();
    const idx = upperRemaining.indexOf(prefixUpper);
    if (idx !== -1) {
      // Extract the full auction house name (prefix + next word if exists)
      const afterPrefix = remaining.substring(idx + prefix.length).trim();
      const nextWord = afterPrefix.match(/^(\S+)/);
      let auctionName: string;

      // Check if next word looks like a location name (not a number, not a chassis code)
      const nextWordStr = nextWord ? nextWord[1] : "";
      if (nextWordStr && nextWordStr.length > 1 && !nextWordStr.match(/^\d/) && /^[A-Za-z]/.test(nextWordStr)) {
        auctionName = prefix + " " + nextWordStr;
        remaining = remaining.substring(0, idx) + remaining.substring(idx + prefix.length + 1 + nextWordStr.length);
      } else if (prefix === "AUCNET" || prefix === "Aux") {
        // Single-word auction houses
        auctionName = prefix === "Aux" ? "Aux Mobility" : "AUCNET";
        remaining = remaining.substring(0, idx) + remaining.substring(idx + prefix.length);
      } else {
        auctionName = prefix;
        remaining = remaining.substring(0, idx) + remaining.substring(idx + prefix.length);
      }

      filters.auctionHouse = auctionName.trim();
      tags.push({ type: "auction", label: auctionName.trim(), value: auctionName.trim(), key: "auctionHouse" });
      break; // only one auction house at a time
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

export function SmartSearch({ onFiltersChange, auctionDays, selectedDay, onDaySelect, sort, onSortChange, total }: Props) {
  const [inputValue, setInputValue] = useState("");
  const [tags, setTags] = useState<ParsedTag[]>([]);
  const [hintIdx, setHintIdx] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
