"""GitHub Issues(라벨: 제보) → docs/data/reports.js
GitHub Actions 안에서는 자동 제공되는 GITHUB_TOKEN / GITHUB_REPOSITORY 를 사용합니다(개인 토큰 불필요).
상태: 라벨 '조치완료' > '확인됨' > 그 외 '접수'.  닫힌 이슈는 라벨 없어도 '조치완료'로 봅니다.
"""
import os, re, json, requests

repo = os.environ.get("GITHUB_REPOSITORY"); token = os.environ.get("GITHUB_TOKEN")
os.makedirs("docs/data", exist_ok=True)
out = "docs/data/reports.js"
if not repo:
    if not os.path.exists(out):
        open(out,"w",encoding="utf-8").write("var REPORTS=[];\n")
    print("GITHUB_REPOSITORY 없음 — 제보 수집 건너뜀"); raise SystemExit

hdr = {"Accept":"application/vnd.github+json", **({"Authorization":f"Bearer {token}"} if token else {})}
issues, page = [], 1
while True:
    r = requests.get(f"https://api.github.com/repos/{repo}/issues",
                     params={"labels":"제보","state":"all","per_page":100,"page":page}, headers=hdr, timeout=60)
    r.raise_for_status(); b = r.json()
    if not b: break
    issues += [i for i in b if "pull_request" not in i]; page += 1

coord = re.compile(r"(3[3-9]\.\d{3,})\s*[, ]\s*(12[4-9]\.\d{3,}|13[0-2]\.\d{3,})")
def field(body, name):
    m = re.search(rf"### {name}\s*\n+(.*?)(?=\n### |\Z)", body or "", re.S)
    return (m.group(1).strip() if m else "")
reports = []
for i in issues:
    body = i.get("body") or ""
    m = coord.search(field(body,"위치") or body)
    if not m: continue
    labels = {l["name"] for l in i.get("labels",[])}
    status = "조치완료" if ("조치완료" in labels or i["state"]=="closed") else ("확인됨" if "확인됨" in labels else "접수")
    reports.append({"n":i["number"],"t":i["title"],"lat":float(m.group(1)),"lon":float(m.group(2)),
                    "type":field(body,"문제 유형") or "기타","desc":field(body,"설명")[:300],
                    "status":status,"url":i["html_url"],"by":i["user"]["login"],
                    "created":i["created_at"][:10],"updated":i["updated_at"][:10],"comments":i.get("comments",0)})
open(out,"w",encoding="utf-8").write("var REPORTS="+json.dumps(reports,ensure_ascii=False,separators=(",",":"))+";\n")
print(f"제보 {len(reports)}건 → {out}", {s:sum(1 for r in reports if r['status']==s) for s in ('접수','확인됨','조치완료')})
