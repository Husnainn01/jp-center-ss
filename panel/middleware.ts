import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4000";

// API paths that should be proxied to the backend
const PROXY_PATHS = [
  "/api/auctions",
  "/api/lists",
  "/api/bid-requests",
  "/api/bid-to-crm",
  "/api/filter-options",
  "/api/stats",
  "/api/sync-logs",
  "/api/users",
  "/api/settings",
  "/api/auction-sites",
  "/api/s3-image",
];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Only proxy API routes that should go to the backend
  const shouldProxy = PROXY_PATHS.some(
    (path) => pathname === path || pathname.startsWith(path + "/")
  );

  if (!shouldProxy) return NextResponse.next();

  // Read NextAuth JWT token and inject user info as headers
  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });

  const backendUrl = new URL(pathname + request.nextUrl.search, BACKEND_URL);
  const headers = new Headers(request.headers);

  if (token) {
    headers.set("x-user-id", String(token.id || ""));
    headers.set("x-user-role", String(token.role || ""));
    headers.set("x-crm-customer-id", String(token.crmCustomerId || ""));
    headers.set("x-crm-token", String(token.crmToken || ""));
  }

  return NextResponse.rewrite(backendUrl, { request: { headers } });
}

export const config = {
  matcher: "/api/:path*",
};
