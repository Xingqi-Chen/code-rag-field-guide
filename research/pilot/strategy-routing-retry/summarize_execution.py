"""Recompute retry costs from public event records, without API access."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;OUT=HERE/'results'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def calculate():
    execution=read(OUT/'execution.json');events=execution['events'];services={}
    for service in ('generation','embedding'):
        rows=[e for e in events if e['service']==service]
        services[service]={
            'reserved_attempts':len(rows),
            'dispatched_attempts':sum(e.get('request_dispatched') is True for e in rows),
            'validated_responses':sum(e['status']=='validated' for e in rows),
            'unknown_provider_usage_attempts':sum(e.get('usage') is None for e in rows),
            'reserved_input_tokens':sum(e['input_tokens'] for e in rows),
            'known_provider_input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in rows),
            'known_provider_output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in rows),
            'failure_categories':dict(Counter(e['error_category'] for e in rows if e['status']=='failed')),
        }
    segments=sum(c['elapsed_seconds_query_segments_new'] for c in execution['cells'])
    recovery=sum(c['recovery_prefetch_wall_seconds_new'] for c in execution['cells'])
    return {
        'execution_sha256':sha(OUT/'execution.json'),'status':execution['status'],
        'completed_retry_cells':execution['completion_counts']['complete'],
        'new_events':len(events),'services':services,'cumulative_counts':execution['counts'],
        'new_embedding_estimate_usd_reserved_tokens':round(services['embedding']['reserved_input_tokens']*.13/1_000_000,8),
        'cumulative_embedding_estimate_usd_reserved_tokens':round(execution['counts']['embedding_tokens']*.13/1_000_000,8),
        'timing':{'new_query_segment_seconds':segments,'new_recovery_prefetch_seconds_utc_reconstructed':recovery,
                  'new_active_seconds_approximate':segments+recovery,
                  'includes_prior_stop_segments_and_eof_backoff':True,'includes_waiting_for_review_or_initial_data_loading':False},
        'generation_price_usd':None,'peak_memory_bytes':None,
        'limitations':['Unknown provider usage is not zero; reservations include failed attempts.',
                      'Embedding dollar figures use the frozen $0.13 per million tokens, not an invoice.',
                      'Six original failed generation responses remain unavailable and unknown usage remains unknown.',
                      'Active time mixes monotonic query segments with two UTC-reconstructed recovery windows; not an equal-cache latency comparison.']
    }

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args();value=calculate()
    if args.check:assert read(OUT/'execution-statistics.json')==value
    else:(OUT/'execution-statistics.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(value,ensure_ascii=False,indent=2))
