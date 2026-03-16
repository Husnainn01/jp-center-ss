export function proxyUrl(url: string | null | undefined): string {
  if (!url) return "";
  // S3 proxied images — route through frontend /api/ which proxies to backend
  if (url.startsWith("/s3/")) return `/api/s3-image${url.slice(3)}`;
  // Legacy S3 direct URLs — convert to proxy path
  if (url.includes("storageapi.dev")) {
    const match = url.match(/\/(ninja-images|taa-images)\/([a-f0-9]+\.jpg)$/);
    if (match) return `/api/s3-image/${match[1]}/${match[2]}`;
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
