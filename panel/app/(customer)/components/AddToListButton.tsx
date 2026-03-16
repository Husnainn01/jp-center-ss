"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ListPlus, Plus, Check, X } from "lucide-react";

interface ListData {
  id: number;
  name: string;
  itemCount: number;
  createdAt: string;
}

export function AddToListButton({ auctionId }: { auctionId: number }) {
  const [open, setOpen] = useState(false);
  const [lists, setLists] = useState<ListData[]>([]);
  const [newName, setNewName] = useState("");
  const [loading, setLoading] = useState(false);
  const [added, setAdded] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (open) {
      fetch("/api/lists").then(r => r.json()).then(setLists);
    }
  }, [open]);

  async function createList() {
    if (!newName.trim()) return;
    setLoading(true);
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
    setLoading(false);
  }

  async function addToList(listId: number) {
    const res = await fetch(`/api/lists/${listId}/items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auctionId }),
    });
    if (res.ok || res.status === 409) {
      setAdded(prev => ({ ...prev, [listId]: true }));
    }
  }

  if (!open) {
    return (
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <ListPlus className="h-3.5 w-3.5 mr-1.5" />
        Add to List
      </Button>
    );
  }

  return (
    <div className="border rounded-lg bg-card p-3 space-y-3 w-64 shadow-lg">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold">Add to List</span>
        <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Create new list */}
      <div className="flex gap-1.5">
        <Input
          placeholder="New list name..."
          value={newName}
          onChange={e => setNewName(e.target.value)}
          onKeyDown={e => e.key === "Enter" && createList()}
          className="h-8 text-xs"
        />
        <Button size="sm" className="h-8 px-2" onClick={createList} disabled={loading || !newName.trim()}>
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Existing lists */}
      <div className="space-y-1 max-h-40 overflow-y-auto">
        {lists.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-2">No lists yet — create one above</p>
        ) : (
          lists.map(list => (
            <button
              key={list.id}
              onClick={() => addToList(list.id)}
              disabled={added[list.id]}
              className="w-full flex items-center justify-between px-2 py-1.5 rounded text-xs hover:bg-accent transition-colors disabled:opacity-50"
            >
              <div className="text-left">
                <span className="font-medium">{list.name}</span>
                <span className="text-muted-foreground ml-1.5">({list.itemCount})</span>
              </div>
              {added[list.id] ? (
                <Check className="h-3 w-3 text-emerald-500" />
              ) : (
                <Plus className="h-3 w-3 text-muted-foreground" />
              )}
            </button>
          ))
        )}
      </div>

      <p className="text-[10px] text-muted-foreground">
        {new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" })}
      </p>
    </div>
  );
}
