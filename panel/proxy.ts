import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";
import crypto from "crypto";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4000";
const SIGNING_SECRET = process.env.PROXY_SIGNING_SECRET || process.env.NEXTAUTH_SECRET || "change-me-in-production";

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

// Protected page paths that require authentication
const PROTECTED_PATHS = ["/dashboard", "/lists", "/profile", "/auctions", "/settings", "/sync", "/users"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check auth for protected pages — redirect to login if token expired/missing
  const isProtectedPage = PROTECTED_PATHS.some(
    (path) => pathname === path || pathname.startsWith(path + "/")
  );

  if (isProtectedPage) {
    const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });
    if (!token) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("error", "session_expired");
      return NextResponse.redirect(loginUrl);
    }
  }

  // Only proxy API routes that should go to the backend
  const shouldProxy = PROXY_PATHS.some(
    (path) => pathname === path || pathname.startsWith(path + "/")
  );

  if (!shouldProxy) return NextResponse.next();

  // Read NextAuth JWT token and inject user info as headers
  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });

  // Reject API calls with no auth token
  if (!token && shouldProxy) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const backendUrl = new URL(pathname + request.nextUrl.search, BACKEND_URL);
  const headers = new Headers(request.headers);

  if (token) {
    const userId = String(token.id || "");
    const role = String(token.role || "");
    const crmCustomerId = String(token.crmCustomerId || "");
    headers.set("x-user-id", userId);
    headers.set("x-user-role", role);
    headers.set("x-crm-customer-id", crmCustomerId);
    headers.set("x-crm-token", String(token.crmToken || ""));
    // HMAC signature to prevent header spoofing — backend verifies this
    const payload = `${userId}:${role}:${crmCustomerId}`;
    const signature = crypto.createHmac("sha256", SIGNING_SECRET).update(payload).digest("hex");
    headers.set("x-proxy-signature", signature);
  }

  return NextResponse.rewrite(backendUrl, { request: { headers } });
}

export const config = {
  matcher: ["/api/:path*", "/dashboard/:path*", "/lists/:path*", "/profile/:path*", "/auctions/:path*", "/settings/:path*", "/sync/:path*", "/users/:path*"],
};
