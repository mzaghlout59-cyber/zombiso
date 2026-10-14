"""Build a one-page preview website and a sales pitch for every lead.

    python shopsites/build_sites.py --me "Mohamad" --my-phone "+55 51 99999-0000" --price "R$ 300"
    python shopsites/build_sites.py --base-url https://you.github.io/shops

Reads shopsites/out/leads.csv (from find_shops.py) and writes:
    shopsites/out/sites/<slug>/index.html   the shop's preview site
    shopsites/out/sites/<slug>/pitch.txt    the message to send the owner
    shopsites/out/index.html                your gallery: every preview, with one-click
                                            WhatsApp / call buttons to pitch each shop

Put shopsites/out/sites online (GitHub Pages, Netlify Drop) and pass its address as
--base-url so each pitch links to that shop's own preview.
"""
import argparse
import csv
import re
import sys
import urllib.parse
from html import escape
from pathlib import Path

# Look and copy per kind of business: (label, accent colour, tagline, three selling points)
THEMES = {
    "food": ("Restaurant", "#c2410c", "Good food, made fresh every day.",
             ["Fresh, home-made dishes", "Friendly service", "Takeaway available — just call"]),
    "bakery": ("Bakery", "#b45309", "Baked fresh every morning.",
               ["Fresh bread every day", "Cakes for every occasion", "Orders by phone or WhatsApp"]),
    "cafe": ("Café", "#92400e", "Your daily coffee, done right.",
             ["Freshly brewed coffee", "Cakes and snacks", "A cosy place to stop by"]),
    "beauty": ("Beauty & hair", "#be185d", "Look good, feel better.",
               ["Experienced professionals", "Book by phone or WhatsApp", "Relaxed, welcoming salon"]),
    "health": ("Health care", "#0f766e", "Care you can trust, close to home.",
               ["Qualified professionals", "Appointments by phone", "Attentive, personal care"]),
    "auto": ("Car services", "#1d4ed8", "Keep your car running at its best.",
             ["Honest, skilled work", "Fair prices", "Call for a quick quote"]),
    "trade": ("Craft & repairs", "#a16207", "Skilled work, done properly.",
              ["Years of experience", "Quality materials", "Free quotes by phone"]),
    "office": ("Professional services", "#334155", "Expert advice when you need it.",
               ["Experienced and reliable", "Clear, honest pricing", "Call to book a meeting"]),
    "fitness": ("Fitness", "#15803d", "Get stronger, every week.",
                ["Modern equipment", "Friendly coaches", "Come for a free trial"]),
    "shop": ("Shop", "#4f46e5", "Quality products and friendly advice.",
             ["Carefully chosen products", "Helpful, local service", "Call to check what's in stock"]),
}
KIND_TO_THEME = {
    **dict.fromkeys(["restaurant", "fast_food", "bar", "pub", "ice_cream", "butcher",
                     "deli", "greengrocer", "seafood"], "food"),
    **dict.fromkeys(["bakery", "pastry", "confectionery"], "bakery"),
    "cafe": "cafe", "coffee": "cafe",
    **dict.fromkeys(["hairdresser", "beauty", "cosmetics", "massage", "tattoo", "nails"], "beauty"),
    **dict.fromkeys(["dentist", "doctors", "clinic", "veterinary", "pharmacy", "optician",
                     "chemist", "hearing_aids", "medical_supply"], "health"),
    **dict.fromkeys(["car_repair", "car", "car_parts", "tyres", "motorcycle", "bicycle"], "auto"),
    **dict.fromkeys(["carpenter", "electrician", "plumber", "tailor", "shoemaker", "locksmith",
                     "painter", "builder", "upholsterer", "glazier", "photographer"], "trade"),
    **dict.fromkeys(["lawyer", "accountant", "estate_agent", "insurance", "architect",
                     "driving_school"], "office"),
    **dict.fromkeys(["fitness_centre", "sports_centre"], "fitness"),
}
DAYS = {"Mo": "Monday", "Tu": "Tuesday", "We": "Wednesday", "Th": "Thursday", "Fr": "Friday",
        "Sa": "Saturday", "Su": "Sunday", "PH": "Public holidays"}

PITCH = """Hi! My name is {me}. I noticed {name} doesn't have a website yet, so I made one for you to see, free:

{url}

It shows your hours, phone, a map to find you and a WhatsApp button, and it works on any phone.

If you like it, I can put it online under your own name (like {domain}) for {price}, with changes included. If not, no problem at all.

{signoff}"""


def theme_for(kind):
    return THEMES[KIND_TO_THEME.get(kind, "shop")]


