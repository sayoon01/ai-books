# 8. 지능적 오케스트레이션: Coordinator 및 Router 구조

## 8. 지능적 오케스트레이션: Coordinator 및 Router 구조

지난 챕터에서 우리는 에이전트들을 단순히 순차적으로 혹은 병렬로 연결하는 방법을 배웠습니다. 하지만 실제 비즈니스 환경에서는 "사용자의 질문에 따라 어떤 전문가에게 보낼지"를 결정해야 하거나, "거대한 목표를 작은 단위로 쪼개어 적절한 에이전트에게 배분"해야 하는 상황이 훨씬 더 많습니다. 이번 챕터에서는 에이전트들의 지휘자 역할을 하는 Coordinator와 Router 구조를 학습합니다.

---

## 1. 쉬운 비유: 회사 운영의 '리셉션'과 '팀장님'

우리가 아주 큰 회사의 고객센터에 전화를 했다고 가정해 봅시다.

*   **Router(라우터)는 '리셉션 직원'과 같습니다.**
    전화를 받은 리셉션 직원은 고객의 말을 듣고 "결제 관련 문의시군요? 회계팀으로 연결해 드리겠습니다" 또는 "기술적 결함이시군요? 엔지니어링팀으로 연결하겠습니다"라고 판단합니다. 리셉션 직원은 직접 문제를 해결하지 않습니다. 오직 **'어디로 가야 할지'** 방향만 정해줍니다.

*   **Coordinator(코디네이터)는 '프로젝트 팀장님'과 같습니다.**
    "신제품 런칭 캠페인을 진행하라"는 거대한 목표가 떨어지면, 팀장님은 이를 쪼갭니다. "A님은 시장 조사를 하시고, B님은 광고 시안을 잡으세요. 결과가 나오면 제가 취합해서 최종 보고서를 만들겠습니다." 코디네이터는 목표를 달성하기 위해 **'작업을 분해하고 배분하며 결과를 취합'**합니다.

---

## 2. ADK 개념 및 용어

### 라우터 (Router)
사용자의 입력(Input)을 분석하여 미리 정의된 여러 에이전트 중 가장 적합한 하나(또는 소수)를 선택해 요청을 전달하는 구조입니다. 입력값에 기반한 '분기 처리'가 핵심입니다.

### 코디네이터 (Coordinator)
복잡하고 추상적인 상위 목표(High-level Goal)를 수신하여, 이를 수행 가능한 하위 작업(Sub-tasks)으로 분해하고, 각 작업에 적합한 에이전트를 할당하며, 최종 결과물을 통합하는 관리자 에이전트입니다.

### 오케스트레이션 (Orchestration)
여러 에이전트, 도구, 데이터 흐름을 조율하여 하나의 완성된 워크플로우를 만드는 전체적인 설계 과정을 의미합니다.

---

## 3. 왜/언제 사용하는가? (당위성)

단순한 Sequential(순차) 구조만으로는 다음과 같은 한계가 발생합니다.

1.  **토큰 낭비:** 모든 요청에 대해 모든 에이전트를 거치게 하면 불필요한 토큰 소모가 극심해집니다. → **Router**를 통해 필요한 에이전트만 호출하여 **비용을 최적화**합니다.
2.  **예측 불가능성:** 너무 복잡한 지시문을 하나의 에이전트에게 주면 할루시네이션(환각)이 발생할 확률이 높습니다. → **Coordinator**가 작업을 세분화하여 각 전문가 에이전트에게 전달함으로써 **품질과 정확도를 높입니다.**
3.  **확장성 문제:** 새로운 기능이 추가될 때마다 전체 파이프라인을 수정해야 합니다. → **Router** 구조를 도입하면 새로운 에이전트만 추가하고 라우팅 규칙만 업데이트하면 되므로 **유지보수가 용이**합니다.

---

## 4. 단계별 Python 코드 실습

이번 실습에서는 **[고객 지원 시스템]**을 구축합니다. 사용자의 요청이 '결제' 관련인지 '기술' 관련인지 판단하여 배분하고, 기술 문의의 경우 '진단'과 '해결' 단계를 거치도록 설계합니다.

### (1) `tools.py`: 외부 도구 정의
에이전트들이 사용할 간단한 모의 도구들입니다.

```python
# tools.py

def get_billing_info(user_id: str):
    """사용자의 결제 상태를 조회합니다."""
    # 실제로는 DB 조회가 들어가겠지만, 여기서는 모의 데이터를 반환합니다.
    db = {"user123": "결제 완료 (플랜: Pro)", "user456": "결제 미납 (플랜: Free)"}
    return db.get(user_id, "사용자 정보를 찾을 수 없습니다.")

def get_technical_docs(error_code: str):
    """에러 코드에 따른 기술 문서를 조회합니다."""
    docs = {
        "ERR_01": "네트워크 설정을 확인하고 방화벽을 해제하세요.",
        "ERR_02": "API 키의 유효 기간이 만료되었습니다. 재발급 받으세요."
    }
    return docs.get(error_code, "해당 에러에 대한 문서가 없습니다.")
```

