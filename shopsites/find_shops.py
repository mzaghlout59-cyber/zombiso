"""Find local businesses that have no website, using OpenStreetMap.

    python shopsites/find_shops.py "Porto Alegre, Brazil"
    python shopsites/find_shops.py "Lisbon" --out shopsites/out/leads.csv --allow-no-phone

Asks Nominatim for the city's boundary, then Overpass for every named shop,
craft and small business inside it. Keeps the ones with no website or social
page in OpenStreetMap, skips chains (anything with a brand tag), and by default
keeps only those with a phone number, since those are the ones you can reach.

OpenStreetMap is not complete: a shop missing a website there may still have one.
Search the name before you pitch it.
"""
import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = "shopsites/1.0 (finding local shops without a website)"

# Businesses that usually want a website; amenity/office values are limited to these.
AMENITIES = ("restaurant", "cafe", "fast_food", "bar", "pub", "ice_cream", "dentist",
             "doctors", "clinic", "veterinary", "pharmacy", "driving_school")
OFFICES = ("lawyer", "accountant", "estate_agent", "insurance", "architect")
LEISURE = ("fitness_centre", "sports_centre")
WEB_TAGS = ("website", "contact:website", "url", "facebook", "contact:facebook",
            "instagram", "contact:instagram")
FIELDS = ["slug", "name", "kind", "phone", "email", "street", "housenumber", "postcode",
          "city", "opening_hours", "lat", "lon", "osm_url"]


def http_get(url, params=None, data=None, timeout=180):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode({"data": data}).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def find_area_id(place):
    """Overpass area id for a city name (OSM relation id + 3600000000)."""
    hits = http_get(NOMINATIM, {"q": place, "format": "json", "limit": 10})
    for hit in hits:
        if hit.get("osm_type") == "relation":
            return 3600000000 + int(hit["osm_id"]), hit["display_name"]
    raise SystemExit(f"No city boundary found for {place!r}; try adding the country.")


def overpass_query(area_id):
    alt = lambda vals: "^(" + "|".join(vals) + ")$"
    return f"""[out:json][timeout:170];
area({area_id})->.a;
(
  nwr["shop"]["name"](area.a);
  nwr["craft"]["name"](area.a);
  nwr["amenity"~"{alt(AMENITIES)}"]["name"](area.a);
  nwr["office"~"{alt(OFFICES)}"]["name"](area.a);
  nwr["leisure"~"{alt(LEISURE)}"]["name"](area.a);
  nwr["beauty"]["name"](area.a);
);
out center tags;"""


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "shop"


def kind_of(tags):
    for key in ("shop", "craft", "amenity", "office", "leisure"):
        if tags.get(key):
            return tags[key]
    return "beauty" if tags.get("beauty") else "shop"


def leads_from(elements, need_phone=True):
    """Turn Overpass elements into lead rows: no website, no chain, reachable."""
    leads, seen = [], set()
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name or tags.get("brand") or tags.get("brand:wikidata"):
            continue
        if any(tags.get(t) for t in WEB_TAGS):
            continue
        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile") or ""
        phone = phone.split(";")[0].strip()
        if need_phone and not phone:
            continue
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        slug = base = slugify(name)
        n = 2
        while slug in seen:
            slug, n = f"{base}-{n}", n + 1
        seen.add(slug)
        leads.append({
            "slug": slug, "name": name, "kind": kind_of(tags), "phone": phone,
            "email": tags.get("email") or tags.get("contact:email") or "",
            "street": tags.get("addr:street", ""), "housenumber": tags.get("addr:housenumber", ""),
            "postcode": tags.get("addr:postcode", ""), "city": tags.get("addr:city", ""),
            "opening_hours": tags.get("opening_hours", ""),
            "lat": lat or "", "lon": lon or "",
            "osm_url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        })
    return leads


def write_leads(leads, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(leads)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("place", help='city, ideally with the country: "Porto Alegre, Brazil"')
    ap.add_argument("--out", type=Path, default=Path("shopsites/out/leads.csv"))
    ap.add_argument("--allow-no-phone", action="store_true", help="keep shops with no phone number too")
    args = ap.parse_args(argv)

    area_id, label = find_area_id(args.place)
    print(f"Searching {label} ...")
    time.sleep(1)  # Nominatim's usage policy: at most one request per second
    data = http_get(OVERPASS, data=overpass_query(area_id))
    elements = data.get("elements", [])
    leads = leads_from(elements, need_phone=not args.allow_no_phone)
    write_leads(leads, args.out)
    print(f"{len(elements)} businesses found, {len(leads)} with no website -> {args.out}")


if __name__ == "__main__":
    sys.exit(main())
