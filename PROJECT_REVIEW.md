# 프로젝트 리뷰 — AI Books (현행)

> 기준: 2026-06-11 코드 기준. 상세는 [ARCHITECTURE.md](ARCHITECTURE.md) · [PIPELINE.md](PIPELINE.md) · [MOLD_DX_AGENT_DESIGN.md](MOLD_DX_AGENT_DESIGN.md).

## 1. 한 줄 요약
로컬 LLM(Ollama·gemma4:31b)으로 **문서 유형 무관(genre-agnostic)** 하게 글을 단위별로 생성하고, GitHub를 CMS 삼아 Next.js(Vercel)로 게시하는 파이프라인. 장르는 코드가 아니라 `toc/*.json`이 정하고, 실측 근거가 필요하면 선택 필드 `grounding`으로 주입한다.

## 2. 아키텍처 3계층
1. **입력** — `toc/*.json` 단일 스키마(`description`/`target_reader`/`writing_guidelines`/`units`/선택 `grounding`). `units`로 통일(옛 `chapters`/`sections` 폴백).
2. **grounding(선택·다형)** — `grounding.py`의 resolver(`mold_api`/`file`/`url`/`text`). 결과는 `cache/grounding/`에 스냅샷. `ref_keys`는 데이터에서 재귀 자동 추출(하드코딩 없음).
3. **생성 파이프라인** — (선택)Planner→Writer→Reviewer→Reviser→재검수. 판단/계획은 `call_structured`(Pydantic 스키마 강제 + self-heal), 생성은 `_call`(자유 마크다운).

## 3. 구현 완료 항목
- ✅ 장르 무관 `generate()` — 책·기술서·소설 한 파이프라인(`GENRES` 하드코딩 제거)
- ✅ **Pydantic 수렴 엔진** `call_structured` — 옛 `_parse_review` 정규식 대체
- ✅ **grounding 레이어** — 선택·다형·캐시·폴백(API 다운 시 엑셀)
- ✅ **digest(mold_api)** — summary·공정시간·상관·클러스터·운영모델 + 센서별 통계·사이클간격·대기분포·이상 카테고리(요약 압축, ~3.8k tokens)
- ✅ 환각 탐지 `ungrounded_numbers`, Planner `data_refs` 자동 검증
- ✅ GitHub 자동 푸시(units), 웹 `unit-NN.md` 인식 + meta 정규화

## 4. 산출물
- 📘 `파이썬으로 배우는 머신러닝` (15장, 완료)
- 📊 `금형 사출 데이터 해석 보고서` (9단위, 완료) — 517,130 사이클 실측 해석. **환각 수치 0건**, 섹션 검수 대부분 85~95.

## 5. 검증된 것
- 책 콘텐츠 프롬프트 바이트 동일(리팩터 회귀 0), 구조화 검수 실측 동작
- digest 실측 그라운딩(517,130 / 이상률 11.72% / CT 58.02초 등 정확 인용)
- 웹 라이브 표시(홈 카운트 + 상세 본문) 확인

## 6. 알려진 이슈 · 리스크
| 이슈 | 영향 | 상태/완화 |
| --- | --- | --- |
| **웹 코드 두 레포 분리** (`ai-books/web` 사본 ↔ 배포본 `ai-books-web`) | 모노레포만 고치면 배포 안 됨 | 현재 양쪽 동기화. **장기적으로 단일화 권장** |
| `:33001` API 간헐 다운(uvicorn 앱 전역 500) | digest 생성 실패 | 스냅샷 캐시 + 엑셀 폴백. 서버 측 재시작/로그 필요 |
| PAT 토큰이 git remote URL에 평문 노출 | 보안 | **토큰 교체 + credential helper 권장** |
| gemma4:31b 한국어 기술문서 품질 | 산출물 깊이 | 단계별 temperature, 필요 시 Writer 상위 모델 분리 |
| 생성 단위 제목 H1 중복(구버전 산출물 일부) | 경미 | 새 프롬프트 + `_strip_title_h1`로 해결 |

## 7. 권장 다음 단계
- 웹 두 레포 단일화(또는 Vercel을 `ai-books`의 `web/`로 재지정)
- README 자동 테이블과 수동 설명 공존(델리미터 블록)
- 소설/웹툰 등 신규 장르 toc 추가로 일반화 실검증
- (선택) 디지트 더 깊은 센서값 해석(uniformity 등) 확장
