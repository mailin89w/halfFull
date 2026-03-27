# Per-Condition Top-1 / Top-3 Across All Layers

Generated: 2026-03-27

- Cohort: `profiles_v3_three_layer.json`
- Sample: `600` profiles with seed `42`
- Final layer uses the kept KNN reranker version: top-1 frozen, slot-2/3 rescue bonuses, unsupported-condition penalties

| Condition | N | ML Top-1 | ML Top-3 | Bayesian Top-1 | Bayesian Top-3 | Final Top-1 | Final Top-3 | Bayes Top-3 Gain | Final Top-3 Gain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Hepatitis | 43 | 11.6% | 27.9% | 55.8% | 72.1% | 55.8% | 72.1% | +44.2% | +0.0% |
| Iron Deficiency | 38 | 0.0% | 15.8% | 73.7% | 92.1% | 73.7% | 92.1% | +76.3% | +0.0% |
| Anemia | 60 | 10.0% | 46.7% | 46.7% | 56.7% | 46.7% | 58.3% | +10.0% | +1.7% |
| Hypothyroidism | 68 | 70.6% | 92.6% | 79.4% | 98.5% | 79.4% | 98.5% | +5.9% | +0.0% |
| Kidney | 43 | 0.0% | 23.3% | 46.5% | 74.4% | 46.5% | 79.1% | +51.2% | +4.7% |
| Prediabetes | 43 | 2.3% | 25.6% | 18.6% | 79.1% | 18.6% | 86.0% | +53.5% | +7.0% |
| Electrolytes | 44 | 0.0% | 47.7% | 43.2% | 61.4% | 43.2% | 59.1% | +13.6% | -2.3% |
| Inflammation | 46 | 15.2% | 28.3% | 37.0% | 39.1% | 37.0% | 39.1% | +10.9% | +0.0% |
| Sleep Disorder | 82 | 32.9% | 90.2% | 19.5% | 56.1% | 19.5% | 56.1% | -34.1% | +0.0% |
| Perimenopause | 68 | 0.0% | 0.0% | 0.0% | 13.2% | 0.0% | 13.2% | +13.2% | +0.0% |
| Liver | 41 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | +0.0% | +0.0% |
