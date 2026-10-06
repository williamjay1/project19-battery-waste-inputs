"""Generate citation/Zenodo metadata only from real, user-supplied creators.

No API calls, DOI reservations, uploads or fictitious author records.
JSON is a valid YAML subset and is used for CITATION.cff to avoid escaping bugs.
Unsplit personal names are preserved in Zenodo JSON. CFF is omitted rather than
guessing family/given names or treating a natural person as an organisation.
"""
from __future__ import annotations
import argparse
from datetime import date
import json
from pathlib import Path
import re
from urllib.parse import urlparse

TITLE = 'Battery-waste recycling input identification: reproducibility software'
ABSTRACT = ('Software for report-conditioned battery-waste input identification and '
            'deterministic assumption stresses. MIT covers original software only; '
            'embedded Eurostat/UBA/ILT data retain their source-specific conditions, '
            'including the Austria-declared CN8 commercial-use restriction. Basel raw '
            'records and Basel-derived numerical result/display files are not included. '
            'The study does not identify actual EV flow or facility receipts.')

def real_text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Real, non-empty creator names are required')
    value = value.strip()
    if re.search(r'(?i)^(?:your name|author|placeholder|anonymous|family|given|owner|test|example|姓名|待填|xxx|tbd)$', value):
        raise ValueError('Placeholder identity is not permitted')
    return value

def valid_orcid(value):
    value = value.removeprefix('https://orcid.org/')
    if not re.fullmatch(r'\d{4}-\d{4}-\d{4}-\d{3}[\dX]', value):
        raise ValueError('Invalid ORCID format')
    digits = value.replace('-', '')
    total = 0
    for character in digits[:-1]:
        total = (total + int(character)) * 2
    remainder = (12 - total % 11) % 11
    if digits[-1] != ('X' if remainder == 10 else str(remainder)):
        raise ValueError('Invalid ORCID checksum')
    return value

def metadata(creators, repository_url=None, release_date=None, version='1.0.0'):
    if repository_url is not None:
        url = urlparse(repository_url)
        pieces = url.path.strip('/').split('/')
        if (url.scheme != 'https' or url.netloc != 'github.com' or len(pieces) != 2
                or not all(pieces) or url.query or url.fragment):
            raise ValueError('Supply the actual HTTPS GitHub owner/repository URL')
        if any(x.casefold() in {'owner','repository','your-repo','example'} for x in pieces):
            raise ValueError('A template repository URL is not an actual destination')
    if release_date is not None:
        date.fromisoformat(release_date)
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?', version):
        raise ValueError('Use an explicit semantic version')
    if not isinstance(creators, list) or not creators:
        raise ValueError('Supply a non-empty list of real software/data creators')
    cff_authors, zenodo_creators = [], []
    can_write_cff = True
    for creator in creators:
        if not isinstance(creator, dict):
            raise ValueError('Each creator must be an explicit identity object')
        if set(creator) - {'name','family_names','given_names','affiliation','orcid'}:
            raise ValueError('Unsupported creator fields; do not invent contributor roles')
        if 'name' in creator:
            if 'family_names' in creator or 'given_names' in creator:
                raise ValueError('Use an unsplit name OR supplied family/given names, not both')
            ca = None
            za = {'name':real_text(creator['name'])}
            can_write_cff = False
        else:
            family = real_text(creator.get('family_names'))
            given = real_text(creator.get('given_names'))
            ca = {'family-names':family, 'given-names':given}
            za = {'name':family + ', ' + given}
        if creator.get('affiliation'):
            za['affiliation'] = real_text(creator['affiliation'])
            if ca is not None: ca['affiliation'] = za['affiliation']
        if creator.get('orcid'):
            orcid = valid_orcid(creator['orcid'])
            za['orcid'] = orcid
            if ca is not None: ca['orcid'] = 'https://orcid.org/' + orcid
        if any(previous['name']==za['name'] for previous in zenodo_creators):
            raise ValueError('Duplicate creator identity')
        cff_authors.append(ca); zenodo_creators.append(za)
    keywords = ['battery waste','material flow','scope identification','reproducibility','Europe']
    cff = {'cff-version':'1.2.0', 'message':'If you use this software, cite the exact archived version.',
           'type':'software', 'title':TITLE, 'version':version,
           'authors':cff_authors, 'license':'MIT',
           'abstract':ABSTRACT, 'keywords':keywords}
    zenodo = {'title':TITLE,'version':version,'creators':zenodo_creators,'upload_type':'software',
              'access_right':'open','license':'mit','language':'eng','keywords':keywords,
              'description':ABSTRACT + ' See DATA_REUSE.md and the per-file release manifest. '
                            'No blanket licence is granted over third-party data.'}
    if repository_url is not None:
        cff['repository-code'] = repository_url
        zenodo['related_identifiers'] = [{'identifier':repository_url, 'relation':'isSupplementTo',
                                         'resource_type':'other'}]
    if release_date is not None:
        cff['date-released'] = release_date
    # No publication_date or DOI is invented. Release date remains in CFF;
    # Zenodo publication date is checked by the owner in the actual record.
    return cff if can_write_cff else None, zenodo

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--creators', type=Path, required=True)
    p.add_argument('--repository-url', help='Actual URL only; omit until the repository exists')
    p.add_argument('--release-date', help='Actual release date only; omit for an unreleased candidate')
    p.add_argument('--version', default='1.0.0')
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    a = p.parse_args()
    cff, zenodo = metadata(json.loads(a.creators.read_text(encoding='utf-8-sig')),
                           a.repository_url, a.release_date, a.version)
    destinations = [a.root/'CITATION.cff', a.root/'.zenodo.json']
    if any(path.exists() for path in destinations):
        raise FileExistsError('Existing metadata preserved; edit/version it deliberately')
    for path, content in zip(destinations, [cff, zenodo]):
        if content is None: continue
        with path.open('x',encoding='utf-8') as stream:
            json.dump(content,stream,indent=2,ensure_ascii=False)
            stream.write('\n')
    print('True creator metadata generated. No upload or DOI request performed.')
    if cff is None:
        print('Unsplit personal name retained in .zenodo.json; use CITATION.md, not guessed CFF name fields.')
    print('Refresh the release manifest before archiving: python -m tools.verify_release --refresh-metadata')

if __name__ == '__main__':
    main()
