"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  LayoutDashboard,
  Car,
  Clock,
  RefreshCw,
  Settings,
  Gavel,
  Users,
  Menu,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/auctions", label: "All Auctions", icon: Car },
  { href: "/auctions?status=upcoming", label: "Upcoming", icon: Clock },
  { href: "/users", label: "Users", icon: Users },
  { href: "/sync", label: "Sync Logs", icon: RefreshCw },
  { href: "/settings", label: "Settings", icon: Settings },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="px-2 py-3 space-y-0.5">
      {navItems.map((item) => {
        // For items with query params, match on pathname only
        const hrefPath = item.href.split("?")[0];
        const isActive =
          (hrefPath === "/" && pathname === "/") ||
          (hrefPath !== "/" &&
            (pathname === hrefPath || pathname.startsWith(hrefPath + "/")));
        return (
          <Link
            key={item.href + item.label}
            href={item.href}
            onClick={onNavigate}
            className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md text-[13px] transition-colors ${
              isActive
                ? "bg-primary text-primary-foreground font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            }`}
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarLogo() {
  return (
    <div className="px-4 py-4 flex items-center gap-2.5 bg-gradient-to-r from-primary/5 to-transparent">
      <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary to-primary/80 flex items-center justify-center shadow-sm">
        <Gavel className="h-4 w-4 text-primary-foreground" />
      </div>
      <div>
        <h1 className="text-sm font-bold leading-none tracking-tight">
          JP Auction
        </h1>
        <p className="text-[11px] text-muted-foreground">Admin Panel</p>
      </div>
    </div>
  );
}

export function AdminSidebar() {
  return (
    <aside className="w-[220px] flex-shrink-0 border-r bg-card flex-col hidden md:flex">
      <SidebarLogo />
      <Separator />
      <ScrollArea className="flex-1">
        <NavItems />
      </ScrollArea>
    </aside>
  );
}

export function AdminMobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger className="md:hidden p-2 rounded-md hover:bg-accent transition-colors">
        <Menu className="h-5 w-5" />
      </SheetTrigger>
      <SheetContent side="left" className="w-[260px] p-0">
        <SidebarLogo />
        <Separator />
        <ScrollArea className="flex-1">
          <NavItems onNavigate={() => setOpen(false)} />
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
