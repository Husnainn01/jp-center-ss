import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import Link from "next/link";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Car, Gavel, User, LogOut, List, Bell, ChevronDown } from "lucide-react";
import { cache } from "react";

const navItems = [
  { href: "/dashboard", label: "Upcoming Cars", icon: Car },
  { href: "/lists", label: "My Lists", icon: List },
  { href: "/profile", label: "Profile", icon: User },
];

const getSession = cache(() => getServerSession(authOptions));

export default async function CustomerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session) redirect("/login");

  if ((session.user as { role: string }).role === "admin") {
    redirect("/");
  }

  const userName = session.user?.name || "User";
  const userEmail = session.user?.email || "";
  const initials = userName.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside className="w-[220px] flex-shrink-0 border-r bg-card flex flex-col">
        <div className="px-4 py-4 flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
            <Gavel className="h-4 w-4 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-sm font-semibold leading-none">JP Auction</h1>
            <p className="text-[11px] text-muted-foreground">Vehicle Search</p>
          </div>
        </div>
        <Separator />
        <ScrollArea className="flex-1">
          <nav className="px-2 py-3 space-y-0.5">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-2.5 px-2.5 py-2 rounded-md text-[13px] text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            ))}
          </nav>
        </ScrollArea>
      </aside>

      {/* Main content with top header */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header Bar */}
        <header className="h-14 border-b bg-card flex items-center justify-between px-6 flex-shrink-0">
          <div className="text-sm text-muted-foreground">
            Welcome back, <span className="font-medium text-foreground">{userName}</span>
          </div>
          <div className="flex items-center gap-3">
            {/* Notifications placeholder */}
            <button className="relative p-2 rounded-md hover:bg-accent transition-colors">
              <Bell className="h-4 w-4 text-muted-foreground" />
            </button>

            <Separator orientation="vertical" className="h-6" />

            {/* Profile dropdown */}
            <div className="flex items-center gap-2">
              <Link href="/profile" className="flex items-center gap-2.5 group">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <span className="text-xs font-semibold text-primary">{initials}</span>
                </div>
                <div className="hidden sm:block">
                  <p className="text-sm font-medium leading-none group-hover:text-primary transition-colors">{userName}</p>
                  <p className="text-[11px] text-muted-foreground">{userEmail}</p>
                </div>
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground hidden sm:block" />
              </Link>
            </div>

            <Separator orientation="vertical" className="h-6" />

            <Link
              href="/api/auth/signout"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Sign out</span>
            </Link>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-6 max-w-[1400px]">{children}</div>
        </main>
      </div>
    </div>
  );
}
