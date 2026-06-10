# AI Generated Books Web — 프로젝트 리뷰 & 설계 분석

> 원본 저장소: https://github.com/prof-lijar/ai-generated-books-web  
> 동반 데이터 저장소: https://github.com/prof-lijar/ai-generated-books  
> 작성일: 2026-06-10

---

## 1. 프로젝트 개요

이 프로젝트는 두 개의 GitHub 저장소로 분리된 **AI 책 생성 + 웹 열람 플랫폼**입니다.

| 저장소 | 역할 |
|---|---|
| `ai-generated-books` | AI가 생성한 책 원고(텍스트/마크다운)를 저장 |
| `ai-generated-books-web` | 웹에서 해당 콘텐츠를 탐색·열람하는 Next.js 앱 |

사용자는 웹 앱을 통해 AI가 밤새 생성한 책들을 브라우저에서 PDF로 읽고, 검색·필터링·다운로드할 수 있습니다.

---

## 2. 전체 아키텍처

```
[Ollama + Gemma 모델]
       │ 로컬에서 야간 실행
       ▼
[Python 책 생성 에이전트]
  outline → write → review → finalize
       │ 챕터 단위로 자동 커밋
       ▼
[GitHub: ai-generated-books 저장소]
  book-slug/
    chapter-01.md
    chapter-02.md
    ...
       │ GitHub REST API
       ▼
[Next.js 14 웹 앱 (Vercel 배포)]
  - 책 목록 탐색
  - 인브라우저 PDF 뷰어
  - 검색 / 필터링
  - 다운로드
```

---

## 3. 기술 스택 분석

### 3-1. 백엔드 / 콘텐츠 생성 (`ai-generated-books`)

| 항목 | 세부 내용 |
|---|---|
| LLM 런타임 | Ollama (완전 로컬 실행) |
| 사용 모델 | Gemma 4 31B |
| 생성 언어 | Python |
| 입력 | 목차(TOC) 파일 + 출력 디렉토리 지정 |
| 생성 단계 | 4단계: 개요 → 집필 → 검토 → 최종화 |
| 출력 형식 | Markdown 텍스트 파일 (챕터별) |
| 자동화 | 챕터 단위 GitHub 자동 커밋 |
| 도서 장르 | 기술서, 소설, 철학, 다국어(한국어·버마어·영어) |

**강점:**
- 완전 오프라인/로컬 실행으로 API 비용 없음
- 4단계 파이프라인으로 품질 향상 시도
- 챕터 단위 커밋으로 진행 상황 추적 용이

**약점:**
- Gemma 31B를 로컬 실행하려면 고사양 GPU 필요
- 생성 속도가 느려 "야간 실행" 전략에 의존
- 검토(review) 단계가 동일 모델에 의해 수행 → 자기 검증 한계
- 출력이 마크다운이지만 웹 앱은 PDF로 제공 → 변환 파이프라인이 불명확

### 3-2. 프론트엔드 웹 앱 (`ai-generated-books-web`)

| 항목 | 세부 내용 |
|---|---|
| 프레임워크 | Next.js 14 (App Router) |
| 언어 | TypeScript |
| 스타일링 | Tailwind CSS |
| 데이터 소스 | GitHub REST API |
| 배포 | Vercel |
| 테스트 | Vitest (유닛) + Playwright (E2E) |

**강점:**
- Next.js App Router 사용으로 서버 컴포넌트 최적화 가능
- Vercel 배포로 CI/CD 자동화
- Playwright E2E 테스트 포함 (테스트 커버리지 의식)
- 별도 백엔드 서버 없이 GitHub API만으로 데이터 소비

**약점:**
- **GitHub API Rate Limit 의존성**: 토큰 없이는 분당 60회 제한 → 트래픽 증가 시 장애 발생
- 데이터 소스가 GitHub에 고정되어 있어 유연성 부족
- PDF 뷰어가 어떻게 구현되었는지 명확하지 않음 (마크다운→PDF 변환 위치 불명)
- `.env.example`만 있고 실제 환경 설정 문서가 부족

---

## 4. 데이터 흐름 상세

```
1. 생성 단계
   Python 스크립트 실행
     → LLM에 목차 전달
     → 챕터별 outline 생성
     → 각 챕터 본문 작성 (write)
     → 같은 LLM으로 self-review
     → 최종 파일 저장
     → git add & commit & push (자동)

2. 소비 단계
   Next.js 서버 컴포넌트
     → GitHub REST API 호출 (저장소 파일 목록 조회)
     → 클라이언트에 책 목록 렌더링
     → 사용자가 책 선택 시 파일 내용 fetch
     → PDF 변환 후 인브라우저 렌더링
```

