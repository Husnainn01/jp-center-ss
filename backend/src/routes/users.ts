import { Router } from "express";
import { prisma } from "../lib/prisma.js";
import { requireAdmin } from "../middleware/auth.js";
import bcrypt from "bcryptjs";

export const usersRouter = Router();

usersRouter.use(requireAdmin);

// GET /api/users
usersRouter.get("/", async (_req, res) => {
  try {
    const users = await prisma.user.findMany({
      orderBy: { createdAt: "desc" },
      select: {
        id: true,
        email: true,
        name: true,
        role: true,
        isActive: true,
        createdAt: true,
        lastLoginAt: true,
      },
    });
    res.json(users);
  } catch (err) {
    console.error("GET /api/users error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /api/users
usersRouter.post("/", async (req, res) => {
  try {
    const { email, password, name, role } = req.body;

    if (!email || !password || !name) {
      res.status(400).json({ error: "Email, password, and name are required" });
      return;
    }

    const exists = await prisma.user.findUnique({ where: { email } });
    if (exists) {
      res.status(409).json({ error: "Email already exists" });
      return;
    }

    const hashed = await bcrypt.hash(password, 14);
    const user = await prisma.user.create({
      data: { email, password: hashed, name, role: role === "admin" ? "admin" : "customer" },
      select: { id: true, email: true, name: true, role: true },
    });

    res.status(201).json(user);
  } catch (err) {
    console.error("POST /api/users error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// PUT /api/users
usersRouter.put("/", async (req, res) => {
  try {
    const { id, name, role, isActive, password } = req.body;
    if (!id) {
      res.status(400).json({ error: "User ID required" });
      return;
    }

    const data: Record<string, unknown> = {};
    if (name !== undefined) data.name = name;
    if (role !== undefined) data.role = role;
    if (typeof isActive === "boolean") data.isActive = isActive;
    if (password) data.password = await bcrypt.hash(password, 14);

    await prisma.user.update({ where: { id }, data });
    res.json({ success: true });
  } catch (err) {
    console.error("PUT /api/users error:", err);
    res.status(500).json({ error: "Internal server error" });
  }
});
