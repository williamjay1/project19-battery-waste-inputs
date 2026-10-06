"""Exact sensitivity and decision certificates for a finite reported population.

No sampling probabilities, actual facilities, physical yields or measured
verification accuracy are invented. Perturbations relax report-label evidence;
they are deterministic assumption stress tests, not confidence intervals.
"""
import argparse
import json
from pathlib import Path
from battery_scope_identification import basel_pilot, bounds, write_csv

def margin(nl_lower, be_upper, label_relaxation=0., relative_quantity_error=0.):
    if not (0 <= label_relaxation <= 1 and 0 <= relative_quantity_error < 1):
        raise ValueError('Invalid assumption relaxation')
    return (1-relative_quantity_error)*(1-label_relaxation)*nl_lower-(1+relative_quantity_error)*be_upper

def run(sources, output):
    if output.exists(): raise FileExistsError(output)
    output.mkdir(parents=True)
    certificate=[];sensitivity=[];ablations=[];counterexamples=[]
    for year, path in sources.items():
        rows=basel_pilot(path,year)
        routes={c:[r for r in rows if r['origin']==c] for c in ['BE','NL']}
        for c, rr in routes.items():
            gross=sum(r['quantity_t'] for r in rr)
            excluded=sum(r['quantity_t'] for r in rr if r['low_code']=='160602')
            chemistry_candidates=gross-excluded
            stage_candidates=sum(r['quantity_t'] for r in rr if r['low_code']!='160602' and r['r_code']=='R4' and not r['d_code'])
            final=bounds(rr,'lithium_family','R4')
            for level, lower, upper in [('unqualified_A1170',0,gross),('known_chemistry_exclusion',0,chemistry_candidates),
                                        ('plus_reported_R4',0,stage_candidates),('plus_explicit_lithium_label',final['lower_t'],final['upper_t'])]:
                ablations.append({'year':year,'origin':c,'level':level,'lower_t':lower,'upper_t':upper,'width_t':upper-lower})
            counterexamples.append({'year':year,'origin':c,'naive_A1170_t':gross,'known_NiCd_t':excluded,
                                    'Li_R4_lower_t':final['lower_t'],'Li_R4_upper_t':final['upper_t'],
                                    'spurious_active_Li_R4_route_if_naive':gross>0 and final['upper_t']==0,
                                    'overcommitment_threshold_interval_lower_exclusive_t':final['upper_t'],
                                    'overcommitment_threshold_interval_upper_inclusive_t':gross,
                                    'transit_NL_not_origin_NL_t':sum(r['quantity_t'] for r in rr if c=='BE' and r['transit']=='NL'),
                                    'interpretation':'conditional finite-report input mistake, not demonstrated operator error'})
        for stage in ['all','R4']:
            a=bounds(routes['NL'],'lithium_family',stage);b=bounds(routes['BE'],'lithium_family',stage)
            critical=1-b['upper_t']/a['lower_t'] if a['lower_t'] else None
            certificate.append({'year':year,'target':'lithium_family','stage':stage,
                                'NL_lower_t':a['lower_t'],'BE_upper_t':b['upper_t'],
                                'strict_margin_t':margin(a['lower_t'],b['upper_t']),
                                'label_relaxation_critical_fraction':critical})
            for delta in [0,.25,.5,.75,.9,.95,.99,1]:
                for epsilon in [0,.01,.05,.1,.25]:
                    m=margin(a['lower_t'],b['upper_t'],delta,epsilon)
                    sensitivity.append({'year':year,'stage':stage,'label_relaxation':delta,'quantity_error':epsilon,
                                        'margin_t':m,'NL_strictly_above_BE':m>0})
    for name, data in [('decision_certificates.csv',certificate),('assumption_sensitivity.csv',sensitivity),
                       ('sequential_scope_ablation.csv',ablations),('counterfactual_input_errors.csv',counterexamples)]:
        write_csv(output/name,data)
    audit={'rows':{'certificates':len(certificate),'sensitivity':len(sensitivity),'ablation':len(ablations),
                   'conditional_counterexamples':len(counterexamples)},'design':'post-extraction analytic assumption stress test; no probability law or physical validation',
           'applied_label_rule':'2023 exact description rule unchanged in 2024; H4.2 alone does not identify lithium',
           'strict_versus_weak_order':'EV R4 BE=0 in finite 2024 report implies weak NL dominance but not strict dominance',
           'capacity_decisions':'thresholds concern report-labelled eligible input, not actual facility or annual metal supply'}
    (output/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--basel2023',type=Path,required=True);p.add_argument('--basel2024',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run({2023:a.basel2023,2024:a.basel2024},a.output)
