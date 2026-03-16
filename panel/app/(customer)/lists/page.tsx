"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, List, Trash2, Calendar, ChevronRight } from "lucide-react";

interface ListData {
  id: number;
  name: string;
  itemCount: number;
  createdAt: string;
}

export default function ListsPage() {
  const [lists, setLists] = useState<ListData[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetch("/api/lists").then(r => r.json()).then(setLists).finally(() => setLoading(false));
  }, []);

  async function createList(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    const res = await fetch("/api/lists", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName.trim() }),
    });
    if (res.ok) {
      const list = await res.json();
      setLists(prev => [list, ...prev]);
      setNewName("");
    }
    setCreating(false);
  }

  async function deleteList(id: number) {
    if (!confirm("Delete this list and all its items?")) return;
    const res = await fetch(`/api/lists/${id}`, { method: "DELETE" });
    if (res.ok) setLists(prev => prev.filter(l => l.id !== id));
  }

  // Group lists by month
  const grouped = lists.reduce<Record<string, ListData[]>>((acc, list) => {
    const d = new Date(list.createdAt);
    const key = `${d.toLocaleString("en-US", { month: "long" })} ${d.getFullYear()}`;
    (acc[key] ||= []).push(list);
    return acc;
  }, {});

  if (loading) return <div className="text-center py-10 text-muted-foreground text-sm">Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">My Lists</h1>
          <p className="text-sm text-muted-foreground">
            {lists.length} lists · {lists.reduce((sum, l) => sum + l.itemCount, 0)} vehicles saved
          </p>
        </div>
      </div>

      {/* Create new list */}
      <Card>
        <CardContent className="p-4">
          <form onSubmit={createList} className="flex gap-2">
            <Input
              placeholder="Create a new list (e.g. Monday Picks, Budget Under 1M...)"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" disabled={creating || !newName.trim()}>
              <Plus className="h-4 w-4 mr-1.5" />
              Create
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Lists grouped by month */}
      {lists.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <List className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
            <p className="text-muted-foreground">No lists yet</p>
            <p className="text-xs text-muted-foreground mt-1">Create a list and start adding vehicles from the Upcoming Auctions page</p>
          </CardContent>
        </Card>
      ) : (
        Object.entries(grouped).map(([month, monthLists]) => (
          <div key={month} className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Calendar className="h-3.5 w-3.5" />
              <span className="font-medium">{month}</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {monthLists.map(list => (
                <Card key={list.id} className="group hover:shadow-md transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <Link href={`/lists/${list.id}`} className="flex-1 min-w-0">
                        <h3 className="font-semibold text-sm group-hover:text-primary transition-colors truncate">
                          {list.name}
                        </h3>
                        <div className="flex items-center gap-2 mt-1.5">
                          <Badge variant="secondary" className="text-[10px]">
                            {list.itemCount} vehicles
                          </Badge>
                          <span className="text-[11px] text-muted-foreground">
                            {new Date(list.createdAt).toLocaleDateString("en-US", {
                              month: "short", day: "numeric",
                            })}
                          </span>
                        </div>
                      </Link>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteList(list.id)}>
                          <Trash2 className="h-3 w-3 text-muted-foreground" />
                        </Button>
                        <Link href={`/lists/${list.id}`}>
                          <Button variant="ghost" size="icon" className="h-7 w-7">
                            <ChevronRight className="h-3.5 w-3.5" />
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
