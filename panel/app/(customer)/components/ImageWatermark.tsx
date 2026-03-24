"use client";

import { useSession } from "next-auth/react";

/**
 * ImageWatermark — Renders an invisible/semi-visible watermark overlay on images.
 *
 * The watermark contains the user's email + ID + timestamp.
 * It's rendered as a repeating CSS pattern over the image container.
 * If someone screenshots or records the screen, the watermark is captured.
 * The watermark is subtle (low opacity) so it doesn't ruin the viewing experience.
 *
 * Usage: Wrap any image container with <ImageWatermark>
 * <ImageWatermark><img src="..." /></ImageWatermark>
 */
export function ImageWatermark({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const { data: session } = useSession();

  const userId = (session?.user as Record<string, unknown>)?.id || "?";
  const userEmail = session?.user?.email || "?";
  const watermarkText = `${userEmail} | ID:${userId}`;

  return (
    <div className={`relative overflow-hidden ${className}`}>
      {children}
      {/* Watermark overlay — repeating diagonal text */}
      <div
        className="absolute inset-0 pointer-events-none z-10 select-none"
        aria-hidden="true"
        style={{
          backgroundImage: `url("data:image/svg+xml,${encodeURIComponent(
            `<svg xmlns='http://www.w3.org/2000/svg' width='400' height='200'>
              <text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle'
                font-family='monospace' font-size='11' fill='rgba(255,255,255,0.04)'
                transform='rotate(-30, 200, 100)'>${watermarkText}</text>
            </svg>`
          )}")`,
          backgroundRepeat: "repeat",
        }}
      />
    </div>
  );
}