def digits(phone):
    return re.sub(r"\D", "", phone)


def address(lead):
    street = " ".join(p for p in (lead["street"], lead["housenumber"]) if p)
    return ", ".join(p for p in (street, lead["postcode"], lead["city"]) if p)


def hours_rows(opening_hours):
    """OSM opening_hours ("Mo-Fr 09:00-18:00; Sa 09:00-13:00") as (days, times) rows."""
    rows = []
    for part in filter(None, (p.strip() for p in opening_hours.split(";"))):
        m = re.match(r"^([A-Za-z,\- ]+?)\s+(\d.*|off|closed)$", part)
        if not m:
            rows.append(("", part))
            continue
        days = re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b", lambda d: DAYS[d.group(1)], m.group(1))
        rows.append((days.replace("-", " – "), m.group(2).replace("off", "Closed")))
    return rows


def render_site(lead):
    label, accent, tagline, points = theme_for(lead["kind"])
    e = {k: escape(str(v)) for k, v in lead.items()}
    tel, addr = digits(lead["phone"]), address(lead)
    buttons = []
    if tel:
        buttons.append(f'<a class="btn" href="tel:+{tel}">Call {e["phone"]}</a>')
        buttons.append(f'<a class="btn alt" href="https://wa.me/{tel}">WhatsApp</a>')
    if lead["lat"]:
        buttons.append(f'<a class="btn alt" href="https://www.google.com/maps/dir/?api=1&amp;destination='
                       f'{lead["lat"]},{lead["lon"]}">Directions</a>')
    hours = "".join(f"<tr><th>{escape(d)}</th><td>{escape(t)}</td></tr>" for d, t in hours_rows(lead["opening_hours"]))
    hours_html = f'<section><h2>Opening hours</h2><table>{hours}</table></section>' if hours else ""
    map_html = ""
    if lead["lat"]:
        lat, lon = float(lead["lat"]), float(lead["lon"])
        bbox = f"{lon - .004},{lat - .0025},{lon + .004},{lat + .0025}"
        map_html = (f'<iframe title="Map" loading="lazy" src="https://www.openstreetmap.org/export/embed.html?'
                    f'bbox={bbox}&amp;layer=mapnik&amp;marker={lat},{lon}"></iframe>')
    contact = "".join(f"<p>{x}</p>" for x in (
        escape(addr), e["phone"] and f'<a href="tel:+{tel}">{e["phone"]}</a>',
        e["email"] and f'<a href="mailto:{e["email"]}">{e["email"]}</a>') if x)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e["name"]} · {escape(label)}</title>