### (2) `agent.py`: 전문가 에이전트 정의
각 역할에 특화된 지시문을 가진 에이전트들을 생성합니다.

```python
# agent.py
from adk import Agent # ADK 프레임워크 가정

# 1. 결제 전문 에이전트
billing_agent = Agent(
    name="BillingAgent",
    instruction="당신은 결제 전문가입니다. 결제 상태를 확인하고 안내하세요.",
    tools=[get_billing_info]
)

# 2. 기술 진단 에이전트 (Coordinator의 하위 작업자 1)
diagnosis_agent = Agent(
    name="DiagnosisAgent",
    instruction="사용자의 증상을 듣고 정확한 에러 코드를 판별하세요.",
)

# 3. 기술 해결 에이전트 (Coordinator의 하위 작업자 2)
solution_agent = Agent(
    name="SolutionAgent",
    instruction="에러 코드를 바탕으로 해결책을 제시하세요.",
    tools=[get_technical_docs]
)
```

### (3) `main.py`: Router 및 Coordinator 구현
전체 흐름을 제어하는 오케스트레이션 로직을 작성합니다.

```python
# main.py
from agent import billing_agent, diagnosis_agent, solution_agent

class SupportOrchestrator:
    def __init__(self):
        self.agents = {
            "billing": billing_agent,
            "tech_diag": diagnosis_agent,
            "tech_sol": solution_agent
        }

    def route_request(self, user_input: str):
        """[Router 역할] 입력에 따라 경로를 결정합니다."""
        print(f"--- [Router] 요청 분석 중: {user_input} ---")
        if "결제" in user_input or "돈" in user_input:
            return "billing"
        elif "오류" in user_input or "안돼요" in user_input:
            return "tech_coordinator" # 기술 쪽은 코디네이터가 필요함
        else:
            return "general"

    def handle_tech_support(self, user_input: str):
        """[Coordinator 역할] 기술 지원 프로세스를 관리합니다."""
        print("--- [Coordinator] 기술 지원 워크플로우 시작 ---")
        
        # Step 1: 진단 에이전트에게 에러 코드 추출 요청
        diag_res = self.agents["tech_diag"].run(f"다음 증상에서 에러 코드를 찾아줘: {user_input}")
        print(f"[Step 1 - Diagnosis]: {diag_res}")
        
        # Step 2: 해결 에이전트에게 해결책 요청
        sol_res = self.agents["tech_sol"].run(f"에러 코드 {diag_res}에 대한 해결책을 알려줘.")
        print(f"[Step 2 - Solution]: {sol_res}")
        
        return f"기술 지원 결과: {sol_res}"

    def run(self, user_input: str):
        path = self.route_request(user_input)
        
        if path == "billing":
            return self.agents["billing"].run(user_input)
        elif path == "tech_coordinator":
            return self.handle_tech_support(user_input)
        else:
            return "죄송합니다. 어떤 도움이 필요하신지 정확히 말씀해 주세요."

# 실행 테스트
if __name__ == "__main__":
    orchestrator = SupportOrchestrator()
    
    print("\n테스트 1: 결제 문의")
    print(orchestrator.run("제 결제 상태가 어떻게 되나요? ID는 user123입니다."))
    
    print("\n테스트 2: 기술 문의")
    print(orchestrator.run("로그인 하려는데 ERR_01 오류가 떠서 안돼요."))
```

---

## 5. 설계 관점: 비용 vs 속도 vs 품질 트레이드오프

멀티 에이전트 구조를 설계할 때 가장 중요한 것은 무조건 복잡하게 만드는 것이 아니라, 목적에 맞는 구조를 선택하는 것입니다.

| 구분 | Router 구조 | Coordinator 구조 |
| :--- | :--- | :--- |
| **작동 방식** | A → (B or C) | A → (B → C → D) → A |
| **속도 (Latency)** | **매우 빠름**. 한 번의 선택 후 즉시 실행. | **느림**. 단계별 추론과 취합 과정이 필요함. |
| **비용 (Token)** | **낮음**. 필요한 에이전트만 호출. | **높음**. 여러 에이전트가 서로 주고받는 토큰 발생. |
| **품질 (Quality)** | **보통**. 선택된 에이전트의 능력에 의존. | **매우 높음**. 단계적 검증과 전문화된 분업 가능. |
| **적합한 사례** | 단순 분류, FAQ, 단순 요청 처리 | 복잡한 문제 해결, 리서치 보고서 작성, 소프트웨어 개발 |

**설계 팁:** 
- 먼저 **Router**로 최대한 많은 요청을 빠르게 처리하게 하고, 
- Router가 판단하기에 "이것은 복잡한 작업이다"라고 판별한 경우에만 **Coordinator** 워크플로우로 진입시키십시오. 이것이 엔터프라이즈급 에이전트의 효율적인 설계 방식입니다.

---

## 6. 핵심 정리

