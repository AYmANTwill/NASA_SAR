"""Run before the demo: computes every library event and the discoveries, stores them in cache/.
Usage:  python precompute.py            (add --no-exposure if there is no internet)"""
import sys
import time

import catalog
import discoveries
import events

if __name__ == "__main__":
    ps = catalog.refresh()
    print(f"{len(ps)} products in the catalog")
    for ev in events.EVENTS:
        t = time.time()
        r = events.compute(ev)
        print(f"- {ev['id']:<16} {r.get('confidence','?'):<7} {r.get('alert_level','?'):<7} "
              f"{time.time()-t:5.1f}s  {(r.get('verdict') or '')[:110]}")
    d = discoveries.scan(with_exposure="--no-exposure" not in sys.argv)
    print(f"discoveries: {len(d['zones'])} zones over {d['n_geometries']} geometries")
    for z in d["zones"][:10]:
        print(f"  #{z['rank']:<2} {z['lat']:.4f},{z['lon']:.4f}  {z['mean']:+.1f} {z['unit']}  "
              f"{z['area_km2']} km²  {z['confidence']}  {z['alert_level']}")
