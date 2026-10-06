"""Synthetic metadata/privacy edge cases; not study observations."""
from pathlib import Path
import pytest
from tools.prepare_metadata import metadata, valid_orcid
from tools.verify_release import privacy_schema, verify
from tools.reproduce import scientific_digest
from src.capture_basel_readonly_table5 import validate_public_viewer_url

@pytest.mark.parametrize('value',['0000-0000-0000-0000','not-an-orcid','0000-0002-1825-0098'])
def test_invalid_orcid_rejected(value):
    with pytest.raises(ValueError): valid_orcid(value)

def test_orcid_checksum_implementation():
    # Official documentation example used only as a checksum test, not an author.
    assert valid_orcid('https://orcid.org/0000-0002-1825-0097')=='0000-0002-1825-0097'

@pytest.mark.parametrize('creators',[[],[{'family_names':'Placeholder','given_names':'Author'}],[{'family_names':'','given_names':'A'}]])
def test_fictitious_or_missing_creators_rejected(creators):
    with pytest.raises(ValueError): metadata(creators,'https://github.com/fixture-testing/synthetic-metadata','2026-10-05')

def test_test_identity_stays_in_unit_test_and_doi_is_not_invented():
    cff,z=metadata([{'family_names':'FixtureSurname','given_names':'FixtureGiven'}],
                   'https://github.com/fixture-testing/synthetic-metadata','2026-10-05')
    assert 'doi' not in cff and 'doi' not in z
    assert cff['version']==z['version']
    assert cff['authors'][0]['family-names'] in z['creators'][0]['name']
    assert 'Austria' in z['description'] and 'source-specific' in z['description']

def test_single_declared_contributor_is_preserved_without_guessing_names():
    cff,z=metadata([{'name':'junjiezhang'}])
    assert cff is None  # Do not turn a natural person into a CFF organisation.
    assert z['creators']==[{'name':'junjiezhang'}]
    assert 'contributors' not in z
    for field in ['doi','publication_date','related_identifiers']:
        assert field not in z
    assert 'orcid' not in z['creators'][0] and 'affiliation' not in z['creators'][0]

@pytest.mark.parametrize('creators',[
    [{'name':'Placeholder'}],
    [{'name':'junjiezhang','family_names':'Inferred','given_names':'Name'}],
    [{'name':'junjiezhang'},{'name':'junjiezhang'}],
    [{'name':'junjiezhang','role':'invented contribution'}],
])
def test_ambiguous_duplicate_or_fictitious_identity_is_rejected(creators):
    with pytest.raises(ValueError): metadata(creators)

@pytest.mark.parametrize('url',[
    'https://github.com/OWNER/REPOSITORY',
    'https://github.com/junjiezhang',
    'https://github.com/owner/',
    'http://github.com/fixture-testing/synthetic-metadata',
])
def test_unspecified_or_template_repository_is_not_invented(url):
    with pytest.raises(ValueError): metadata([{'name':'junjiezhang'}],url)

def test_qualified_release_has_exactly_one_declared_creator():
    audit=verify(Path(__file__).resolve().parents[1])
    assert audit['creators']==['junjiezhang']
    assert not audit['cff_present']

@pytest.mark.parametrize('fields',[['email'],['company_name'],['phone','notification_id']])
def test_personal_fields_rejected(fields):
    with pytest.raises(ValueError): privacy_schema(fields)

def test_non_personal_scope_fields_allowed():
    privacy_schema(['notification_id','decision','waste_description','planned_tonnes'])

def test_public_release_inventory_passes():
    assert verify(Path(__file__).resolve().parents[1])['status']=='PASS'

@pytest.mark.parametrize('url',[
    'http://ers.basel.int/ERS-Extended/FeedbackServer/fsadmin.aspx?fscontrol=respondentReport&readonly=1',
    'https://ers.basel.int/ERS-Extended/FeedbackServer/fsadmin.aspx?fscontrol=respondentReport&readonly=10',
    'https://ers.basel.int/ERS-Extended/FeedbackServer/fsadmin.aspx?fscontrol=respondentReport&readonly=0',
    'https://ers.basel.int/ERS-Extended/FeedbackServer/fsadmin.aspx?fscontrol=editReport&readonly=1',
    'https://ers.basel.int.evil.invalid/ERS-Extended/FeedbackServer/fsadmin.aspx?fscontrol=respondentReport&readonly=1',
])
def test_non_readonly_report_actions_are_not_allowed(url):
    with pytest.raises(ValueError): validate_public_viewer_url(url)

def test_official_readonly_navigation_is_allowed():
    url='https://ers.basel.int/ERS-Extended/FeedbackServer/fsadmin.aspx?fscontrol=respondentReport&surveyid=86&voterid=62482&readonly=1&nomenu=1'
    assert validate_public_viewer_url(url)==url

def test_envelope_change_is_not_scientific_row_change(tmp_path):
    # Wholly synthetic HTML, not copied from any report.
    def payload(state,quantity=10):
        def row(origin):
            cells=['1','A1170','','200133','Lithium batteries','',str(quantity),'',origin,'','R4']
            return '<tr>'+''.join('<td>'+cell+'</td>' for cell in cells)+'</tr>'
        return '<input type="hidden" value="'+state+'"><table>'+row('BE')+row('NL')+'</table>'
    a,b,c=[tmp_path/name for name in ['a.html','b.html','c.html']]
    for path,data in [(a,payload('envelope-1')),(b,payload('envelope-2')),(c,payload('envelope-2',11))]:
        path.write_text(data,encoding='utf-8')
    assert scientific_digest(a,2023)==scientific_digest(b,2023)
    assert scientific_digest(a,2023)!=scientific_digest(c,2023)
