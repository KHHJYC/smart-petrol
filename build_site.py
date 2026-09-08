"""data/cctv_clean.csv (+ data/pets.csv, data/lights.csv) → docs/data/data.js  (map.html·index.html 이 읽는 데이터)
취약도: 도심(주변 24격자 중 12개↑ CCTV 존재) 내 카메라 0~3대 격자.  우선순위: 취약도 × 반려견 등록 밀도.
"""
import os, re, json
import pandas as pd, numpy as np
from scipy.spatial import cKDTree

CL, CN = 0.0045, 0.0055   # 500m 격자
os.makedirs("docs", exist_ok=True)

df = pd.read_csv("data/cctv_clean.csv", dtype=str)
df["cam"] = pd.to_numeric(df["camera_vcnt"], errors="coerce").fillna(1).clip(lower=1).astype(int)
df["lat"] = pd.to_numeric(df["refine_wgs84_lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["refine_wgs84_logt"], errors="coerce")
df = df.dropna(subset=["lat","lon"])
df["addr"] = df["refine_lotno_addr"].fillna(df["refine_road_nm_addr"]).fillna("")

def parse_addr(a):
    p = str(a).split(); sgg, dong = "미상", "미상"
    if len(p) >= 2: sgg = p[1]
    if len(p) >= 3:
        if p[2].endswith("구") and len(p) >= 4: sgg, dong = p[1]+" "+p[2], p[3]
        else: dong = p[2]
    dong = re.sub(r"^(.+?(?:동|리|읍|면|가))\d.*$", r"\1", dong)   # 산본동1212-1 → 산본동
    return sgg, dong
pa = df["addr"].map(parse_addr); df["sgg"] = [x[0] for x in pa]; df["dong"] = [x[1] for x in pa]
df["sigun"] = df["sgg"].str.split().str[0]
purposes = list(df["instl_purps_div"].fillna("기타").value_counts().index)
df["p"] = df["instl_purps_div"].fillna("기타").map({p:i for i,p in enumerate(purposes)})

# ---- 반려동물 등록 현황 (있으면 결합) ----
pets = None
if os.path.exists("data/pets.csv"):
    pets = pd.read_csv("data/pets.csv", dtype=str)
    pets["n"] = pd.to_numeric(pets["regist_animal_cnt"], errors="coerce").fillna(0)
    pets = pets.sort_values("std_yy").groupby(["sigun_nm","emd_nm"], as_index=False).tail(1)   # 읍면동별 최신 연도 (연도별 등록 범위가 달라 전체 최신연도 필터는 부적절)
    norm = lambda s: re.sub(r"제?\d+", "", str(s)).strip()          # 정자1동→정자동
    pets["key"] = pets["sigun_nm"].str.strip() + "|" + pets["emd_nm"].map(norm)
    pet_dong = pets.groupby("key")["n"].sum().to_dict()
    pet_sigun = pets.groupby("sigun_nm")["n"].sum().to_dict()
    print("반려동물 결합: 읍면동", len(pet_dong), "시군", len(pet_sigun))
def pets_for(sigun, dong):
    if pets is None: return None, "none"
    k = sigun + "|" + re.sub(r"제?\d+", "", dong)
    if k in pet_dong: return int(pet_dong[k]), "dong"
    if sigun in pet_sigun: return int(pet_sigun[sigun]), "sigun"
    return None, "none"

# ---- 보안등 정보 현황 (있으면 결합) ----
lights = None
if os.path.exists("data/lights.csv"):
    lights = pd.read_csv("data/lights.csv", dtype=str)
    lights["lat"]=pd.to_numeric(lights["lat"],errors="coerce"); lights["lon"]=pd.to_numeric(lights["lon"],errors="coerce")
    lights["n"]=pd.to_numeric(lights["instl_cnt"],errors="coerce").fillna(1).clip(lower=1)
    lights=lights.dropna(subset=["lat","lon"])
    lights["gy"]=np.floor(lights["lat"]/CL).astype(int); lights["gx"]=np.floor(lights["lon"]/CN).astype(int)
    lights["sigun"]=lights["addr"].astype(str).str.split().str[1].str.replace(r"\?.*$","",regex=True)
    light_grid = lights.groupby(["gy","gx"])["n"].sum().to_dict()
    light_sigun = lights.groupby("sigun")["n"].sum().to_dict()
    print("보안등 결합:", len(lights), "건, 격자", len(light_grid))

# ---- 격자 & 취약도 ----
s = df[df["instl_purps_div"].isin(["생활방범","다목적","어린이보호","차량방범"])].copy()
s["gy"] = np.floor(s["lat"]/CL).astype(int); s["gx"] = np.floor(s["lon"]/CN).astype(int)
grid = {k:int(v) for k,v in s.groupby(["gy","gx"])["cam"].sum().items()}
cand = {(y+dy,x+dx) for (y,x) in grid for dy in range(-2,3) for dx in range(-2,3)}
rows = []
for (y,x) in cand:
    nb = np.array([grid.get((y+dy,x+dx),0) for dy in range(-2,3) for dx in range(-2,3) if (dy,dx)!=(0,0)])
    rows.append((y,x,grid.get((y,x),0),nb.mean(),(nb>0).sum()))
G = pd.DataFrame(rows, columns=["gy","gx","own","nbr_mean","nbr_active"])
G = G[(G.nbr_active>=12)&(G.own<=3)]
G["score"] = (G.nbr_mean-G.own).clip(lower=0)*(G.nbr_active/24)
G = G[G.score>0].copy(); G["lat"]=(G.gy+.5)*CL; G["lon"]=(G.gx+.5)*CN
tree = cKDTree(np.c_[s["lat"]*111000, s["lon"]*88800])
d,i = tree.query(np.c_[G["lat"]*111000, G["lon"]*88800])
G["near_m"]=d.round().astype(int); G["sgg"]=s["sgg"].values[i]; G["dong"]=s["dong"].values[i]; G["addr"]=s["addr"].values[i]
G["sigun"]=G["sgg"].str.split().str[0]
G["score100"]=(100*G["score"]/G["score"].max()).round(1)

# 보안등: 격자 내 설치수 + 시군별 자료 신뢰도(시군 보안등 수 / 시군 CCTV 활성격자 수 < 12 이면 자료 미비로 간주)
if lights is not None:
    cells_per_sigun = s.groupby("sigun").apply(lambda t: len(set(zip(t.gy,t.gx)))).to_dict()
    ok_sigun = {k for k,v in light_sigun.items() if v/max(cells_per_sigun.get(k,1),1) >= 12}   # 안양·평택·파주는 보안등 자료가 부분 등록으로 보여 제외(자료 없음 처리)
    G["lights"]=[ (int(light_grid.get((y,x),0)) if sg in ok_sigun else None) for y,x,sg in zip(G.gy,G.gx,G.sigun) ]
    cell_sigun = s.groupby(["gy","gx"])["sigun"].first().to_dict()
    med = np.median([light_grid.get(k,0) for k,sg in cell_sigun.items() if sg in ok_sigun]) if ok_sigun else 15
    LCAP = max(float(med),5.0)
    G["dark"]=[ (1-min(l/LCAP,1)) if l is not None else np.nan for l in G["lights"] ]
    print("보안등 신뢰 시군", len(ok_sigun), "/ 격자 기준 보안등 중앙값", LCAP)
else:
    G["lights"]=None; G["dark"]=np.nan

# 반려견 밀도 지수: 읍면동 등록수 / 그 읍면동의 CCTV 활성 격자 수 (≈ 정주지 면적 보정)
cells_per_dong = s.groupby(["sigun","dong"]).apply(lambda t: len(set(zip(t.gy,t.gx)))).to_dict()
pv, lvl = zip(*[pets_for(a,b) for a,b in zip(G["sigun"],G["dong"])]) if len(G) else ([],[])
G["pets"]=pv; G["pets_lvl"]=lvl
cells_per_sigun_all = s.groupby("sigun").apply(lambda t: len(set(zip(t.gy,t.gx)))).to_dict()
G["pet_idx"]=[ (p/max(cells_per_dong.get((a,b),1),1) if lv=="dong" else p/max(cells_per_sigun_all.get(a,1),1)) if p is not None else np.nan
               for p,a,b,lv in zip(G["pets"],G["sigun"],G["dong"],G["pets_lvl"]) ]
# 살펴볼 곳 우선순위 = CCTV 공백 60% + 보안등 공백 40%  (반려견 등록은 순찰대 모집 지역 검토용 보조 지표 — 점수에 넣지 않음)
parts=[("score",G["score100"]/100,.6)]
if G["dark"].notna().any():
    parts.append(("dark",G["dark"].fillna(G["dark"].median()),.4))
wsum=sum(w for _,_,w in parts)
G["prio"]=(100*sum(v*w for _,v,w in parts)/wsum).round(1)
G = G.sort_values("prio", ascending=False).head(4000)
print("취약지점", len(G))

VUL=[[round(r.lat,5),round(r.lon,5),r.score100,int(r.own),round(r.nbr_mean,1),int(r.near_m),r.sgg,r.dong,r.addr,
      (int(r.pets) if r.pets==r.pets and r.pets is not None else None), r.pets_lvl, float(r.prio), (int(r.lights) if r.lights==r.lights and r.lights is not None else None)] for r in G.itertuples()]
PTS=[[round(r.lat,5),round(r.lon,5),int(r.p),int(r.cam)] for r in df.itertuples()]
dg=df.groupby(["sgg","dong"]).agg(lat=("lat","mean"),lon=("lon","mean"),n=("cam","count"),cam=("cam","sum")).reset_index()
vg=G.groupby(["sgg","dong"]).size().rename("v").reset_index(); dg=dg.merge(vg,how="left").fillna({"v":0})
dg=dg[(dg.sgg!="미상")&(dg.dong!="미상")]
DONG=[[r.sgg,r.dong,round(r.lat,5),round(r.lon,5),int(r.n),int(r.cam),int(r.v),pets_for(r.sgg.split()[0],r.dong)[0]] for r in dg.itertuples()]
sg=df.groupby("sgg").agg(lat=("lat","mean"),lon=("lon","mean"),n=("cam","count"),cam=("cam","sum")).reset_index()
sv=G.groupby("sgg").size().rename("v").reset_index(); sg=sg.merge(sv,how="left").fillna({"v":0}); sg=sg[sg.sgg!="미상"]
SGG=[[r.sgg,round(r.lat,5),round(r.lon,5),int(r.n),int(r.cam),int(r.v),(int(pet_sigun.get(r.sgg.split()[0],0)) if pets is not None else None)] for r in sg.itertuples()]
h=s.groupby(["gy","gx"])["cam"].sum().reset_index(); cap=h["cam"].quantile(.95)
HEAT=[[round((r.gy+.5)*CL,5),round((r.gx+.5)*CN,5),round(min(r.cam,cap)/cap,3)] for r in h.itertuples()]

meta = json.load(open("data/meta.json",encoding="utf-8")) if os.path.exists("data/meta.json") else {}
os.makedirs("docs/data", exist_ok=True)
J=lambda v: json.dumps(v,ensure_ascii=False,separators=(",",":"))
# 랜딩용 요약 통계
pet_total = int(pets["n"].sum()) if pets is not None else None
dark_cells = int((G["lights"].fillna(-1)==0).sum()) if lights is not None else None
top10 = [[r.sgg,r.dong,float(r.prio),float(r.score100),(int(r.lights) if r.lights==r.lights and r.lights is not None else None),(int(r.pets) if r.pets==r.pets and r.pets is not None else None),round(r.lat,5),round(r.lon,5)] for r in G.head(10).itertuples()]
by_sigun = G.groupby("sigun").agg(n=("prio","size"),top=("prio","max")).reset_index().sort_values("n",ascending=False)
sig_rank = [[r.sigun,int(r.n),float(r.top)] for r in by_sigun.head(12).itertuples()]
# 순찰대 모집 검토 지역: 살펴볼 곳이 있는 읍면동 중 반려견 등록이 많은 순
rec = G.groupby(["sgg","dong","sigun"]).agg(cells=("prio","size"),top=("prio","max")).reset_index()
rec["pets"]=[pets_for(a,b)[0] for a,b in zip(rec.sigun,rec.dong)]; rec["lvl"]=[pets_for(a,b)[1] for a,b in zip(rec.sigun,rec.dong)]
rec=rec[rec.lvl=="dong"].dropna(subset=["pets"]).sort_values(["pets","cells"],ascending=False).head(15)
RECRUIT=[[r.sgg,r.dong,int(r.pets),int(r.cells),float(r.top)] for r in rec.itertuples()]
# 보안등 집계(조명기기 종류) — 시군 단위, 점수 미반영 보조자료. 기준일 2020년 이전이면 stale
LAMP=[]
if os.path.exists("data/lamp_types.csv"):
    lt=pd.read_csv("data/lamp_types.csv",dtype=str)
    for c in ["sodium","metal","led","total"]: lt[c]=pd.to_numeric(lt[c],errors="coerce").fillna(0)
    lt=lt[lt.total>0]
    LAMP=[[r.sigun,int(r.total),round(100*r.led/r.total,1),round(100*(r.sodium+r.metal)/r.total,1),(str(r.data_std_de)[:4] if r.data_std_de==r.data_std_de else ""),
           bool(r.data_std_de==r.data_std_de and str(r.data_std_de)[:4]>="2020")] for r in lt.itertuples()]
    LAMP.sort(key=lambda r:r[2])
STATS={"lamp":LAMP,"recruit":RECRUIT,"cctv":len(PTS),"cameras":int(df["cam"].sum()),"vul":len(VUL),"vul_high":int((G["prio"]>=60).sum()),
       "lights":(int(lights["n"].sum()) if lights is not None else None),"dark_cells":dark_cells,"pets":pet_total,
       "dong":len(DONG),"sgg":len(SGG),"top10":top10,"sig_rank":sig_rank,
       "src":{"cctv":str(df["dat_crtr_ymd"].dropna().max())[:8],"lights":"20240322","pets":(str(pets["data_std_de"].dropna().max())[:8] if pets is not None else "")}}
META={"updated":meta.get("collected_at","")[:10] or __import__("datetime").date.today().isoformat(),"pets":pets is not None,"lights":lights is not None}
with open("docs/data/data.js","w",encoding="utf-8") as f:
    f.write("// 자동 생성 파일 — build_site.py. 수정하지 마세요.\n")
    for k,v in [("PURPOSES",purposes),("PTS",PTS),("VUL",VUL),("DONG",DONG),("SGG",SGG),("HEAT",HEAT),("META",META),("STATS",STATS)]:
        f.write(f"const {k}={J(v)};\n")
print("docs/data/data.js", round(os.path.getsize("docs/data/data.js")/1e6,2),"MB")
print("STATS:", {k:v for k,v in STATS.items() if k not in ("top10","sig_rank")})
for t in top10: print(" ",t)
