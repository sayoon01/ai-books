"""
실측 통계 API 소스.

주의: keti-ev1:33001은 평문 HTTP만 제공한다(HTTPS 차단). httpx는 HTTP를
HTTPS로 강제 업그레이드하지 않으므로 그대로 호출 가능하다. 서버 가용성이
불안정하므로(간헐적 500) 엔드포인트별 실패를 허용하고 None으로 건너뛴다.
"""
import httpx

# digest에 필요한 엔드포인트만
ENDPOINTS = ["summary", "proc-stats", "correlation", "cluster-stats", "model-meta"]


class ApiSource:
    name = "api"

    def __init__(self, base: str = "http://keti-ev1.iptime.org:33001",
                 timeout: float = 10.0, retries: int = 2):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.retries = retries

    def _get(self, ep: str):
        url = f"{self.base}/api/{ep}"
        last = None
        for _ in range(self.retries + 1):
            try:
                r = httpx.get(url, timeout=self.timeout)  # 평문 HTTP 유지
                if r.status_code == 200:
                    return r.json()
                last = f"HTTP {r.status_code}"
            except Exception as e:  # noqa: BLE001 — 네트워크 오류 전부 폴백 대상
                last = str(e)
        print(f"  [api] /{ep} 실패: {last}")
        return None

    def fetch_all(self) -> dict:
        return {ep: self._get(ep) for ep in ENDPOINTS}
