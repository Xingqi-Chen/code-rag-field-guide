"""Apply reviewed one-shot patches once and run the frozen offline suites.

Never asks an editing model to repair an output. Reviews are separate, explicit
records tied to the patch hash; this tool does not infer safety from passing tests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'results'


def sanitized(text,candidate):
    return text.replace(str(candidate),'<CANDIDATE>').replace(str(ROOT),'<WORKSPACE>')


def suite(candidate,label,name):
    started=time.perf_counter()
    try:
        done=subprocess.run([str(ROOT/'.venv/bin/python'),str(HERE/'run_tests.py'),name,
            '--candidate',str(candidate)],text=True,capture_output=True,timeout=60)
        output=done.stdout+done.stderr
        code=done.returncode
    except subprocess.TimeoutExpired:
        return {'suite':name,'status':'timeout','elapsed_seconds':time.perf_counter()-started}
    output=sanitized(output,candidate)
    logfile=OUT/'features'/f'{label}-{name}.log'
    logfile.write_text(output)
    summaries=[line for line in output.splitlines() if re.search(r'\b\d+ (?:passed|failed|error|errors|skipped)\b.*\bin \d',line)]
    counts={}
    if summaries:
        counts={kind:int(number) for number,kind in re.findall(r'(\d+) (passed|failed|errors?|skipped)\b',summaries[-1])}
    return {'suite':name,'status':'passed' if code==0 else 'failed_or_error','exit_code':code,
            'counts':counts,'elapsed_seconds':time.perf_counter()-started,'log':'features/'+logfile.name}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'F0[12]-(bm25|hybrid|ms_basic|ms_local)',args.label):raise ValueError('unknown candidate')
    feature,method=args.label.split('-',1)
    original=json.loads((OUT/'feature-generations.json').read_text())
    generation=next(r for r in original['results'] if r['feature_id']==feature and r['method']==method)
    record_file=OUT/'features'/f'{args.label}-evaluation.json'
    if record_file.exists():raise ValueError('candidate already evaluated')
    result={'feature_id':feature,'method':method,'generation':generation,'suites':[]}
    if generation['patch_status']=='invalid_format':
        result['status']='invalid_format'
    else:
        patch=OUT/'features'/f'{args.label}.patch'
        review=json.loads((OUT/'features'/f'{args.label}-review.json').read_text())
        assert review['patch_sha256']==hashlib.sha256(patch.read_bytes()).hexdigest()
        assert review['approved_for_isolated_tests'] is True
        candidate=ROOT/'.cache/pilot/candidates'/args.label
        if candidate.exists():raise ValueError('candidate directory already exists')
        shutil.copytree(ROOT/'.cache/pilot/source',candidate)
        subprocess.run(['git','init','--quiet',str(candidate)],check=True)
        checked=subprocess.run(['git','apply','--check',str(patch)],cwd=candidate,text=True,capture_output=True)
        result['patch_check_exit_code']=checked.returncode
        result['patch_check_diagnostic']=sanitized(checked.stdout+checked.stderr,candidate)
        if checked.returncode:
            result['status']='patch_did_not_apply'
        else:
            applied=subprocess.run(['git','apply','--whitespace=nowarn',str(patch)],cwd=candidate,text=True,capture_output=True)
            assert applied.returncode==0,'patch changed after check'
            result['status']='tested'
            result['suites']=[suite(candidate,args.label,feature),suite(candidate,args.label,'regression')]
        result['manual_review']=review
    record_file.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'label':args.label,'status':result['status'],'suites':result['suites']},ensure_ascii=False))


if __name__=='__main__':main()
