from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.util import hash_pandas_object


DATA_FILE = Path("data/processed/nhanes_merged_adults_final_normalized.csv")
ACTIONS_FILE = Path("data/processed/nhanes_merged_adults_final_normalization_actions.csv")
REPORT_JSON = Path("data/processed/nhanes_normalized_ml_audit.json")
REPORT_MD = Path("data/processed/nhanes_normalized_ml_audit.md")
SENTINEL_CSV = Path("data/processed/nhanes_normalized_sentinel_flags.csv")
OUTLIER_CSV = Path("data/processed/nhanes_normalized_outlier_flags.csv")
DUPLICATE_CSV = Path("data/processed/nhanes_normalized_duplicate_columns.csv")
MISSINGNESS_CSV = Path("data/processed/nhanes_normalized_missingness_flags.csv")

SENTINEL_VALUES = [7, 9, 77, 99, 777, 999, 7777, 9999, 77777, 99999]


def find_sentinel_flags(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    numeric = df.select_dtypes(include=[np.number])
    for column in numeric.columns:
        series = pd.to_numeric(numeric[column], errors="coerce")
        non_null = series.dropna()
        if non_null.empty:
            continue

        max_realistic = non_null.quantile(0.95)
        min_value = float(non_null.min())
        max_value = float(non_null.max())
        for sentinel in SENTINEL_VALUES:
            count = int((series == sentinel).sum())
            if count == 0:
                continue
            rows.append(
                {
                    "column": column,
                    "sentinel_value": sentinel,
                    "count": count,
                    "fraction": count / len(df),
                    "column_min": min_value,
                    "column_max": max_value,
                    "q95": float(max_realistic),
                    "likely_special_missing_code": bool(sentinel > max_realistic and sentinel >= 7),
                }
            )
    return pd.DataFrame(rows).sort_values(["likely_special_missing_code", "count", "column"], ascending=[False, False, True])


def find_outlier_flags(df: pd.DataFrame, action_log: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    flagged_columns = action_log.loc[action_log["action"].isin(["reference_normalize", "zscore_normalize"]), ["column", "action"]]
    for column, action in flagged_columns.itertuples(index=False):
        if column not in df.columns:
            continue
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        if series.empty:
            continue
        abs_series = series.abs()
        gt8 = int((abs_series > 8).sum())
        gt12 = int((abs_series > 12).sum())
        if gt8 == 0 and gt12 == 0:
            continue
        rows.append(
            {
                "column": column,
                "action": action,
                "count_abs_gt_8": gt8,
                "count_abs_gt_12": gt12,
                "min": float(series.min()),
                "q01": float(series.quantile(0.01)),
                "median": float(series.quantile(0.5)),
                "q99": float(series.quantile(0.99)),
                "max": float(series.max()),
            }
        )
    return pd.DataFrame(rows).sort_values(["count_abs_gt_12", "count_abs_gt_8", "column"], ascending=[False, False, True])


def find_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    numeric = df.select_dtypes(include=[np.number])
    hashes = {column: hash_pandas_object(numeric[column], index=False).sum() for column in numeric.columns}
    groups: dict[int, list[str]] = {}
    for column, value in hashes.items():
        groups.setdefault(value, []).append(column)

    rows: list[dict[str, object]] = []
    for columns in groups.values():
        if len(columns) < 2:
            continue
        base = columns[0]
        for other in columns[1:]:
            if numeric[base].equals(numeric[other]):
                rows.append({"column": base, "duplicate_of": other})
    return pd.DataFrame(rows).sort_values(["column", "duplicate_of"])


def find_missingness_flags(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in df.columns:
        frac = float(df[column].isna().mean())
        if frac >= 0.9:
            rows.append({"column": column, "missing_fraction": frac})
    return pd.DataFrame(rows).sort_values(["missing_fraction", "column"], ascending=[False, True])


def build_markdown(
    df: pd.DataFrame,
    actions: pd.DataFrame,
    sentinel_flags: pd.DataFrame,
    outlier_flags: pd.DataFrame,
    duplicate_flags: pd.DataFrame,
    missingness_flags: pd.DataFrame,
) -> str:
    total_columns = len(df.columns)
    total_rows = len(df)
    action_counts = actions["action"].value_counts().to_dict()

    likely_sentinel = sentinel_flags[sentinel_flags["likely_special_missing_code"]].copy()
    top_sentinel = likely_sentinel.head(20)
    top_outliers = outlier_flags.head(20)
    top_duplicates = duplicate_flags.head(20)
    top_missingness = missingness_flags.head(20)

    lines = [
        "# NHANES Normalized Dataset ML Audit",
        "",
        f"- Rows: {total_rows}",
        f"- Columns: {total_columns}",
        f"- Action counts: {json.dumps(action_counts, sort_keys=True)}",
        "",
        "## Bottom line",
        "",
        "- Further normalization is not the main blocker now.",
        "- The main ML risks are sentinel-coded missing values in untouched numeric survey columns, duplicate alias columns, and a long tail of very sparse or ultra-extreme continuous features.",
        "",
        "## Likely sentinel-coded missing values",
        "",
    ]

    if top_sentinel.empty:
        lines.append("- None detected.")
    else:
        for row in top_sentinel.itertuples(index=False):
            lines.append(
                f"- `{row.column}` contains `{row.sentinel_value}` in {row.count} rows ({row.fraction:.2%}); flagged as likely special missing code."
            )

    lines.extend(["", "## Extreme transformed values", ""])
    if top_outliers.empty:
        lines.append("- No columns exceeded |value| > 8.")
    else:
        for row in top_outliers.itertuples(index=False):
            lines.append(
                f"- `{row.column}` ({row.action}) has {row.count_abs_gt_8} values with |x| > 8 and {row.count_abs_gt_12} with |x| > 12; max={row.max:.3f}."
            )

    lines.extend(["", "## Exact duplicate columns", ""])
    if top_duplicates.empty:
        lines.append("- None found.")
    else:
        for row in top_duplicates.itertuples(index=False):
            lines.append(f"- `{row.column}` is exactly duplicated by `{row.duplicate_of}`.")

    lines.extend(["", "## Very sparse columns", ""])
    if top_missingness.empty:
        lines.append("- None above 90% missingness.")
    else:
        for row in top_missingness.itertuples(index=False):
            lines.append(f"- `{row.column}` is {row.missing_fraction:.2%} missing.")

    lines.extend(
        [
            "",
            "## Recommendation for ML",
            "",
            "- Keep the current normalization pipeline.",
            "- Before training, convert flagged questionnaire sentinel codes like `7/9/77/99/7777/9999` to missing using NHANES codebooks or a curated per-column map.",
            "- Drop one column from each exact duplicate pair to reduce redundancy and leakage-like feature duplication.",
            "- Consider excluding columns with >95% missingness unless they are explicitly needed.",
            "- Consider winsorizing, log-transforming, or excluding some of the most extreme long-tail continuous variables for linear models.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    df = pd.read_csv(DATA_FILE, low_memory=False)
    actions = pd.read_csv(ACTIONS_FILE)

    sentinel_flags = find_sentinel_flags(df)
    outlier_flags = find_outlier_flags(df, actions)
    duplicate_flags = find_duplicate_columns(df)
    missingness_flags = find_missingness_flags(df)

    SENTINEL_CSV.parent.mkdir(parents=True, exist_ok=True)
    sentinel_flags.to_csv(SENTINEL_CSV, index=False)
    outlier_flags.to_csv(OUTLIER_CSV, index=False)
    duplicate_flags.to_csv(DUPLICATE_CSV, index=False)
    missingness_flags.to_csv(MISSINGNESS_CSV, index=False)

    report = {
        "data_file": str(DATA_FILE),
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "action_counts": actions["action"].value_counts().to_dict(),
        "likely_sentinel_flags": int(sentinel_flags["likely_special_missing_code"].sum()) if not sentinel_flags.empty else 0,
        "outlier_columns": int(len(outlier_flags)),
        "duplicate_pairs": int(len(duplicate_flags)),
        "high_missingness_columns": int(len(missingness_flags)),
        "output_files": {
            "sentinel_flags": str(SENTINEL_CSV),
            "outlier_flags": str(OUTLIER_CSV),
            "duplicate_columns": str(DUPLICATE_CSV),
            "missingness_flags": str(MISSINGNESS_CSV),
            "markdown_report": str(REPORT_MD),
        },
    }

    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    REPORT_MD.write_text(
        build_markdown(df, actions, sentinel_flags, outlier_flags, duplicate_flags, missingness_flags),
        encoding="utf-8",
    )

    print(f"Saved markdown report to {REPORT_MD}")
    print(f"Saved json report to {REPORT_JSON}")
    print(f"Saved sentinel flags to {SENTINEL_CSV}")
    print(f"Saved outlier flags to {OUTLIER_CSV}")
    print(f"Saved duplicate column flags to {DUPLICATE_CSV}")
    print(f"Saved missingness flags to {MISSINGNESS_CSV}")


if __name__ == "__main__":
    main()
