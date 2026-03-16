import { type NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

const CRM_API_URL = process.env.CRM_API_URL || "http://localhost:5000";
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4000";

interface CrmLoginResponse {
  token: string;
  user: {
    id: string;
    email: string;
    name: string;
    role: string;
    customerId?: string;
    hasAuctionAccess?: boolean;
  };
}

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;

        try {
          // 1. Authenticate against CRM
          console.log("[AUTH] Attempting CRM login for:", credentials.email);
          const crmRes = await fetch(`${CRM_API_URL}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: credentials.email, password: credentials.password }),
          });

          if (!crmRes.ok) {
            console.log("[AUTH] CRM login failed:", crmRes.status);
            return null;
          }

          const crmData: CrmLoginResponse = await crmRes.json();
          const crmUser = crmData.user;
          console.log("[AUTH] CRM response:", { id: crmUser.id, role: crmUser.role, hasAuctionAccess: crmUser.hasAuctionAccess });

          if (!crmUser.hasAuctionAccess) {
            console.log("[AUTH] Denied — hasAuctionAccess is false");
            return null;
          }

          // 2. Sync user to backend (which has the DB)
          const syncRes = await fetch(`${BACKEND_URL}/api/auth/sync`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              crmUserId: crmUser.id,
              crmCustomerId: crmUser.customerId || null,
              email: crmUser.email,
              name: crmUser.name,
              role: crmUser.role === "ADMIN" ? "admin" : "customer",
            }),
          });

          if (!syncRes.ok) {
            console.error("[AUTH] Backend user sync failed:", syncRes.status);
            return null;
          }

          const localUser = await syncRes.json();
          console.log("[AUTH] Local user synced:", { id: localUser.id, email: localUser.email });

          if (!localUser.isActive) {
            console.log("[AUTH] Denied — local user is inactive");
            return null;
          }

          return {
            id: String(localUser.id),
            email: localUser.email,
            name: localUser.name,
            role: localUser.role,
            crmUserId: crmUser.id,
            crmCustomerId: crmUser.customerId || null,
            crmToken: crmData.token,
          };
        } catch (err) {
          console.error("[AUTH] Login error:", err instanceof Error ? err.message : err);
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.role = (user as unknown as { role: string }).role;
        token.id = user.id;
        token.crmUserId = (user as unknown as { crmUserId: string }).crmUserId;
        token.crmCustomerId = (user as unknown as { crmCustomerId: string | null }).crmCustomerId;
        token.crmToken = (user as unknown as { crmToken: string }).crmToken;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as Record<string, unknown>).role = token.role;
        (session.user as Record<string, unknown>).id = token.id;
        (session.user as Record<string, unknown>).crmUserId = token.crmUserId;
        (session.user as Record<string, unknown>).crmCustomerId = token.crmCustomerId;
        (session.user as Record<string, unknown>).crmToken = token.crmToken;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
  },
};
