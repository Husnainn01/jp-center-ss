"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Gavel, Check, Loader2, X } from "lucide-react";

interface Props {
  auctionId: number;
  variant?: "default" | "compact";
}

function BidForm({ auctionId, onDone }: { auctionId: number; onDone: (refCode?: string) => void }) {
  const [maxBid, setMaxBid] = useState("");
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function send() {
    setSending(true);
    setError("");

    try {
      const res = await fetch("/api/bid-to-crm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          auctionId,
          maxBidPrice: maxBid ? maxBid.replace(/[^0-9]/g, "") : undefined,
          note: note || undefined,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Failed to send bid");
        setSending(false);
        return;
      }

      onDone(data.referenceCode);
    } catch {
      setError("Network error. Please try again.");
      setSending(false);
    }
  }

  return (
    <div className="border rounded-lg bg-card p-3 space-y-2 w-64 shadow-lg">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold">Send for Bidding</span>
        <button onClick={() => onDone()} className="text-muted-foreground hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="space-y-1">
        <label className="text-[11px] text-muted-foreground">Max Bid (¥, optional)</label>
        <Input type="number" placeholder="e.g. 500000" value={maxBid} onChange={e => setMaxBid(e.target.value)} className="h-8 text-xs" />
      </div>
      <div className="space-y-1">
        <label className="text-[11px] text-muted-foreground">Note (optional)</label>
        <Input placeholder="Any instructions..." value={note} onChange={e => setNote(e.target.value)} className="h-8 text-xs" />
      </div>
      {error && <p className="text-[11px] text-destructive">{error}</p>}
      <Button size="sm" className="w-full h-8" onClick={send} disabled={sending}>
        {sending ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Gavel className="h-3.5 w-3.5 mr-1.5" />}
        Send
      </Button>
    </div>
  );
}

export function SendForBiddingButton({ auctionId, variant = "default" }: Props) {
  const [showForm, setShowForm] = useState(false);
  const [sent, setSent] = useState(false);
  const [refCode, setRefCode] = useState<string | null>(null);

  function handleDone(referenceCode?: string) {
    setShowForm(false);
    if (referenceCode) {
      setSent(true);
      setRefCode(referenceCode);
    }
  }

  if (sent) {
    return (
      <Badge variant="secondary" className="text-xs gap-1">
        <Check className="h-3 w-3 text-emerald-500" /> Sent{refCode ? ` (${refCode})` : ""}
      </Badge>
    );
  }

  if (showForm) {
    return <BidForm auctionId={auctionId} onDone={handleDone} />;
  }

  if (variant === "compact") {
    return (
      <Button variant="default" size="sm" className="h-7 text-xs" onClick={() => setShowForm(true)}>
        <Gavel className="h-3 w-3 mr-1" /> Bid
      </Button>
    );
  }

  return (
    <Button variant="default" size="sm" onClick={() => setShowForm(true)}>
      <Gavel className="h-3.5 w-3.5 mr-1.5" /> Send for Bidding
    </Button>
  );
}

export function BulkSendForBidding({ auctionIds }: { auctionIds: number[] }) {
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ sent: number; failed: number } | null>(null);

  async function sendAll() {
    setSending(true);
    let sent = 0;
    let failed = 0;

    for (const auctionId of auctionIds) {
      try {
        const res = await fetch("/api/bid-to-crm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ auctionId }),
        });
        if (res.ok) sent++;
        else failed++;
      } catch {
        failed++;
      }
    }

    setResult({ sent, failed });
    setSending(false);
  }

  if (result !== null) {
    return (
      <Badge variant="secondary" className="text-xs gap-1">
        <Check className="h-3 w-3 text-emerald-500" /> {result.sent} sent for bidding
        {result.failed > 0 && `, ${result.failed} failed`}
      </Badge>
    );
  }

  return (
    <Button variant="default" size="sm" onClick={sendAll} disabled={auctionIds.length === 0 || sending}>
      {sending ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Gavel className="h-3.5 w-3.5 mr-1.5" />}
      Send All for Bidding ({auctionIds.length})
    </Button>
  );
}
