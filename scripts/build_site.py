#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoSpec site builder
- Generates detail pages from data/items.csv
- Writes index.html
- Writes ads.txt / robots.txt
- Writes sitemap.xml (with XML declaration + RFC3339 UTC lastmod)
- Optional soft-redirects from data/redirects.csv (old_slug,new_slug)
  -> Creates OUT/{old}.html containing a meta refresh to the new URL
  -> Targets only (new URLs) are listed in the sitemap
"""
import os
import csv
import json
import datetime
import pathlib
from typing import List, Dict
from xml.etree.ElementTree import Element, SubElement, tostring
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "items.csv"
REDIRECTS = ROOT / "data" / "redirects.csv"  # optional: old_slug,new_slug
CONF = ROOT / "config" / "affiliates.json"  # optional
TPL = ROOT / "templates"
OUT = ROOT / "dist"


# ── Helpers ──────────────────────────────────────────────────────────────────
def ensure_dir(p: pathlib.Path) -> None:
    os.makedirs(p, exist_ok=True)


def read_json_safe(path: pathlib.Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def now_utc_iso() -> str:
    # RFC3339 / ISO-8601 UTC like 2025-09-19T05:12:00Z
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def norm_base_url(url: str) -> str:
    return url[:-1] if url.endswith("/") else url


def load_affiliate(merchant: str, slug: str) -> str:
    """
    config/affiliates.json example:
    {
      "amazon": {
        "deeplink_base": "https://amazon.com/dp/{slug}",
        "utm": "tag=rino-20"
      }
    }
    """
    conf = read_json_safe(CONF)
    m = conf.get(merchant or "", {})
    base = (m.get("deeplink_base") or "").format(slug=slug)
    utm = m.get("utm") or ""
    if base and utm:
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{utm}"
    return base


def schema_org_article(title: str, desc: str, url: str) -> Dict:
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": desc,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "author": {"@type": "Person", "name": "AutoSpec"},
        "dateModified": datetime.date.today().isoformat(),
    }


def write_ads_txt(dist: pathlib.Path, default_line: str) -> None:
    line = (os.getenv("ADS_TXT_LINE") or default_line).strip()
    (dist / "ads.txt").write_text(line + "\n", encoding="utf-8")


def write_robots_txt(dist: pathlib.Path, base_url: str) -> None:
    robots_txt = "User-agent: *\n" "Allow: /\n" f"Sitemap: {base_url}/sitemap.xml\n"
    (dist / "robots.txt").write_text(robots_txt, encoding="utf-8")


def write_sitemap(dist: pathlib.Path, base_url: str, pages_meta: List[Dict]) -> None:
    """
    Writes sitemap.xml with XML declaration, UTC datetime lastmod.
    Only target URLs (index + generated pages) are listed.
    """
    urlset = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    def add_url(
        loc: str, changefreq: str = "weekly", priority: str = "0.6", lastmod: str | None = None
    ) -> None:
        url = SubElement(urlset, "url")
        SubElement(url, "loc").text = loc
        if lastmod:
            SubElement(url, "lastmod").text = lastmod
        SubElement(url, "changefreq").text = changefreq
        SubElement(url, "priority").text = priority

    ts = now_utc_iso()
    add_url(f"{base_url}/", lastmod=ts, priority="0.8")

    for p in pages_meta:
        add_url(f"{base_url}/{p['path']}", lastmod=ts)

    xml_body = tostring(urlset, encoding="utf-8", method="xml")
    xml_full = b"<?xml version='1.0' encoding='UTF-8'?>\n" + xml_body
    (dist / "sitemap.xml").write_bytes(xml_full)


def write_soft_redirect(dist: pathlib.Path, from_slug: str, to_url: str) -> None:
    """
    Creates OUT/{from_slug}.html that meta-refreshes to to_url.
    Useful as a temporary guard to avoid hard 404s after slug changes.
    """
    html = f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"/>
<meta http-equiv="refresh" content="0;url={to_url}"/>
<link rel="canonical" href="{to_url}"/>
<title>Redirecting…</title>
</head><body>
<p>이 페이지는 <a href="{to_url}">여기로 이동</a>했어.</p>
</body></html>
"""
    (dist / f"{from_slug}.html").write_text(html, encoding="utf-8")


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    env = Environment(
        loader=FileSystemLoader(str(TPL)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    base_url = norm_base_url(os.environ.get("BASE_URL", "https://rinosene.github.io"))
    ensure_dir(OUT)

    pages_meta: List[Dict] = []

    # ── Generate detail pages from items.csv ─────────────────────────────────
    if DATA.exists():
        with open(DATA, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                slug = (row.get("deeplink_slug") or "").strip()
                if not slug:
                    continue

                title = f"{(row.get('keyword') or '').strip()} | {(row.get('entity') or '').strip()} {(row.get('attribute') or '').strip()}".strip()
                desc = f"{(row.get('entity') or '').strip()} {(row.get('attribute') or '').strip()} — {(row.get('modifier') or '').strip()} 기준으로 정리했어."
                url = f"{base_url}/{slug}.html"
                schema_json = json.dumps(
                    schema_org_article(title, desc, url), ensure_ascii=False, indent=2
                )
                affiliate_url = load_affiliate(row.get("merchant", ""), slug)

                body_paragraph = (
                    f"{row.get('entity','')}의 {row.get('attribute','')} 선택 기준을 한눈에 정리했어. "
                    f"추천 스펙은 '{row.get('modifier','')}'이야. "
                    "상황에 따라 다를 수 있으니 실제 상품 상세를 꼭 확인해줘."
                )

                tmpl = env.get_template("page.html")
                html = tmpl.render(
                    title=title,
                    description=desc,
                    canonical=url,
                    schema_json=schema_json,
                    year=datetime.date.today().year,
                    h1=title,
                    subtitle=desc,
                    item=row,
                    affiliate_url=affiliate_url,
                    body_paragraph=body_paragraph,
                    faq_q1=f"{row.get('entity','')} {row.get('attribute','')}은(는) 무엇을 의미해?",
                    faq_a1=f"{row.get('attribute','')}은(는) {row.get('entity','')}의 핵심 특성을 정의하는 항목이야.",
                    faq_q2=f"{row.get('modifier','')}가 모두에게 최선이야?",
                    faq_a2="아니야. 사용 환경과 목적에 따라 다를 수 있어. 본 페이지는 의사결정을 돕기 위한 가이드야.",
                    updated=datetime.date.today().isoformat(),
                )
                (OUT / f"{slug}.html").write_text(html, encoding="utf-8")
                pages_meta.append({"title": title, "desc": desc, "path": f"{slug}.html"})
    # else: silently proceed with index/aux files only

    # ── Index page ───────────────────────────────────────────────────────────
    tmpl = env.get_template("index.html")
    index_html = tmpl.render(
        title="AutoSpec",
        description="사양·호환·규격 모음",
        canonical=f"{base_url}/",
        schema_json=json.dumps(
            {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AutoSpec"},
            ensure_ascii=False,
        ),
        year=datetime.date.today().year,
        pages=pages_meta,
    )
    (OUT / "index.html").write_text(index_html, encoding="utf-8")

    # ── Optional soft redirects from data/redirects.csv ──────────────────────
    # CSV header: old_slug,new_slug
    if REDIRECTS.exists():
        with open(REDIRECTS, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                old_slug = (row.get("old_slug") or "").strip()
                new_slug = (row.get("new_slug") or "").strip()
                if not old_slug or not new_slug:
                    continue
                to_url = f"{base_url}/{new_slug}.html"
                write_soft_redirect(OUT, old_slug, to_url)

    # ── Crawler / Ad assets ──────────────────────────────────────────────────
    write_ads_txt(OUT, default_line="google.com, pub-4919301978364078, DIRECT, f08c47fec0942fa0")
    write_robots_txt(OUT, base_url)
    write_sitemap(OUT, base_url, pages_meta)

    print(f"Generated {len(pages_meta)} pages.")
    print(f"Wrote: {OUT/'index.html'}, {OUT/'ads.txt'}, {OUT/'robots.txt'}, {OUT/'sitemap.xml'}")
    if REDIRECTS.exists():
        print("Soft redirects created from data/redirects.csv")


if __name__ == "__main__":
    main()
