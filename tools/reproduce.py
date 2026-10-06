"""Portable frozen-source replay. Generated restricted results remain local."""
from __future__ import annotations
import argparse
from decimal import Decimal as D
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def scientific_digest(path, year):
    from battery_scope_identification import basel_pilot
    rows=basel_pilot(path,year)
    # Selected scientific fields only; navigation state/timestamps are excluded.
    fields=['origin','destination','year','basel_code','y_code','low_code','description',
            'hazard_code','quantity_t','transit','d_code','r_code']
    canonical=[]
    for row in rows:
        record={key:row[key] for key in fields}
        record['quantity_t']=format(D(str(row['quantity_t'])).normalize(),'f')
        canonical.append(record)
    payload=json.dumps(sorted(canonical,key=lambda row:json.dumps(row,sort_keys=True)),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()

def independently_check(raw,output):
    from src.verify_scope_manuscript import raw_cases, independent_bounds, read_csv
    checks=0
    for year,reference,folder in [(2023,'scope_identification_pilot_20261002_v1','basel_table5_navigation_20261002_v1'),
                                 (2024,'scope_identification_transfer_20261002_v1','basel_table5_transfer_20261002_v1')]:
        rows=raw_cases(raw/folder/f'germany_{year}_table5.html')
        if len(rows)!=(9 if year==2023 else 10): raise ValueError('Frozen selected-row count changed')
        for record in read_csv(output/reference/'finite_report_scope_bounds.csv'):
            low,high=independent_bounds(rows,record['origin'],record['target'],record['stage'])
            for field,value in [('lower_t',low),('upper_t',high),('width_t',high-low)]:
                if abs(D(record[field])-value)>D('0.000001'): raise ValueError('Independent interval check failed')
                checks+=1
    certificate=read_csv(output/'scope_decision_certificates_20261002_v1/decision_certificates.csv')
    pressure=read_csv(output/'scope_decision_certificates_20261002_v1/assumption_sensitivity.csv')
    strict=0
    for record in pressure:
        one=next(x for x in certificate if x['year']==record['year'] and x['stage']==record['stage'])
        expected=(1-D(record['quantity_error']))*(1-D(record['label_relaxation']))*D(one['NL_lower_t'])-(1+D(record['quantity_error']))*D(one['BE_upper_t'])
        if abs(D(record['margin_t'])-expected)>D('0.000001') or (expected>0)!=(record['NL_strictly_above_BE']=='True'):
            raise ValueError('Independent pressure margin/flag check failed')
        checks+=1; strict+=int(expected>0)
    if len(pressure)!=160 or strict!=119: raise ValueError('A pressure case was lost or changed')
    return {'checks':checks,'pressure_cases':160,'strict':strict,'non_strict':41,
            'independence':'separate raw parser and Decimal, no production eligibility imported',
            'physical_validation':False}

def run(raw,output,stable_content=False):
    raw,output=raw.resolve(),output.resolve()
    if output.exists(): raise FileExistsError(output)
    catalogue=json.loads((ROOT/'provenance/source_inputs.json').read_text(encoding='utf-8'))
    sources={}; source_checks=[]
    for key,record in catalogue['inputs'].items():
        path=(ROOT if record.get('included') else raw)/record['relative_path']
        if not path.exists(): raise FileNotFoundError(f'{key}: obtain the cited source following REPRODUCING.md')
        before=sha(path); exact=before==record['sha256']
        semantic=None
        if key.startswith('basel'):
            semantic=scientific_digest(path,int(key[-4:]))
            if semantic!=record['selected_scientific_content_sha256']:
                raise ValueError('Selected Basel scientific content changed; frozen replay aborted')
        if not exact and not (stable_content and key.startswith('basel')):
            raise ValueError(f'{key}: changed frozen source; no silent substitution')
        source_checks.append({'source':key,'byte_identical_to_study_snapshot':exact,'actual_sha256':before,
                              'selected_scientific_content_sha256':semantic,
                              'mode':'exact_bytes' if exact else 'explicit_stable_scientific_content'})
        sources[key]=path
    output.mkdir(parents=True)
    env={**os.environ,'PYTHONIOENCODING':'utf-8',
         'PYTHONPATH':str(ROOT/'src')+os.pathsep+str(ROOT)}
    commands=[]
    def job(module,args):
        command=[sys.executable,'-m',module,*map(str,args)]
        start=time.perf_counter()
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (output/(module.replace('.','_')+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
        commands.append({'module':module,'return_code':result.returncode,'elapsed_seconds':round(time.perf_counter()-start,4)})
        if result.returncode: raise RuntimeError(f'{module} failed; preserved logs in output')
    for year,reference in [(2023,'scope_identification_pilot_20261002_v1'),(2024,'scope_identification_transfer_20261002_v1')]:
        job('src.battery_scope_identification',['--basel',sources[f'basel{year}'],'--uba',sources[f'uba{year}'],
            '--comext',sources['comext'],'--year',year,'--output',output/reference])
    job('src.scope_decision_certificate',['--basel2023',sources['basel2023'],'--basel2024',sources['basel2024'],
         '--output',output/'scope_decision_certificates_20261002_v1'])
    job('src.inspect_public_notification_register',['--source',sources['permits'],'--output',output/'public_permit_field_gate_20261002_v1'])
    comparisons=[]
    for reference in catalogue['main_result_fingerprints']:
        path=output/reference['path']; equal=path.exists() and sha(path)==reference['sha256']
        comparisons.append({'path':reference['path'],'byte_identical':equal})
        if not equal: raise ValueError(f'Result replay differs: {reference["path"]}')
    independent=independently_check(raw,output)
    inputdir=ROOT/'datasets/eucomext_battery_waste_trade_20260929_v2'
    for module,reference in [('comext_network_quality_analysis','comext_network_quality_20260930_v1r6'),
                             ('comext_decision_input_analysis','comext_decision_inputs_20260930_v1'),
                             ('comext_information_check_diagnostics','comext_information_checks_20261001_v1')]:
        job('src.'+module,['--input-dir',inputdir,'--output-dir',output/reference])
    job('src.comext_temporal_priority_validation',['--source',inputdir/'eu27_mirror_comparison.csv','--output',output/'comext_temporal_holdout_20261001_v1'])
    for reference in catalogue['retained_trade_result_fingerprints']:
        path=output/reference['path']; equal=path.exists() and sha(path)==reference['sha256']
        if not equal: raise ValueError(f'Trade diagnostic differs: {reference["path"]}')
        comparisons.append({'path':reference['path'],'byte_identical':equal})
    if any(sha(sources[record['source']])!=record['actual_sha256'] for record in source_checks):
        raise ValueError('A source changed during replay')
    audit={'status':'PASS','main_CSVs_compared':len(catalogue['main_result_fingerprints']),
           'all_CSVs_compared':len(comparisons),'comparisons':comparisons,'commands':commands,
           'independent_checks':independent,'source_checks':source_checks,'inputs_unchanged':True,
           'environment':{'python':sys.version,'packages':{name:importlib.metadata.version(name) for name in ['beautifulsoup4','pdfplumber','pytest']}},
           'scope':'report-conditioned input reproduction, not physical validation',
           'vintage_check':'retained original two-snapshot agreement; not presented as a new revision experiment',
           'restricted_outputs':'generated locally; do not add to public GitHub release without permission'}
    (output/'replay_audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:audit[key] for key in ['status','main_CSVs_compared','all_CSVs_compared','independent_checks','inputs_unchanged']},indent=2))
    return audit

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-stable-basel-content',action='store_true')
    a=p.parse_args();run(a.raw_root,a.output,a.allow_stable_basel_content)
