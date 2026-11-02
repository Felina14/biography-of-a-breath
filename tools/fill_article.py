"""Fill article/ARTICLE_TEMPLATE.md with numbers from the latest LIVE run (out/stats.json)."""
import json, re, sys
S = json.load(open("out/stats.json"))
if "aggregate" not in S: sys.exit("out/stats.json has no live run yet - run python tools/stats.py first")
A = S["aggregate"]; J = {j["name"]: j for j in S["journeys"]}
extra = dict(site_url="https://d28nym7zkli7me.cloudfront.net/", video_url=sys.argv[1] if len(sys.argv) > 1 else "{{video_url}}",
             repo_url=sys.argv[2] if len(sys.argv) > 2 else "{{repo_url}}")
def city(name, field):
    j = J[name]
    if field == "km": return f"{round(j['km']):,}"
    if field == "countries_n": return str(len(j["countries"]))
    if field == "route":
        stops = [p for i, p in enumerate(j["stops"]) if p not in j["stops"][:i]]
        if len(stops) > 6: stops = [stops[round(i * (len(stops) - 2) / 4)] for i in range(5)] + [stops[-1]]
        start = j["start"]["region"]
        mid, end = stops[:-1], (stops[-1] if stops else j["name"])
        s_ = (f"from the {start} " if start else "") + (f"through {', '.join(mid[:-1]) + ' and ' + mid[-1] if len(mid) > 1 else mid[0]} " if mid else "")
        return (s_ + f"to {end}").strip()
    if field == "seas_phrase": return f", much of it over the {' and the '.join(j['seas'][:2])}" if j["seas"] else ""
    return str(j.get(field))
def sub(m):
    k = m.group(1)
    if k.startswith("agg."): v = A[k[4:]]; return f"{v:,}" if isinstance(v, int) and v > 999 else str(v).replace("T", " ").replace("Z", " UTC")
    if k.startswith("j."): name, field = k[2:].rsplit(".", 1); return city(name, field)
    return extra.get(k, m.group(0))
out = re.sub(r"\{\{([^}]+)\}\}", sub, open("article/ARTICLE_TEMPLATE.md").read())
open("article/ARTICLE.md", "w").write(out); print("wrote article/ARTICLE.md;", len(out.split()), "words; unfilled:", re.findall(r"\{\{[^}]+\}\}", out))
