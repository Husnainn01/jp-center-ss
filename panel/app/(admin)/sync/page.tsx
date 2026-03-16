import { backendFetch } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export const dynamic = "force-dynamic";

interface SyncLog {
  id: number;
  runAt: string;
  newCount: number;
  updatedCount: number;
  expiredCount: number;
  totalScraped: number;
  source: string;
  error: string | null;
  durationMs: number | null;
}

interface SyncLogsResponse {
  logs: SyncLog[];
  session?: {
    lastLogin: string | null;
    isValid: boolean;
  };
}

export default async function SyncLogsPage() {
  const data = await backendFetch<SyncLogsResponse>("/api/sync-logs?limit=20&includeSession=true");

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Sync Logs</h1>
        <p className="text-sm text-muted-foreground">Scraper history and session status</p>
      </div>

      {data.session && (
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Scraper Session</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Last login: {data.session.lastLogin ? formatDate(data.session.lastLogin) : "Never"}
              </p>
            </div>
            <Badge variant={data.session.isValid ? "default" : "destructive"}>
              {data.session.isValid ? "Valid" : "Invalid"}
            </Badge>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Recent Syncs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {data.logs.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground text-sm">No sync logs yet</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead className="text-right">Scraped</TableHead>
                  <TableHead className="text-right">New</TableHead>
                  <TableHead className="text-right">Updated</TableHead>
                  <TableHead className="text-right">Expired</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="text-sm">{formatDate(log.runAt)}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{log.totalScraped}</TableCell>
                    <TableCell className="text-right font-mono text-sm text-emerald-600">+{log.newCount}</TableCell>
                    <TableCell className="text-right font-mono text-sm text-blue-600">{log.updatedCount}</TableCell>
                    <TableCell className="text-right font-mono text-sm text-orange-600">{log.expiredCount}</TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground">
                      {log.durationMs ? `${(log.durationMs / 1000).toFixed(1)}s` : "—"}
                    </TableCell>
                    <TableCell>
                      {log.error ? (
                        <Badge variant="destructive" className="text-[10px]">Error</Badge>
                      ) : (
                        <Badge variant="default" className="text-[10px]">OK</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
