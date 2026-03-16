"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Eye, EyeOff, Save, Check, X, Power, PowerOff, RefreshCw, Globe } from "lucide-react";

interface SiteData {
  id: string;
  name: string;
  url: string;
  userId: string;
  hasPassword: boolean;
  isEnabled: boolean;
  isConnected: boolean;
  lastLogin: string | null;
  lastSync: string | null;
}

const SITE_META: Record<string, { color: string; abbr: string }> = {
  aucnet: { color: "bg-blue-600", abbr: "AN" },
  taa: { color: "bg-red-600", abbr: "TA" },
  uss: { color: "bg-emerald-600", abbr: "US" },
};

export default function SettingsPage() {
  const [sites, setSites] = useState<SiteData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/auction-sites")
      .then((r) => r.json())
      .then((data: SiteData[]) => { setSites(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-center py-10 text-muted-foreground text-sm">Loading...</div>;
  }

  const enabledCount = sites.filter((s) => s.isEnabled).length;
  const connectedCount = sites.filter((s) => s.isConnected).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage auction site connections and credentials
        </p>
      </div>

      {/* Summary */}
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Globe className="h-4 w-4" />
          <span>{sites.length} sites</span>
        </div>
        <Separator orientation="vertical" className="h-4" />
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Check className="h-4 w-4 text-emerald-500" />
          <span>{enabledCount} enabled</span>
        </div>
        <Separator orientation="vertical" className="h-4" />
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <RefreshCw className="h-4 w-4 text-blue-500" />
          <span>{connectedCount} connected</span>
        </div>
      </div>

      {/* Site cards */}
      <div className="space-y-4">
        {sites.map((site) => (
          <SiteCard
            key={site.id}
            site={site}
            onUpdate={(updated) => {
              setSites((prev) => prev.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)));
            }}
          />
        ))}
      </div>
    </div>
  );
}

function SiteCard({
  site,
  onUpdate,
}: {
  site: SiteData;
  onUpdate: (s: Partial<SiteData> & { id: string }) => void;
}) {
  const [userId, setUserId] = useState(site.userId);
  const [password, setPassword] = useState(site.hasPassword ? "••••••••" : "");
  const [showPw, setShowPw] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const meta = SITE_META[site.id] || { color: "bg-gray-500", abbr: "??" };

  async function handleToggle() {
    const res = await fetch("/api/auction-sites", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: site.id, isEnabled: !site.isEnabled }),
    });
    if (res.ok) onUpdate({ id: site.id, isEnabled: !site.isEnabled });
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    try {
      const res = await fetch("/api/auction-sites", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: site.id, userId, password }),
      });
      if (res.ok) {
        setMsg({ ok: true, text: "Credentials saved" });
        onUpdate({ id: site.id, userId, hasPassword: true });
      } else {
        const data = await res.json();
        setMsg({ ok: false, text: data.error || "Failed" });
      }
    } catch {
      setMsg({ ok: false, text: "Network error" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className={!site.isEnabled ? "border-dashed" : ""}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`h-9 w-9 rounded-lg ${meta.color} flex items-center justify-center`}>
              <span className="text-xs font-bold text-white">{meta.abbr}</span>
            </div>
            <div>
              <CardTitle className="text-base leading-none">{site.name}</CardTitle>
              <CardDescription className="text-xs mt-1">{site.url}</CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {site.isEnabled && (
              <Badge
                variant={site.isConnected ? "default" : site.hasPassword ? "secondary" : "outline"}
                className="text-[10px]"
              >
                {site.isConnected ? (
                  <><Check className="h-3 w-3 mr-1" />Connected</>
                ) : site.hasPassword ? (
                  "Not verified"
                ) : (
                  "No credentials"
                )}
              </Badge>
            )}
            <Button
              variant={site.isEnabled ? "default" : "outline"}
              size="sm"
              onClick={handleToggle}
            >
              {site.isEnabled ? (
                <><Power className="h-3.5 w-3.5 mr-1.5" />Enabled</>
              ) : (
                <><PowerOff className="h-3.5 w-3.5 mr-1.5" />Disabled</>
              )}
            </Button>
          </div>
        </div>
      </CardHeader>

      {site.isEnabled && (
        <CardContent className="pt-0">
          <Separator className="mb-4" />
          <form onSubmit={handleSave}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium">User ID</label>
                <Input
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="Enter your auction user ID"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium">Password</label>
                <div className="relative">
                  <Input
                    type={showPw ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="pr-10"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-0 top-0 h-full w-8"
                    onClick={() => setShowPw(!showPw)}
                  >
                    {showPw ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </Button>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between mt-4">
              <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                {site.lastLogin && (
                  <span>Login: {new Date(site.lastLogin).toLocaleDateString()}</span>
                )}
                {site.lastSync && (
                  <span>Sync: {new Date(site.lastSync).toLocaleDateString()}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {msg && (
                  <span className={`text-xs ${msg.ok ? "text-emerald-600" : "text-destructive"}`}>
                    {msg.text}
                  </span>
                )}
                <Button type="submit" size="sm" disabled={saving}>
                  <Save className="h-3.5 w-3.5 mr-1.5" />
                  {saving ? "Saving..." : "Save"}
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      )}
    </Card>
  );
}
