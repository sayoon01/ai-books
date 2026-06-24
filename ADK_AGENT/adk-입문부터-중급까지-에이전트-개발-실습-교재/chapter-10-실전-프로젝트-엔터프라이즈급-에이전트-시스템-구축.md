# 10. 실전 프로젝트: 엔터프라이즈급 에이전트 시스템 구축

## 10. 실전 프로젝트: 엔터프라이즈급 에이전트 시스템 구축

지금까지 우리는 에이전트의 기본 구성 요소부터 멀티 에이전트의 오케스트레이션, 그리고 그래프 기반의 아키텍처까지 학습했습니다. 마지막 챕터에서는 이 모든 조각을 하나로 합쳐, 실제 기업 환경에서 사용할 수 있는 **'엔터프라이즈급 기술 지원 시스템'**을 구축해 보겠습니다.

---

## 1. 쉬운 비유: 회사의 전문 부서 운영 방식

혼자서 모든 일을 처리하는 '만능 직원'은 처음에는 효율적으로 보이지만, 업무가 복잡해지면 금방 한계에 부딪힙니다. 기억력에 의존하다 보니 중요한 내용을 까먹거나(컨텍스트 소실), 전문 지식이 없는 분야에서도 아는 척을 하는(환각 현상) 문제가 발생합니다.

**엔터프라이즈급 시스템**은 이를 '회사 조직'처럼 운영하는 것입니다.
- **안내 데스크(Router):** 고객의 요청을 듣고 어떤 부서로 보낼지 결정합니다.
- **CS 팀(Support Agent):** 일반적인 질문에 답하며, 회사 매뉴얼을 참고합니다.
- **기술 전문 팀(Technical Agent):** 복잡한 로그 분석이나 심층 기술 문제를 해결합니다.
- **공용 문서 보관함(Artifacts):** 수백 페이지의 매뉴얼을 다 읽지 않고, 필요한 부분만 꺼내 봅니다.
- **업무 시스템(Tools):** 최종 해결이 안 되면 티켓 시스템에 접수하여 사람이 개입하게 합니다.

이렇게 역할을 나누고 체계적인 프로세스(Graph)를 정의하면, 비용은 최적화되면서 결과물의 품질과 예측 가능성은 비약적으로 상승합니다.

---

## 2. ADK 개념 및 용어 (ADK Concepts & Terms)

실전 프로젝트를 위해 반드시 숙지해야 할 ADK의 핵심 엔터프라이즈 개념입니다.

- **구조적 컨텍스트 관리 (Structural Context Management):** 단순한 대화 기록의 나열이 아니라, 세션(Session), 메모리(Memory), 도구 출력(Tool Output), 아티팩트(Artifact)를 구분하여 관리하는 방식입니다. 이를 통해 불필요한 토큰 낭비를 막고 모델이 현재 상황을 정확히 인지하게 합니다.
- **그래프 기반 아키텍처 (Graph-based Architecture):** 결정론적 경로(Deterministic Path, 예: A 다음엔 무조건 B)와 적응형 추론(Adaptive Reasoning, 예: AI가 판단하여 A 또는 C 선택)을 결합하여 전체 워크플로우를 설계하는 방식입니다.
- **아티팩트 지연 로딩 (Artifact Lazy-loading):** 대용량 데이터를 에이전트에게 미리 다 주는 것이 아니라, 에이전트가 "그 문서의 내용을 확인하겠다"라고 요청할 때만 컨텍스트에 삽입하여 토큰 효율성을 극대화하는 기법입니다.
- **프로덕션 배포 (Production Deployment):** 개발 환경을 넘어 Google Cloud(Cloud Run, GKE) 및 Agent Runtime을 통해 컨테이너화된 에이전트를 실제 서비스 환경에 배포하고 관리하는 과정입니다.

---

## 3. '왜/언제' 사용하는가? (Justification)

단순한 챗봇이 아니라 **엔터프라이즈급 멀티 에이전트 시스템**이 필요한 이유는 다음과 같습니다.

