"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/lib/format";
import { useNavigationContext } from "../../components/NavigationContext";
import { AddToListButton } from "../../components/AddToListButton";
import { SendForBiddingButton } from "../../components/SendForBiddingButton";

interface Props {
  auctionId: number;
  title: string;
  price: number | null;
}

export function StickyHeader({ auctionId, title, price }: Props) {
  const [visible, setVisible] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const navCtx = useNavigationContext();

  // Read nav state with sessionStorage fallback (same as VehicleNavigation)
  let prevId: number | null = null, nextId: number | null = null, index = -1, totalCount = 0;
  const fromCtx = navCtx?.getAdjacentIds(auctionId);
  if (fromCtx && fromCtx.index !== -1) {
    ({ prevId, nextId, index } = fromCtx);
    totalCount = navCtx?.totalCount ?? 0;
  } else {
    try {
      const raw = sessionStorage.getItem("auction-nav-context");
      if (raw) {
        const data = JSON.parse(raw);
        const ids: number[] = data.ids || [];
        const idx = ids.indexOf(auctionId);
        if (idx !== -1) {
          prevId = idx > 0 ? ids[idx - 1] : null;
          nextId = idx < ids.length - 1 ? ids[idx + 1] : null;
          index = idx;
          totalCount = data.total || 0;
        }
      }
    } catch {}
  }

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => setVisible(!entry.isIntersecting),
      { threshold: 0 }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  return (
    <>
      {/* Sentinel — when this scrolls out, sticky header appears */}
      <div ref={sentinelRef} className="h-0" />

      {/* Sticky header bar */}
      <div
        className={`fixed top-0 left-0 right-0 z-40 bg-background/95 backdrop-blur-md border-b border-border transition-all duration-200 hidden md:block ${
          visible ? "translate-y-0 opacity-100" : "-translate-y-full opacity-0 pointer-events-none"
        }`}
      >
        <div className="max-w-[1600px] mx-auto px-4 h-12 flex items-center justify-between gap-4">
          {/* Left: Vehicle info */}
          <div className="flex items-center gap-3 min-w-0">
            {index !== -1 && (
              <span className="text-[11px] font-mono text-muted-foreground flex-shrink-0">
                {index + 1}/{totalCount}
              </span>
            )}
            <p className="text-sm font-semibold truncate text-foreground">{title}</p>
            {price && (
              <span className="text-sm font-mono font-bold text-blue-400 flex-shrink-0">
                {formatPrice(price)}
              </span>
            )}
          </div>

          {/* Right: Actions + navigation */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <AddToListButton auctionId={auctionId} />
            <SendForBiddingButton auctionId={auctionId} />

            {index !== -1 && (
              <div className="flex items-center gap-1 ml-2">
                {prevId ? (
                  <Link href={`/dashboard/${prevId}`} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-8 w-8 p-0")}>
                    <ChevronLeft className="h-4 w-4" />
                  </Link>
                ) : (
                  <Button variant="outline" size="sm" className="h-8 w-8 p-0" disabled><ChevronLeft className="h-4 w-4" /></Button>
                )}
                {nextId ? (
                  <Link href={`/dashboard/${nextId}`} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-8 w-8 p-0")}>
                    <ChevronRight className="h-4 w-4" />
                  </Link>
                ) : (
                  <Button variant="outline" size="sm" className="h-8 w-8 p-0" disabled><ChevronRight className="h-4 w-4" /></Button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
