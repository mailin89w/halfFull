from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


FINAL_DATASET = Path("data/processed/nhanes_merged_adults_final.csv")
FINAL_NORMALIZED_DATASET = Path("data/processed/nhanes_merged_adults_final_normalized.csv")
NOTEBOOK_PATH = Path("notebooks/disease_definitions.ipynb")
DEFINITION_JSON = Path("data/processed/perimenopause_proxy_definition.json")


def as_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def yes_no(series: pd.Series, yes: int = 1, no: int = 2) -> pd.Series:
    s = as_num(series)
    out = pd.Series(np.nan, index=series.index, dtype="float64")
    out.loc[s == yes] = 1.0
    out.loc[s == no] = 0.0
    return out


def compute_perimenopause_proxy(df: pd.DataFrame) -> pd.DataFrame:
    age = as_num(df["age_years"])
    menopause = as_num(df["menopause"])
    female = df["gender"].astype("string").str.lower().eq("female")

    hysterectomy = yes_no(df["rhd280___had_a_hysterectomy?"])
    both_ovaries_removed = yes_no(df["rhq305___had_both_ovaries_removed?"])
    pregnant_now = yes_no(df["rhd143___are_you_pregnant_now?"])
    breastfeeding = yes_no(df["rhq200___now_breastfeeding_a_child?"])
    hormone_use = yes_no(df["rhq540___ever_use_female_hormones?"])
    regular_periods = yes_no(df["rhq031___had_regular_periods_in_past_12_months"])

    fsh = as_num(df["LBXFSH_follicle_stimulating_hormone_miu_ml"])
    amh = as_num(df["LBXAMH_anti_mullerian_hormone_ng_ml"])
    age_at_last_period = as_num(df["rhq060___age_at_last_menstrual_period"])
    years_since_last_period = age - age_at_last_period

    sleep_problem = yes_no(df["slq050___ever_told_doctor_had_trouble_sleeping?"])
    fatigue = as_num(df["dpq040___feeling_tired_or_having_little_energy"])

    urinary_leakage_freq = as_num(df["kiq005___how_often_have_urinary_leakage?"])
    urinary_stress = yes_no(df["kiq042___leak_urine_during_physical_activities?"])
    urinary_urge = yes_no(df["kiq044___urinated_before_reaching_the_toilet?"])
    urinary_nonphysical = yes_no(df["kiq046___leak_urine_during_nonphysical_activities"])

    eligible = (
        female
        & age.between(35, 55, inclusive="both")
        & menopause.eq(0)
        & ~hysterectomy.eq(1)
        & ~both_ovaries_removed.eq(1)
        & ~pregnant_now.eq(1)
        & ~breastfeeding.eq(1)
    )

    irregular_periods = regular_periods.eq(0)
    recent_last_period = years_since_last_period.between(0, 1.5, inclusive="both")
    borderline_fsh = fsh.between(10, 24.999, inclusive="both")
    high_fsh = fsh >= 25
    low_amh = amh < 1

    major_transition_evidence = irregular_periods | recent_last_period | high_fsh | (borderline_fsh & low_amh)

    urinary_support = (
        urinary_leakage_freq.gt(1)
        | urinary_stress.eq(1)
        | urinary_urge.eq(1)
        | urinary_nonphysical.eq(1)
    )

    score = pd.Series(0.0, index=df.index, dtype="float64")
    score += np.where(age.between(40, 44, inclusive="both"), 1, 0)
    score += np.where(age.between(45, 55, inclusive="both"), 2, 0)
    score += np.where(irregular_periods, 4, 0)
    score += np.where(recent_last_period, 2, 0)
    score += np.where(borderline_fsh, 2, 0)
    score += np.where(high_fsh, 3, 0)
    score += np.where(low_amh, 2, 0)
    score += np.where(sleep_problem.eq(1), 1, 0)
    score += np.where(fatigue >= 2, 1, 0)
    score += np.where(urinary_support, 1, 0)
    score -= np.where(hormone_use.eq(1), 1, 0)

    score = score.where(eligible, np.nan)

    probable = (eligible & major_transition_evidence & score.ge(6)).astype("float64")
    strict = (eligible & major_transition_evidence & score.ge(8)).astype("float64")
    probable = probable.where(eligible, np.nan).astype("Float64")
    strict = strict.where(eligible, np.nan).astype("Float64")

    return pd.DataFrame(
        {
            "SEQN": df["SEQN"],
            "perimenopause_proxy_score": score,
            "perimenopause_proxy_probable": probable,
            "perimenopause_proxy_strict": strict,
        }
    )