1. **토큰 비용 및 성능 최적화:** 모든 요청에 가장 비싼 모델을 쓰거나 모든 매뉴얼을 컨텍스트에 넣는 것은 비용 낭비입니다. Router가 요청의 난이도를 판단해 적절한 에이전트와 모델을 배정함으로써 비용을 절감합니다.
2. **예측 가능성 확보:** AI에게 모든 것을 맡기면 실행 경로가 매번 달라집니다. 그래프 아키텍처를 통해 "기술 문의 → 로그 분석 → 티켓 생성"이라는 비즈니스 프로세스를 강제함으로써 운영 안정성을 확보합니다.
3. **데이터 격리 및 보안:** 일반 상담원은 접근해서는 안 될 기술 내부 문서를 기술 에이전트만 접근 가능하도록 설정하여 보안 수준을 제어할 수 있습니다.
4. **유지보수의 용이성:** 특정 도구(API)가 변경되었을 때, 전체 시스템을 수정하는 것이 아니라 해당 도구를 사용하는 특정 에이전트의 설정만 변경하면 됩니다.

---

## 4. 단계별 Python 코드 실습

이번 프로젝트에서는 **[고객 문의 접수 → 유형 분류 → 전문 에이전트 처리 → 해결 불가 시 티켓 생성]** 흐름을 구현합니다.

### (1) `tools.py`: 외부 시스템 연동 도구
에이전트가 사용할 지식 베이스 검색 및 티켓 생성 도구를 정의합니다.

```python
# tools.py
import random

def search_knowledge_base(query: str):
    """회사 내부 지식 베이스에서 정보를 검색합니다."""
    print(f"[Tool] 지식 베이스 검색 중: {query}")
    # 실제로는 DB나 Vector DB 검색이 들어갑니다.
    kb = {
        "환불 규정": "구매 후 7일 이내, 미사용 제품에 한해 환불 가능합니다.",
        "API 연결 오류": "API 401 에러는 API Key 만료 시 발생합니다. 콘솔에서 갱신하세요.",
        "서버 다운": "현재 서버 점검 중이며, 오후 2시에 복구 예정입니다."
    }
    return kb.get(query, "관련 정보를 찾을 수 없습니다.")

def create_support_ticket(issue: str, priority: str):
    """해결되지 않은 문제를 위해 기술 지원 티켓을 생성합니다."""
    print(f"[Tool] 티켓 생성 중... 우선순위: {priority}, 내용: {issue}")
    ticket_id = f"TICKET-{random.randint(1000, 9999)}"
    return f"티켓이 성공적으로 생성되었습니다. 티켓 번호: {ticket_id}"
```

### (2) `agent.py`: 역할별 에이전트 설계
각 에이전트의 페르소나와 지시문을 정의합니다.

```python
# agent.py
from adk import Agent, ModelConfig

# 모델 설정 (비용과 성능의 트레이드오프를 고려하여 설정)
# Router는 빠르고 저렴한 모델, Expert는 정교한 모델 사용 권장
ROUTER_MODEL = ModelConfig(model_name="gemini-1.5-flash") 
EXPERT_MODEL = ModelConfig(model_name="gemini-1.5-pro")

class CustomerRouter(Agent):
    def __init__(self):
        super().__init__(
            name="CustomerRouter",
            model=ROUTER_MODEL,
            instruction="""당신은 고객 문의 분류기입니다. 
            문의 내용을 분석하여 'GENERAL' (일반 문의) 또는 'TECHNICAL' (기술적 문제)로 분류하십시오.
            결과는 반드시 한 단어로만 응답하세요."""
        )

class SupportAgent(Agent):
    def __init__(self, tools):
        super().__init__(
            name="SupportAgent",
            model=ROUTER_MODEL,
            instruction="""당신은 친절한 고객 지원 담당자입니다. 
            제공된 지식 베이스 도구를 사용하여 답변하세요. 
            답변할 수 없는 내용은 무리하게 추측하지 말고 기술 팀으로 인계해야 한다고 알리세요.""",
            tools=tools
        )

class TechnicalAgent(Agent):
    def __init__(self, tools):
        super().__init__(
            name="TechnicalAgent",
            model=EXPERT_MODEL,
            instruction="""당신은 수석 엔지니어입니다. 
            복잡한 기술 문제를 심층 분석하여 해결책을 제시하세요. 
            지식 베이스로 해결이 불가능한 심각한 결함인 경우, 반드시 티켓 생성 도구를 사용하여 티켓을 발행하세요.""",
            tools=tools
        )
```

