"""Public, standard-library verification; never starts a worker or model call."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ready=read(HERE/'live-readiness.json');review=read(HERE/'independent-review.json')
    assert ready['status']==review['status']=='independent_review_passed'
    assert ready['independent_review_sha256']==sha(HERE/'independent-review.json')
    assert not review['unresolved_blocking_findings']
    assert ready['implementation_sha256']==review['implementation_sha256']
    for name,value in ready['implementation_sha256'].items():assert sha(ROOT/name)==value,name
    for name,value in read(HERE.parent/'freeze.json')['sha256'].items():assert sha(ROOT/name)==value,name
    manifest=read(HERE/'input-manifest.json')
    public=[name for name in manifest['sha256'] if not name.startswith('.cache/')]
    for name in public:assert sha(ROOT/name)==manifest['sha256'][name],name
    approval=read(HERE/'authorization.json')
    assert approval['approved_change']['generation_reservations_new']==1883
    assert approval['carry_generation_reservations']==1349
    verification=read(HERE/'offline-verification.json')
    assert verification['status']=='offline_integration_passed'
    assert verification['new_model_api_calls']==verification['new_embedding_api_calls']==0
    print(f'Verified reviewed runtime, authorization, protocol and {len(public)} public input hashes; private cache hashes are checked at live startup. No API calls.')

if __name__=='__main__':main()
