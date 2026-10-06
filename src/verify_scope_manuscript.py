"""Independent Decimal replay of source rows and article tables.

No production eligibility/bounds routines are imported. Output contains checks
and hashes, not a reconstructed Basel row-level dataset for redistribution.
"""
import argparse
import csv
import hashlib
import json
import re
from decimal import Decimal as D
from pathlib import Path
from bs4 import BeautifulSoup

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def raw_cases(path):
    soup=BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
    found=[]
    for tr in soup.find_all('tr'):
        cells=[td.get_text(' ',strip=True) for td in tr.find_all('td',recursive=False)]
        if len(cells)==11 and cells[1]=='A1170' and cells[8] in {'BE','NL'}:
            q=D(cells[6])
            assert q.is_finite() and q>=0
            found.append(dict(origin=cells[8],code=cells[3],description=cells[4],
                              q=q,transit=cells[7],disposal=cells[9],operation=cells[10]))
    return found

def independent_bounds(rows,origin,target,stage):
    selected=[r for r in rows if r['origin']==origin and r['code'] not in {'160601','160602','160603'}
              and (stage=='all' or (r['operation']=='R4' and not r['disposal']))]
    upper=sum((r['q'] for r in selected),D(0))
    lower=sum((r['q'] for r in selected if target=='lithium_family' and
               r['description'].casefold()=='lithium batteries'),D(0))
    return lower,upper