### (3) `main.py`: 그래프 기반 워크플로우 및 실행
ADK 2.0의 그래프 구조를 모사하여 전체 흐름을 제어합니다.

```python
# main.py
from agent import CustomerRouter, SupportAgent, TechnicalAgent
from tools import search_knowledge_base, create_support_ticket
from adk import Session, Graph

def run_enterprise_system(user_query):
    # 1. 환경 설정
    session = Session()
    tools = [search_knowledge_base, create_support_ticket]
    
    router = CustomerRouter()
    support_agent = SupportAgent(tools)
    tech_agent = TechnicalAgent(tools)

    print(f"\n[User]: {user_query}")
    
    # 2. 그래프 기반 경로 결정 (Deterministic + Adaptive)
    # Step 1: 분류 (Router)
    category = router.run(user_query, session=session)
    print(f"[System] 분류 결과: {category}")

    # Step 2: 분기 처리 (Routing)
    if "GENERAL" in category.upper():
        response = support_agent.run(user_query, session=session)
    elif "TECHNICAL" in category.upper():
        response = tech_agent.run(user_query, session=session)
    else:
        response = "문의 유형을 파악하지 못했습니다. 다시 말씀해 주세요."

    print(f"[Agent]: {response}")

# --- 테스트 실행 ---
if __name__ == "__main__":
    # 케이스 1: 일반 문의
    run_enterprise_system("환불 규정이 어떻게 되나요?")
    
    # 케이스 2: 기술 문의 (해결 가능)
    run_enterprise_system("API 연결 시 401 에러가 발생합니다.")
    
    # 케이스 3: 심각한 기술 문제 (티켓 생성 필요)
    run_enterprise_system("전사 시스템이 완전히 다운되어 접속이 안 됩니다. 긴급 상황입니다!")
```

---

## 5. 설계 관점의 트레이드오프 분석

엔터프라이즈 시스템 설계 시 에이전트 설계자는 다음 세 가지 요소의 균형을 잡아야 합니다.

| 분석 항목 | 선택 A: 단일 강력한 에이전트 | 선택 B: 멀티 에이전트 분산 구조 (본 프로젝트) | 비고 |
| :--- | :--- | :--- | :--- |
| **비용 (Cost)** | 높음 (모든 요청에 Pro 모델 사용) | 최적화 (Router-Flash / Expert-Pro 조합) | 요청 빈도에 따라 비용 차이 극대화 |
| **속도 (Speed)** | 빠름 (단일 호출) | 상대적으로 느림 (Router → Agent 순차 호출) | 네트워크 홉(Hop) 증가로 인한 지연 발생 |
| **품질 (Quality)** | 보통 (컨텍스트 혼선 가능성) | 높음 (역할 전문화 및 전용 지침 적용) | 복잡한 작업일수록 분산 구조가 유리 |

**설계 전략:**
- **속도가 최우선인 서비스** → Router를 제거하고 단일 에이전트의 Prompt를 최적화하거나, 병렬 실행(Parallel) 구조를 채택합니다.
- **정확도와 비용 효율이 최우선인 서비스** → 위와 같은 계층적 구조(Hierarchical Structure)를 채택하고, 각 단계에서 토큰 필터링을 수행합니다.

---

## 6. 핵심 정리

1. **엔터프라이즈 에이전트**는 단순 구현이 아니라 **비즈니스 프로세스의 자동화**를 목표로 합니다.
2. **구조적 컨텍스트 관리**를 통해 토큰 효율을 높이고, **아티팩트**를 통해 대규모 데이터를 지연 로딩함으로써 성능을 최적화합니다.
3. **그래프 기반 아키텍처**는 AI의 유연성과 코드의 결정론적 제어를 결합하여 예측 가능한 시스템을 만듭니다.
4. **트레이드오프 분석**을 통해 서비스의 목적(비용 vs 속도 vs 품질)에 맞는 모델 배치와 구조를 선택해야 합니다.

