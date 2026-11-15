"""Limits every case carries about the NISAR products it used, read from the catalog (never typed by hand).

- product maturity: the CRID of each product (e.g. P05023 = provisional);
- wavelength: products without centerFrequency (no radar_geometry.npz value and no raw .h5) fall back to
  config.WAVELENGTH_M (recipes/wavelength.py).
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)
PROVISIONAL = "provisional"


def _limit(fr: str, en: str, ar: str) -> dict:
    return {"template": "backend.case_limit", "params": {}, "text": {"fr": fr, "en": en, "ar": ar}}


def crid_limits(products: list, extra: list[tuple[str, str]] = ()) -> list[dict]:
    """One limit per maturity that is not 'validated', naming the CRIDs. extra: (crid, maturity) pairs read from
    the inputs when the products themselves are not in the local catalog."""
    by_maturity: dict[str, set[str]] = {}
    for crid, maturity in [(getattr(p, "crid", ""), getattr(p, "maturity", "unknown")) for p in products] + list(extra):
        if crid:
            by_maturity.setdefault(maturity or "unknown", set()).add(crid)
    out = []
    if PROVISIONAL in by_maturity:
        crids = ", ".join(sorted(by_maturity[PROVISIONAL]))
        out.append(_limit(f"Produits NISAR provisoires (CRID {crids}) : les valeurs peuvent changer avec les produits "
                          "validés.",
                          f"Provisional NISAR products (CRID {crids}): values may change with the validated products.",
                          f"منتجات NISAR مؤقتة (CRID {crids}): قد تتغير القيم مع المنتجات المعتمدة."))
    if "unknown" in by_maturity:
        crids = ", ".join(sorted(by_maturity["unknown"]))
        out.append(_limit(f"Maturité inconnue pour le CRID {crids}.", f"Unknown maturity for CRID {crids}.",
                          f"نضج غير معروف لـ CRID {crids}."))
    return out


def wavelength_limits(products: list) -> list[dict]:
    """A limit when some products use the config wavelength because their centerFrequency is not available."""
    if not products:
        return []
    from config import WAVELENGTH_M
    from recipes.wavelength import wavelength_m
    fallback = []
    for p in products:
        try:
            _, source = wavelength_m(p)
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            log.warning("%s: wavelength source unknown (%s)", getattr(p, "id", p), exc)
            source = "config"
        if source.startswith("config"):
            fallback.append(p)
    if not fallback:
        return []
    n, m = len(fallback), len(products)
    return [_limit(f"{n} produit(s) sur {m} sans centerFrequency (pas de .h5 brut) : longueur d'onde de la "
                   f"configuration, λ = {WAVELENGTH_M} m.",
                   f"{n} of {m} product(s) have no centerFrequency (no raw .h5): the config wavelength "
                   f"λ = {WAVELENGTH_M} m is used.",
                   f"{n} من أصل {m} منتجات بدون centerFrequency (لا يوجد ملف .h5 خام): استُخدم الطول الموجي "
                   f"λ = {WAVELENGTH_M} م من الإعدادات.")]


def product_limits(products: list, extra: list[tuple[str, str]] = ()) -> list[dict]:
    return crid_limits(products, extra) + wavelength_limits(products)
