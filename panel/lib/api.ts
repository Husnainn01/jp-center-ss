/**
 * Server-side helper for fetching data from the backend API.
 * Used by server components. Automatically includes auth headers
 * from the current session + HMAC signature for backend verification.
 */

import { getServerSession } from "next-auth";
import { createHmac } from "crypto";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4000";
const SIGNING_SECRET = process.env.PROXY_SIGNING_SECRET || process.env.NEXTAUTH_SECRET || "";

export async function backendFetch<T = unknown>(
  path: string,
  options?: {
    userId?: number;
    userRole?: string;
    crmCustomerId?: string;
    crmToken?: string;
  }
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  // If explicit options provided, use them
  if (options?.userId) {
    headers["x-user-id"] = String(options.userId);
    headers["x-user-role"] = options.userRole || "customer";
    if (options.crmCustomerId) headers["x-crm-customer-id"] = options.crmCustomerId;
    if (options.crmToken) headers["x-crm-token"] = options.crmToken;
  } else {
    // Auto-inject from current session (server components)
    try {
      const { authOptions } = await import("@/lib/auth");
      const session = await getServerSession(authOptions);
      if (session?.user) {
        const user = session.user as Record<string, unknown>;
        headers["x-user-id"] = String(user.id || "");
        headers["x-user-role"] = String(user.role || "customer");
        headers["x-crm-customer-id"] = String(user.crmCustomerId || "");
        headers["x-crm-token"] = String(user.crmToken || "");
      }
    } catch {
      // Session not available — request goes without auth
    }
  }

  // Add HMAC signature if auth headers are present
  if (headers["x-user-id"] && SIGNING_SECRET) {
    try {
      const payload = `${headers["x-user-id"]}:${headers["x-user-role"] || ""}:${headers["x-crm-customer-id"] || ""}`;
      headers["x-proxy-signature"] = createHmac("sha256", SIGNING_SECRET).update(payload).digest("hex");
    } catch {
      // Crypto failed — send without signature
    }
  }

  const res = await fetch(`${BACKEND_URL}${path}`, {
    headers,
    next: { revalidate: 60 },
  });

  if (!res.ok) {
    throw new Error(`Backend ${path} returned ${res.status}`);
  }

  return res.json() as Promise<T>;
}
