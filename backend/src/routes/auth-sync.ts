import { Router } from "express";
import { prisma } from "../lib/prisma.js";

export const authSyncRouter = Router();

/**
 * POST /api/auth/sync
 * Called by the frontend's NextAuth during login to sync the CRM user
 * to the local database. Creates or updates the local user record.
 */
authSyncRouter.post("/sync", async (req, res) => {
  try {
    const { crmUserId, crmCustomerId, email, name } = req.body;

    if (!crmUserId || !email || !name) {
      res.status(400).json({ error: "crmUserId, email, and name are required" });
      return;
    }

    // Validate input lengths to prevent abuse
    if (String(crmUserId).length > 100 || String(email).length > 255 || String(name).length > 255) {
      res.status(400).json({ error: "Input too long" });
      return;
    }

    // Try to find by crmUserId first
    let localUser = await prisma.user.findUnique({
      where: { crmUserId: String(crmUserId) },
    });

    if (!localUser) {
      // Try by email (migration case)
      localUser = await prisma.user.findUnique({
        where: { email },
      });

      if (localUser) {
        // Prevent linking if this user is already linked to a DIFFERENT CRM account
        if (localUser.crmUserId && localUser.crmUserId !== String(crmUserId)) {
          res.status(409).json({ error: "Email already linked to another account" });
          return;
        }
        // Link existing local user to CRM
        localUser = await prisma.user.update({
          where: { id: localUser.id },
          data: {
            crmUserId: String(crmUserId),
            crmCustomerId: crmCustomerId ? String(crmCustomerId) : null,
            name,
            lastLoginAt: new Date(),
          },
        });
      } else {
        // Create new local user
        localUser = await prisma.user.create({
          data: {
            email,
            password: "", // No local password — CRM handles auth
            name,
            role: "customer", // Always customer — admin role set manually in DB only
            crmUserId: String(crmUserId),
            crmCustomerId: crmCustomerId ? String(crmCustomerId) : null,
            lastLoginAt: new Date(),
          },
        });
      }
    } else {
      // Update existing linked user
      localUser = await prisma.user.update({
        where: { id: localUser.id },
        data: {
          name,
          email,
          crmCustomerId: crmCustomerId ? String(crmCustomerId) : null,
          lastLoginAt: new Date(),
        },
      });
    }

    res.json({
      id: localUser.id,
      email: localUser.email,
      name: localUser.name,
      role: localUser.role,
      isActive: localUser.isActive,
    });
  } catch (err) {
    console.error("POST /api/auth/sync error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
