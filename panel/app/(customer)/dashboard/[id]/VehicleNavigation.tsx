"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, ChevronRight, ArrowLeft } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { useNavigationContext } from "../../components/NavigationContext";
import { cn } from "@/lib/utils";

interface Props {
  auctionId: number;
}

export function VehicleNavigation({ auctionId }: Props) {
  const router = useRouter();
  const navCtx = useNavigationContext();

  // Read navigation state — also try sessionStorage directly as fallback
  // (context ref may be stale if the listing page updated it after this page mounted)
  const getNavState = useCallback(() => {
    const fromCtx = navCtx?.getAdjacentIds(auctionId);
    if (fromCtx && fromCtx.index !== -1) return fromCtx;
    // Fallback: read directly from sessionStorage
    try {
      const raw = sessionStorage.getItem("auction-nav-context");
      if (raw) {
        const data = JSON.parse(raw);
        const ids: number[] = data.ids || [];
        const idx = ids.indexOf(auctionId);
        if (idx !== -1) {
          return {
            prevId: idx > 0 ? ids[idx - 1] : null,
            nextId: idx < ids.length - 1 ? ids[idx + 1] : null,
            index: idx,
          };
        }
      }
    } catch {}
    return { prevId: null, nextId: null, index: -1 };
  }, [auctionId, navCtx]);

  const [navState, setNavState] = useState(() => getNavState());

  // Re-read on mount and when auctionId changes (client-side navigation)
  useEffect(() => {
    setNavState(getNavState());
  }, [auctionId, getNavState]);

  const { prevId, nextId, index } = navState;
  const backUrl = navCtx?.getBackUrl() ?? "/dashboard";
  const totalCount = navCtx?.totalCount ?? (() => {
    try {
      const raw = sessionStorage.getItem("auction-nav-context");
      if (raw) return JSON.parse(raw).total || 0;
    } catch {}
    return 0;
  })();
  const hasContext = index !== -1;

  // Prefetch adjacent vehicle pages for instant navigation
  useEffect(() => {
    if (prevId) router.prefetch(`/dashboard/${prevId}`);
    if (nextId) router.prefetch(`/dashboard/${nextId}`);
  }, [prevId, nextId, router]);

  // Keyboard navigation: ArrowLeft = prev, ArrowRight = next
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't intercept when typing in input/textarea or when lightbox is open
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (document.querySelector("[data-lightbox-open]")) return;

      if (e.key === "ArrowLeft" && prevId) {
        e.preventDefault();
        router.push(`/dashboard/${prevId}`);
      } else if (e.key === "ArrowRight" && nextId) {
        e.preventDefault();
        router.push(`/dashboard/${nextId}`);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [prevId, nextId, router]);

  return (
    <div className="flex items-center justify-between gap-2 mb-4">
      {/* Back link */}
      <Link
        href={backUrl}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        <span className="hidden sm:inline">Back to listings</span>
        <span className="sm:hidden">Back</span>
      </Link>

      {/* Position indicator + Prev/Next */}
      {hasContext && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {index + 1} of {totalCount.toLocaleString()}
          </span>

          <div className="flex items-center gap-1">
            {prevId ? (
              <Link href={`/dashboard/${prevId}`} aria-label="Previous vehicle" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-8 w-8 p-0")}>
                <ChevronLeft className="h-4 w-4" />
              </Link>
            ) : (
              <Button variant="outline" size="sm" className="h-8 w-8 p-0" disabled>
                <ChevronLeft className="h-4 w-4" />
              </Button>
            )}

            <span className="text-xs text-muted-foreground min-w-[3ch] text-center sm:hidden">
              {index + 1}/{totalCount}
            </span>

            {nextId ? (
              <Link href={`/dashboard/${nextId}`} aria-label="Next vehicle" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-8 w-8 p-0")}>
                <ChevronRight className="h-4 w-4" />
              </Link>
            ) : (
              <Button variant="outline" size="sm" className="h-8 w-8 p-0" disabled>
                <ChevronRight className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
