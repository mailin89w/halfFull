# KNN Condition Rerank Eval

Generated: 2026-03-26T23:40:59Z

## Summary

- Profiles evaluated: `600`
- Labeled profiles: `576`
- Multi-condition profiles: `354`
- Healthy profiles: `24`

## Success Criteria

- Top-3 condition hit rate: `57.8%` -> `58.2%` (`+0.4%`)
- Secondary-condition recovery: `46.3%` -> `46.3%` (`+0.0%`)
- Healthy over-alert: `45.8%` -> `45.8%` (`+0.0%`)
- Added-condition ground-truth rate: `22.2%` across `36` additions
- Removed-condition ground-truth rate: `16.7%` across `36` removals
- Top-1 changed profiles: `0`

## Sample Improved Profiles

- `SYN-C0000097`: expected `['kidney', 'liver', 'sleep_disorder', 'electrolytes']`, Bayes top-3 `['thyroid', 'prediabetes', 'anemia']`, KNN top-3 `['thyroid', 'prediabetes', 'kidney']`, bonuses `{'kidney': {'base_score': 0.3837, 'adjusted_score': 0.4637, 'applied_bonus': 0.08, 'matched_groups': ['kidney'], 'top1_anchor': 'thyroid', 'rank_before': 4}}`
- `SYN-R0000224`: expected `['prediabetes', 'sleep_disorder', 'iron_deficiency']`, Bayes top-3 `['thyroid', 'inflammation', 'electrolytes']`, KNN top-3 `['thyroid', 'inflammation', 'prediabetes']`, bonuses `{'prediabetes': {'base_score': 0.2431, 'adjusted_score': 0.2731, 'applied_bonus': 0.03, 'matched_groups': ['lipids'], 'top1_anchor': 'thyroid', 'rank_before': 4}}`
- `SYN-C0000090`: expected `['kidney', 'prediabetes', 'electrolytes']`, Bayes top-3 `['thyroid', 'sleep_disorder', 'prediabetes']`, KNN top-3 `['thyroid', 'kidney', 'sleep_disorder']`, bonuses `{'kidney': {'base_score': 0.2801, 'adjusted_score': 0.3601, 'applied_bonus': 0.08, 'matched_groups': ['kidney'], 'top1_anchor': 'thyroid', 'rank_before': 4}}`
- `SYN-R0000211`: expected `['prediabetes', 'inflammation']`, Bayes top-3 `['thyroid', 'electrolytes', 'sleep_disorder']`, KNN top-3 `['thyroid', 'electrolytes', 'prediabetes']`, bonuses `{'prediabetes': {'base_score': 0.2637, 'adjusted_score': 0.2937, 'applied_bonus': 0.03, 'matched_groups': ['lipids'], 'top1_anchor': 'thyroid', 'rank_before': 4}}`
