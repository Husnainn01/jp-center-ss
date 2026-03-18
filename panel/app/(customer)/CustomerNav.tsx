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
import { Car, List, User, Gavel, Menu } from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Upcoming Cars", icon: Car, badge: true },
  { href: "/lists", label: "My Lists", icon: List },
  { href: "/profile", label: "Profile", icon: User },
];

interface CustomerNavProps {
  vehicleCount?: number;
}

function NavItems({ vehicleCount, onNavigate }: CustomerNavProps & { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="px-2 py-3 space-y-0.5">
      {navItems.map((item) => {
        const isActive =
          pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md text-[13px] transition-colors ${
              isActive
                ? "bg-primary text-primary-foreground font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            }`}
          >
            <item.icon className="h-4 w-4" />
            <span className="flex-1">{item.label}</span>
            {item.badge && vehicleCount !== undefined && vehicleCount > 0 && (
              <span
                className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                  isActive
                    ? "bg-primary-foreground/20 text-primary-foreground"
                    : "bg-primary/10 text-primary"
                }`}
              >
                {vehicleCount > 999
                  ? `${(vehicleCount / 1000).toFixed(1)}k`
                  : vehicleCount}
              </span>
            )}
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
        <p className="text-[11px] text-muted-foreground">Vehicle Search</p>
      </div>
    </div>
  );
}

export function CustomerSidebar({ vehicleCount }: CustomerNavProps) {
  return (
    <aside className="w-[220px] flex-shrink-0 border-r bg-card flex-col hidden md:flex">
      <SidebarLogo />
      <Separator />
      <ScrollArea className="flex-1">
        <NavItems vehicleCount={vehicleCount} />
      </ScrollArea>
    </aside>
  );
}

export function MobileNav({ vehicleCount }: CustomerNavProps) {
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
          <NavItems
            vehicleCount={vehicleCount}
            onNavigate={() => setOpen(false)}
          />
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
