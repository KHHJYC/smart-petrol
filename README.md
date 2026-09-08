# 스마트 펫트롤 · 우리동네 안전지킴이

반려견 산책 중 발견한 시설 문제를 **기록 → 확인 → 안심지도 반영**하는 자원봉사 플랫폼.
공공데이터(CCTV·보안등)는 "먼저 살펴볼 곳"을 고르는 기초자료, 반려동물 등록 현황은 순찰대 모집 지역 검토용 보조자료.

```
docs/index.html            랜딩 (문제 → 활동 → 살펴볼 곳 → 모집 지역 → 조명 노후도 → 기대효과 → 데이터)
docs/map.html              안심지도: 동네 검색, 살펴볼 곳, 현장 제보(이슈), 순찰 목록·일지
docs/config.js             repo:"계정/저장소" 한 줄 → 제보 버튼 활성화
docs/data/data.js          공공데이터 결합 결과 (build_site.py 생성)
docs/data/reports.js       제보 이슈 요약 (fetch_reports.py 생성)
collect_gg.py              경기데이터드림 API 4종 수집(CCTV·보안등 위치·보안등 집계·반려동물) (키: 환경변수 GG_API_KEY)
build_site.py              취약도·보안등·반려견 결합
fetch_reports.py           GitHub Issues(라벨 제보) → reports.js  (Actions 기본 토큰 사용)
.github/ISSUE_TEMPLATE/report.yml   제보 양식 (위치·유형·설명·사진)
.github/workflows/collect.yml       매일 04:30 KST 수집 + 이슈 변경 시 즉시 반영
```

## 제보 처리 흐름
1. 안심지도에서 "이 위치 제보하기" → 좌표가 채워진 이슈 양식이 열림 → 사진 끌어넣고 제출
2. 다른 대원이 재확인하면 이슈에 라벨 **확인됨**
3. 지자체 조치 확인 후 이슈 **닫기** → 조치완료
4. 각 단계마다 Actions가 돌아 지도 마커 색이 바뀜 (접수 빨강 · 확인 노랑 · 조치 청록)

## 처음 한 번만
1. Settings › Secrets and variables › Actions › New repository secret: `GG_API_KEY` = 경기데이터드림 인증키
2. Settings › Pages › Deploy from a branch › main › /docs
3. Issues 탭 › Labels 에 `제보`, `확인됨`, `순찰일지` 라벨 생성
4. Actions › "데이터 수집·제보 반영·배포" › Run workflow 1회
5. 접속: https://khhjyc.github.io/smart-petrol/

## 로컬 실행
```
export GG_API_KEY=인증키      # Windows: set GG_API_KEY=인증키
python collect_gg.py && python build_site.py
```
