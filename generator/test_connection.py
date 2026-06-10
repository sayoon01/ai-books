"""
Ollama 연결 테스트
실행: python generator/test_connection.py
"""
import ollama

MODEL = "gemma4:31b"

def test():
    print(f"[연결 테스트] 모델: {MODEL}")
    print("-" * 40)

    res = ollama.chat(
        model=MODEL,
        options={"temperature": 0.7},
        messages=[
            {"role": "system", "content": "당신은 책 작가입니다. 짧게 답하세요."},
            {"role": "user",   "content": "파이썬이란 무엇인지 두 문장으로 설명해주세요."},
        ]
    )

    content = res["message"]["content"]
    print(content)
    print("-" * 40)
    print("[OK] Ollama 연결 성공")

if __name__ == "__main__":
    test()
