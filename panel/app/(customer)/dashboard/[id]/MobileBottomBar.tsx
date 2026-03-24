"use client";

import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useNavigationContext } from "../../components/NavigationContext";

interface Props {
  auctionId: number;
}

export function MobileBottomBar({ auctionId }: Props) {
  const navCtx = useNavigationContext();

  const { prevId, nextId, index } = navCtx?.getAdjacentIds(auctionId) ?? { prevId: null, nextId: null, index: -1 };
  const totalCount = navCtx?.totalCount ?? 0;

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
