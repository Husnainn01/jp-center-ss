import type { Request, Response, NextFunction } from "express";

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
 * Reads user info from headers injected by the Next.js middleware.
 * Protected routes should check req.user exists.
 */
export function parseUser(req: Request, _res: Response, next: NextFunction) {
  const userId = req.headers["x-user-id"] as string | undefined;
  const role = req.headers["x-user-role"] as string | undefined;
  const crmCustomerId = req.headers["x-crm-customer-id"] as string | undefined;
  const crmToken = req.headers["x-crm-token"] as string | undefined;

  if (userId) {
    req.user = {
      id: parseInt(userId),
      role: role || "customer",
      crmCustomerId: crmCustomerId || null,
      crmToken: crmToken || null,
    };
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
