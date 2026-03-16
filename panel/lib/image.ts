const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:4000";

export function proxyUrl(url: string | null | undefined): string {
  if (!url) return "";
  // S3 proxied images — route through backend
  if (url.startsWith("/s3/")) return `${BACKEND_URL}${url}`;
  // Legacy S3 direct URLs — convert to proxy path
  if (url.includes("storageapi.dev")) {
    const match = url.match(/\/(ninja-images|taa-images)\/([a-f0-9]+\.jpg)$/);
    if (match) return `${BACKEND_URL}/s3/${match[1]}/${match[2]}`;
    return url;
  }
  // AucNet images need proxy due to CloudFront blocking
  if (url.includes("aucnetcars.com")) {
    return `/api/proxy-image?url=${encodeURIComponent(url)}`;
  }
  // Legacy local paths
  if (url.startsWith("/taa-images/") || url.startsWith("/ninja-images/")) return url;
  // TAA remote images
  if (url.includes("taacaa.jp")) {
    return `/api/proxy-image?url=${encodeURIComponent(url)}`;
  }
  return url;
}
