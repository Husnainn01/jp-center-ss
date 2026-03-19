const FRONTEND_URL = process.env.FRONTEND_URL || "http://localhost:3000";

export function proxyUrl(url: string | null | undefined): string {
  if (!url) return "";
  // S3/R2 images (stored as /s3/prefix/hash.jpg) → frontend proxy route
  if (url.startsWith("/s3/")) return `${FRONTEND_URL}/api/s3-image${url.slice(3)}`;
  if (url.startsWith("/taa-images/")) return `${FRONTEND_URL}${url}`;
  if (url.includes("aucnetcars.com")) return `${FRONTEND_URL}/api/proxy-image?url=${encodeURIComponent(url)}`;
  if (url.startsWith("/ninja-images/")) return `${FRONTEND_URL}${url}`;
  if (url.includes("taacaa.jp")) return `${FRONTEND_URL}/api/proxy-image?url=${encodeURIComponent(url)}`;
  if (url.startsWith("http")) return url;
  return `${FRONTEND_URL}${url}`;
}
