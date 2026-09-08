"""경기데이터드림 OpenAPI 수집기 — CCTV 현황(제공표준) + 반려동물 등록 현황 + 보안등 정보 현황(제공표준) + 보안등 집계 현황
사용법:  GG_API_KEY=발급키 python collect_gg.py
결과:    data/cctv_clean.csv, data/pets.csv, data/lights.csv, data/lamp_types.csv, data/meta.json
키는 코드에 절대 넣지 말고 환경변수(로컬) 또는 GitHub Secret(자동화)으로만 전달합니다.
"""
import os, sys, csv, json, time
from datetime import datetime, timezone, timedelta
import requests

KEY = os.environ.get("GG_API_KEY")
if not KEY:
    sys.exit("GG_API_KEY 환경변수가 없습니다.")

BASE = "https://openapi.gg.go.kr/{svc}"
PSIZE = 1000          # 최대 1,000 (에러 336 방지)
KST = timezone(timedelta(hours=9))

def fetch_all(svc: str) -> list[dict]:
    """서비스명의 전체 row를 페이지네이션으로 수집"""
    rows, page = [], 1
    while True:
        r = requests.get(BASE.format(svc=svc),
                         params={"KEY": KEY, "Type": "json", "pIndex": page, "pSize": PSIZE},
                         timeout=60)
        r.raise_for_status()
        body = r.json()
        # 정상 응답: {"CCTV":[{"head":[{"list_total_count":N},{"RESULT":{"CODE":"INFO-000",...}}]},{"row":[...]}]}
        # 오류 응답: {"RESULT":{"CODE":"ERROR-290","MESSAGE":"..."}}
        if svc not in body:
            res = body.get("RESULT", {})
            if res.get("CODE") == "INFO-200":      # 더 이상 데이터 없음
                break
            sys.exit(f"[{svc}] API 오류: {res}")
        head, data = body[svc][0]["head"], body[svc][1].get("row", [])
        total = head[0]["list_total_count"]
        rows.extend(data)
        print(f"[{svc}] page {page}: {len(rows):,}/{total:,}")
        if len(rows) >= total or not data:
            break
        page += 1
        time.sleep(0.2)
    return rows

def num(v, default=0):
    try: return float(v)
    except (TypeError, ValueError): return default

def save_cctv(rows):
    keep = [r for r in rows if 33 <= num(r.get("REFINE_WGS84_LAT")) <= 39 and 124 <= num(r.get("REFINE_WGS84_LOGT")) <= 132]
    with open("data/cctv_clean.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mnginst_nm","refine_road_nm_addr","refine_lotno_addr","instl_purps_div","camera_vcnt",
                    "camera_pixel_cnt","potogrf_directn_info","custody_day_cnt","instl_ym","mnginst_telno",
                    "refine_wgs84_lat","refine_wgs84_logt","dat_crtr_ymd"])
        for r in keep:
            w.writerow([r.get("MANAGE_INST_NM"), r.get("REFINE_ROADNM_ADDR"), r.get("REFINE_LOTNO_ADDR"),
                        r.get("INSTL_PUPRS_DIV_NM"), r.get("CAMERA_CNT"), r.get("CAMERA_PIXEL_CNT"),
                        r.get("POTOGRF_DIRECTN_INFO"), r.get("CUSTODY_DAY_CNT"), r.get("INSTL_YM"),
                        r.get("MANAGE_INST_TELNO"), r.get("REFINE_WGS84_LAT"), r.get("REFINE_WGS84_LOGT"),
                        r.get("DATA_STD_DE")])
    return len(rows), len(keep)

def save_lights(rows):
    keep = [r for r in rows if 33 <= num(r.get("REFINE_WGS84_LAT")) <= 39 and 124 <= num(r.get("REFINE_WGS84_LOGT")) <= 132]
    with open("data/lights.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["addr","instl_cnt","lat","lon"])
        for r in keep:
            w.writerow([r.get("REFINE_LOTNO_ADDR") or r.get("REFINE_ROADNM_ADDR"), r.get("INSTL_CNT"),
                        r.get("REFINE_WGS84_LAT"), r.get("REFINE_WGS84_LOGT")])
    return len(rows), len(keep)

def save_lamp_types(rows):
    """경기도_보안등 집계 현황(Secrtlgt): 시군별 나트륨/메탈/LED 개소 (기준일이 시군마다 다름)"""
    agg={}
    for r in rows:
        s=r.get("SIGUN_NM"); d=agg.setdefault(s,{"sodium":0,"metal":0,"led":0,"date":r.get("DATA_STD_DE","")})
        for k,v in r.items():
            if k.startswith("NTRM_"): d["sodium"]+=num(v)
            elif k.startswith("MTAL_"): d["metal"]+=num(v)
            elif k.startswith("LED_"): d["led"]+=num(v)
    with open("data/lamp_types.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["sigun","sodium","metal","led","data_std_de","total"])
        for s,d in agg.items(): w.writerow([s,d["sodium"],d["metal"],d["led"],d["date"],d["sodium"]+d["metal"]+d["led"]])
    return len(rows)

def save_pets(rows):
    with open("data/pets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["std_yy","sigun_nm","sigun_cd","emd_nm","regist_animal_cnt","animal_owner_cnt","data_std_de"])
        for r in rows:
            w.writerow([r.get("STD_YY"), r.get("SIGUN_NM"), r.get("SIGUN_CD"), r.get("EMD_NM"),
                        r.get("REGIST_ANIMAL_CNT"), r.get("ANIMAL_OWNER_CNT"), r.get("DATA_STD_DE")])
    return len(rows)

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    cctv_total, cctv_kept = save_cctv(fetch_all("CCTV"))
    pets_total = save_pets(fetch_all("AnimalRegistStus"))
    light_total, light_kept = save_lights(fetch_all("SECRTLGT"))   # 보안등 정보 현황(제공표준), 약 30만 건 = 300페이지
    lamp_rows = save_lamp_types(fetch_all("Secrtlgt"))               # 보안등 집계 현황 (엔드포인트 대소문자 주의)
    meta = {"collected_at": datetime.now(KST).isoformat(timespec="seconds"),
            "cctv_rows": cctv_total, "cctv_valid_coord": cctv_kept, "pet_rows": pets_total,
            "light_rows": light_total, "light_valid_coord": light_kept, "lamp_type_rows": lamp_rows}
    json.dump(meta, open("data/meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(meta)
