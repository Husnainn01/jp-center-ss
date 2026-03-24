"use client";

import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useNavigationContext } from "../../components/NavigationContext";

interface Props {
  auctionId: number;
}

export function MobileBottomBar({ auctionId }: Props) {
  const navCtx = useNavigationContext();

  // Read nav state with sessionStorage fallback
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

  if (index === -1) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-background/95 backdrop-blur-md border-t border-border md:hidden">
      <div className="flex items-center justify-between h-14 px-3">
        {/* Prev */}
        {prevId ? (
          <Link
            href={`/dashboard/${prevId}`}
            className="flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors min-w-[80px]"
          >
            <ChevronLeft className="h-4 w-4 flex-shrink-0" />
            <span className="truncate">Prev</span>
          </Link>
        ) : (
          <div className="min-w-[80px]" />
        )}

        {/* Position */}
        <span className="text-[11px] font-mono text-muted-foreground">
          {index + 1}/{totalCount}
        </span>

        {/* Next */}
        {nextId ? (
          <Link
            href={`/dashboard/${nextId}`}
            className="flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors min-w-[80px] justify-end"
          >
            <span className="truncate">Next</span>
            <ChevronRight className="h-4 w-4 flex-shrink-0" />
          </Link>
        ) : (
          <div className="min-w-[80px]" />
        )}
      </div>
    </div>
  );
}
