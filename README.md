# AutoSpec — 자동 수익 사이트 스타터

**목표:** CSV → 수백 개 페이지를 자동 생성하고, 제휴 링크·광고를 삽입해 "손 안 대고 돌아가는" 트래픽 머신 만들기.

## 빠른 시작
1) 이 레포를 GitHub에 올리고 `Settings → Pages`에서 **GitHub Pages**로 배포해.
2) `BASE_URL`을 레포의 **Secrets**에 추가(예: `https://yourdomain.com`).
3) `data/items.csv`에 네 이슈(사양/호환/규격) 항목을 300행 이상 채워.
4) `config/affiliates.json`에 제휴 딥링크 패턴을 업데이트해.
5) 매일 03:00 KST에 자동 빌드·배포돼. 필요하면 `.github/workflows/build.yml`의 cron을 수정해.

## 로컬 빌드
```bash
pip install Jinja2
python scripts/build_site.py
open dist/index.html
```

## 검색 제출
배포 후 `scripts/ping_search.py`로 sitemap 핑을 보낼 수 있어.
```bash
SITEMAP_URL="https://yourdomain.com/sitemap.xml" python scripts/ping_search.py
```

## 참고
- 템플릿은 `templates/`에서 수정.
- 페이지는 `dist/`에 생성.
- 광고 스니펫·애널리틱스는 `templates/base.html`의 `<head>`나 `<footer>`에 넣어.

