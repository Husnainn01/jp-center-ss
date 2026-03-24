import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";
import { createHmac } from "crypto";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4000";
const SIGNING_SECRET = process.env.PROXY_SIGNING_SECRET || process.env.NEXTAUTH_SECRET || "";

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

  // Determine what kind of request this is
  const isProtectedPage = PROTECTED_PATHS.some(
    (path) => pathname === path || pathname.startsWith(path + "/")
  );
  const isProxyRoute = PROXY_PATHS.some(
    (path) => pathname === path || pathname.startsWith(path + "/")
  );

  // If not a protected page or API route, pass through
  if (!isProtectedPage && !isProxyRoute) return NextResponse.next();

  // Get the auth token (once, used for both page auth and API proxy)
  let token = null;
  try {
    token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });
  } catch {
    // Token parsing failed — treat as unauthenticated
  }

  // Protected page: redirect to login if no token
  if (isProtectedPage && !token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("error", "session_expired");
    return NextResponse.redirect(loginUrl);
  }

  // Not an API proxy route — just a page that passed auth check
  if (!isProxyRoute) return NextResponse.next();

  // API proxy: reject if no token
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Build proxy request with auth headers
  const backendUrl = new URL(pathname + request.nextUrl.search, BACKEND_URL);
  const headers = new Headers(request.headers);

  const userId = String(token.id || "");
  const role = String(token.role || "");
  const crmCustomerId = String(token.crmCustomerId || "");
  headers.set("x-user-id", userId);
  headers.set("x-user-role", role);
  headers.set("x-crm-customer-id", crmCustomerId);
  headers.set("x-crm-token", String(token.crmToken || ""));

  // HMAC signature to prevent header spoofing — backend verifies this
  if (SIGNING_SECRET) {
    try {
      const payload = `${userId}:${role}:${crmCustomerId}`;
      const signature = createHmac("sha256", SIGNING_SECRET).update(payload).digest("hex");
      headers.set("x-proxy-signature", signature);
    } catch {
      // If crypto fails, still send the request without signature
      // Backend will reject if it requires signature verification
    }
  }

  return NextResponse.rewrite(backendUrl, { request: { headers } });
}

export const config = {
  matcher: ["/api/:path*", "/dashboard/:path*", "/lists/:path*", "/profile/:path*", "/auctions/:path*", "/settings/:path*", "/sync/:path*", "/users/:path*"],
};
