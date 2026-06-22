"""
관측(OpenTelemetry) 셋업 — ADK 내장 span을 Phoenix / Langfuse 로 fan-out.

ADK 2.3.0 은 LLM 호출·그래프 노드·도구 호출을 전역 OTel 트레이서(google.adk.telemetry.tracer)로
이미 방출한다. 여기서는 전역 TracerProvider 에 익스포터(들)를 달아 그 span 을 실제 백엔드로 보낸다.

설계:
- 기본 OFF. 환경변수가 있는 백엔드만 활성화 → 아무 변수도 없으면 setup_tracing()은 False 반환(무동작).
- 같은 trace 를 여러 백엔드에 동시 전송(fan-out): 각 백엔드마다 BatchSpanProcessor 를 add.
- 모든 OTel import 는 함수 안에서 지연 import(미설치 환경 보호 — core/llm.make_gemma 와 같은 원칙).

환경변수:
  Phoenix   : PHOENIX_OTLP_ENDPOINT            (예: http://localhost:4317, gRPC)
  Langfuse  : LANGFUSE_OTLP_ENDPOINT           (예: http://localhost:3000/api/public/otel, HTTP)
              LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY   (Basic 인증)
"""
import base64
import os

_provider = None        # 설치한 TracerProvider 보관(flush 용)


def _phoenix_processor():
    """PHOENIX_OTLP_ENDPOINT 있으면 gRPC OTLP BatchSpanProcessor 반환, 없으면 None."""
    endpoint = os.getenv("PHOENIX_OTLP_ENDPOINT")
    if not endpoint:
        return None
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    # gRPC OTLP. 로컬 평문이면 insecure=True.
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=endpoint.startswith("http://"))
    print(f"  [trace] Phoenix → {endpoint}")
    return BatchSpanProcessor(exporter)


def _langfuse_processor():
    """LANGFUSE_OTLP_ENDPOINT + 키 있으면 HTTP OTLP BatchSpanProcessor 반환, 없으면 None."""
    endpoint = os.getenv("LANGFUSE_OTLP_ENDPOINT")
    pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    sec = os.getenv("LANGFUSE_SECRET_KEY")
    if not (endpoint and pub and sec):
        return None
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    auth = base64.b64encode(f"{pub}:{sec}".encode()).decode()
    # Langfuse 는 traces 를 <endpoint>/v1/traces 로 받는다. 끝 슬래시 정리.
    traces_url = endpoint.rstrip("/") + "/v1/traces"
    exporter = OTLPSpanExporter(endpoint=traces_url,
                                headers={"Authorization": f"Basic {auth}"})
    print(f"  [trace] Langfuse → {traces_url}")
    return BatchSpanProcessor(exporter)


def setup_tracing(service_name: str = "adk-book", run_name: str | None = None) -> bool:
    """환경변수를 보고 전역 TracerProvider + 익스포터(들)를 설치.

    활성 익스포터가 하나라도 있으면 True, 없으면(=OFF) False.
    OTel 미설치/익스포터 미설치면 경고 후 False(크래시 X).
    """
    global _provider
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
    except ImportError as e:
        print(f"  [trace] opentelemetry-sdk 미설치 — 트레이싱 건너뜀 ({e})")
        return False

    processors = []
    for make in (_phoenix_processor, _langfuse_processor):
        try:
            p = make()
            if p is not None:
                processors.append(p)
        except ImportError as e:
            print(f"  [trace] 익스포터 미설치 — 건너뜀 ({e})")

    if not processors:
        # 백엔드 env 가 하나도 없으면 조용히 OFF(기본 실행을 시끄럽게 하지 않음).
        return False

    attrs = {"service.name": service_name}
    if run_name:
        attrs["run.name"] = run_name
    provider = TracerProvider(resource=Resource.create(attrs))
    for p in processors:
        provider.add_span_processor(p)
    trace.set_tracer_provider(provider)
    _provider = provider
    print(f"  [trace] 활성 — 백엔드 {len(processors)}개")
    return True


def flush_tracing() -> None:
    """종료 시 BatchSpanProcessor 잔여 span 을 강제 방출(짧은 실행에서 유실 방지)."""
    global _provider
    if _provider is None:
        return
    try:
        _provider.force_flush()
        _provider.shutdown()
    except Exception as e:
        print(f"  [trace] flush 실패(무시): {e}")
    finally:
        _provider = None
