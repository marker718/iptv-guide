#!/usr/bin/env python3
"""Builds channels.xml for the iptv-org/epg grabber, limited to the channels you actually have.

1. Reads iptv-org playlists (US, Israel, English-language sports) and collects their tvg-ids.
2. Keeps matching channels from the grabber's own site lists (tvtv.us, tvguide.com, mako, 9tv ...).
3. For Israeli sites whose channels have no xmltv_id, maps them to the playlist tvg-id by name.
"""
import re, sys, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

EPG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("epg")
BASE = "https://iptv-org.github.io/iptv/"
LISTS = {"us": "countries/us.m3u", "il": "countries/il.m3u", "sports": "categories/sports.m3u", "eng": "languages/eng.m3u"}
# tvtv.us returned 404 for every request in the first run, so it is left out.
US_SITES = ["tvguide.com", "tvpassport.com", "bein.com", "nhl.com"]
IL_SITES = ["yes.co.il", "mako.co.il", "9tv.co.il"]
MAX_SPORTS_ENG = 100000

def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return r.read().decode("utf-8", "replace")

def parse(text):
    out = []
    for line in text.splitlines():
        if not line.startswith("#EXTINF"):
            continue
        m = re.search(r'tvg-id="([^"]*)"', line)
        name = line.rsplit(",", 1)[-1].strip()
        if m and m.group(1):
            out.append((m.group(1).split("@")[0], name))
    return out

def norm(s):
    s = s.lower()
    s = re.sub(r"\b(hd|sd|fhd|tv|channel|ערוץ)\b", " ", s)
    return re.sub(r"[^0-9a-z֐-׿]", "", s)

pl = {k: parse(fetch(v)) for k, v in LISTS.items()}
eng_ids = {i for i, _ in pl["eng"]}
sports_en = {i for i, _ in pl["sports"] if i in eng_ids}
us_ids = {i for i, _ in pl["us"]}
wanted = us_ids | sports_en
il_names = {norm(n): i for i, n in pl["il"] if norm(n)}
print(f"wanted ids: {len(wanted)} (US {len(us_ids)}, English sports {len(sports_en)}); IL playlist channels {len(il_names)}")

root = ET.Element("channels")
seen = set()
used_ids = set()

def add(ch, xid):
    key = (ch.get("site"), ch.get("site_id"), xid)
    if key in seen or xid in used_ids:  # one source per channel id, first site wins
        return
    seen.add(key); used_ids.add(xid)
    e = ET.SubElement(root, "channel", {"site": ch.get("site"), "site_id": ch.get("site_id"), "lang": ch.get("lang", "en"), "xmltv_id": xid})
    e.text = ch.text

for site in US_SITES + IL_SITES:
    for f in (EPG / "sites" / site).glob("*.channels.xml"):
        kept = 0
        for ch in ET.parse(f).getroot().iter("channel"):
            xid = (ch.get("xmltv_id") or "").split("@")[0]
            if xid and xid in wanted:
                add(ch, xid); kept += 1
            elif site in IL_SITES:
                m = il_names.get(norm(ch.text or ""))
                if m:
                    add(ch, m); kept += 1
        print(f"{site}: kept {kept}")

ET.indent(root)
ET.ElementTree(root).write("channels.xml", encoding="utf-8", xml_declaration=True)
print("channels written:", len(seen))