<meta name="description" content="{e["name"]}: {escape(tagline)} {escape(addr)}">
<style>
  :root {{ --accent: {accent}; --ink: #1c1917; --muted: #57534e; --bg: #fafaf9; --card: #fff; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font: 16px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--ink); background: var(--bg); }}
  .preview {{ background: #fef3c7; color: #78350f; text-align: center; font-size: 13px; padding: 6px 16px; }}
  header {{ background: var(--accent); color: #fff; padding: 64px 20px 56px; text-align: center; }}
  header small {{ text-transform: uppercase; letter-spacing: .14em; opacity: .85; font-size: 12px; }}
  h1 {{ font-size: clamp(32px, 7vw, 54px); line-height: 1.1; margin: 8px 0 12px; }}
  header p {{ font-size: 19px; margin: 0 0 28px; opacity: .95; }}
  .btns {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }}
  .btn {{ background: #fff; color: var(--accent); padding: 12px 22px; border-radius: 999px; font-weight: 700; text-decoration: none; }}
  .btn.alt {{ background: transparent; color: #fff; border: 2px solid #fff; }}
  main {{ max-width: 860px; margin: 0 auto; padding: 32px 16px; display: grid; gap: 20px; }}
  section {{ background: var(--card); border-radius: 14px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  h2 {{ margin: 0 0 12px; font-size: 20px; color: var(--accent); }}
  ul.points {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }}
  ul.points li {{ padding: 14px; border-left: 4px solid var(--accent); background: var(--bg); border-radius: 6px; font-weight: 600; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 6px 0; border-bottom: 1px solid #e7e5e4; }}
  th {{ font-weight: 600; padding-right: 16px; }}
  iframe {{ width: 100%; height: 300px; border: 0; border-radius: 10px; margin-top: 12px; }}
  section p {{ margin: 4px 0; }}
  a {{ color: var(--accent); }}
  footer {{ text-align: center; color: var(--muted); font-size: 13px; padding: 24px 16px 40px; }}
</style>
</head>
<body>
<div class="preview">Preview made for {e["name"]} — not live yet</div>
<header>
  <small>{escape(label)}</small>
  <h1>{e["name"]}</h1>
  <p>{escape(tagline)}</p>
  <div class="btns">{"".join(buttons)}</div>
</header>
<main>
  <section><h2>Why come to us</h2><ul class="points">{"".join(f"<li>{escape(p)}</li>" for p in points)}</ul></section>
  {hours_html}
  <section><h2>Find us</h2>{contact}{map_html}</section>
</main>
<footer>© {e["name"]}</footer>
</body>
</html>
"""


def render_pitch(lead, url, me, my_phone, price):
    domain = lead["slug"].replace("-", "") + ".com"
    signoff = " · ".join(x for x in (me, my_phone) if x)
    return PITCH.format(me=me or "…", name=lead["name"], url=url, domain=domain,
                        price=price or "a small one-off price", signoff=signoff)


def render_gallery(rows):
    cards = []
    for lead, pitch in rows:
        tel = digits(lead["phone"])
        wa = f"https://wa.me/{tel}?text={urllib.parse.quote(pitch)}" if tel else ""
        label = theme_for(lead["kind"])[0]
        cards.append(f"""<li>
  <a class="name" href="sites/{escape(lead["slug"])}/index.html" target="_blank">{escape(lead["name"])}</a>
  <span class="kind">{escape(label)} · {escape(lead["kind"])}</span>
  <span>{escape(address(lead))}</span>
  <span class="act">{f'<a href="{escape(wa)}" target="_blank">Send pitch on WhatsApp</a>' if wa else ""}
    {f'<a href="tel:+{tel}">Call {escape(lead["phone"])}</a>' if tel else ""}
    <a href="sites/{escape(lead["slug"])}/pitch.txt" target="_blank">Pitch text</a>
    <a href="https://www.google.com/search?q={urllib.parse.quote(lead["name"] + " " + lead["city"])}" target="_blank">Check: really no site?</a></span>
</li>""")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shop leads</title>
<style>
  body {{ margin: 0; font: 15px/1.5 system-ui, sans-serif; background: #f5f5f4; color: #1c1917; }}
  h1 {{ margin: 0; padding: 24px 16px 8px; max-width: 960px; margin-inline: auto; }}
  p.sub {{ max-width: 960px; margin: 0 auto; padding: 0 16px; color: #57534e; }}
  ul {{ list-style: none; max-width: 960px; margin: 16px auto; padding: 0 16px; display: grid; gap: 10px; }}
  li {{ background: #fff; border-radius: 10px; padding: 14px 16px; display: grid; gap: 2px; box-shadow: 0 1px 2px rgba(0,0,0,.06); }}
  .name {{ font-weight: 700; font-size: 17px; color: #1c1917; }}
  .kind {{ color: #78716c; font-size: 13px; }}
  .act {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 6px; }}
  .act a {{ color: #4f46e5; font-weight: 600; text-decoration: none; }}
</style></head>
<body><h1>{len(rows)} shops without a website</h1>
<p class="sub">Open a preview, check the shop really has no site, then send the pitch.</p>
<ul>{"".join(cards)}</ul></body></html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--leads", type=Path, default=Path("shopsites/out/leads.csv"))
    ap.add_argument("--out", type=Path, default=Path("shopsites/out"))
    ap.add_argument("--base-url", default="", help="where out/sites is hosted, e.g. https://you.github.io/shops")
    ap.add_argument("--me", default="", help="your name, for the pitch")
    ap.add_argument("--my-phone", default="", help="your phone, for the pitch")
    ap.add_argument("--price", default="", help='your price, e.g. "R$ 300" or "$150"')
    args = ap.parse_args(argv)

    with open(args.leads, encoding="utf-8") as f:
        leads = list(csv.DictReader(f))
    rows = []
    for lead in leads:
        folder = args.out / "sites" / lead["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(render_site(lead), encoding="utf-8")
        url = f'{args.base_url.rstrip("/")}/{lead["slug"]}/' if args.base_url else "[link to your preview]"
        pitch = render_pitch(lead, url, args.me, args.my_phone, args.price)
        (folder / "pitch.txt").write_text(pitch, encoding="utf-8")
        rows.append((lead, pitch))
    (args.out / "index.html").write_text(render_gallery(rows), encoding="utf-8")
    print(f"{len(rows)} preview sites -> {args.out / 'sites'}; open {args.out / 'index.html'} to start pitching")


if __name__ == "__main__":
    sys.exit(main())
