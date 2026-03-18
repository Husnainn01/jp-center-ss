"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

export function BackButton() {
  const router = useRouter();

  return (
    <button
      onClick={() => router.back()}
      className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-3"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      Back to listings
    </button>
  );
}