*   **Router**는 입력값에 따라 적절한 에이전트를 선택하는 '분기점' 역할을 수행하며, 비용과 속도 최적화에 유리합니다.
*   **Coordinator**는 상위 목표를 하위 작업으로 쪼개고 배분하는 '관리자' 역할을 수행하며, 복잡한 작업의 품질을 높이는 데 유리합니다.
*   **오케스트레이션** 설계 시에는 항상 **비용(Cost), 속도(Latency), 품질(Quality)**의 트레이드오프를 고려해야 합니다.
*   ADK 2.0의 그래프 기반 아키텍처를 활용하면 이러한 Router → Coordinator 흐름을 결정론적인 경로로 설계하여 예측 가능성을 높일 수 있습니다.

---

## 7. 연습문제

**Q1. [빈칸 채우기]**
사용자의 요청이 들어왔을 때, 특정 조건을 기준으로 어떤 에이전트에게 전달할지 결정하는 구조를 ( \quad )라고 하며, 거대한 목표를 작은 단위로 쪼개어 여러 에이전트에게 배분하고 취합하는 구조를 ( \quad )라고 한다.

**Q2. [코드 리뷰]**
위의 `main.py` 코드에서 `route_request` 함수는 현재 단순한 키워드(`"결제"`, `"오류"`) 매칭 방식을 사용하고 있습니다. 만약 사용자가 "돈 낸 지 오래됐는데 왜 안 되죠?"라고 말한다면 어떻게 동작할까요? 이 부분을 LLM 기반의 라우팅으로 변경하려면 어떤 식으로 수정해야 할지 설계 아이디어를 제시하세요.

**Q3. [구조 설계]**
당신은 '여행 플래너 에이전트'를 설계하고 있습니다. 다음 기능들이 필요합니다: [항공권 조회, 호텔 예약, 일정 최적화, 예산 계산]. 이 기능을 Router 구조와 Coordinator 구조 중 각각 어떻게 설계할지 설명하세요.

**Q4. [트레이드오프 분석]**
모든 요청을 Coordinator가 처리하게 설계했을 때 발생할 수 있는 가장 큰 문제점 두 가지를 '비용'과 '사용자 경험' 관점에서 서술하세요.

**Q5. [확장 과제 - 중급자]**
제시된 코드의 `handle_tech_support` 함수에 '검수 에이전트(ReviewerAgent)'를 추가해 보세요. `SolutionAgent`가 내놓은 답변이 충분히 친절하고 정확한지 검수하고, 부적절하다면 다시 `SolutionAgent`에게 수정을 요청하는 '루프(Loop) 구조'를 구현해 보십시오.

---

### [정답 및 설계 의도]

**A1.** Router / Coordinator
*(의도: 두 핵심 개념의 정의를 명확히 구분할 수 있는지 확인)*

**A2.** 
- **동작:** `"돈"`이라는 키워드가 포함되어 있으므로 `billing` 경로로 이동합니다. 하지만 문맥상으로는 기술적 문제일 수도 있습니다.
- **수정 아이디어:** `route_request` 내부에서 단순 `if`문 대신, 가벼운 모델(예: Gemini Flash)에게 "다음 문장이 [결제, 기술, 일반] 중 어디에 해당하는지 단어로만 답해줘"라고 요청하는 **LLM Router**를 구현합니다.
*(의도: 결정론적 라우팅의 한계를 이해하고 AI 기반 라우팅의 필요성을 인식하게 함)*

**A3.**
- **Router 구조:** 사용자가 "항공권 알려줘" → 항공권 에이전트 / "호텔 예약해줘" → 호텔 에이전트. (단순 기능 호출)
- **Coordinator 구조:** 사용자가 "일본 3박 4일 여행 계획 짜줘" → 코디네이터가 [항공권 조회 → 호텔 예약 → 일정 최적화 → 예산 계산] 순으로 작업을 분배하고 최종 일정표를 생성. (복합 목표 달성)
*(의도: 단순 요청과 복합 요청의 차이를 구분하여 설계에 적용할 수 있는지 확인)*

**A4.**
- **비용:** 모든 요청에 대해 여러 번의 LLM 호출과 컨텍스트 전달이 발생하므로 토큰 사용량이 급증하여 운영 비용이 상승합니다.
- **사용자 경험:** 단계별 추론 과정이 추가됨에 따라 응답 시간이 길어져 사용자가 체감하는 대기 시간(Latency)이 늘어납니다.
*(의도: 성능-비용-품질의 상관관계를 분석하는 설계자적 관점을 함양)*

**A5. [설계 가이드]**
- `agent.py`에 `reviewer_agent` 추가 (Instruction: "답변의 정확성과 친절도를 평가하여 OK 또는 REJECT를 반환하라").
- `main.py`의 `handle_tech_support` 내부에 `while` 루프를 생성.
- `Reviewer`가 `REJECT`를 보낼 때까지 `SolutionAgent`를 다시 호출하는 로직 구현.
*(의도: 단순 순차 실행을 넘어 피드백 루프가 포함된 적응형 워크플로우 구현 능력을 테스트)*