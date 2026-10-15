/** Sample agreement never marks population verification complete. */
export function verificationState(quality: {
  blind_verifier: string
  verification?: { status: string; selected: number; observed: number; missing: number; not_human_accuracy: boolean } | null
}): "sample" | "pending" {
  const v = quality.verification
  return quality.blind_verifier === "sample_measured" && v?.status === "sample_measured" &&
    v.not_human_accuracy === true && Number.isInteger(v.selected) && Number.isInteger(v.observed) &&
    Number.isInteger(v.missing) && v.observed > 0 && v.observed <= v.selected && v.missing === v.selected - v.observed
    ? "sample" : "pending"
}
