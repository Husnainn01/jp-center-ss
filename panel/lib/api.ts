/**
 * Server-side helper for fetching data from the backend API.
 * Used by server components that previously queried Prisma directly.
 */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4000";

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

  // Inject user context for authenticated requests
  if (options?.userId) {
    headers["x-user-id"] = String(options.userId);
    headers["x-user-role"] = options.userRole || "customer";
    if (options.crmCustomerId) headers["x-crm-customer-id"] = options.crmCustomerId;
    if (options.crmToken) headers["x-crm-token"] = options.crmToken;
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
