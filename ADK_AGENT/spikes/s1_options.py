"""
S1: LiteLlm(ollama_chat/gemma4:31b) 옵션 전달 검증.

확인 목표:
  - num_ctx / repeat_penalty / keep_alive 가 ADK LlmAgent -> LiteLlm -> ollama 로 전달되는가.
검증법(외부):
  - 추론 직후 `ollama ps` 의 CONTEXT 컬럼이 32768 인지(기본값 4096 이면 전달 실패).
실행:
  .venv/bin/python spikes/s1_options.py
"""
import asyncio

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types

MODEL = "ollama_chat/gemma4:31b"
NUM_CTX = 32768

# 후보 1: LiteLlm 생성자에 옵션을 kwargs 로 직접
llm = LiteLlm(
    model=MODEL,
    num_ctx=NUM_CTX,
    repeat_penalty=1.2,
    keep_alive="30m",
    temperature=0.7,
)

agent = LlmAgent(
    name="s1",
    model=llm,
    instruction="너는 한국어 도우미다. 사용자가 시키는 대로 충실히 답하라.",
)


async def main():
    runner = InMemoryRunner(agent=agent, app_name="s1")
    sess = await runner.session_service.create_session(app_name="s1", user_id="u")
    msg = types.Content(
        role="user",
        parts=[types.Part(text="아무 주제나 골라 200자 이상 한국어로 한 단락 써줘.")],
    )
    out = []
    async for ev in runner.run_async(user_id="u", session_id=sess.id, new_message=msg):
        if ev.content and ev.content.parts:
            for p in ev.content.parts:
                if p.text:
                    out.append(p.text)
    text = "".join(out)
    print("=== 응답 길이:", len(text), "자 ===")
    print(text[:400])
    print("\n>>> 이제 다른 셸에서 `ollama ps` 의 CONTEXT 를 확인하세요 (기대: 32768).")


if __name__ == "__main__":
    asyncio.run(main())
