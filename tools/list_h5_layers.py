#!/usr/bin/env python3
"""Liste les datasets d'un fichier HDF5 NISAR (chemin, forme, type), en lecture seule (h5py seulement).
Sert à vérifier les noms de couches avant d'éditer EXTRA_LAYERS / EXTRA_META_KEYWORDS dans download_all.py.

Usage :
    python tools/list_h5_layers.py <fichier.h5> [mot-clé ...]
Sans mot-clé : tous les datasets. Avec mots-clés : ceux dont le chemin contient l'un d'eux (insensible à la casse).
Exemples (PowerShell) :
    python tools/list_h5_layers.py D:\\nisar_data\\GUNW\\<nom>\\<nom>.h5
    python tools/list_h5_layers.py <fichier.h5> iono tropo tide mask coherence
"""
import sys


def list_datasets(path, keywords=()):
    """Renvoie [(chemin, forme, dtype)] triés ; `keywords` filtre sur le chemin (insensible à la casse)."""
    import h5py
    kws = [k.lower() for k in keywords]
    out = []

    def visit(name, obj):
        if isinstance(obj, h5py.Dataset) and (not kws or any(k in name.lower() for k in kws)):
            out.append(("/" + name, tuple(obj.shape), str(obj.dtype)))

    with h5py.File(path, "r") as h5:
        h5.visititems(visit)
    return sorted(out)


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    try:
        rows = list_datasets(argv[1], argv[2:])
    except (OSError, ImportError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    for p, shape, dtype in rows:
        print(f"{p}  shape={shape}  dtype={dtype}")
    print(f"-- {len(rows)} dataset(s)" + (f" pour {', '.join(argv[2:])}" if argv[2:] else ""), file=sys.stderr)
    return 0 if rows else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
