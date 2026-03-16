export function proxyUrl(url: string | null | undefined): string {
  if (!url) return "";
  // S3 bucket images — serve directly (public)
  if (url.includes("storageapi.dev")) return url;
  // AucNet images need proxy due to CloudFront blocking
  if (url.includes("aucnetcars.com")) {
    return `/api/proxy-image?url=${encodeURIComponent(url)}`;
  }
  // Legacy local paths (fallback for old data)
  if (url.startsWith("/taa-images/") || url.startsWith("/ninja-images/")) return url;
  // TAA remote images also need proxy (require auth cookies)
  if (url.includes("taacaa.jp")) {
    return `/api/proxy-image?url=${encodeURIComponent(url)}`;
  }
  return url;
}
