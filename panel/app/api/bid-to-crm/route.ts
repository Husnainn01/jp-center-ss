import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4000";

export async function POST(request: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const user = session.user as {
    id: string;
    crmCustomerId: string | null;
    crmToken: string;
  };

  const body = await request.json();

  try {
    const res = await fetch(`${BACKEND_URL}/api/bid-to-crm`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-user-id": user.id,
        "x-crm-customer-id": user.crmCustomerId || "",
        "x-crm-token": user.crmToken || "",
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to reach backend";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
