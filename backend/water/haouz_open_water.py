"""Haouz case: extra finding "open_water_change" (team decision: candidate surface change, no flooded area claimed).

Reads the measured result of haouz_flood.py (outputs/haouz_flooded_area.json: U-Net new open water, MC-dropout +
orbit uncertainty) and writes outputs/haouz_open_water.json with findings[] and figures[] that validate as
science.case_models.Finding / Figure. Ayman's science/cases.py reads it as an extra source; results/ is not touched.
Usage: python haouz_open_water.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from common import OUTPUTS

HERE = Path(__file__).resolve().parent


def main() -> None:
    sys.path.insert(0, str(HERE.parent))
    from science.case_models import Figure, Finding, Measurement, TemplatedText, agreement

    src = json.loads((OUTPUTS / "haouz_flooded_area.json").read_text(encoding="utf-8"))
    n = Measurement(**src["findings"][0]["nisar"])
    zero_ok = abs(n.value) <= 2 * n.one_sigma
    finding = Finding(
        id="open_water_change",
        label={"en": "Persistent open water after the storm (U-Net)",
               "fr": "Eau libre persistante après l'orage (U-Net)",
               "ar": "المياه المفتوحة المستمرة بعد العاصفة (U-Net)"},
        nisar=n, reference=None, reference_source=None, agreement=agreement(n, None)).model_dump(mode="json")
    clouds = Figure(
        id="water_radar_vs_clouds", kind="image",
        title={"en": "Radar sees water through clouds", "fr": "Le radar voit l'eau à travers les nuages",
               "ar": "الرادار يرى المياه عبر السحب"},
        url="water/outputs/figures/clouds.png",
        caption=TemplatedText(template="backend.water_clouds", params={}, text={
            "en": "Same day: the optical water map (OPERA DSWx) is masked by clouds; the NISAR U-Net map is not.",
            "fr": "Même jour : la carte optique de l'eau (OPERA DSWx) est masquée par les nuages ; la carte NISAR U-Net ne l'est pas.",
            "ar": "في اليوم نفسه: خريطة المياه البصرية (OPERA DSWx) محجوبة بالسحب، أما خريطة NISAR U-Net فلا."})
    ).model_dump(mode="json")
    zero = {"en": "consistent with zero" if zero_ok else "distinct from zero",
            "fr": "compatible avec zéro" if zero_ok else "différente de zéro",
            "ar": "متوافقة مع الصفر" if zero_ok else "مختلفة عن الصفر"}
    limits = [
        {"en": f"The value is {zero['en']} at 1σ uncertainty: no flooded area is claimed.",
         "fr": f"La valeur est {zero['fr']} compte tenu de l'incertitude (1σ) : aucune surface inondée n'est revendiquée.",
         "ar": f"القيمة {zero['ar']} ضمن هامش عدم اليقين (1σ): لا يُدّعى وجود مساحة مغمورة."},
        *src["limits"]]  # 12-day revisit (3-5 days after the event, not the peak), narrow valleys, layover/shadow, no DSWx pair
    out = {"case_id": "haouz-flood-2026", "source": "backend/water (Water U-Net)", "date": src["date"], "bbox": src["bbox"],
           "products": src.get("products", []), "findings": [finding], "figures": [clouds], "limits": limits,
           "interpretation": src.get("interpretation"),
           "method": f"Water U-Net, variant '{__import__('timeseries').best_method()}' (ResNet-34) on NISAR GCOV HH/HV; new water = post AND NOT pre, same track; "
                     "1σ = MC-dropout area std and half the ascending/descending range, in quadrature"}
    (OUTPUTS / "haouz_open_water.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"open_water_change: {n.value:.2f} ± {n.uncertainty:.2f} km2 (1σ), {zero['en']}; figures: clouds.png")


if __name__ == "__main__":
    main()
