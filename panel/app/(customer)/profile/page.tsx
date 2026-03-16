"use client";

import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { User, Mail, Shield } from "lucide-react";

export default function ProfilePage() {
  const { data: session } = useSession();

  if (!session) {
    return <div className="text-center py-10 text-muted-foreground text-sm">Loading...</div>;
  }

  const user = session.user as { name?: string; email?: string; role?: string };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Profile</h1>
        <p className="text-sm text-muted-foreground">Your account information</p>
      </div>

      <Card className="max-w-md">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Account Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
              <User className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="font-semibold">{user.name}</p>
              <Badge variant="secondary" className="text-[10px] capitalize mt-0.5">
                <Shield className="h-3 w-3 mr-1" />{user.role}
              </Badge>
            </div>
          </div>

          <div className="space-y-3 pt-2">
            <div className="flex items-center gap-2">
              <Mail className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">{user.email}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
