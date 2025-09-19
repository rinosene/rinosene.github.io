#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import csv
import json
import datetime
import pathlib
from xml.etree.ElementTree import Element, SubElement, tostring
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "items.csv"
CONF = ROOT / "config" / "affiliates.json"
TPL = ROOT / "templates"
OUT = ROOT / "dist"


# ── Helpers ──────────────────────────────────────────────────────────────────
def ensure_dir(p: pathlib.Path) -> None:
    os.makedirs(p, exist_ok=True)


def read_json_safe(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_affiliate(merchant: str, slug: str) -> str:
    """
    affiliates.json 예시:
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


def schema_org_article(title: str, desc: str, url: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": desc,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "author": {"@type": "Person", "name": "AutoSpec"},
        "dateModified": datetime.date.today().isoformat(),
    }


def norm_base_url(url: str) -> str:
    # 끝 슬래시 제거(일관성 위해)
    return url[:-1] if url.endswith("/") else url


def write_ads_txt(dist: pathlib.Path, default_line: str) -> None:
    """
    GitHub Actions 환경 변수 ADS_TXT_LINE 을 우선 사용.
    로컬/기본 배포 환경에서는 default_line 사용.
    """
    line = (os.getenv("ADS_TXT_LINE") or default_line).strip()
    # 관례상 마지막에 개행 1개
    (dist / "ads.txt").write_text(line + "\n", encoding="utf-8")


def write_robots_txt(dist: pathlib.Path, base_url: str) -> None:
    robots_txt = "User-agent: *\n" "Allow: /\n" f"Sitemap: {base_url}/sitemap.xml\n"
    (dist / "robots.txt").write_text(robots_txt, encoding="utf-8")


def write_sitemap(dist: pathlib.Path, base_url: str, pages_meta: list) -> None:
    """
    items.csv 기반으로 생성된 모든 페이지(URL) + 홈을 수집해 sitemap.xml 생성.
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

    today_iso = datetime.date.today().isoformat()
    add_url(f"{base_url}/", lastmod=today_iso, priority="0.8")

    for p in pages_meta:
        add_url(f"{base_url}/{p['path']}", lastmod=today_iso)

    xml_bytes = tostring(urlset, encoding="utf-8", method="xml")
    (dist / "sitemap.xml").write_bytes(xml_bytes)


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    env = Environment(
        loader=FileSystemLoader(str(TPL)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # BASE_URL 은 Actions Secrets 로 주입하거나 로컬에선 기본값 사용
    base_url = norm_base_url(os.environ.get("BASE_URL", "https://rinosene.github.io"))
    ensure_dir(OUT)

    pages_meta: list[dict] = []

    # ── 페이지 생성: items.csv → 각 상세 페이지 ───────────────────────────────
    if DATA.exists():
        with open(DATA, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                slug = (row.get("deeplink_slug") or "").strip()
                if not slug:
                    # slug 없으면 스킵
                    continue

                title = f"{row.get('keyword','').strip()} | {row.get('entity','').strip()} {row.get('attribute','').strip()}".strip()
                desc = f"{row.get('entity','').strip()} {row.get('attribute','').strip()} — {row.get('modifier','').strip()} 기준으로 정리했어."
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
    else:
        # items.csv 가 없으면 최소한 index 만 생성
        pass

    # ── 인덱스 페이지 ────────────────────────────────────────────────────────
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

    # ── 크롤러/애드센스 파일 자동 생성 ────────────────────────────────────────
    # 1) ads.txt
    write_ads_txt(OUT, default_line="google.com, pub-4919301978364078, DIRECT, f08c47fec0942fa0")
    # 2) robots.txt
    write_robots_txt(OUT, base_url)
    # 3) sitemap.xml (items.csv 기반 자동 확장)
    write_sitemap(OUT, base_url, pages_meta)

    print(f"Generated {len(pages_meta)} pages.")
    print(f"Wrote: {OUT/'index.html'}, {OUT/'ads.txt'}, {OUT/'robots.txt'}, {OUT/'sitemap.xml'}")


if __name__ == "__main__":
    main()
