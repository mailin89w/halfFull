# KNN Layer Explained Like I'm 5

Generated: 2026-03-27

## One-Sentence Summary

The KNN layer looks at "people who seem similar" and asks:

"Do similar people usually support this diagnosis, or does this diagnosis look suspicious here?"

Then it makes small changes to the Bayesian shortlist:
- it can help rescue a likely missed condition into slot 2 or 3
- it can push down a weak over-flagged condition if similar people do not support it
- it is **not allowed** to invent a brand-new top-1 diagnosis

## ELI5 Version

Imagine we already have a best guess list after the ML models and Bayesian questions:

1. thyroid
2. prediabetes
3. inflammation

Now KNN comes in and says:

- "This person looks a lot like other people who had kidney-type lab patterns"
- or "People like this do **not** usually look like thyroid cases"

So KNN does two kinds of things:

1. **Support**
If similar people often show a kidney-like or liver-like pattern, KNN gives that condition a small boost.

2. **Doubt**
If the model is shouting "thyroid" or "kidney" but similar people do not show that pattern, KNN can lower that condition a bit.

But KNN is only a helper. It is not allowed to suddenly say:

"Actually forget everything, the main diagnosis is now something completely different."

That is why top-1 is frozen in the current version.

## Why We Added It

Our main system problem is over-flagging:
- too many users are being marked as sick with too many things
- some conditions stay in the top-3 even when they are probably false positives
- the weakest models, especially kidney / thyroid / prediabetes / inflammation / electrolytes, often appear too often

The KNN layer is supposed to help with two things:

1. rescue plausible missed comorbidities
2. reduce unsupported false positives

## What "KNN" Means Here

KNN = k-nearest neighbors.

In simple terms:
- take the user's current pattern
- find similar users / similar lab-pattern neighborhoods
- convert those neighborhoods into broad lab-group signals

Examples of lab groups:
- `kidney`
- `liver_panel`
- `inflammation`
- `glycemic`
- `lipids`
- `thyroid`
- `iron_studies`
- `cbc`

Those group signals are then used to slightly rerank conditions.

## Where The Logic Lives

- KNN reranker: [knn_condition_reranker.py](/Users/annaesakova/aipm/halfFull/evals/pipeline/knn_condition_reranker.py)
- Eval harness: [run_knn_condition_rerank_eval.py](/Users/annaesakova/aipm/halfFull/evals/run_knn_condition_rerank_eval.py)
- Layered report wiring: [run_layered_knn_report.py](/Users/annaesakova/aipm/halfFull/evals/run_layered_knn_report.py)

## Exact Logic Right Now

### Step 1: Start from Bayesian scores

KNN only runs **after** Bayesian.

So the order is:

1. ML models make initial guesses
2. Bayesian questions rerank those guesses
3. KNN makes a small final adjustment

### Step 2: Only look at plausible candidates

KNN ignores very weak conditions.

Current guardrails:
- minimum Bayesian prior: `0.20`
- only top `6` Bayesian conditions are considered
- KNN only meaningfully tries to affect the shortlist around top-3

### Step 3: Positive support bonuses

If KNN sees a condition-specific neighborhood pattern, it can add a small bonus.

Current examples:
- `kidney` gets support from `kidney`
- `liver` gets support from `liver_panel`
- `hepatitis` gets support from `liver_panel`
- `inflammation` gets support from `inflammation`
- `prediabetes` gets support from `glycemic` and `lipids`
- `thyroid` gets support from `thyroid`
- `iron_deficiency` gets support from `iron_studies` and `cbc`
- `anemia` gets support from `cbc` and `iron_studies`

These are the base boosts:
- kidney: `+0.08`
- liver: `+0.08`
- hepatitis: `+0.08`
- inflammation: `+0.08`
- prediabetes: `+0.08` from glycemic or `+0.03` from lipids
- thyroid: `+0.08`
- iron deficiency: `+0.08` from iron studies or `+0.03` from CBC
- anemia: `+0.06` from CBC or `+0.04` from iron studies

### Step 4: Comorbidity pair boosts

If the top-1 condition and the candidate often co-occur clinically, KNN can add a little extra.

Current pairs:
- anemia <-> kidney: `+0.03`
- liver <-> hepatitis: `+0.03`
- prediabetes <-> inflammation: `+0.02`

### Step 5: Slot-2 / Slot-3 rescue boosts

This is the key design choice.

We decided KNN should work harder on **slots 2 and 3**, not on replacing the main diagnosis.

