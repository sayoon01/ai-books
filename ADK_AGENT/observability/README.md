# 관측(Observability) — Phoenix + Langfuse

ADK가 방출하는 OpenTelemetry trace를 받아 **챕터별 단계 타임라인(waterfall)·LLM 프롬프트/응답·토큰**을
대시보드로 본다. 두 백엔드를 **각각 독립적으로** 켤 수 있고, 둘 다 켜면 같은 trace가 양쪽에 동시에 들어간다(fan-out).

| 백엔드 | 성격 | 무게 | UI |
|--------|------|------|----|
| **Phoenix** | LLM 전용 관측, 단계 디버깅에 최적 | 가벼움(단일 컨테이너) | http://localhost:6006 |
| **Langfuse** | 제품급(세션·비용·여러 실행 누적) | 무거움(6개 컨테이너) | http://localhost:3000 |

> 트레이싱은 **기본 자동**이다. 아래 환경변수가 채워진(=쉘에 로드된) 백엔드로 생성 시 자동 전송한다.
> 둘 다 채우면 양쪽에 동시 전송(fan-out). env 를 로드 안 했으면 조용히 OFF — 평소처럼 `output/<slug>/`에
> 결과만 생성된다. 명시적으로 끄려면 `main.py --no-trace`.

---

## 0. 사전 준비 (앱 의존성)
```bash
# OTLP 익스포터 (이미 설치돼 있으면 건너뜀)
.venv/bin/pip install opentelemetry-exporter-otlp-proto-grpc opentelemetry-exporter-otlp-proto-http
```

## 1. 백엔드 띄우기

### Phoenix (권장 — 가볍고 빠름)
```bash
docker-compose -f observability/docker-compose.yml up -d
# UI: http://localhost:6006   (OTLP gRPC 4317 로 수신)
```

### Langfuse (선택 — 제품급, 무거움)
공식 self-host compose를 그대로 받아 둠(`observability/langfuse/docker-compose.yml`).
로컬 개발용 기본 비밀키가 들어 있어 그대로도 뜬다(운영은 `# CHANGEME` 표시된 값 교체 필수).
```bash
docker-compose -f observability/langfuse/docker-compose.yml up -d
# UI: http://localhost:3000  →  회원가입 → 프로젝트 생성
#     → Settings → API Keys → Public/Secret 키 발급
```

## 2. 환경변수 설정
```bash
cp observability/.env.example observability/.env
# .env 편집:
#  - Phoenix만 쓰면 LANGFUSE_* 비워둠
#  - Langfuse 쓰면 위에서 발급한 PUBLIC/SECRET 키를 채움
```
> `observability/.env` 는 `core/config.py` 가 실행 시 **자동 로드**한다 — `source` 안 해도 된다.

## 3. 생성 (트레이싱 자동)
```bash
.venv/bin/python main.py --toc toc/mold-dx-auto.json --no-push
```
실행 로그에 활성 백엔드가 찍힌다:
```
  [trace] Phoenix → http://localhost:4317
  [trace] Langfuse → http://localhost:3000/api/public/otel/v1/traces
  [trace] 활성 — 백엔드 2개
```

## 4. 보기
- **Phoenix** http://localhost:6006 → Traces. `chapter-N` span 아래 write/review/revise의 `call_llm` span,
  그래프 노드, 가드/게이트 함수 span이 시간순으로 보인다(프롬프트·응답·토큰 포함).
- **Langfuse** http://localhost:3000 → Tracing. 같은 실행이 trace로 쌓이고, 여러 실행을 누적 비교할 수 있다.

## 끄기
```bash
docker-compose -f observability/docker-compose.yml down                 # Phoenix (데이터 유지)
docker-compose -f observability/langfuse/docker-compose.yml down        # Langfuse
# 데이터까지 삭제하려면 끝에 -v
```

---

## 동작 원리 (요약)
- ADK 2.3.0은 LLM 호출·그래프 노드·도구 호출을 전역 OTel 트레이서로 이미 방출한다.
- `core/tracing.py: setup_tracing()`이 env를 보고 **전역 TracerProvider + 익스포터(들)**를 설치 → 그 span들이
  Phoenix/Langfuse로 흘러간다. `AutoTracingPlugin`을 붙여 우리 FunctionNode 내부까지 span으로 잡는다.
- 종료 시 `flush_tracing()`이 배치 버퍼를 비워 짧은 실행에서도 span 유실을 막는다.