def update_dataset(path: Path, proxy_df: pd.DataFrame) -> None:
    df = pd.read_csv(path, low_memory=False)
    df = df.drop(
        columns=[
            c
            for c in [
                "perimenopause_proxy_score",
                "perimenopause_proxy_probable",
                "perimenopause_proxy_strict",
            ]
            if c in df.columns
        ]
    )
    updated = df.merge(proxy_df, on="SEQN", how="left", validate="one_to_one")
    updated.to_csv(path, index=False)


def update_notebook() -> None:
    with NOTEBOOK_PATH.open(encoding="utf-8") as handle:
        nb = json.load(handle)

    cells = nb["cells"]
    marker = "## Supplementary · perimenopause proxy"
    cells = [
        cell
        for cell in cells
        if marker not in "".join(cell.get("source", ""))
        and "perimenopause_proxy_score" not in "".join(cell.get("source", ""))
    ]

    markdown = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            "## Supplementary · perimenopause proxy\n",
            "\n",
            "**Purpose:** approximate the menopausal transition while explicitly excluding confirmed menopause.\n",
            "\n",
            "**Clinical rationale:** the best available evidence supports menstrual-pattern change as the backbone of menopausal transition staging, with ovarian-aging biomarkers used only as supportive evidence because hormone levels fluctuate across cycles.\n",
            "\n",
            "**Key references:**\n",
            "- STRAW+10 bleeding criteria and transition staging: [CDC / Harlow 2018](https://stacks.cdc.gov/view/cdc/213402)\n",
            "- Biomarker variability in perimenopause and the limits of FSH-only diagnosis: [Management of the Perimenopause](https://pmc.ncbi.nlm.nih.gov/articles/PMC6082400/)\n",
            "- Menopause nomenclature review and STRAW+10 context: [A review of menopause nomenclature](https://pmc.ncbi.nlm.nih.gov/articles/PMC8805414/)\n",
            "- Sleep disruption during the transition: [Sleep during the perimenopause: a SWAN story](https://pmc.ncbi.nlm.nih.gov/articles/PMC3185248/)\n",
            "- Mood risk during the menopausal transition: [SWAN depressive symptoms paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9268212/)\n",
            "\n",
            "**Eligibility:**\n",
            "```\n",
            "eligible = female\n",
            "           AND 35 <= age_years <= 55\n",
            "           AND menopause == 0\n",
            "           AND rhd280 != 1              # no hysterectomy\n",
            "           AND rhq305 != 1              # no bilateral oophorectomy\n",
            "           AND rhd143 != 1              # not pregnant now\n",
            "           AND rhq200 != 1              # not breastfeeding now\n",
            "```\n",
            "\n",
            "**Major transition evidence (require at least one):**\n",
            "```\n",
            "irregular_periods = (rhq031 == 2)\n",
            "recent_last_period = 0 <= (age_years - rhq060) <= 1.5\n",
            "high_fsh = LBXFSH >= 25\n",
            "borderline_fsh_plus_low_amh = (10 <= LBXFSH < 25) AND (LBXAMH < 1)\n",
            "\n",
            "major_transition_evidence = irregular_periods\n",
            "                            OR recent_last_period\n",
            "                            OR high_fsh\n",
            "                            OR borderline_fsh_plus_low_amh\n",
            "```\n",
            "\n",
            "**Scoring rule:**\n",
            "```\n",
            "score = 0\n",
            "score += 1 if 40 <= age_years <= 44\n",
            "score += 2 if 45 <= age_years <= 55\n",
            "score += 4 if rhq031 == 2                              # irregular / not regular periods\n",
            "score += 2 if 0 <= (age_years - rhq060) <= 1.5        # last period roughly within a year\n",
            "score += 2 if 10 <= LBXFSH < 25\n",
            "score += 3 if LBXFSH >= 25\n",
            "score += 2 if LBXAMH < 1\n",
            "score += 1 if slq050 == 1                             # sleep problem\n",
            "score += 1 if dpq040 >= 2                             # at least several days tired/low energy\n",
            "score += 1 if any urinary transition support symptom\n",
            "score -= 1 if rhq540 == 1                             # hormone use lowers confidence\n",
            "```\n",
            "\n",
            "**Outputs added to the dataset:**\n",
            "```\n",
            "perimenopause_proxy_score\n",
            "perimenopause_proxy_probable = 1 if eligible AND major_transition_evidence AND score >= 6\n",
            "perimenopause_proxy_strict   = 1 if eligible AND major_transition_evidence AND score >= 8\n",
            "```\n",
            "\n",
            "**Notes:**\n",
            "- `probable` is intentionally a bit looser than `strict`.\n",
            "- These proxy labels are `NaN` for ineligible participants rather than forcing a negative label outside the biologically relevant population.\n",
            "- This is a proxy for **perimenopause**, not a replacement for the existing `menopause` label.\n",
        ],
    }

    code = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "peri_cols = ['perimenopause_proxy_score', 'perimenopause_proxy_probable', 'perimenopause_proxy_strict']\n",
            "print(df[peri_cols].describe(include='all'))\n",
            "print('\\nProbable positives:', int(df['perimenopause_proxy_probable'].fillna(0).sum()))\n",
            "print('Strict positives:', int(df['perimenopause_proxy_strict'].fillna(0).sum()))\n",
            "print('\\nEligible rows:', int(df['perimenopause_proxy_score'].notna().sum()))\n",
        ],
    }

    cells.extend([markdown, code])
    nb["cells"] = cells

    with NOTEBOOK_PATH.open("w", encoding="utf-8") as handle:
        json.dump(nb, handle, ensure_ascii=False, indent=1)