So if a condition:
- already has some plausible Bayesian support
- is sitting just below the top-3
- and KNN has condition-specific evidence

then it can get extra rescue bonuses to move into the shortlist.

This is why KNN is better at:
- "also consider kidney"
- "also consider prediabetes"

than at:
- "your main diagnosis is now kidney instead of thyroid"

### Step 6: Unsupported-condition penalties

This is the most important recent addition.

Some conditions overfire a lot, so now KNN can also say:

"I do **not** see neighborhood evidence for this."

Current penalized conditions:
- `kidney`
- `thyroid`
- `prediabetes`
- `inflammation`
- `electrolytes`

Current penalty sizes:
- kidney: `-0.10`
- thyroid: `-0.08`
- prediabetes: `-0.08`
- inflammation: `-0.08`
- electrolytes: `-0.06`

Extra penalty:
- shortlist rank 3 gets a little more penalty
- shortlist rank 2 can also get a little more if it is weak

This is meant to trim false positives from the shortlist.

### Step 7: Freeze top-1

In the kept version, top-1 is frozen.

That means:
- KNN can change slot 2 and slot 3
- KNN can penalize the existing top-1 internally
- but the final displayed top-1 condition does not get replaced by KNN

We tested removing this freeze and decided **not** to keep that version.

## What We Evaluated

We compared:

1. Bayesian only
2. Bayesian + KNN rerank

on the same `600`-profile benchmark sample with seed `42`.

Sample composition:
- total profiles: `600`
- labeled profiles: `576`
- multi-condition profiles: `354`
- healthy profiles: `24`

## Current Results Of The Kept Version

This is the version we are keeping:
- top-1 frozen
- slot-2/slot-3 rescue bonuses
- unsupported-condition penalties

### Core Metrics

| Metric | Bayesian only | Bayesian + KNN | Delta |
|---|---:|---:|---:|
| Top-3 primary condition hit rate | 57.8% | 58.7% | +0.9 pp |
| Secondary / comorbidity recovery | 46.3% | 47.2% | +0.8 pp |
| Healthy over-alert | 45.8% | 45.8% | 0.0 pp |
| Top-1 changed profiles | - | 0 | - |

### Added vs Removed Condition Quality

| Metric | Value |
|---|---:|
| Added conditions count | 299 |
| Removed conditions count | 299 |
| Added-condition truth rate | 16.4% |
| Removed-condition truth rate | 14.7% |

Interpretation:
- when KNN swaps conditions in or out of the shortlist, the added conditions are slightly more often true than the removed ones
- this is a good sign, but the margin is still small

### Practical Meaning

The KNN layer is helping a bit:
- it rescues some missed true conditions into top-3
- it rescues some secondary conditions
- it does not make the main diagnosis unstable

But it is **not** a dramatic improvement layer.

## Examples Where It Helped

### Example 1

- Profile: `SYN-C0000097`
- Truth: `kidney`, `liver`, `sleep_disorder`, `electrolytes`
- Bayesian top-3: `thyroid`, `prediabetes`, `anemia`
- KNN top-3: `thyroid`, `prediabetes`, `kidney`

Why:
- KNN saw kidney-group support
- kidney got promoted into slot 3

### Example 2

- Profile: `SYN-R0000224`
- Truth: `prediabetes`, `sleep_disorder`, `iron_deficiency`
- Bayesian top-3: `thyroid`, `inflammation`, `electrolytes`
- KNN top-3: `thyroid`, `inflammation`, `prediabetes`

Why:
- KNN saw lipid support
- prediabetes got rescued into the shortlist

### Example 3

- Profile: `SYN-C0000090`
- Truth: `kidney`, `prediabetes`, `electrolytes`
- Bayesian top-3: `thyroid`, `sleep_disorder`, `prediabetes`
- KNN top-3: `thyroid`, `kidney`, `sleep_disorder`

Why:
- KNN saw kidney support
- kidney was promoted into slot 2

## What Problems Still Remain

### 1. Healthy over-alert did not improve

This is the biggest disappointment.

Healthy over-alert stayed:
- `45.8% -> 45.8%`

So although shortlist quality improved a bit, the user-facing "someone healthy still gets flagged" problem did not move.

Why this likely happened:
- top-1 is frozen
- many healthy profiles already have an overfired top-1 condition
- changing slots 2 and 3 does not fix that
- surfacing logic still often shows at least one condition

### 2. Gains are still small

