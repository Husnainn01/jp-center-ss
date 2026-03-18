"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Car, List, User, Menu, ChevronRight } from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Auction Vehicles", icon: Car },
  { href: "/lists", label: "My Lists", icon: List },
  { href: "/profile", label: "Profile", icon: User },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="px-3 py-4 space-y-1">
      <p className="px-2 mb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">
        Navigation
      </p>
      {navItems.map((item) => {
        const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={`group flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition-all duration-150 ${
              isActive
                ? "bg-foreground text-background font-medium shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            }`}
          >
            <item.icon className={`h-4 w-4 ${isActive ? "text-background" : ""}`} />
            <span className="flex-1">{item.label}</span>
            {isActive && <ChevronRight className="h-3 w-3 opacity-50" />}
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarBrand() {
  return (
    <div className="px-4 py-5 flex items-center gap-3">
      <div className="h-9 w-9 rounded-xl overflow-hidden bg-foreground/5 flex items-center justify-center ring-1 ring-border">
        <Image src="/background.png" alt="SS Holdings" width={32} height={32} className="rounded-lg" />
      </div>
      <div>
        <h1 className="text-sm font-bold leading-none tracking-tight">JP Auction</h1>
        <p className="text-[10px] text-muted-foreground mt-0.5">SS Holdings</p>
      </div>
    </div>
  );
}

export function CustomerSidebar() {
  return (
    <aside className="w-[200px] flex-shrink-0 border-r bg-card flex-col hidden md:flex">
      <SidebarBrand />
      <div className="h-px bg-border mx-3" />
      <ScrollArea className="flex-1">
        <NavItems />
      </ScrollArea>
      <div className="h-px bg-border mx-3" />
      <div className="px-4 py-3">
        <p className="text-[9px] text-muted-foreground/50 text-center">Partners for Success</p>
      </div>
    </aside>
  );
}

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger className="md:hidden p-1.5 -ml-1 rounded-md hover:bg-accent transition-colors">
        <Menu className="h-5 w-5" />
      </SheetTrigger>
      <SheetContent side="left" className="w-[240px] p-0">
        <SidebarBrand />
        <div className="h-px bg-border mx-3" />
        <ScrollArea className="flex-1">
          <NavItems onNavigate={() => setOpen(false)} />
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
