"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import { UserPlus, Shield, User, Ban, Check } from "lucide-react";

interface UserData {
  id: number;
  email: string;
  name: string;
  role: string;
  isActive: boolean;
  createdAt: string;
  lastLoginAt: string | null;
}

export default function UsersPage() {
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", name: "", role: "customer" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    fetch("/api/users").then(r => r.json()).then(setUsers).finally(() => setLoading(false));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    const res = await fetch("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    const data = await res.json();
    if (res.ok) {
      setMsg({ ok: true, text: "User created" });
      setUsers(prev => [{ ...data, isActive: true, createdAt: new Date().toISOString(), lastLoginAt: null }, ...prev]);
      setForm({ email: "", password: "", name: "", role: "customer" });
      setShowForm(false);
    } else {
      setMsg({ ok: false, text: data.error });
    }
    setSaving(false);
  }

  async function toggleActive(user: UserData) {
    await fetch("/api/users", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: user.id, isActive: !user.isActive }),
    });
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, isActive: !u.isActive } : u));
  }

  if (loading) return <div className="text-center py-10 text-muted-foreground text-sm">Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Users</h1>
          <p className="text-sm text-muted-foreground">{users.length} users · {users.filter(u => u.role === "customer").length} customers</p>
        </div>
        <Button size="sm" onClick={() => setShowForm(!showForm)}>
          <UserPlus className="h-4 w-4 mr-1.5" />
          Add User
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Create New User</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="flex flex-wrap gap-3 items-end">
              <div className="space-y-1">
                <label className="text-xs font-medium">Name</label>
                <Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="Full name" required className="w-44" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Email</label>
                <Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} placeholder="user@email.com" required className="w-52" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Password</label>
                <Input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} placeholder="Min 6 chars" required className="w-40" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Role</label>
                <select value={form.role} onChange={e => setForm({...form, role: e.target.value})} className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm">
                  <option value="customer">Customer</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <Button type="submit" size="sm" disabled={saving}>
                {saving ? "Creating..." : "Create"}
              </Button>
              {msg && <span className={`text-xs ${msg.ok ? "text-emerald-600" : "text-destructive"}`}>{msg.text}</span>}
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Login</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map(user => (
                <TableRow key={user.id}>
                  <TableCell>
                    <div className="font-medium">{user.name}</div>
                    <div className="text-xs text-muted-foreground">{user.email}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.role === "admin" ? "default" : "secondary"} className="text-[10px] capitalize">
                      {user.role === "admin" ? <><Shield className="h-3 w-3 mr-1" />Admin</> : <><User className="h-3 w-3 mr-1" />Customer</>}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.isActive ? "default" : "destructive"} className="text-[10px]">
                      {user.isActive ? "Active" : "Disabled"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {user.lastLoginAt ? new Date(user.lastLoginAt).toLocaleString() : "Never"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(user.createdAt).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="outline" size="sm" onClick={() => toggleActive(user)}>
                      {user.isActive ? <Ban className="h-3 w-3 mr-1" /> : <Check className="h-3 w-3 mr-1" />}
                      {user.isActive ? "Disable" : "Enable"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
