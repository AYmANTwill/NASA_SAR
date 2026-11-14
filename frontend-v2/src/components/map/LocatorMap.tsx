import { useEffect, useMemo, useState } from "react";
import type { Bounds } from "@/api/contract";
import { landPath, locatorView, project } from "./extent";
import { loadLand, type Ring } from "./land";
import "./LocatorMap.css";

const WIDTH = 320;
const HEIGHT = 180;

/**
 * A small, offline locator: coastlines around the case and its study area
 * (the API's bbox) as a rectangle, with the API's point. Decorative for screen
 * readers: the place name is always given in text next to it.
 */
export function LocatorMap({ bbox, point }: { bbox: Bounds; point: { lat: number; lon: number } }) {
  const [rings, setRings] = useState<Ring[] | null>(null);
  useEffect(() => {
    let live = true;
    void loadLand().then((r) => live && setRings(r));
    return () => {
      live = false;
    };
  }, []);

  const view = useMemo(() => locatorView(bbox, WIDTH, HEIGHT), [bbox]);
  const land = useMemo(() => (rings ? landPath(view, rings) : ""), [rings, view]);
  const [x0, y0] = project(view, bbox[0], bbox[3]);
  const [x1, y1] = project(view, bbox[2], bbox[1]);
  const [px, py] = project(view, point.lon, point.lat);

  return (
    <svg className="locator" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMid slice">
      <rect className="locator-sea" width={WIDTH} height={HEIGHT} />
      <path className="locator-land" d={land} />
      <rect className="locator-area" x={x0} y={y0} width={Math.max(x1 - x0, 2)} height={Math.max(y1 - y0, 2)} />
      <circle className="locator-point" cx={px} cy={py} r={3} />
    </svg>
  );
}
