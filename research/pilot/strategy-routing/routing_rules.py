"""Predeclared question-text routing; never reads gold, scores or outputs."""
import re

SEED = 20261012
RULES = [
    ('global_scope', 'global', r'\b(distributed across|module responsibilities|architecture|global overview|whole repository)\b'),
    ('explicit_trace', 'drift', r'\btrace\b|^follow\b|\bfallback\b'),
    ('change_impact_or_plan', 'drift', r'^if\b|^when changing\b|^plan the following feature\b'),
]


def route(query):
    text = ' '.join(query.lower().split())
    for rule, method, pattern in RULES:
        if re.search(pattern, text):
            return {'method': method, 'rule': rule}
    return {'method': 'local', 'rule': 'fixed_local_fallback'}


def call_bounds(route_counts, baseline_methods, unique_queries, map_batches):
    # DRIFT: HyDE + primer fold + (2 epochs x at most2 followups) + reduce.
    drift = 1 + 1 + 2 * 2 + 1
    generation = route_counts['local'] + route_counts['drift'] * drift
    generation += route_counts['global'] * (map_batches + 1)
    generation += unique_queries * baseline_methods
    return {
        'drift_logical_generation_per_question_max': drift,
        'global_logical_generation_per_question_max': map_batches + 1,
        'nominal_generation_max': generation,
        'generation_with_two_extra_transient_attempts_per_request_max': generation * 3,
    }
