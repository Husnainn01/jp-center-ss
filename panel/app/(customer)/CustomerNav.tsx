"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Car, List, User, Menu } from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Vehicles", icon: Car },
  { href: "/lists", label: "Lists", icon: List },
  { href: "/profile", label: "Account", icon: User },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="px-2 py-3 space-y-0.5">
      {navItems.map((item) => {
        const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={`group relative flex items-center gap-2.5 px-3 py-2 text-[13px] transition-all duration-100 ${
              isActive
                ? "bg-muted/80 text-foreground font-medium"
                : "text-muted-foreground hover:text-foreground/80 hover:bg-muted/40"
            }`}
          >
            {isActive && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 bg-blue-500 rounded-r-sm" />
            )}
            <item.icon className={`h-4 w-4 ${isActive ? "text-blue-400" : ""}`} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarBrand() {
  return (
    <div className="px-4 py-4 flex items-center gap-2.5">
      <div className="h-7 w-7 bg-blue-500 rounded flex items-center justify-center">
        <Car className="h-4 w-4 text-white" />
      </div>
      <div>
        <h1 className="text-sm font-bold tracking-tight text-foreground">JP CENTER</h1>
        <p className="text-[9px] text-foreground0 font-medium tracking-wider uppercase">Auction Panel</p>
      </div>
    </div>
  );
}

export function CustomerSidebar() {
  return (
    <aside className="w-[180px] flex-shrink-0 border-r border-border bg-background flex-col hidden md:flex">
      <SidebarBrand />
      <div className="h-px bg-muted mx-3" />
      <ScrollArea className="flex-1">
        <NavItems />
      </ScrollArea>
      <div className="h-px bg-muted mx-3" />
      <div className="px-4 py-3">
        <p className="text-[9px] text-muted-foreground/40 text-center tracking-wide">SS Holdings</p>
      </div>
    </aside>
  );
}

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger className="md:hidden p-1.5 -ml-1 rounded hover:bg-muted transition-colors">
        <Menu className="h-5 w-5 text-muted-foreground" />
      </SheetTrigger>
      <SheetContent side="left" className="w-[220px] p-0 bg-background border-border">
        <SidebarBrand />
        <div className="h-px bg-muted mx-3" />
        <ScrollArea className="flex-1">
          <NavItems onNavigate={() => setOpen(false)} />
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
