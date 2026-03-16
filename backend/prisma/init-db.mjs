/**
 * Creates all tables if they don't exist. Runs before the server starts.
 * This replaces `prisma db push` which has issues with Prisma 7 + no URL in schema.
 */
import pg from "pg";

const client = new pg.Client({ connectionString: process.env.DATABASE_URL });

const SQL = `
-- Auctions
CREATE TABLE IF NOT EXISTS auctions (
  id SERIAL PRIMARY KEY,
  item_id TEXT UNIQUE NOT NULL,
  lot_number TEXT NOT NULL,
  maker TEXT NOT NULL,
  model TEXT NOT NULL,
  grade TEXT,
  chassis_code TEXT,
  engine_specs TEXT,
  year TEXT,
  mileage TEXT,
  color TEXT,
  rating TEXT,
  start_price DECIMAL(12,2),
  auction_date TEXT NOT NULL,
  auction_house TEXT NOT NULL,
  location TEXT NOT NULL,
  status TEXT DEFAULT 'upcoming',
  sold_price DECIMAL(12,2),
  sold_at TIMESTAMPTZ,
  image_url TEXT,
  images JSONB DEFAULT '[]',
  exhibit_sheet TEXT,
  inspection_expiry TEXT,
  source TEXT DEFAULT 'aucnet',
  first_seen TIMESTAMPTZ DEFAULT NOW(),
  last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Sync logs
CREATE TABLE IF NOT EXISTS sync_logs (
  id SERIAL PRIMARY KEY,
  run_at TIMESTAMPTZ DEFAULT NOW(),
  new_count INT DEFAULT 0,
  updated_count INT DEFAULT 0,
  expired_count INT DEFAULT 0,
  total_scraped INT DEFAULT 0,
  source TEXT DEFAULT 'aucnet',
  error TEXT,
  duration_ms INT
);

-- Session state
CREATE TABLE IF NOT EXISTS session_state (
  id INT PRIMARY KEY DEFAULT 1,
  cookies_path TEXT,
  last_login TIMESTAMPTZ,
  is_valid BOOLEAN DEFAULT false,
  auction_user_id TEXT,
  auction_password TEXT
);

-- Auction sites
CREATE TABLE IF NOT EXISTS auction_sites (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  user_id TEXT,
  password TEXT,
  is_enabled BOOLEAN DEFAULT false,
  is_connected BOOLEAN DEFAULT false,
  last_login TIMESTAMPTZ,
  last_sync TIMESTAMPTZ,
  cookies_path TEXT
);

-- Users
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT DEFAULT 'customer',
  is_active BOOLEAN DEFAULT true,
  crm_user_id TEXT UNIQUE,
  crm_customer_id TEXT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_login_at TIMESTAMPTZ
);

-- Car lists
CREATE TABLE IF NOT EXISTS car_lists (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  user_id INT NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Car list items
CREATE TABLE IF NOT EXISTS car_list_items (
  id SERIAL PRIMARY KEY,
  list_id INT NOT NULL REFERENCES car_lists(id) ON DELETE CASCADE,
  auction_id INT NOT NULL,
  note TEXT,
  added_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(list_id, auction_id)
);

-- Bid requests
CREATE TABLE IF NOT EXISTS bid_requests (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id),
  auction_id INT NOT NULL,
  max_bid DECIMAL(12,2),
  note TEXT,
  status TEXT DEFAULT 'pending',
  crm_bid_ref_code TEXT,
  sent_to_crm BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  reviewed_at TIMESTAMPTZ,
  UNIQUE(user_id, auction_id)
);

-- Seed default auction sites
INSERT INTO auction_sites (id, name, url) VALUES
  ('aucnet', 'Aucnet', 'https://www.aucneostation.com/'),
  ('uss', 'USS/NINJA', 'https://www.ninja-cartrade.jp/'),
  ('taa', 'TAA', 'https://taacaa.jp/')
ON CONFLICT (id) DO NOTHING;
`;

async function main() {
  try {
    await client.connect();
    console.log("[init-db] Connected to database");
    await client.query(SQL);
    console.log("[init-db] All tables created/verified");
  } catch (err) {
    console.error("[init-db] Error:", err.message);
    process.exit(1);
  } finally {
    await client.end();
  }
}

main();
