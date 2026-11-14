import { clamp01, easeInOutCubic, PASS_HEADING, type PassDirection } from "./motion";

/**
 * Drawing of a NISAR pass in screen space, over the map.
 *
 * Geometry shown (schematic, not to scale): the satellite moves along its
 * ground track; the radar looks to the LEFT of the track (NISAR is a
 * left-looking SAR), so the imaged swath is a strip beside the track. The
 * footprint of the beam slides along the strip; behind it the ground has been
 * imaged. Pulses leave the satellite towards the swath.
 */

export interface Pt {
  x: number;
  y: number;
}

export interface PassGeometry {
  /** Flight direction (unit vector, screen space, y down). */
  u: Pt;
  /** Look direction: left of the flight direction. */
  look: Pt;
  /** Point the swath is centred on. */
  centre: Pt;
  /** Along-track extent [start, end] in px relative to the centre. */
  along: [number, number];
  /** Cross-track: near and far edges of the swath, px from the ground track. */
  near: number;
  far: number;
  /** Offset of the ground track from the centre (towards the right of flight). */
  trackOffset: number;
}

export function headingVector(direction: PassDirection): Pt {
  const rad = (PASS_HEADING[direction] * Math.PI) / 180;
  return { x: Math.sin(rad), y: -Math.cos(rad) };
}

const dot = (a: Pt, b: Pt) => a.x * b.x + a.y * b.y;
const add = (a: Pt, b: Pt, k = 1): Pt => ({ x: a.x + b.x * k, y: a.y + b.y * k });

/** A pass that covers the given screen points (or the whole viewport). */
export function passCovering(direction: PassDirection, width: number, height: number, points: Pt[] = []): PassGeometry {
  const u = headingVector(direction);
  const look: Pt = { x: u.y, y: -u.x };
  const centre: Pt = points.length
    ? { x: points.reduce((s, p) => s + p.x, 0) / points.length, y: points.reduce((s, p) => s + p.y, 0) / points.length }
    : { x: width / 2, y: height / 2 };
  // Along-track: run from beyond one edge of the viewport to beyond the other.
  const corners: Pt[] = [{ x: 0, y: 0 }, { x: width, y: 0 }, { x: 0, y: height }, { x: width, y: height }];
  const proj = corners.map((c) => dot({ x: c.x - centre.x, y: c.y - centre.y }, u));
  const margin = 60;
  const along: [number, number] = [Math.min(...proj) - margin, Math.max(...proj) + margin];
  // Cross-track: wide enough for every target, at least a third of the view.
  const cross = points.map((p) => dot({ x: p.x - centre.x, y: p.y - centre.y }, look));
  const half = Math.max(Math.min(width, height) * 0.22, ...cross.map((c) => Math.abs(c) + 36));
  const trackOffset = half + Math.min(width, height) * 0.08;
  return { u, look, centre, along, near: trackOffset - half, far: trackOffset + half, trackOffset };
}

/** Position of the satellite (on the ground track) for progress t in [0,1]. */
function satAt(g: PassGeometry, t: number): Pt {
  const s = g.along[0] + (g.along[1] - g.along[0]) * t;
  const track = add(g.centre, g.look, -g.trackOffset);
  return add(track, g.u, s);
}

function quad(ctx: CanvasRenderingContext2D, pts: Pt[]) {
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  for (const p of pts.slice(1)) ctx.lineTo(p.x, p.y);
  ctx.closePath();
}

export interface PassStyle {
  ink: string; // rgb triplet "r g b"
  accent: string;
}

/**
 * Draws one frame of a pass. `t` is the linear progress; the beam position is eased.
 * Returns the along-track coordinate (px from the centre) of the beam front.
 */
