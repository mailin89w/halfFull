/** Minimum probability for a condition to be considered flagged (architecture spec: P > 0.40) */
export const ML_THRESHOLD = 0.40;

/** Maximum number of top conditions passed to the LLM */
export const ML_TOP_N = 3;

/**
 * Given a scores record, returns the top conditions to pass to the LLM:
 * - All conditions with P >= ML_THRESHOLD, sorted descending, capped at ML_TOP_N
 * - If none meet the threshold, falls back to the top ML_TOP_N by probability
 */
export function selectTopConditions(
  mlScores: Record<string, number>
): Array<[string, number]> {
  const sorted = Object.entries(mlScores).sort(([, a], [, b]) => b - a);
  const flagged = sorted.filter(([, p]) => p >= ML_THRESHOLD);
  return (flagged.length > 0 ? flagged : sorted).slice(0, ML_TOP_N);
}
