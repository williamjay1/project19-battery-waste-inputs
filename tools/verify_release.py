"""Offline inventory/privacy verification; not physical/source accuracy validation."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
from tools.prepare_metadata import metadata

ROOT = Path(__file__).resolve().parents[1]
PERSONAL_FIELDS = {'name','company','company_name','contact','email','telephone','phone','address','notifier_name','processor_name'}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def privacy_schema(fields):
    forbidden = PERSONAL_FIELDS & {f.casefold() for f in fields}
    if forbidden:
        raise ValueError(f'Personal/company fields are not approved: {sorted(forbidden)}')

def verify(root=ROOT):
    manifest = json.loads((root/'release_manifest.json').read_text(encoding='utf-8'))
    checked=[]; csv_files=0
    for record in manifest['files']:
        path = root / record['path']
        if not path.is_file() or sha(path)!=record['sha256'] or path.stat().st_size!=record['bytes']:
            raise ValueError(f'Release file missing or changed: {record["path"]}')
        if path.suffix == '.csv':
            with path.open(encoding='utf-8-sig',newline='') as stream:
                reader=csv.DictReader(stream); fields=reader.fieldnames; rows=list(reader)
            if len(rows)!=record['rows']:
                raise ValueError('CSV row count differs from release inventory')
            if path.name=='public_permit_scope_cases.csv':
                privacy_schema(fields)
                if len(rows)!=151:
                    raise ValueError('Frozen permit coverage changed')
            if path.name=='eu27_directed_trade_observations.csv':
                keys=[(r['product'],r['year'],r['flow'],r['origin'],r['destination']) for r in rows]
                if len(keys)!=980 or len(set(keys))!=980:
                    raise ValueError('Duplicate or changed Comext keys')
                for row in rows:
                    for value, flag in [('quantity_t','quantity_observation_present'),('value_eur','value_observation_present')]:
                        if bool(row[value].strip()) != (row[flag]=='True'):
                            raise ValueError('Missing/observed status mismatch')
            csv_files+=1
        checked.append(record['path'])
    # Catch accidentally added raw/sensitive files, including files not inventoried.
    tracked={record['path'] for record in manifest['files']}
    for path in root.rglob('*'):
        if not path.is_file(): continue
        relative=path.relative_to(root)
        if any(part in {'.git','.venv','__pycache__','.pytest_cache','reproduction'} for part in relative.parts):
            continue
        if relative.as_posix() not in tracked and relative.as_posix() not in {'release_manifest.json','CITATION.cff','.zenodo.json'}:
            raise ValueError(f'Uninventoried file: {relative}; curate a new release rather than silently including it')
        if path.suffix.lower() in {'.ods','.html','.ttf','.otf','.pem','.key','.p12','.zip','.pdf','.docx'}:
            raise ValueError(f'Non-whitelisted raw/private/document artifact: {relative}')
        if path.name.startswith('.env'):
            raise ValueError('Environment/credential files must not be distributed')
        if path.suffix.lower() in {'.py','.md','.json','.csv','.txt','.yml','.yaml','.cff'}:
            text=path.read_text(encoding='utf-8-sig',errors='replace')
            # Sensitive literals, not source code mentioning how to avoid them.
            secrets=[r'gh[pousr]_[A-Za-z0-9]{30,}', r'github_pat_[A-Za-z0-9_]{50,}',
                     r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                     r'[A-Z]:[\\/]Users[\\/]Administrator[\\/]']
            if any(re.search(pattern,text) for pattern in secrets):
                raise ValueError(f'Sensitive literal or personal local path: {relative}')
    has_cff=(root/'CITATION.cff').exists()
    has_zenodo=(root/'.zenodo.json').exists()
    if has_cff and not has_zenodo:
        raise ValueError('CFF requires matching Zenodo metadata in this release')
    creators=[]
    if has_zenodo:
        zenodo=json.loads((root/'.zenodo.json').read_text(encoding='utf-8'))
        declared=json.loads((root/'CONTRIBUTORS.json').read_text(encoding='utf-8'))
        _, expected=metadata(declared,version=zenodo['version'])
        if zenodo['creators']!=expected['creators'] or zenodo['title']!=expected['title']:
            raise ValueError('Zenodo attribution differs from declared contributors')
        if zenodo.get('contributors'):
            raise ValueError('Undeclared additional contributors')
        creators=[item['name'] for item in zenodo['creators']]
        citation=(root/'CITATION.md').read_text(encoding='utf-8')
        if any(name not in citation for name in creators):
            raise ValueError('Human-readable citation is missing a declared contributor')
    if (root/'CITATION.cff').exists():
        cff=json.loads((root/'CITATION.cff').read_text(encoding='utf-8'))
        zenodo=json.loads((root/'.zenodo.json').read_text(encoding='utf-8'))
        if cff['title']!=zenodo['title'] or cff['version']!=zenodo['version'] or len(cff['authors'])!=len(zenodo['creators']):
            raise ValueError('Citation/Zenodo metadata differ')
        actual_names=[item['family-names']+', '+item['given-names'] for item in cff['authors']]
        if actual_names!=creators: raise ValueError('CFF/Zenodo creator names differ')
    return {'status':'PASS','verified_files':len(checked),'verified_csvs':csv_files,
            'physical_validation':False,'withheld_source_validation':'not performed offline',
            'metadata':'creator metadata absent' if not has_zenodo else 'declared creators verified; external deposit not claimed',
            'creators':creators,'cff_present':has_cff,
            'data_permission':'source-specific; not a blanket MIT/CC0 data licence'}

def refresh_metadata(root=ROOT):
    path=root/'release_manifest.json'; obj=json.loads(path.read_text(encoding='utf-8'))
    # Only truthful, validated metadata may be added; never silently re-baseline scientific/code changes.
    verify(root)
    names=[name for name in ['CITATION.cff','.zenodo.json'] if (root/name).exists()]
    if '.zenodo.json' not in names: raise FileNotFoundError('.zenodo.json')
    for name in names:
        file=root/name
        if not file.exists(): raise FileNotFoundError(name)
        if any(r['path']==name for r in obj['files']): raise ValueError('Metadata already inventoried; use a new release version')
        obj['files'].append({'path':name,'bytes':file.stat().st_size,'sha256':sha(file),'license_class':'original_software_MIT'})
    obj['files'].sort(key=lambda item:item['path'])
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path)
    p.add_argument('--refresh-metadata',action='store_true')
    a=p.parse_args()
    if a.refresh_metadata: refresh_metadata()
    audit=verify()
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open('x',encoding='utf-8') as stream: json.dump(audit,stream,indent=2)
    print(json.dumps(audit,indent=2))

if __name__=='__main__': main()
