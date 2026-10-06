"""Public permit field gate; planned authorisations are not received waste.

Only notification IDs and non-personal scope/status/route fields are retained.
No company or contact names are extracted into the output. Do not add quantities
across decision versions or convert multi-year ceilings to annual shipments.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

NS = {'t': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
      'x': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}

def ods_rows(path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read('content.xml'))
    for row in root.findall('.//t:table-row', NS):
        cells = []
        for cell in row:
            text = ' '.join(''.join(p.itertext()) for p in cell.findall('.//x:p', NS))
            repeat = int(cell.get('{'+NS['t']+'}number-columns-repeated', '1'))
            cells.extend([text] * min(repeat, max(0, 26-len(cells))))
        yield cells

def run(source, output):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    rows = list(ods_rows(source))
    if rows[0][20] != 'Geplande hoeveelheid in ton' or rows[0][24] != 'Datum besluit':
        raise ValueError('Public ODS schema changed')
    selected = [r for r in rows[1:] if len(r)>24 and r[5]=='NLD' and r[14]=='DUI'
                and any(k in r[15].casefold() for k in ['batter','accu','lithium'])]
    indices = [0,1,2,5,14,15,16,17,18,19,20,21,22,23,24]
    names = ['notification_id','application_type','decision','notifier_country_source','processor_country_source',
             'waste_description','OECD_code','Basel_code','LoW_code','D_R_codes','planned_tonnes',
             'planned_shipments','planned_first_departure','planned_last_departure','decision_date']
    with (output/'public_permit_scope_cases.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(names);writer.writerows([[r[i] for i in indices] for r in selected])
    meta = {'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(), 'XML_rows_including_header':len(rows),
            'selected_route_battery_decision_rows':len(selected), 'unique_notification_ids':len({r[0] for r in selected}),
            'source_country_convention':'DUI is Germany, not ISO DEU; NLD is Netherlands',
            'planned_quantity_not_actual':True, 'public_received_weighing_field':False,
            'independent_annual_physical_validation':False, 'descriptions_are_case_evidence_not_truth_labels':True,
            'no_personal_fields_retained':True,'aggregation_of_planned_tonnage':'prohibited',
            'copyright':'ILT site text CC0 except specified material; original ODS credit and snapshot retained'}
    (output/'audit.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps(meta,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.source,a.output)
