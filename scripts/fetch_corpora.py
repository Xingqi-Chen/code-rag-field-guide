"""Fetch exact commits only. No setup, import, build, tests, or corpus scripts."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for repo in json.loads((ROOT/'benchmark/corpora.json').read_text()):
    dest=ROOT/'.cache/corpora'/repo['name']
    if not dest.exists():
        dest.mkdir(parents=True)
        subprocess.run(['git','init','-q',str(dest)],check=True)
        subprocess.run(['git','-C',str(dest),'remote','add','origin',repo['url']+'.git'],check=True)
    actual=subprocess.run(['git','-C',str(dest),'rev-parse','HEAD'],capture_output=True,text=True)
    if actual.returncode or actual.stdout.strip()!=repo['commit']:
        subprocess.run(['git','-C',str(dest),'fetch','--depth','1','origin',repo['commit']],check=True)
        subprocess.run(['git','-C',str(dest),'-c','advice.detachedHead=false','checkout','--detach',repo['commit']],check=True)
    assert subprocess.check_output(['git','-C',str(dest),'rev-parse','HEAD'],text=True).strip()==repo['commit']
    assert hashlib.sha256((dest/repo['license_path']).read_bytes()).hexdigest()==repo['license_sha256']
    print(repo['name'],repo['commit'],repo['license'])
