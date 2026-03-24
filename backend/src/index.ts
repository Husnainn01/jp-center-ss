import "dotenv/config";
import express from "express";
import cors from "cors";
import { parseUser, requireAuth, requireAdmin } from "./middleware/auth.js";
import { rateLimit } from "./middleware/rateLimit.js";
import { auctionsRouter } from "./routes/auctions.js";
import { listsRouter } from "./routes/lists.js";
import { bidRequestsRouter } from "./routes/bid-requests.js";
import { bidToCrmRouter } from "./routes/bid-to-crm.js";
import { filterOptionsRouter } from "./routes/filter-options.js";
import { statsRouter } from "./routes/stats.js";
import { syncLogsRouter } from "./routes/sync-logs.js";
import { usersRouter } from "./routes/users.js";
import { settingsRouter } from "./routes/settings.js";
import { auctionSitesRouter } from "./routes/auction-sites.js";
import { authSyncRouter } from "./routes/auth-sync.js";
import { scraperStatusRouter } from "./routes/scraper-status.js";
import { imagesRouter } from "./routes/images.js";
import { cacheRouter } from "./routes/cache.js";

const app = express();
const PORT = parseInt(process.env.PORT || "4000");

// Middleware
app.use(cors({
  origin: process.env.FRONTEND_URL || "http://localhost:3000",
  credentials: true,
}));
app.use(express.json({ limit: "1mb" })); // Limit request body size
app.use(parseUser);

// Routes — public (no auth required, rate limited)
app.use("/api/auth", rateLimit(10, 60 * 1000), authSyncRouter); // 10 requests/min per IP
app.use("/s3", imagesRouter);                // Image proxy (public)
app.use("/api/s3-image", imagesRouter);      // Image proxy (public)
app.use("/api/cache", requireAuth, cacheRouter); // Cache invalidation (auth required)

// Routes — authenticated (customer or admin)
app.use("/api/auctions", requireAuth, auctionsRouter);
app.use("/api/lists", requireAuth, listsRouter);
app.use("/api/bid-requests", requireAuth, bidRequestsRouter);
app.use("/api/bid-to-crm", requireAuth, bidToCrmRouter);
app.use("/api/filter-options", requireAuth, filterOptionsRouter);
app.use("/api/stats", requireAuth, statsRouter);

// Routes — admin only
app.use("/api/sync-logs", requireAdmin, syncLogsRouter);
app.use("/api/users", requireAdmin, usersRouter);
app.use("/api/settings", requireAdmin, settingsRouter);
app.use("/api/auction-sites", requireAdmin, auctionSitesRouter);
app.use("/api/scraper-status", requireAdmin, scraperStatusRouter);

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// Global error handler — prevents stack traces from leaking to clients
app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error("[ERROR]", err.message); // Log message only, not stack
  res.status(500).json({ error: "Internal server error" });
});

app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
});
