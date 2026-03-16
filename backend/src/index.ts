import "dotenv/config";
import express from "express";
import cors from "cors";
import { parseUser } from "./middleware/auth.js";
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

const app = express();
const PORT = parseInt(process.env.PORT || "4000");

// Middleware
app.use(cors({
  origin: process.env.FRONTEND_URL || "http://localhost:3000",
  credentials: true,
}));
app.use(express.json());
app.use(parseUser);

// Routes
app.use("/api/auctions", auctionsRouter);
app.use("/api/lists", listsRouter);
app.use("/api/bid-requests", bidRequestsRouter);
app.use("/api/bid-to-crm", bidToCrmRouter);
app.use("/api/filter-options", filterOptionsRouter);
app.use("/api/stats", statsRouter);
app.use("/api/sync-logs", syncLogsRouter);
app.use("/api/users", usersRouter);
app.use("/api/settings", settingsRouter);
app.use("/api/auction-sites", auctionSitesRouter);
app.use("/api/auth", authSyncRouter);
app.use("/api/scraper-status", scraperStatusRouter);

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
});
