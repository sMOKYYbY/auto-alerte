import re, json, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
      "Accept-Language": "nl-NL,nl;q=0.9", "Accept": "text/html,application/xhtml+xml"}
urls = ["https://www.autotrack.nl/aanbod/volkswagen/golf",
        "https://www.autotrack.nl/aanbod?merkIds=volkswagen&modelIds=golf",
        "https://www.gaspedaal.nl/volkswagen/golf",
        "https://www.gaspedaal.nl/volkswagen/golf?bmin=2017&bmax=2020"]
for u in urls:
    try:
        r = requests.get(u, headers=UA, timeout=30)
    except Exception as e:
        print("##", u, "ERR", e); continue
    h = r.text
    print("##", u, r.status_code, len(h), "final:", r.url)
    nd = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    print("  next_data:", bool(nd), "| nuxt:", "__NUXT__" in h, "| ld+json:", h.count("application/ld+json"))
    if nd:
        d = json.loads(nd.group(1)); pp = d.get("props", {}).get("pageProps", {})
        print("  pp keys:", list(pp)[:30])
        def walk(o, p="", depth=0):
            if depth > 7: return
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, list) and v and isinstance(v[0], dict) and len(v) >= 5:
                        print("  LIST", p + "." + k, len(v), "keys:", list(v[0])[:25])
                    walk(v, p + "." + k, depth + 1)
        walk(pp)
    for m in re.findall(r'https?://[a-z0-9.-]*(?:autotrack|gaspedaal)[a-z0-9.-]*/(?:api|graphql|search)[^"\'\s<>]{0,120}', h)[:10]:
        print("  api-like:", m)
    for m in re.findall(r'href="(/[^"]*(?:/detail/|/occasion/|/auto/|/aanbod/)[^"]{10,140})"', h)[:5]:
        print("  link:", m)
    i = h.find("BTW"); print("  BTW ctx:", re.sub(r"\s+", " ", h[max(0,i-150):i+150]) if i >= 0 else None)
    lj = re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)
    if lj: print("  ld sample:", lj[0][:600])
