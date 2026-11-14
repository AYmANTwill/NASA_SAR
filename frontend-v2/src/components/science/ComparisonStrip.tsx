import type { Measurement } from "@/api/contract";
import { stripGeometry, type StripMark } from "@/science/strip";
import "./science.css";

const WIDTH = 320;
const HEIGHT = 44;
const NISAR_Y = 15;
const REF_Y = 31;

/**
 * NISAR and the reference on one number line: each mark with its ±1σ (solid)
 * and ±2σ (light) bar. No tick labels: the values are written in the rows
 * above, so the strip is a picture of those numbers and is hidden from
 * screen readers. Left to right in every language, like any number line.
 */
export function ComparisonStrip({ nisar, reference }: { nisar: Measurement; reference: Measurement }) {
  const g = stripGeometry(nisar, reference, WIDTH);
  return (
    <svg className="strip" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} aria-hidden="true" focusable="false">
      <line className="strip-axis" x1="0" x2={WIDTH} y1={HEIGHT / 2} y2={HEIGHT / 2} />
      <Bars mark={g.nisar} y={NISAR_Y} />
      <Bars mark={g.reference} y={REF_Y} />
      <circle className="strip-nisar" cx={g.nisar.x} cy={NISAR_Y} r="4.5" />
      <rect className="strip-ref" x={g.reference.x - 4} y={REF_Y - 4} width="8" height="8" transform={`rotate(45 ${g.reference.x} ${REF_Y})`} />
    </svg>
  );
}

function Bars({ mark, y }: { mark: StripMark; y: number }) {
  return (
    <>
      <line className="strip-s2" x1={mark.sigma2[0]} x2={mark.sigma2[1]} y1={y} y2={y} />
      <line className="strip-s1" x1={mark.sigma1[0]} x2={mark.sigma1[1]} y1={y} y2={y} />
    </>
  );
}

/** The glyphs that tie a row of numbers to its mark on the strip. */
export function NisarGlyph() {
  return (
    <svg className="glyph" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
      <circle cx="6" cy="6" r="4.5" className="strip-nisar" />
    </svg>
  );
}

export function ReferenceGlyph() {
  return (
    <svg className="glyph" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
      <rect x="2" y="2" width="8" height="8" transform="rotate(45 6 6)" className="strip-ref" />
    </svg>
  );
}