def save_definition() -> None:
    definition = {
        "name": "perimenopause_proxy",
        "eligibility": [
            "female",
            "35 <= age_years <= 55",
            "menopause == 0",
            "rhd280 != 1",
            "rhq305 != 1",
            "rhd143 != 1",
            "rhq200 != 1",
        ],
        "major_transition_evidence": [
            "rhq031 == 2",
            "0 <= age_years - rhq060 <= 1.5",
            "LBXFSH >= 25",
            "(10 <= LBXFSH < 25) and (LBXAMH < 1)",
        ],
        "score_thresholds": {
            "probable": 6,
            "strict": 8,
        },
    }
    DEFINITION_JSON.write_text(json.dumps(definition, indent=2), encoding="utf-8")


def main() -> None:
    final_df = pd.read_csv(FINAL_DATASET, low_memory=False)
    proxy_df = compute_perimenopause_proxy(final_df)

    update_dataset(FINAL_DATASET, proxy_df)
    update_dataset(FINAL_NORMALIZED_DATASET, proxy_df)
    update_notebook()
    save_definition()

    eligible = int(proxy_df["perimenopause_proxy_score"].notna().sum())
    probable = int(proxy_df["perimenopause_proxy_probable"].fillna(0).sum())
    strict = int(proxy_df["perimenopause_proxy_strict"].fillna(0).sum())

    print(f"Eligible women: {eligible}")
    print(f"Probable proxy positives: {probable}")
    print(f"Strict proxy positives: {strict}")
    print(f"Updated {FINAL_DATASET}")
    print(f"Updated {FINAL_NORMALIZED_DATASET}")
    print(f"Updated {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
