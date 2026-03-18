import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import Link from "next/link";
import { Separator } from "@/components/ui/separator";
import { LogOut, Bell, Shield } from "lucide-react";
import { cache } from "react";
import { AdminSidebar, AdminMobileNav } from "./AdminNav";

const getSession = cache(() => getServerSession(authOptions));

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session) redirect("/login");
  if ((session.user as { role: string }).role !== "admin") redirect("/dashboard");

  const userName = session.user?.name || "Admin";
  const userEmail = session.user?.email || "";
  const initials = userName.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop Sidebar */}
      <AdminSidebar />

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-14 border-b bg-card flex items-center justify-between px-4 md:px-6 flex-shrink-0">
          <div className="flex items-center gap-3">
            {/* Mobile menu */}
            <AdminMobileNav />
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Shield className="h-4 w-4 text-primary" />
              Admin Panel
            </div>
          </div>
          <div className="flex items-center gap-2 md:gap-3">
            <button className="relative p-2 rounded-md hover:bg-accent transition-colors">
              <Bell className="h-4 w-4 text-muted-foreground" />
            </button>

            <Separator orientation="vertical" className="h-6 hidden sm:block" />

            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                <span className="text-xs font-semibold text-primary">{initials}</span>
              </div>
              <div className="hidden sm:block">
                <p className="text-sm font-medium leading-none">{userName}</p>
                <p className="text-[11px] text-muted-foreground">{userEmail}</p>
              </div>
            </div>

            <Separator orientation="vertical" className="h-6 hidden sm:block" />

            <Link
              href="/api/auth/signout"
              className="flex items-center gap-1.5 px-2 py-1.5 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Sign out</span>
            </Link>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="p-4 md:p-6 max-w-[1400px]">{children}</div>
        </main>
      </div>
    </div>
  );
}
