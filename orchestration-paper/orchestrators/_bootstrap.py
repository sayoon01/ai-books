"""벤더링된 testbed(ADK 엔진)를 import 경로에 추가한다.

orchestration-paper/testbed/ 에 agent/ 와 core/ 가 복사되어 있고,
그 코드는 `from agent...`, `from core...` (최상위) 형태로 import하므로
testbed 디렉토리 자체를 sys.path 에 넣어주면 수정 없이 동작한다.
"""
import sys
from pathlib import Path

TESTBED = Path(__file__).resolve().parent.parent / "testbed"

if str(TESTBED) not in sys.path:
    sys.path.insert(0, str(TESTBED))
