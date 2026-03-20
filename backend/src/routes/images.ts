import { Router } from "express";
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { Readable } from "stream";

export const imagesRouter = Router();

const S3_ENDPOINT = process.env.S3_ENDPOINT || "https://dffe00b2c327c69b4a869d74b4e7a2a2.r2.cloudflarestorage.com";
// Railway storage needs forcePathStyle, Cloudflare R2 also supports it
const s3 = new S3Client({
  endpoint: S3_ENDPOINT,
  region: "auto",
  credentials: {
    accessKeyId: process.env.S3_ACCESS_KEY || "",
    secretAccessKey: process.env.S3_SECRET_KEY || "",
  },
  forcePathStyle: true,
});

const BUCKET = process.env.S3_BUCKET || "jpcenter";

console.log(`[images] S3 endpoint: ${process.env.S3_ENDPOINT || "NOT SET"}`);
console.log(`[images] S3 bucket: ${BUCKET}`);
console.log(`[images] S3 access key: ${(process.env.S3_ACCESS_KEY || "").substring(0, 10)}... (${(process.env.S3_ACCESS_KEY || "").length} chars)`);
console.log(`[images] S3 secret key: ${(process.env.S3_SECRET_KEY || "").length} chars`);

// GET /s3/:prefix/:filename — proxy S3 images with auth
imagesRouter.get("/:prefix/:filename", async (req, res) => {
  const { prefix, filename } = req.params;

  if (!["ninja-images", "taa-images", "iauc-images"].includes(prefix)) {
    res.status(404).send("Not found");
    return;
  }

  if (!/^[a-f0-9]+\.jpg$/.test(filename)) {
    res.status(400).send("Invalid filename");
    return;
  }

  try {
    const command = new GetObjectCommand({
      Bucket: BUCKET,
      Key: `${prefix}/${filename}`,
    });

    const response = await s3.send(command);

    res.set({
      "Content-Type": response.ContentType || "image/jpeg",
      "Cache-Control": "public, max-age=86400, immutable",
    });

    if (response.Body instanceof Readable) {
      response.Body.pipe(res);
    } else {
      const bytes = await response.Body!.transformToByteArray();
      res.send(Buffer.from(bytes));
    }
  } catch (err: unknown) {
    const code = (err as { name?: string }).name;
    const message = (err as { message?: string }).message;
    console.error(`S3 proxy error: [${code}] ${message} — bucket=${BUCKET} key=${prefix}/${filename} endpoint=${S3_ENDPOINT}`);
    if (code === "NoSuchKey") {
      res.status(404).send("Not found");
    } else {
      res.status(500).send("Error");
    }
  }
});
