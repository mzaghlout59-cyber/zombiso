"""Shop sites: only reachable, independent shops without a website become leads, and each gets a site and a pitch."""
from shopsites import build_sites, find_shops

ELEMENTS = [
    {"type": "node", "id": 1, "lat": -30.03, "lon": -51.23,
     "tags": {"shop": "bakery", "name": "Padaria São João", "phone": "+55 51 3333-4444",
              "addr:street": "Rua A", "addr:housenumber": "10", "addr:city": "Porto Alegre",
              "opening_hours": "Mo-Fr 07:00-19:00; Sa 07:00-12:00; Su off"}},
    {"type": "way", "id": 2, "center": {"lat": -30.04, "lon": -51.22},
     "tags": {"shop": "hairdresser", "name": "Padaria São João", "contact:phone": "+55 51 9999-0000"}},
    {"type": "node", "id": 3, "tags": {"shop": "bakery", "name": "Has Site", "phone": "1", "website": "https://x"}},
    {"type": "node", "id": 4, "tags": {"shop": "bakery", "name": "Insta Only", "phone": "1", "instagram": "x"}},
    {"type": "node", "id": 5, "tags": {"shop": "supermarket", "name": "Chain", "phone": "1", "brand": "Big"}},
    {"type": "node", "id": 6, "tags": {"shop": "florist", "name": "No Phone"}},
    {"type": "node", "id": 7, "tags": {"shop": "florist"}},
]


def test_leads_keep_only_reachable_shops_without_a_site():
    leads = find_shops.leads_from(ELEMENTS)
    assert [l["name"] for l in leads] == ["Padaria São João", "Padaria São João"]
    assert [l["slug"] for l in leads] == ["padaria-sao-joao", "padaria-sao-joao-2"]
    assert leads[1]["lat"] == -30.04 and leads[1]["phone"] == "+55 51 9999-0000"
    assert leads[0]["osm_url"] == "https://www.openstreetmap.org/node/1"


def test_no_phone_shops_kept_when_asked():
    names = [l["name"] for l in find_shops.leads_from(ELEMENTS, need_phone=False)]
    assert "No Phone" in names and "Has Site" not in names


def test_build_writes_site_pitch_and_gallery(tmp_path):
    leads_csv = tmp_path / "leads.csv"
    find_shops.write_leads(find_shops.leads_from(ELEMENTS), leads_csv)
    build_sites.main(["--leads", str(leads_csv), "--out", str(tmp_path),
                      "--base-url", "https://me.example/shops/", "--me", "Mo", "--price", "R$ 300"])
    site = (tmp_path / "sites/padaria-sao-joao/index.html").read_text(encoding="utf-8")
    assert "Padaria São João" in site and "Bakery" in site
    assert 'href="tel:+555133334444"' in site and "https://wa.me/555133334444" in site
    assert "<th>Monday – Friday</th><td>07:00-19:00</td>" in site and "<td>Closed</td>" in site
    assert "Beauty &amp; hair" in (tmp_path / "sites/padaria-sao-joao-2/index.html").read_text(encoding="utf-8")
    pitch = (tmp_path / "sites/padaria-sao-joao/pitch.txt").read_text(encoding="utf-8")
    assert "https://me.example/shops/padaria-sao-joao/" in pitch and "R$ 300" in pitch and "Mo" in pitch
    gallery = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "2 shops without a website" in gallery and "wa.me/555133334444?text=" in gallery


def test_site_escapes_shop_data():
    lead = {k: "" for k in find_shops.FIELDS}
    lead.update(name='<script>alert(1)</script>', kind="shop", slug="x")
    html = build_sites.render_site(lead)
    assert "<script>alert" not in html and "&lt;script&gt;" in html
