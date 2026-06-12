# AI Books

로컬 LLM(Ollama · gemma4:31b)으로 **문서 유형 무관**하게 글을 작성 단위별로 생성하고, GitHub를 CMS 삼아 Next.js(Vercel)로 게시하는 파이프라인.

장르(책·기술서·소설 등)는 코드가 아니라 **`toc/*.json`** 이 정하고, 실측 근거가 필요하면 선택 필드 **`grounding`** 으로 파일/링크/API의 사실을 주입한다(없으면 모델 지식).

## 사용법
```bash
# 책 (grounding 없음)
python generator/main.py --toc toc/python-ml.json

# 데이터 해석 보고서 (grounding 자동 + Planner)
python generator/main.py --toc toc/mold-dx-report.json --planner

# grounding 스냅샷 수동 재생성
cd generator && python -m digest.build --force
```

## 구조
- `generator/` — 생성 파이프라인 (`main`·`book_writer`·`prompts`·`llm`·`schemas`·`grounding`·`digest/`·`github_push`)
- `toc/` — 문서 정의(JSON, 모든 장르) · `data/` — grounding 원본 · `cache/` — 근거 스냅샷
- `web/` — Next.js 프론트엔드 **(참고용 사본)**. 실제 배포본은 별도 레포 **`sayoon01/ai-books-web`** (콘텐츠는 이 레포에서 API로 읽음 → 웹 코드 수정은 `ai-books-web`에 반영해야 배포됨)

## 문서
- [ARCHITECTURE.md](ARCHITECTURE.md) — 전체 아키텍처
- [PIPELINE.md](PIPELINE.md) — 단위 생성 파이프라인 상세
- [MOLD_DX_AGENT_DESIGN.md](MOLD_DX_AGENT_DESIGN.md) — 금형 DX 해석 보고서 설계
- [PROJECT_REVIEW.md](PROJECT_REVIEW.md) — 현행 프로젝트 리뷰

## 생성된 문서
<!-- 아래 블록은 generator가 자동 갱신(github_push.update_readme). 이 줄과 위 설명은 보존됨. -->

<!-- DOCS:START -->

| 제목 | 언어 | 진행 | 모델 | 상태 |
|---|---|---|---|---|
| [금형 사출 데이터 해석 보고서](./금형-사출-데이터-해석-보고서) | ko | 9/9 | gemma4:31b | ✅ 완료 |
| [금형 사출 데이터 기반 분석 시스템 기술분석서](./금형-사출-데이터-기반-분석-시스템-기술분석서) | ko | 4/4 | gemma4:31b | ✅ 완료 |
| [파이썬으로 배우는 머신러닝](./파이썬으로-배우는-머신러닝) | ko | 15/15 | gemma4:31b | ✅ 완료 |

<!-- DOCS:END -->