---

## 5. 구조적 장단점 요약

### 잘된 점

1. **관심사 분리**: 생성(content) 저장소와 웹(display) 저장소를 분리해 각각 독립 발전 가능
2. **GitOps 패턴**: GitHub를 CMS처럼 사용, 별도 DB 불필요
3. **오픈소스 LLM**: Ollama + Gemma로 비용 없이 무제한 생성
4. **다국어 지원**: 한국어·버마어·영어 책 포함

### 개선이 필요한 점

1. **GitHub API 단일 의존점**: 캐싱 레이어(Redis, CDN) 없이 API 직접 호출
2. **변환 파이프라인 불투명**: MD → PDF 변환이 어디서 어떻게 이루어지는지 문서화 부족
3. **생성 품질 제어 미흡**: 동일 모델의 self-review는 편향 검증에 한계
4. **확장성**: 책이 수천 권이 되면 GitHub API 기반 조회 방식은 성능 저하
5. **메타데이터 구조화 부족**: 장르·언어·난이도 등 풍부한 메타데이터 스키마 없음

---

## 6. 우리 프로젝트에 적용할 시사점

이 레퍼런스 프로젝트를 기반으로 더 나은 AI 책 생성 플랫폼을 만들기 위한 개선 방향:

### 6-1. 생성 파이프라인 개선안

```
현재 (레퍼런스)          →    개선안
────────────────────────────────────────────────────────
단일 LLM (Gemma 31B)    →    Claude API + 검증 에이전트 분리
self-review             →    별도 critic 모델로 교차 검증
마크다운 파일 저장       →    구조화된 DB (PostgreSQL / Supabase)
야간 배치 실행           →    API 요청 기반 온디맨드 생성
```

### 6-2. 웹 앱 개선안

```
현재 (레퍼런스)          →    개선안
────────────────────────────────────────────────────────
GitHub API 직접 호출    →    자체 API + 캐싱 레이어
PDF 뷰어               →    마크다운 렌더링 (react-markdown) or PDF
GitHub 저장소 의존      →    자체 스토리지 (S3 / Supabase Storage)
정적 필터링             →    벡터 검색 (의미 기반 추천)
```

### 6-3. 권장 기술 스택 (우리 프로젝트)

| 레이어 | 기술 선택 |
|---|---|
| LLM | Claude API (claude-sonnet-4-6 / claude-opus-4-8) |
| 백엔드 | Next.js API Routes 또는 FastAPI |
| DB | Supabase (PostgreSQL + 파일 스토리지) |
| 웹 | Next.js 14 + Tailwind + shadcn/ui |
| 검색 | pgvector 또는 Supabase Vector |
| 배포 | Vercel (프론트) + Railway/Fly.io (백엔드) |

---

## 7. 레퍼런스 저장소 파일 구조 (추정)

```
ai-generated-books-web/
├── src/
│   ├── app/                  # Next.js App Router
│   │   ├── page.tsx          # 홈 (책 목록)
│   │   ├── books/[slug]/     # 개별 책 페이지
│   │   └── layout.tsx        # 공통 레이아웃
│   ├── components/           # 재사용 UI 컴포넌트
│   └── lib/                  # GitHub API 유틸리티
├── docs/                     # 문서
├── tests/                    # Vitest 유닛 테스트
├── playwright-report/        # E2E 테스트 결과
├── .env.example              # 환경변수 템플릿 (GITHUB_TOKEN)
├── next.config.mjs
├── tailwind.config.ts
├── vitest.config.ts
└── work_plan.json            # 프로젝트 계획서

ai-generated-books/
├── {book-slug}/
│   ├── chapter-01.md
│   ├── chapter-02.md
│   └── ...
├── README.md                 # 책 목록 테이블
└── (Python 생성 스크립트)
```

---

## 8. 총평

**레퍼런스 프로젝트 점수: 6.5 / 10**

- 아이디어와 오픈소스 기술 조합은 훌륭함
- 실제 프로덕션 사용보다는 개인 실험/포트폴리오 수준
- GitHub API 단일 의존, 변환 파이프라인 불투명, 품질 제어 부재가 주요 약점
- 이 프로젝트를 기반으로 Claude API + 구조화된 DB + 캐싱을 더하면 상업적 수준으로 발전 가능

우리 프로젝트는 이 레퍼런스의 "GitOps as CMS" 발상은 유지하되, 생성 품질·확장성·사용자 경험 측면에서 한 단계 위를 목표로 하면 충분히 차별화된 제품이 될 수 있습니다.
