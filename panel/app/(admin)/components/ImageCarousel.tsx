"use client";

import { useState } from "react";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";
import { proxyUrl } from "@/lib/image";

interface ImageCarouselProps {
  images: string[];
  alt: string;
}

function Thumb({ src, alt, onClick }: { src: string; alt: string; onClick: () => void }) {
  const [ok, setOk] = useState(true);
  if (!ok) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      className="h-12 w-16 rounded object-cover bg-muted flex-shrink-0 cursor-pointer opacity-70 hover:opacity-100 hover:ring-2 ring-primary transition-all"
      onError={() => setOk(false)}
      onClick={onClick}
      loading="lazy"
    />
  );
}

export function ImageCarousel({ images, alt }: ImageCarouselProps) {
  const [lightbox, setLightbox] = useState<string | null>(null);

  const proxied = images.map(proxyUrl).filter(Boolean);

  if (proxied.length === 0) {
    return (
      <div className="w-full aspect-[4/3] rounded-lg bg-muted flex items-center justify-center text-muted-foreground text-sm">
        No images available
      </div>
    );
  }

  if (proxied.length === 1) {
    return (
      <>
        <button onClick={() => setLightbox(proxied[0])} className="w-full cursor-zoom-in">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={proxied[0]} alt={alt} className="w-full rounded-lg object-contain bg-muted" />
        </button>
        {lightbox && <Lightbox src={lightbox} alt={alt} onClose={() => setLightbox(null)} />}
      </>
    );
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <Carousel className="w-full" opts={{ loop: true }}>
          <CarouselContent className="-ml-0">
            {proxied.map((url, i) => (
              <CarouselItem key={i} className="pl-0">
                <div
                  className="relative w-full cursor-zoom-in overflow-hidden rounded-lg bg-muted"
                  style={{ paddingBottom: "75%" }}
                  onClick={() => setLightbox(url)}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={url}
                    alt={`${alt} - ${i + 1}`}
                    className="absolute inset-0 h-full w-full object-cover"
                    loading={i === 0 ? "eager" : "lazy"}
                  />
                </div>
              </CarouselItem>
            ))}
          </CarouselContent>
          <CarouselPrevious className="left-2" />
          <CarouselNext className="right-2" />
        </Carousel>
      </div>

      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {proxied.map((url, i) => (
          <Thumb key={i} src={url} alt={`Thumb ${i + 1}`} onClick={() => setLightbox(url)} />
        ))}
      </div>

      <p className="text-[11px] text-muted-foreground">{proxied.length} photos</p>

      {lightbox && <Lightbox src={lightbox} alt={alt} onClose={() => setLightbox(null)} />}
    </div>
  );
}

function Lightbox({ src, alt, onClose }: { src: string; alt: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4 backdrop-blur-sm" onClick={onClose}>
      <button className="absolute top-4 right-4 text-white/60 hover:text-white text-3xl font-light z-50" onClick={onClose}>
        ✕
      </button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} className="max-h-[90vh] max-w-[90vw] object-contain rounded" onClick={(e) => e.stopPropagation()} />
    </div>
  );
}
