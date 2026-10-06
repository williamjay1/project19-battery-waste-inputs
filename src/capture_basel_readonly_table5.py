"""Navigate the public readonly national-report viewer to Table 5.

The POST is the page-navigation event shown by the public viewer, not a report
submission: URL must retain readonly=1, and only hidden navigation state is
sent. No answer fields, save events, login or submission actions are used.
Basel captures remain for local source inspection, not redistribution.
"""
import hashlib
import argparse
import http.cookiejar
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, build_opener, HTTPCookieProcessor
from bs4 import BeautifulSoup

def validate_public_viewer_url(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if (parsed.scheme != 'https' or parsed.netloc != 'ers.basel.int'
            or parsed.path != '/ERS-Extended/FeedbackServer/fsadmin.aspx'
            or query.get('readonly') != ['1']
            or query.get('fscontrol') != ['respondentReport']
            or parsed.fragment):
        raise ValueError('Only the official readonly national-report viewer is permitted')
    return url

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, default=Path("F:/AcademicData/project19/raw/basel_table5_navigation_20261002_v1"))
    parser.add_argument('--url', default="https://ers.basel.int/ERS-Extended/FeedbackServer/fsadmin.aspx?fscontrol=respondentReport&surveyid=86&voterid=62482&readonly=1&nomenu=1")
    parser.add_argument('--year', type=int, default=2023)
    args = parser.parse_args()
    raw = args.raw
    if raw.exists():
        raise FileExistsError(raw)
    raw.mkdir(parents=True)
    url = validate_public_viewer_url(args.url)
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(url, timeout=35) as response:
        initial = response.read()
    soup = BeautifulSoup(initial, "html.parser")
    link = next(a for a in soup.find_all("a") if a.get_text(" ", strip=True).startswith("Table 5"))
    match = re.fullmatch(r"javascript:__doPostBack\('([^']+)',''\)", link["href"])
    if not match or "PageNavigator" not in match[1]:
        raise ValueError("Unrecognised readonly Table 5 navigation event")
    fields = {x["name"]: x.get("value", "") for x in soup.select('input[type="hidden"][name]')}
    fields.update(__EVENTTARGET=match[1], __EVENTARGUMENT="")
    with opener.open(Request(url, data=urlencode(fields).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=35) as response:
        body = response.read()
    for name, payload in [(f"germany_{args.year}_initial.html", initial), (f"germany_{args.year}_table5.html", body)]:
        path = raw / name
        with path.open("xb") as stream:
            stream.write(payload)
        path.chmod(0o444)
    manifest = {"original_url": url, "navigation_event": match[1], "action": "readonly page navigation; no answers submitted",
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "sha256_table5": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                "reuse": "Source inspection only; no Basel raw redistribution or asserted open licence"}
    path = raw / "manifest.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    path.chmod(0o444)
    rendered = BeautifulSoup(body, "html.parser").get_text(" ", strip=True)
    print(json.dumps(manifest, ensure_ascii=True))
    print("A1170 occurrences", rendered.count("A1170"))
