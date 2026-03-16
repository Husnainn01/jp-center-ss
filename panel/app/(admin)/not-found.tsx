import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <p className="text-7xl font-bold text-muted-foreground/20">404</p>
      <p className="mt-2 text-muted-foreground">Page not found</p>
      <Link
        href="/"
        className="mt-4 inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent transition-colors"
      >
        Back to Dashboard
      </Link>
    </div>
  );
}
