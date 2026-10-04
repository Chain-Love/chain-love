"""Exercise proposed production tools against current main and a temporary pilot."""
import copy, csv, io, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path
import requests

import argparse, tempfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-repo',type=Path,required=True,help='Public Chain.Love main checkout')
parser.add_argument('--data-ref',default='HEAD',help='Data snapshot to validate; does not modify it')
parser.add_argument('--output',type=Path,help='Directory for disposable snapshots and logs')
parser.add_argument('--verify-sources',action='store_true',help='Fetch fixed npm manifests to check fixtures')
args=parser.parse_args()
work=args.output or Path(tempfile.mkdtemp(prefix='sdk-peer-check-'))
work.mkdir(parents=True,exist_ok=True)
code=Path(__file__).resolve().parents[2]
data=args.data_repo.resolve()
env=dict(os.environ,PYTHONUTF8='1')
base=args.data_ref
archive=subprocess.check_output(['git','archive','--format=zip',base,'references','listings'],cwd=data)
fixtures=json.loads((code/'tools/tests/fixtures/sdk-peer-requirements.json').read_text(encoding='utf-8'))
for slug,fixture in (fixtures.items() if args.verify_sources else []):
    manifest=requests.get(fixture['source'],timeout=30)
    manifest.raise_for_status()
    manifest=manifest.json()
    assert manifest['name']==fixture['package'] and manifest['version']==fixture['version']
    assert manifest['peerDependencies']=={k:v['constraint'] for k,v in fixture['requirements'].items()}
    assert {k:bool(manifest.get('peerDependenciesMeta',{}).get(k,{}).get('optional',False)) for k in manifest['peerDependencies']}=={k:v['optional'] for k,v in fixture['requirements'].items()}

results=[]
for variant in ('baseline','pilot'):
    directory=work/variant
    directory.mkdir(exist_ok=False)
    zipfile.ZipFile(io.BytesIO(archive)).extractall(directory)
    shutil.copytree(code/'meta',directory/'meta',dirs_exist_ok=True)
    for filename in ('schema.json','validate_csv.py','csv_to_json.py','validate.py'):
        shutil.copy2(code/'tools'/filename,directory/filename)
    if variant=='pilot':
        paths=['references/offers/sdks.csv','listings/all-networks/sdks.csv','listings/specific-networks/filecoin/sdks.csv','listings/specific-networks/somnia/sdks.csv']
        for relative in paths:
            path=directory/relative
            reader=csv.DictReader(path.open(encoding='utf-8',newline=''))
            fields=reader.fieldnames
            rows=list(reader)
            assert 'peerRequirements' not in fields
            fields=fields+['peerRequirements']
            for row in rows:
                row['peerRequirements']=json.dumps(fixtures[row['slug']],separators=(',',':')) if relative.startswith('references') and row['slug'] in fixtures else ''
            with path.open('w',encoding='utf-8',newline='') as file:
                writer=csv.DictWriter(file,fieldnames=fields,lineterminator='\n')
                writer.writeheader(); writer.writerows(rows)
    for script in ('validate_csv.py','csv_to_json.py','validate.py'):
        run=subprocess.run([sys.executable,'-X','utf8',script],cwd=directory,env=env,capture_output=True,text=True,encoding='utf-8')
        (work/(variant+'-'+script+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
        results.append({'variant':variant,'script':script,'exitCode':run.returncode})
        assert run.returncode==0, run.stdout[-5000:]+run.stderr

for network in ('filecoin','somnia'):
    before=json.loads((work/'baseline/json'/f'{network}.json').read_text(encoding='utf-8'))
    after=json.loads((work/'pilot/json'/f'{network}.json').read_text(encoding='utf-8'))
    assert 'peerRequirements' in after['columns']['sdks']
    for row in after['sdks']:
        if row['slug'] in fixtures:
            assert row['peerRequirements']==fixtures[row['slug']]
    assert any(row['slug']=='abitype' for row in after['sdks'])
    if network=='filecoin':
        assert any(row['slug']=='synapse-react' and row['peerRequirements']==fixtures['synapse-react'] for row in after['sdks'])
    stripped=[{k:v for k,v in row.items() if k!='peerRequirements'} for row in after['sdks']]
    assert stripped==before['sdks'], (network,'existing SDK values changed')

# Use actual generator entry point to prove a listing override cannot bypass identity checks.
directory=work/'pilot'
path=directory/'listings/specific-networks/filecoin/sdks.csv'
reader=csv.DictReader(path.open(encoding='utf-8',newline='')); fields=reader.fieldnames; rows=list(reader)
bad=copy.deepcopy(fixtures['abitype']); bad['source']='https://registry.npmjs.org/viem/1.3.0'
next(row for row in rows if row['slug']=='abitype')['peerRequirements']=json.dumps(bad)
with path.open('w',encoding='utf-8',newline='') as file:
    writer=csv.DictWriter(file,fieldnames=fields,lineterminator='\n'); writer.writeheader(); writer.writerows(rows)
run=subprocess.run([sys.executable,'-X','utf8','csv_to_json.py'],cwd=directory,env=env,capture_output=True,text=True,encoding='utf-8')
assert run.returncode!=0 and 'peerRequirements.source must match' in run.stdout
(work/'negative-listing-override.log').write_text(run.stdout+run.stderr,encoding='utf-8')

# Also reject a structurally valid mismatch in an already-generated JSON artifact.
json_path=directory/'json/filecoin.json'
generated=json.loads(json_path.read_text(encoding='utf-8'))
next(row for row in generated['sdks'] if row['slug']=='abitype')['peerRequirements']['source']='https://registry.npmjs.org/abitype/1.2.3'
json_path.write_text(json.dumps(generated),encoding='utf-8')
run=subprocess.run([sys.executable,'-X','utf8','validate.py'],cwd=directory,env=env,capture_output=True,text=True,encoding='utf-8')
assert run.returncode!=0 and 'peerRequirements.source must match' in run.stdout
(work/'negative-generated-json.log').write_text(run.stdout+run.stderr,encoding='utf-8')
report={'sourceManifests':2 if args.verify_sources else 0,'checks':results,'filecoinAndSomniaInheritance':True,'unchangedExistingSDKValues':True,'mismatchedListingOverrideRejected':True,'mismatchedGeneratedJSONRejected':True,'productionCSVsChanged':False,'upstreamSDKExecuted':False}
(work/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(dict(report,output=str(work))))
