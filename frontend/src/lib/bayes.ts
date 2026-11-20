// Tiny TypeScript port of the backend engine. Used ONLY in offline snapshot mode
// (what-if and verification calculator). The backend Python code is the source of truth.
import type {
  ActionSpec, Belief, BayesUpdate, Measurement, OutcomePreview, VerificationResult, WhatIfResult,
} from '../types/api';

/** H(P) = −Σ p·log2 p (bits). */
export function entropy(b: Belief): number {
  return -Object.values(b).reduce((s, p) => (p > 0 ? s + p * Math.log2(p) : s), 0);
}

export function normalise(b: Belief): Belief {
  const total = Object.values(b).reduce((s, p) => s + p, 0);
  const out: Belief = {};
  for (const [k, v] of Object.entries(b)) out[k] = total > 0 ? v / total : 0;
  return out;
}

/** P(h|y) ∝ P(y|h)·P(h) */
export function update(prior: Belief, likelihood: Record<string, number>): { posterior: Belief; py: number } {
  const joint: Belief = {};
  let py = 0;
  for (const h of Object.keys(prior)) {
    joint[h] = (likelihood[h] ?? 0) * prior[h];
    py += joint[h];
  }
  return { posterior: normalise(joint), py };
}

export function previews(prior: Belief, action: ActionSpec): OutcomePreview[] {
  return action.outcomes.map((o) => {
    const { posterior, py } = update(prior, o.likelihood);
    return { outcome_id: o.id, label: o.label, probability: py, posterior, entropy_after: entropy(posterior) };
  });
}

/** EIG(a) = H(P) − Σ_y P(y)·H(P(·|y)) */
export function eig(prior: Belief, action: ActionSpec): number {
  const h0 = entropy(prior);
  const expected = previews(prior, action).reduce((s, p) => s + p.probability * p.entropy_after, 0);
  return Math.max(0, h0 - expected);
}

export function whatIf(prior: Belief, action: ActionSpec, outcomeId: string): WhatIfResult {
  const outcome = action.outcomes.find((o) => o.id === outcomeId) ?? action.outcomes[0];
  const { posterior, py } = update(prior, outcome.likelihood);
  const upd: BayesUpdate = {
    action_id: action.id, outcome_id: outcome.id, prior, posterior,
    entropy_before: entropy(prior), entropy_after: entropy(posterior), outcome_probability: py,
  };
  return { update: upd, eig_bits: eig(prior, action), outcomes: previews(prior, action) };
}

/** Offline port of verification.evaluate_verification (see docs/ASSUMPTIONS.md §4). */
export function verify(pre: Measurement, posts: Measurement[]): VerificationResult {
  const rule = 'VERIFIED_REDUCTION only if post + u_post < pre − u_pre (independent, comparable)';
  const base = {
    pre_rate: pre.rate_kg_h, pre_uncertainty: pre.uncertainty_kg_h,
    pre_low: pre.rate_kg_h - pre.uncertainty_kg_h, pre_high: pre.rate_kg_h + pre.uncertainty_kg_h,
    post_rate: null, post_uncertainty: null, post_low: null, post_high: null,
    conflicting: false, measurements_used: [] as string[], measurements_ignored: [] as string[],
    rule, reasons: [] as string[], recurrence_threshold_kg_h: null,
  };
  const indep = posts.filter((m) => m.independent);
  base.measurements_ignored = posts.filter((m) => !m.independent).map((m) => m.id);
  base.measurements_used = indep.map((m) => m.id);
  if (indep.length === 0) {
    return { ...base, verdict: 'NO_INDEPENDENT_EVIDENCE', reasons: ['No independent post-intervention measurement; the case stays VERIFICATION_PENDING.'] };
  }
  for (let i = 0; i < indep.length; i++) {
    for (let j = i + 1; j < indep.length; j++) {
      const a = indep[i], b = indep[j];
      if (a.rate_kg_h + a.uncertainty_kg_h < b.rate_kg_h - b.uncertainty_kg_h || b.rate_kg_h + b.uncertainty_kg_h < a.rate_kg_h - a.uncertainty_kg_h) {
        return { ...base, verdict: 'INCONCLUSIVE', conflicting: true, reasons: ['Independent measurements conflict (intervals do not overlap). Both retained.'] };
      }
    }
  }
  if (!pre.comparable_conditions || indep.some((m) => !m.comparable_conditions)) {
    return { ...base, verdict: 'INCONCLUSIVE', reasons: ['Measurement conditions are not comparable.'] };
  }
  const w = indep.map((m) => 1 / Math.max(m.uncertainty_kg_h, 1e-6) ** 2);
  const sw = w.reduce((s, x) => s + x, 0);
  const x = indep.reduce((s, m, i) => s + m.rate_kg_h * w[i], 0) / sw;
  const u = 1 / Math.sqrt(sw);
  const post = { post_rate: x, post_uncertainty: u, post_low: x - u, post_high: x + u };
  if (x + u < base.pre_low) {
    return { ...base, ...post, verdict: 'VERIFIED_REDUCTION', recurrence_threshold_kg_h: Math.max(x + u, 100), reasons: [`Post upper bound ${(x + u).toFixed(0)} < pre lower bound ${base.pre_low.toFixed(0)} kg/h.`] };
  }
  if (x >= base.pre_low) {
    return { ...base, ...post, verdict: 'STILL_LEAKING', reasons: [`Post estimate ${x.toFixed(0)} ≥ pre lower bound ${base.pre_low.toFixed(0)} kg/h: no demonstrable reduction.`] };
  }
  return { ...base, ...post, verdict: 'INCONCLUSIVE', reasons: ['Pre and post intervals overlap: reduction not demonstrated.'] };
}
