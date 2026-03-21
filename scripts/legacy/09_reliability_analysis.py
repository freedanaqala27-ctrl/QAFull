from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

try:
    import pingouin as pg
except Exception:
    pg = None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_long_ratings(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "rating_value" in df.columns:
        df["rating_value"] = pd.to_numeric(df["rating_value"], errors="coerce")
    return df


def bootstrap_ci(values: np.ndarray, stat_func, iterations: int = 200) -> tuple[float, float]:
    if len(values) < 2:
        return np.nan, np.nan
    samples: list[float] = []
    rng = np.random.default_rng(42)
    for _ in range(iterations):
        sample_idx = rng.choice(len(values), size=len(values), replace=True)
        stat = stat_func(values[sample_idx])
        if not np.isnan(stat):
            samples.append(float(stat))
    if len(samples) < 10:
        return np.nan, np.nan
    return float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def compute_kappa_table(long_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (evaluator_type, dimension), group_df in long_df.groupby(["evaluator_type", "normalized_dimension"], dropna=False):
        pivot = group_df.pivot_table(index="exercise_id", columns="respondent_id", values="rating_value", aggfunc="mean")
        raters = list(pivot.columns)
        for idx, rater_a in enumerate(raters):
            for rater_b in raters[idx + 1 :]:
                pair = pivot[[rater_a, rater_b]].dropna()
                if len(pair) < 2:
                    continue
                kappa = cohen_kappa_score(pair[rater_a], pair[rater_b])
                ci_lower, ci_upper = bootstrap_ci(
                    pair.to_numpy(),
                    lambda arr: cohen_kappa_score(arr[:, 0], arr[:, 1]),
                )
                rows.append(
                    {
                        "evaluator_type": evaluator_type,
                        "normalized_dimension": dimension,
                        "rater_a": rater_a,
                        "rater_b": rater_b,
                        "sample_size": int(len(pair)),
                        "cohen_kappa": float(kappa),
                        "ci_lower_95": ci_lower,
                        "ci_upper_95": ci_upper,
                    }
                )
    return pd.DataFrame(rows)


def cronbach_alpha_from_matrix(matrix: pd.DataFrame) -> float:
    matrix = matrix.dropna()
    if matrix.shape[0] < 2 or matrix.shape[1] < 2:
        return np.nan
    item_variances = matrix.var(axis=0, ddof=1)
    total_score = matrix.sum(axis=1)
    total_variance = total_score.var(ddof=1)
    if total_variance == 0:
        return np.nan
    k = matrix.shape[1]
    return float((k / (k - 1)) * (1 - item_variances.sum() / total_variance))


def compute_cronbach_table(long_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (evaluator_type, dimension), group_df in long_df.groupby(["evaluator_type", "normalized_dimension"], dropna=False):
        pivot = group_df.pivot_table(index="exercise_id", columns="respondent_id", values="rating_value", aggfunc="mean")
        alpha = cronbach_alpha_from_matrix(pivot)
        ci_lower, ci_upper = bootstrap_ci(
            pivot.dropna().to_numpy(),
            lambda arr: cronbach_alpha_from_matrix(pd.DataFrame(arr)),
        )
        rows.append(
            {
                "evaluator_type": evaluator_type,
                "normalized_dimension": dimension,
                "sample_size": int(pivot.dropna().shape[0]),
                "num_raters": int(pivot.dropna().shape[1]) if not pivot.dropna().empty else 0,
                "cronbach_alpha": alpha,
                "ci_lower_95": ci_lower,
                "ci_upper_95": ci_upper,
            }
        )
    return pd.DataFrame(rows)


def compute_icc_table(long_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (evaluator_type, dimension), group_df in long_df.groupby(["evaluator_type", "normalized_dimension"], dropna=False):
        subset = group_df[["exercise_id", "respondent_id", "rating_value"]].dropna()
        icc_value = np.nan
        ci_lower = np.nan
        ci_upper = np.nan
        if pg is not None and subset["respondent_id"].nunique() >= 2 and subset["exercise_id"].nunique() >= 2:
            try:
                icc_table = pg.intraclass_corr(
                    data=subset,
                    targets="exercise_id",
                    raters="respondent_id",
                    ratings="rating_value",
                )
                icc2 = icc_table[icc_table["Type"] == "ICC2"]
                if not icc2.empty:
                    icc_value = float(icc2.iloc[0]["ICC"])
                    ci = icc2.iloc[0].get("CI95%")
                    if isinstance(ci, (list, tuple)) and len(ci) == 2:
                        ci_lower = float(ci[0])
                        ci_upper = float(ci[1])
            except Exception:
                pass

        rows.append(
            {
                "evaluator_type": evaluator_type,
                "normalized_dimension": dimension,
                "sample_size": int(subset["exercise_id"].nunique()),
                "num_raters": int(subset["respondent_id"].nunique()),
                "icc": icc_value,
                "ci_lower_95": ci_lower,
                "ci_upper_95": ci_upper,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings-long", default="results/human_eval_merged/human_ratings_long.v1.csv")
    parser.add_argument("--output-dir", default="results/reliability")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    ensure_dir(output_dir)

    long_df = load_long_ratings(Path(args.ratings_long))
    if long_df.empty:
        pd.DataFrame().to_csv(output_dir / "cohen_kappa.v1.csv", index=False)
        pd.DataFrame().to_csv(output_dir / "cronbach_alpha.v1.csv", index=False)
        pd.DataFrame().to_csv(output_dir / "icc.v1.csv", index=False)
        print(f"No ratings found. Wrote empty reliability outputs to {output_dir}")
        return

    compute_kappa_table(long_df).to_csv(output_dir / "cohen_kappa.v1.csv", index=False)
    compute_cronbach_table(long_df).to_csv(output_dir / "cronbach_alpha.v1.csv", index=False)
    compute_icc_table(long_df).to_csv(output_dir / "icc.v1.csv", index=False)

    print(f"Reliability analysis complete -> {output_dir}")


if __name__ == "__main__":
    main()
