# Rule (a) recounted with the two excluded pairs removed (no refit; generated from ffm_by_variant_{A,B,C}.json)

Rule (a): k > 0 at more than 3 sigma on at least 3 "tracks" (code: `MIN_TRACKS = 3`, `sign_decision.py:22,61`) and none significantly < 0. The code counts the entries of the `ffm_sign` result, keyed by pair id (so the two T141 F085 product variants, which share an id, count once).
Excluded by `EXCLUSION_CRITERION.md`: T4 F005 and T76 F005.

| Variant | Counted as the code does (distinct pair ids) | Pair-frames (the two T141 F085 variants separately) | Distinct tracks | Distinct geometries (track + direction) | Asc / desc geometries | Flipped frames | Rule (a) met |
|---|---|---|---|---|---|---|---|
| A, without excluded | 5 | 6 of 6 | 3 (T141, T40, T76) | 3 (T141 desc, T40 desc, T76 asce) | 1 / 2 | 0 | yes |
| A, all pairs (for comparison) | 6 | 7 of 8 | 3 | 3 | 1 / 2 | 0 | yes |
| B, without excluded | 5 | 6 of 6 | 3 (T141, T40, T76) | 3 (T141 desc, T40 desc, T76 asce) | 1 / 2 | 0 | yes |
| B, all pairs (for comparison) | 6 | 7 of 8 | 3 | 3 | 1 / 2 | 0 | yes |
| C, without excluded | 5 | 6 of 6 | 3 (T141, T40, T76) | 3 (T141 desc, T40 desc, T76 asce) | 1 / 2 | 0 | yes |
| C, all pairs (for comparison) | 6 | 7 of 8 | 3 | 3 | 1 / 2 | 0 | yes |

Reading: rule (a) is met in all three variants, with or without the excluded pairs, but it rests on **three tracks and three geometries (T40 and T141 descending, T76 ascending)**; without the excluded pairs the only ascending geometry is T76 F006 (T4 is excluded). Rule (b) (pooled VR difference >= 0.10) and rule (c) are not met, so the decision stays undecided.
