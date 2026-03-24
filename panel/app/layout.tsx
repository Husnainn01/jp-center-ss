import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import { Providers } from "./providers";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "SS Holdings Auction",
  description: "Japanese car auction listings dashboard",
  icons: {
    icon: "/background.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={cn("dark font-sans", geist.variable)}>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
