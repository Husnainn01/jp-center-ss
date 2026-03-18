import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import Link from "next/link";
import { LogOut } from "lucide-react";
import { cache } from "react";
import { CustomerSidebar, MobileNav } from "./CustomerNav";

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
  const initials = userName.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <CustomerSidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Minimal header */}
        <header className="h-12 border-b bg-card/80 backdrop-blur-sm flex items-center justify-between px-4 md:px-5 flex-shrink-0">
          <div className="flex items-center gap-2">
            <MobileNav />
            <span className="text-xs text-muted-foreground hidden sm:inline">
              Welcome, <span className="font-medium text-foreground">{userName}</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/profile" className="flex items-center gap-2 group">
              <div className="h-7 w-7 rounded-full bg-foreground text-background flex items-center justify-center">
                <span className="text-[10px] font-bold">{initials}</span>
              </div>
              <span className="text-xs font-medium hidden sm:inline group-hover:text-primary transition-colors">{userName}</span>
            </Link>
            <Link
              href="/api/auth/signout"
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              title="Sign out"
            >
              <LogOut className="h-3.5 w-3.5" />
            </Link>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="p-3 md:p-4 max-w-[1600px]">{children}</div>
        </main>
      </div>
    </div>
  );
}
