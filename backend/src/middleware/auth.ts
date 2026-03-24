import type { Request, Response, NextFunction } from "express";
import crypto from "crypto";

// Shared secret between Next.js proxy and backend — prevents header spoofing
// Must be the same value in both PROXY_SIGNING_SECRET env vars
const SIGNING_SECRET = process.env.PROXY_SIGNING_SECRET || process.env.NEXTAUTH_SECRET || "change-me-in-production";

export interface AuthUser {
  id: number;
  role: string;
  crmCustomerId: string | null;
  crmToken: string | null;
}

declare global {
  namespace Express {
    interface Request {
      user?: AuthUser;
    }
  }
}

/**
 * Reads user info from headers injected by the Next.js proxy.
 * Verifies HMAC signature to prevent header spoofing.
 * The proxy signs: HMAC(userId:role:crmCustomerId, secret)
 */
export function parseUser(req: Request, _res: Response, next: NextFunction) {
  const userId = req.headers["x-user-id"] as string | undefined;
  const role = req.headers["x-user-role"] as string | undefined;
  const crmCustomerId = req.headers["x-crm-customer-id"] as string | undefined;
  const crmToken = req.headers["x-crm-token"] as string | undefined;
  const signature = req.headers["x-proxy-signature"] as string | undefined;

  if (userId) {
    // Verify the signature from the proxy to prevent header spoofing
    const payload = `${userId}:${role || ""}:${crmCustomerId || ""}`;
    const expectedSig = crypto.createHmac("sha256", SIGNING_SECRET).update(payload).digest("hex");

    if (SIGNING_SECRET && SIGNING_SECRET !== "change-me-in-production") {
      // Verify HMAC signature if signing is configured
      if (signature && signature === expectedSig) {
        req.user = {
          id: parseInt(userId),
          role: role || "customer",
          crmCustomerId: crmCustomerId || null,
          crmToken: crmToken || null,
        };
      }
      // If signature is invalid, req.user stays undefined → requireAuth will block
    } else {
      // Signing not configured — trust headers (backward compatible, log warning)
      req.user = {
        id: parseInt(userId),
        role: role || "customer",
        crmCustomerId: crmCustomerId || null,
        crmToken: crmToken || null,
      };
    }
  }

  next();
}

export function requireAuth(req: Request, res: Response, next: NextFunction) {
  if (!req.user) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }
  next();
}

export function requireAdmin(req: Request, res: Response, next: NextFunction) {
  if (!req.user || req.user.role !== "admin") {
    res.status(403).json({ error: "Admin only" });
    return;
  }
  next();
}
