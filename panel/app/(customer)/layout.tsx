import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import Link from "next/link";
import { LogOut } from "lucide-react";
import { cache } from "react";
import { CustomerSidebar, MobileNav } from "./CustomerNav";
import { NavigationProvider } from "./components/NavigationContext";
import { ThemeToggle } from "./components/ThemeToggle";

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
        <header className="h-11 border-b border-border bg-background/80 backdrop-blur-md flex items-center justify-between px-4 md:px-5 flex-shrink-0">
          <div className="flex items-center gap-2">
            <MobileNav />
            <span className="text-xs text-muted-foreground hidden sm:inline">
              <span className="text-foreground font-medium">{userName}</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/profile" className="flex items-center gap-2 group">
              <div className="h-7 w-7 rounded bg-blue-500 text-white flex items-center justify-center">
                <span className="text-[10px] font-bold">{initials}</span>
              </div>
              <span className="text-xs font-medium text-muted-foreground hidden sm:inline group-hover:text-foreground transition-colors">{userName}</span>
            </Link>
            <ThemeToggle />
            <Link
              href="/api/auth/signout"
              className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              title="Sign out"
            >
              <LogOut className="h-3.5 w-3.5" />
            </Link>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-background">
          <div className="p-3 md:p-4 max-w-[1600px]"><NavigationProvider>{children}</NavigationProvider></div>
        </main>
      </div>
    </div>
  );
}