The improvements are real, but small:
- top-3 primary: `+0.9 pp`
- comorbidity recovery: `+0.8 pp`

That means KNN is currently a helper, not a major engine of performance.

### 3. Added-condition precision is still low

Added conditions are only true:
- `16.4%` of the time

That is better than the removed conditions (`14.7%`), but still weak.

So KNN is helping at the margin, not with high-confidence new discoveries.

### 4. KNN support is still coarse

Right now KNN is mostly using broad lab groups:
- kidney
- glycemic
- inflammation
- liver panel
- CBC

That is useful, but still a blunt instrument.

It does **not** yet know enough about:
- richer comorbidity templates
- symptom-specific neighborhoods
- better disease-specific contradictions

### 5. Some conditions are still too noisy for KNN reranking

We intentionally disabled positive reranking for:
- `electrolytes`
- `sleep_disorder`
- `perimenopause`

because KNN lab groups are too nonspecific there.

That means KNN is not helping those conditions much yet.

## Why We Rejected The "No Frozen Top-1" Version

We also tested a version where KNN was allowed to change top-1.

That version gave:
- top-3 primary hit: `58.5%`
- secondary recovery: `46.9%`
- healthy over-alert: still unchanged
- top-1 changed profiles: `44`

Of those top-1 changes:
- `11` were true improvements
- `2` were true worsenings

Why we did **not** keep it:
- it did not improve enough
- it made the main diagnosis less stable
- it complicated trust and explainability

So the frozen-top1 version is safer and cleaner for now.

## What The KNN Layer Is Good For Right Now

Right now, KNN is best thought of as:

1. a **shortlist cleaner**
2. a **slot-2 / slot-3 rescuer**
3. a **comorbidity hint layer**
4. a **lab/test expansion helper**

It is **not** yet good enough to be:

1. a primary diagnosis engine
2. a strong healthy-profile suppressor
3. a major precision fix by itself

## Best Current Product Use

On the final result page, KNN should mostly be used for:

- adding support lines inside a condition card
- suggesting extra tests from similar cases
- suggesting "also worth checking" comorbidities
- quietly suppressing some weak unsupported shortlist items

It should **not** be the main visible reason why a top diagnosis appears.

## What Can Be Improved Next

### 1. Use KNN more directly in user-facing suppression

This is the biggest next opportunity.

Right now KNN improves the shortlist, but does not reduce healthy over-alert.

So the next step should be:
- if a weak condition is above threshold but KNN gives no support, suppress it from user-facing results
- especially for healthy and borderline users

This is likely the fastest way to reduce "everyone is sick with everything."

### 2. Make KNN contradiction logic stronger

Today the penalty is simple:
- no matching support -> small penalty

A better version would say:
- this profile actively looks unlike a kidney case
- this profile actively looks unlike a thyroid case

That would make KNN a better false-positive filter.

### 3. Add better comorbidity templates

Current pair rules are small and limited.

We can expand clinically plausible pairs like:
- kidney + anemia
- liver + hepatitis
- prediabetes + inflammation
- thyroid + sleep disorder
- iron deficiency + anemia

This should help comorbidity rescue more.

### 4. Use richer neighbor information than lab groups only

Right now KNN mostly uses lab-group support.

It would be stronger if it also used:
- neighbor label prevalence
- age / sex / symptom subgroup context
- real co-occurrence patterns from the anchored cohort

### 5. Measure condition-specific KNN value

Right now we mostly have aggregate numbers.

Next useful analysis:
- which conditions benefit from KNN
- which conditions get worse
- where KNN penalties reduce false positives most

Most likely:
- kidney and prediabetes benefit most
- electrolytes and sleep remain weak

### 6. Give KNN more influence only where it has earned trust

Not every condition should use the same KNN strength.

Better approach:
- stronger KNN role for kidney, liver, hepatitis, prediabetes
- weaker KNN role for electrolytes, sleep, perimenopause

That keeps the layer safer.

## Bottom Line

The KNN layer now does something sensible:
- it helps rescue plausible missed secondary conditions
- it penalizes some unsupported false positives
- it keeps the main diagnosis stable

But it is still a modest helper, not a magic fix.

Current honest summary:
- useful: yes
- dramatic: no
- safest current design: yes
- enough to solve over-flagging by itself: no

The next real win will probably come from combining:
- Bayesian ranking
- KNN-based suppression of unsupported weak conditions
- stricter user-facing surfacing rules for healthy and borderline users
