"""Small, explicit official-source retrieval. No credentials or silent vintage substitution."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'www.umweltbundesamt.de','www.ilent.nl'}

def retrieve(raw, selections):
    catalogue=json.loads((ROOT/'provenance/source_inputs.json').read_text(encoding='utf-8'))
    records=[]
    for name in selections:
        source=catalogue['inputs'][name]
        url=source['url']
        if urlparse(url).scheme!='https' or urlparse(url).hostname not in ALLOWED:
            raise ValueError('Only the explicitly listed official UBA/ILT HTTPS files are downloaded here')
        path=raw/source['relative_path']
        if path.exists(): raise FileExistsError(path)
        request=Request(url,headers={'User-Agent':'Battery-scope-reproducibility/1.0 (non-commercial research)'})
        with urlopen(request,timeout=45) as response:
            if urlparse(response.url).hostname not in ALLOWED:
                raise ValueError('Redirect outside official source hosts')
            body=response.read(); final_url=response.url
        if len(body)<100 or (path.suffix=='.pdf' and not body.startswith(b'%PDF')) or (path.suffix=='.ods' and not body.startswith(b'PK')):
            raise ValueError('Empty/challenge/schema response is not a scientific source')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream: stream.write(body)
        path.chmod(0o444)
        digest=hashlib.sha256(body).hexdigest()
        record={'source':name,'url':url,'final_url':final_url,'retrieved_utc':datetime.now(timezone.utc).isoformat(),
                'bytes':len(body),'sha256':digest,'matches_frozen_bytes':digest==source['sha256'],
                'relative_path':source['relative_path'],'redistribution':'raw file is excluded from public repository'}
        records.append(record)
        print(json.dumps(record))
    audit=raw/'retrieval_manifest.json'
    with audit.open('x',encoding='utf-8') as stream: json.dump(records,stream,indent=2)
    audit.chmod(0o444)
    if not all(record['matches_frozen_bytes'] for record in records):
        raise ValueError('An upstream snapshot changed. It is preserved, not substituted for the frozen analysis.')
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-root',type=Path,required=True)
    p.add_argument('--sources',nargs='+',choices=['uba2023','uba2024','permits'],default=['uba2023','uba2024','permits'])
    a=p.parse_args(); retrieve(a.raw_root,a.sources)
