export function proxyUrl(url: string | null | undefined): string {
  if (!url) return "";
  // S3 images (stored as /s3/prefix/hash.jpg) → frontend proxy → backend → R2
  if (url.startsWith("/s3/")) return `/api/s3-image${url.slice(3)}`;
  // AucNet external images → proxy to bypass CloudFront blocking
  if (url.includes("aucnetcars.com")) {
    return `/api/proxy-image?url=${encodeURIComponent(url)}`;
  }
  return url;
}