---

## 7. 연습문제

**Q1. [빈칸 채우기]**
ADK 2.0에서 결정론적인 실행 경로와 AI의 적응형 추론을 결합하여 예측 가능한 워크플로우를 제공하는 아키텍처를 ( \quad ) 기반 아키텍처라고 한다.

**Q2. [코드 리뷰]**
위의 `main.py` 코드에서 `run_enterprise_system` 함수는 현재 순차적(Sequential)으로 동작하고 있습니다. 만약 사용자의 질문이 들어왔을 때, '일반 답변'과 '기술적 분석'을 동시에 수행하여 사용자에게 종합적인 답변을 주고 싶다면, 어떤 구조로 변경해야 하며, 이때 발생할 수 있는 트레이드오프는 무엇입니까?

**Q3. [구조 설계]**
현재 시스템에 '보안 감사 에이전트(Security Auditor)'를 추가하려고 합니다. 이 에이전트는 `TechnicalAgent`가 티켓을 생성하기 직전에, 해당 이슈가 보안 취약점과 관련이 있는지 검토해야 합니다. 전체 워크플로우 그래프를 어떻게 수정해야 할지 단계별로 기술하세요.

**Q4. [토큰 최적화 설계]**
`TechnicalAgent`가 참조해야 할 매뉴얼이 1,000페이지에 달해 모든 내용을 컨텍스트에 넣을 수 없습니다. ADK의 어떤 기능을 사용하여 이를 해결할 수 있으며, 구체적인 작동 메커니즘을 설명하세요.

**Q5. [비즈니스 케이스 분석]**
회사가 비용 절감을 위해 모든 모델을 `gemini-1.5-flash`로 통일하라고 지시했습니다. 이 결정이 '품질'과 '신뢰성' 관점에서 어떤 리스크를 가져올 수 있는지, 그리고 이를 완화하기 위해 프롬프트나 구조적으로 어떤 보완책을 세울 수 있을지 논하세요.

---

### [정답 및 설계 의도]

**A1. 그래프 (Graph)**
- 의도: ADK 2.0의 핵심 정체성인 그래프 기반 설계 개념을 확인합니다.

**A2. 병렬(Parallel) 구조로 변경 / 비용 및 토큰 사용량 증가**
- 의도: Sequential과 Parallel의 차이를 이해하고, 성능 향상에 따른 비용 증가라는 트레이드오프를 인지하고 있는지 확인합니다.

**A3. [수정 경로]: Router → TechnicalAgent → Security Auditor → (보안 이슈 시) 티켓 생성 / (일반 이슈 시) 종료**
- 의도: 기존 워크플로우에 새로운 노드(에이전트)를 삽입하여 파이프라인을 확장하는 설계 능력을 평가합니다.

**A4. 아티팩트(Artifact)의 지연 로딩(Lazy-loading) 기능 사용**
- 의도: 대규모 데이터 처리 시 토큰 효율성을 극대화하는 ADK의 핵심 엔터프라이즈 기능을 이해하고 있는지 확인합니다. 작동 방식은 [전체 목록 제공 → 에이전트의 특정 부분 요청 → 해당 부분만 컨텍스트 삽입] 순입니다.

**A5. 리스크: 복잡한 추론 능력 저하로 인한 오답(환각) 증가, 기술적 심층 분석 실패. 보완책: Few-shot 예시를 대폭 추가하여 가이드를 정교화하거나, Router의 분류 기준을 더 세분화하여 단순 반복 작업 위주로 배분함.**
- 의도: 모델의 체급 차이가 가져오는 실질적인 품질 저하를 예측하고, 이를 프롬프트 엔지니어링이나 구조적 설계로 해결하려는 엔지니어적 사고방식을 평가합니다.