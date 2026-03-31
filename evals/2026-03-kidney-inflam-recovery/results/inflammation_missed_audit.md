# Inflammation Missed-Positive Audit — ML-INFLAM-02

**Cohort:** 760-profile NHANES balanced  |  **Inflammation positives:** 49

## Group Breakdown

| Group | Count | % |
|-------|-------|---|
| missed_both | 30 | 61% |
| found_by_v3_only | 19 | 39% |

## Label Fuzziness Assessment

**The label does not appear obviously fuzzy.**

Missed positives (generic score=1.0702633333333333) look similar to found positives (generic score=1.1174526315789475). The recall problem is likely in model capacity or missing discriminative features, not label quality.

### Recommended Next Steps

1. **Add lab features**: If NHANES hsCRP or ESR is available, add it —    it is the single best discrimination signal for inflammation.
2. **Threshold sweep**: Run recall vs. precision curve to check if a lower    threshold recovers recall without excessive FPs.
3. **Model architecture**: Swap LR for a gradient-boosted tree that can    capture non-linear waist × HDL × BP interactions.