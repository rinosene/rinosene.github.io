#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, csv, json, datetime, pathlib
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "items.csv"
CONF = ROOT / "config" / "affiliates.json"
TPL  = ROOT / "templates"
OUT  = ROOT / "dist"

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def load_affiliate(merchant, slug):
    conf = json.loads(CONF.read_text(encoding="utf-8"))
    m = conf.get(merchant, {})
    base = m.get("deeplink_base", "").format(slug=slug)
    utm = m.get("utm", "")
    if base and utm:
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{utm}"
    return base

def schema_org_article(title, desc, url):
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": desc,
        "mainEntityOfPage": {"@type":"WebPage","@id":url},
        "author": {"@type": "Person", "name": "AutoSpec"},
        "dateModified": datetime.date.today().isoformat(),
    }

def main():
    env = Environment(
        loader=FileSystemLoader(str(TPL)),
        autoescape=select_autoescape(['html', 'xml'])
    )
    base_url = os.environ.get("BASE_URL", "https://example.com")
    ensure_dir(OUT)
    pages_meta = []

    with open(DATA, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = f"{row['deeplink_slug']}".strip()
            path = OUT / f"{slug}.html"
            title = f"{row['keyword']} | {row['entity']} {row['attribute']}"
            desc = f"{row['entity']} {row['attribute']} — {row['modifier']} 기준으로 정리했어."
            url = f"{base_url}/{slug}.html"
            schema_json = json.dumps(schema_org_article(title, desc, url), ensure_ascii=False, indent=2)
            affiliate_url = load_affiliate(row['merchant'], slug)

            body_paragraph = f"{row['entity']}의 {row['attribute']} 선택 기준을 한눈에 정리했어. " \
                             f\"추천 스펙은 '{row['modifier']}'이야. 상황에 따라 다를 수 있으니 실제 상품 상세를 꼭 확인해줘.\"

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
                faq_q1=f"{row['entity']} {row['attribute']}은(는) 무엇을 의미해?",
                faq_a1=f"{row['attribute']}은(는) {row['entity']}의 핵심 특성을 정의하는 항목이야.",
                faq_q2=f"{row['modifier']}가 모두에게 최선이야?",
                faq_a2="아니야. 사용 환경과 목적에 따라 다를 수 있어. 본 페이지는 의사결정을 돕기 위한 가이드야.",
                updated=datetime.date.today().isoformat()
            )
            path.write_text(html, encoding="utf-8")
            pages_meta.append({"title": title, "desc": desc, "path": f"{slug}.html"})

    # Index page
    tmpl = env.get_template("index.html")
    index_html = tmpl.render(
        title="AutoSpec",
        description="사양·호환·규격 모음",
        canonical=f"{base_url}/",
        schema_json=json.dumps({"@context":"https://schema.org","@type":"CollectionPage","name":"AutoSpec"}, ensure_ascii=False),
        year=datetime.date.today().year,
        pages=pages_meta
    )
    (OUT / "index.html").write_text(index_html, encoding="utf-8")

    # robots.txt
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: {}/sitemap.xml\n".format(base_url), encoding="utf-8")

    # sitemap.xml
    from xml.etree.ElementTree import Element, SubElement, tostring
    urlset = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    def add_url(loc):
        url = SubElement(urlset, "url")
        SubElement(url, "loc").text = loc
        SubElement(url, "changefreq").text = "weekly"
        SubElement(url, "priority").text = "0.6"
    add_url(f"{base_url}/")
    for p in pages_meta:
        add_url(f"{base_url}/{p['path']}")
    xml_str = tostring(urlset, encoding="utf-8", method="xml")
    (OUT / "sitemap.xml").write_bytes(xml_str)

    print(f"Generated {len(pages_meta)} pages.")

if __name__ == "__main__":
    main()
