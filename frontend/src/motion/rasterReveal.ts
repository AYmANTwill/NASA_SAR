import type { PassDirection } from "./motion";
import { revealClip, revealFront } from "./swath";

/**
 * A raster layer drawn into a canvas so it can be revealed strip by strip,
 * in the flight direction of the pass that acquired it. The pixels are the
 * backend's PNG, unchanged; only how much of it is shown varies.
 */
export interface RevealRaster {
  url: string;
  canvas: HTMLCanvasElement;
  img: HTMLImageElement;
  loaded: Promise<boolean>;
}

export function loadRaster(url: string): RevealRaster {
  const canvas = document.createElement("canvas");
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.decoding = "async";
  const loaded = new Promise<boolean>((resolve) => {
    img.onload = () => {
      canvas.width = Math.max(1, img.naturalWidth);
      canvas.height = Math.max(1, img.naturalHeight);
      resolve(true);
    };
    img.onerror = () => resolve(false);
  });
  img.src = url;
  return { url, canvas, img, loaded };
}

/** Draws the part of the raster already imaged at progress t (1 = whole image). */
export function drawReveal(r: RevealRaster, direction: PassDirection | null, t: number) {
  const ctx = r.canvas.getContext("2d");
  if (!ctx) return;
  const { width: w, height: h } = r.canvas;
  ctx.clearRect(0, 0, w, h);
  if (t <= 0) return;
  if (!direction || t >= 1) {
    ctx.drawImage(r.img, 0, 0, w, h);
    return;
  }
  ctx.save();
  const clip = revealClip(direction, w, h, t);
  ctx.beginPath();
  ctx.moveTo(clip[0].x, clip[0].y);
  for (const p of clip.slice(1)) ctx.lineTo(p.x, p.y);
  ctx.closePath();
  ctx.clip();
  ctx.drawImage(r.img, 0, 0, w, h);
  ctx.restore();
  // The line being imaged now.
  const [a, b] = revealFront(direction, w, h, t);
  ctx.save();
  ctx.strokeStyle = `rgb(255 255 255 / ${0.85 * (1 - t ** 4)})`;
  ctx.lineWidth = Math.max(2, Math.min(w, h) / 90);
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.stroke();
  ctx.restore();
}