def tables(text):
    groups=[]; current=[]
    for line in text.splitlines()+['']:
        if line.startswith('|'):
            cells=[c.strip() for c in line.strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?', c) for c in cells): current.append(cells)
        elif current: groups.append(current);current=[]
    assert len(groups)==6
    return groups

def run(project,manuscript,basel2023,basel2024,output):
    output.mkdir(parents=True,exist_ok=False)
    text=manuscript.read_text(encoding='utf-8-sig'); tab=tables(text); checks=[]
    def equal(label,got,expected,tolerance=D('0.000001')):
        assert abs(D(str(got))-D(str(expected)))<=tolerance,(label,got,expected)
        checks.append(label)
    def displayed(label,cell,value):
        equal(label,cell.replace(',',''),D(value).quantize(D('.001')),D('.000001'))
    cases={2023:raw_cases(basel2023),2024:raw_cases(basel2024)}
    for y,name in [(2023,'scope_identification_pilot_20261002_v1'),(2024,'scope_identification_transfer_20261002_v1')]:
        rr=cases[y]; equal(f'{y} source row count',len(rr),9 if y==2023 else 10)
        for r in read_csv(project/'results'/name/'finite_report_scope_bounds.csv'):
            lo,hi=independent_bounds(rr,r['origin'],r['target'],r['stage'])
            for field,v in [('lower_t',lo),('upper_t',hi),('width_t',hi-lo)]:
                equal(f'{y} {r["origin"]} {r["target"]} {r["stage"]} {field}',r[field],v)
        for c in ['BE','NL']:
            rr_c=[r for r in rr if r['origin']==c]
            gross=sum((r['q'] for r in rr_c),D(0))
            cd=sum((r['q'] for r in rr_c if r['code']=='160602'),D(0))
            lo,hi=independent_bounds(rr,c,'lithium_family','R4')
            row=next(r for r in tab[2][1:] if r[0]==str(y) and r[1]==c)
            for k,v in [(2,gross),(3,cd),(4,hi)]: displayed(f'T3 {y} {c} col{k}',row[k],v)
            row=next(r for r in tab[3][1:] if r[0]==str(y) and r[1]==c)
            for k,v in [(2,lo),(3,hi),(4,D(0)),(5,hi)]: displayed(f'T4 {y} {c} col{k}',row[k],v)
        for stage,display in [('all','All operations'),('R4','R4')]:
            lo,_=independent_bounds(rr,'NL','lithium_family',stage)
            _,hi=independent_bounds(rr,'BE','lithium_family',stage)
            row=next(r for r in tab[4][1:] if r[0]==str(y) and r[1]==display)
            displayed(f'T5 {y} {stage} margin',row[2],lo-hi)
            displayed(f'T5 {y} {stage} discount',row[3],100*(1-hi/lo))
        actual_cd=sum((r['q'] for r in rr if r['code']=='160602'),D(0))
        assert f'{actual_cd:.3f} t' in text
        checks.append(f'{y} NiCd abstract/body source value')
    cert=project/'results'/'scope_decision_certificates_20261002_v1'
    for row in read_csv(cert/'decision_certificates.csv'):
        y=int(row['year']); lo,_=independent_bounds(cases[y],'NL','lithium_family',row['stage']); _,hi=independent_bounds(cases[y],'BE','lithium_family',row['stage'])
        equal(f'certificate {y} {row["stage"]}',row['strict_margin_t'],lo-hi)
    sens=read_csv(cert/'assumption_sensitivity.csv');equal('all sensitivity rows',len(sens),160)
    for i,row in enumerate(sens):
        y=int(row['year']);lo,_=independent_bounds(cases[y],'NL','lithium_family',row['stage']);_,hi=independent_bounds(cases[y],'BE','lithium_family',row['stage'])
        d=D(row['label_relaxation']);e=D(row['quantity_error']);m=(1-e)*(1-d)*lo-(1+e)*hi
        equal(f'sensitivity {i} margin',row['margin_t'],m)
        assert row['NL_strictly_above_BE']==str(m>0)
    permit=read_csv(project/'results'/'public_permit_field_gate_20261002_v1'/'public_permit_scope_cases.csv')
    equal('permit selected cases',len(permit),151);assert len({r['notification_id'] for r in permit})==151
    for row in tab[5][1:]:
        original=next(r for r in permit if r['notification_id']==row[0])
        assert original['decision']==('Bezwaar' if row[1]=='Objection' else 'Toestemming')
        assert original['Basel_code']=='A1170'
        for op in re.findall(r'\b[RD]\d+\b',row[3]):assert op in original['D_R_codes']
        checks.append('T6 verified status/operations '+row[0])
    trade=read_csv(project/'datasets'/'eucomext_battery_waste_trade_20260929_v2'/'eu27_directed_trade_observations.csv')
    equal('trade observation count',len(trade),980)
    for flow,total in [('export','95,322.436'),('import','75,364.806')]:
        q=sum((D(r['quantity_t']) for r in trade if r['flow']==flow),D(0));displayed('trade total '+flow,total,q)
    source_flags={'no_independent_physical_validation':True,'2024_same_rule_not_preregistered':True,
                  'EV_not_identified':True,'Basel_source_rows_not_redistributed':True}
    for pattern in ['NEEDS STRENGTHENING','publication_state','similarity risk','Reviewer 2','placeholder',r'\begin{',r'\frac{']:
        assert pattern.casefold() not in text.casefold(),pattern
    assert 25000<=len(text)<=35000
    abstract=text.split('## Abstract')[1].split('Keywords:')[0].strip()
    assert len(abstract.split())<=250
    references=[l for l in text.split('## References')[1].splitlines() if l.strip()]
    audit={'status':'PASS','independent_decimal_checks':len(checks),'checks':checks,
           'character_count_including_spaces':len(text),'abstract_words':len(abstract.split()),
           'table_count':6,'reference_count':len(references),'scope_flags':source_flags,
           'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [manuscript,basel2023,basel2024]},
           'claim_support':'Within-source identification and counterfactual input implications; no measured accuracy improvement.'}
    (output/'numeric_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k not in ['checks','source_sha256']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,default=Path('.'));p.add_argument('--manuscript',type=Path,required=True)
    p.add_argument('--basel2023',type=Path,required=True);p.add_argument('--basel2024',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.project,a.manuscript,a.basel2023,a.basel2024,a.output)