export function drawPass(ctx: CanvasRenderingContext2D, g: PassGeometry, t: number, style: PassStyle, now: number, fade = 1): number {
  const e = easeInOutCubic(clamp01(t));
  const sat = satAt(g, e);
  const track = add(g.centre, g.look, -g.trackOffset);
  const startS = g.along[0];
  const frontS = g.along[0] + (g.along[1] - g.along[0]) * e;
  const at = (s: number, c: number) => add(add(track, g.u, s), g.look, c);

  ctx.save();
  ctx.globalAlpha = fade;

  // Ground track, dashed, ahead of and behind the satellite.
  ctx.setLineDash([6, 8]);
  ctx.lineWidth = 1.25;
  ctx.strokeStyle = `rgb(${style.ink} / 0.45)`;
  ctx.beginPath();
  const a = at(g.along[0], 0), b = at(g.along[1], 0);
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.stroke();
  ctx.setLineDash([]);

  // Imaged strip behind the beam.
  const grad = ctx.createLinearGradient(at(startS, 0).x, at(startS, 0).y, at(frontS, 0).x, at(frontS, 0).y);
  grad.addColorStop(0, `rgb(${style.accent} / 0.04)`);
  grad.addColorStop(1, `rgb(${style.accent} / 0.20)`);
  ctx.fillStyle = grad;
  quad(ctx, [at(startS, g.near), at(frontS, g.near), at(frontS, g.far), at(startS, g.far)]);
  ctx.fill();

  // Swath edges.
  ctx.strokeStyle = `rgb(${style.accent} / 0.55)`;
  ctx.lineWidth = 1;
  for (const c of [g.near, g.far]) {
    const p = at(startS, c), q = at(frontS, c);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(q.x, q.y);
    ctx.stroke();
  }

  // Beam front: the line being imaged now.
  ctx.strokeStyle = "rgb(255 255 255 / 0.95)";
  ctx.lineWidth = 2.5;
  ctx.shadowColor = `rgb(${style.accent} / 0.9)`;
  ctx.shadowBlur = 12;
  const f0 = at(frontS, g.near), f1 = at(frontS, g.far);
  ctx.beginPath();
  ctx.moveTo(f0.x, f0.y);
  ctx.lineTo(f1.x, f1.y);
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Pulses: arcs leaving the satellite towards the swath (side-looking).
  const lookAngle = Math.atan2(g.look.y, g.look.x);
  const period = 260;
  for (let k = 0; k < 4; k++) {
    const phase = ((now / period + k / 4) % 1 + 1) % 1;
    const r = g.near * 0.35 + (g.far - g.near * 0.35) * phase;
    ctx.strokeStyle = `rgb(${style.accent} / ${0.55 * (1 - phase)})`;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(sat.x, sat.y, r, lookAngle - 0.32, lookAngle + 0.32);
    ctx.stroke();
  }

  // Satellite.
  ctx.fillStyle = `rgb(${style.ink})`;
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(sat.x, sat.y, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  // Solar panel hint: a short bar across the flight direction.
  ctx.strokeStyle = `rgb(${style.ink})`;
  ctx.lineWidth = 2;
  const p0 = add(sat, g.look, 10), p1 = add(sat, g.look, -10);
  ctx.beginPath();
  ctx.moveTo(p0.x, p0.y);
  ctx.lineTo(p1.x, p1.y);
  ctx.stroke();

  ctx.restore();
  return frontS;
}

/** Along-track coordinate of a screen point, comparable to drawPass's return value. */
export function alongOf(g: PassGeometry, p: Pt): number {
  const track = add(g.centre, g.look, -g.trackOffset);
  return dot({ x: p.x - track.x, y: p.y - track.y }, g.u);
}

/** Expanding echo ring on a target the beam has just crossed. */
export function drawEcho(ctx: CanvasRenderingContext2D, p: Pt, age: number, style: PassStyle) {
  const life = 900;
  if (age < 0 || age > life) return;
  ctx.save();
  for (const [delay, max] of [[0, 34], [180, 22]] as const) {
    const kk = clamp01((age - delay) / (life - delay));
    if (kk <= 0) continue;
    ctx.strokeStyle = `rgb(${style.accent} / ${0.8 * (1 - kk)})`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 8 + max * kk, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

/** Fraction of the image already imaged, for a north-up image of the given size, matching the pass direction. */
export function revealClip(direction: PassDirection, w: number, h: number, t: number): Pt[] {
  const u = headingVector(direction);
  // Extent of the image along u, centred.
  const corners: Pt[] = [{ x: -w / 2, y: -h / 2 }, { x: w / 2, y: -h / 2 }, { x: -w / 2, y: h / 2 }, { x: w / 2, y: h / 2 }];
  const proj = corners.map((c) => dot(c, u));
  const lo = Math.min(...proj), hi = Math.max(...proj);
  const front = lo + (hi - lo) * easeInOutCubic(clamp01(t));
  const look: Pt = { x: u.y, y: -u.x };
  const big = w + h;
  const c: Pt = { x: w / 2, y: h / 2 };
  const back = add(c, u, lo - 4);
  const fr = add(c, u, front);
  return [add(back, look, -big), add(fr, look, -big), add(fr, look, big), add(back, look, big)];
}

/** Along-track coordinates of the image's start and end, plus the current front (for the glow line). */
export function revealFront(direction: PassDirection, w: number, h: number, t: number): [Pt, Pt] {
  const u = headingVector(direction);
  const corners: Pt[] = [{ x: -w / 2, y: -h / 2 }, { x: w / 2, y: -h / 2 }, { x: -w / 2, y: h / 2 }, { x: w / 2, y: h / 2 }];
  const proj = corners.map((c) => dot(c, u));
  const lo = Math.min(...proj), hi = Math.max(...proj);
  const front = lo + (hi - lo) * easeInOutCubic(clamp01(t));
  const look: Pt = { x: u.y, y: -u.x };
  const fr = add({ x: w / 2, y: h / 2 }, u, front);
  return [add(fr, look, -(w + h)), add(fr, look, w + h)];
}
