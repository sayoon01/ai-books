# 챕터 11: 과적합과 하이퍼파라미터 튜닝

# 챕터 11: 과적합과 하이퍼파라미터 튜닝

머신러닝 모델을 구축하며 가장 당혹스러운 순간은 **"학습 데이터에서는 정확도가 100%인데, 실제 데이터에 적용하니 성능이 엉망인 경우"**일 것입니다. 우리는 이를 **과적합(Overfitting)**이라고 부릅니다. 모델이 데이터를 '이해'하는 것과 '단순히 외우는 것'의 차이를 이해하고, 최적의 성능을 내기 위해 모델의 설정값을 정교하게 조절하는 '튜닝' 방법을 살펴보겠습니다.

---

### 1. 실생활 비유: "문제집을 통째로 외운 학생"

시험을 앞둔 세 명의 학생이 서로 다른 방식으로 공부하고 있습니다.

* **학생 A (과소적합):** 공부를 거의 하지 않았습니다. 공식 한두 개만 대충 알고 시험을 봅니다. 기본 문제도 틀리고, 응용 문제는 당연히 틀립니다. (**학습 데이터 $\rightarrow$ 저성능 / 테스트 데이터 $\rightarrow$ 저성능**)
* **학생 B (과적합):** 공부를 정말 열심히 했지만, 잘못된 방식으로 했습니다. 문제집에 있는 모든 문제와 정답을 **토씨 하나 안 틀리고 통째로 외웠습니다.** 문제집에 나온 문제는 100점을 맞지만, 숫자 하나만 바꾼 응용 문제가 나오자 완전히 당황해서 틀려버립니다. (**학습 데이터 $\rightarrow$ 고성능 / 테스트 데이터 $\rightarrow$ 저성능**)
* **학생 C (적정 학습):** 공식의 원리를 이해하고 다양한 유형의 문제를 풀었습니다. 문제집에서도 90점을 맞고, 처음 보는 응용 문제에서도 85점을 맞습니다. (**학습 데이터 $\rightarrow$ 고성능 / 테스트 데이터 $\rightarrow$ 고성능**)

머신러닝의 목표는 학생 B가 아니라 **학생 C**가 되는 것입니다. 이를 전문 용어로 **'일반화(Generalization) 성능을 높인다'**고 합니다.

---

### 2. 직관적 이해: 일반화와 적정 학습

**일반화(Generalization)**란 모델이 학습 과정에서 보지 못한 **새로운 데이터(Unseen Data)**에 대해서도 정확한 예측을 수행하는 능력을 말합니다.

* **과적합(Overfitting):** 모델이 학습 데이터의 세세한 노이즈(Noise)나 우연한 패턴까지 모두 학습해버려, 학습 데이터에만 지나치게 최적화된 상태입니다. 즉, '원리'가 아니라 '정답'을 외운 상태입니다.
* **과소적합(Underfitting):** 모델이 너무 단순해서 데이터 속에 숨겨진 기본적인 패턴조차 찾아내지 못한 상태입니다. 즉, 공부량이 절대적으로 부족하여 '기초'조차 잡히지 않은 상태입니다.

---

### 3. 기술 설명

#### ① 편향-분산 트레이드오프 (Bias-Variance Trade-off)
과적합과 과소적합은 '편향'과 '분산'이라는 두 가지 개념의 충돌로 설명됩니다.

* **편향(Bias):** 모델의 예측값이 실제 정답과 얼마나 떨어져 있는가 하는 정도입니다. 편향이 높으면 모델이 너무 단순해 정답을 제대로 맞히지 못하는 **과소적합**이 발생합니다.
* **분산(Variance):** 데이터가 조금만 바뀌어도 모델의 예측값이 얼마나 크게 변하는가 하는 정도입니다. 분산이 높으면 모델이 학습 데이터의 작은 변화에 너무 민감하게 반응하는 **과적합**이 발생합니다.

> **핵심:** 편향을 줄이려고 모델을 복잡하게 만들면 분산이 커지고, 분산을 줄이려고 모델을 단순하게 만들면 편향이 커집니다. 이 둘의 합(Total Error)이 최소가 되는 **최적의 균형점**을 찾는 것이 머신러닝의 핵심입니다.

#### ② 파라미터 vs 하이퍼파라미터
두 개념은 '누가 결정하느냐'에 따라 구분됩니다.

| 구분 | 파라미터 (Parameter) | 하이퍼파라미터 (Hyperparameter) |
| :--- | :--- | :--- |
| **정의** | 모델이 **학습을 통해 스스로** 찾아내는 값 | 사용자가 **학습 시작 전 직접** 설정하는 값 |
| **예시** | 선형 회귀의 가중치($w$), 편향($b$) | 결정 트리의 최대 깊이(`max_depth`), 학습률 |
| **결정 방식** | 데이터로부터 최적화됨 (자동) | 실험과 경험을 통해 결정됨 (수동) |

#### ③ 하이퍼파라미터 튜닝 기법
최적의 하이퍼파라미터를 찾기 위해 다음과 같은 전략을 사용합니다.

* **Grid Search:** 지정한 후보 값들의 모든 가능한 조합을 하나하나 다 시도해보는 '전수 조사' 방식입니다. 가장 확실하지만, 후보가 많아지면 시간이 매우 오래 걸립니다.
* **Random Search:** 정해진 범위 내에서 무작위로 조합을 선택해 시도하는 방식입니다. 모든 조합을 확인하지 않으므로 훨씬 빠르며, 때로는 Grid Search보다 더 효율적으로 최적값에 도달합니다.

---

### 4. 파이썬 코드 실습: 결정 트리로 보는 과적합과 튜닝

결정 트리(Decision Tree) 모델의 `max_depth`(트리의 최대 깊이)를 조절하며 과적합 현상을 확인하고, `GridSearchCV`를 통해 최적의 깊이를 찾아보겠습니다.

```python
import numpy as np
import matplotlib.pyplot as plt
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score

# 1. 가상의 데이터 생성 (노이즈가 섞인 복잡한 데이터)
X, y = make_classification(n_samples=1000, n_features=20, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 2. 과소적합 모델 (너무 단순함: 깊이를 1로 제한)
underfit_model = DecisionTreeClassifier(max_depth=1, random_state=42)
underfit_model.fit(X_train, y_train)

# 3. 과적합 모델 (너무 복잡함: 깊이 제한 없음)
overfit_model = DecisionTreeClassifier(max_depth=None, random_state=42)
overfit_model.fit(X_train, y_train)

# 4. 하이퍼파라미터 튜닝 (GridSearchCV 사용)
# max_depth 후보군을 설정하여 최적의 값을 탐색
param_grid = {'max_depth': [1, 2, 3, 4, 5, 10, None]}
grid_search = GridSearchCV(DecisionTreeClassifier(random_state=42), param_grid, cv=5)
grid_search.fit(X_train, y_train)
best_model = grid_search.best_estimator_

# 결과 비교 함수
def evaluate_model(model, name):
    train_acc = accuracy_score(y_train, model.predict(X_train))
    test_acc = accuracy_score(y_test, model.predict(X_test))
    print(f"[{name: <20}] Train Acc: {train_acc:.4f} | Test Acc: {test_acc:.4f} | Gap: {abs(train_acc-test_acc):.4f}")

print("--- 모델별 성능 비교 ---")
evaluate_model(underfit_model, "Underfitting (d=1)")
evaluate_model(overfit_model, "Overfitting (d=None)")
evaluate_model(best_model, f"Best Model (d={grid_search.best_params_['max_depth']})")
```

---

### 5. 실행 결과 해설

**예상 출력 결과:**
```text
--- 모델별 성능 비교 ---
[Underfitting (d=1) ] Train Acc: 0.5200 | Test Acc: 0.5100 | Gap: 0.0100
[Overfitting (d=None)] Train Acc: 1.0000 | Test Acc: 0.8400 | Gap: 0.1600
[Best Model (d=5)   ] Train Acc: 0.8900 | Test Acc: 0.8700 | Gap: 0.0200
```

**결과 해석:**
1. **과소적합 모델:** 학습 점수와 테스트 점수가 모두 낮습니다. 모델이 너무 단순해 데이터의 패턴을 전혀 읽지 못했음을 의미합니다.
2. **과적합 모델:** 학습 점수는 **1.0(100%)**이지만 테스트 점수는 그보다 훨씬 낮습니다. 학습 데이터의 노이즈까지 모두 외워버려 새로운 데이터에 대한 대응력이 떨어진 전형적인 사례입니다. (Gap이 가장 큼)
3. **최적 모델:** 학습 점수와 테스트 점수의 **격차(Gap)가 적으면서** 동시에 높은 성능을 유지합니다. `GridSearchCV`가 적절한 깊이를 찾아내어 일반화 성능을 극대화했습니다.

---

### 6. 실무 활용 사례

실무에서 모델을 배포하기 전, 반드시 **검증 셋(Validation Set)**이나 **교차 검증(Cross-Validation)**을 사용하는 이유가 바로 과적합을 방지하기 위해서입니다.

예를 들어, **카드 부정 결제 탐지(Fraud Detection)** 모델을 만들었는데 학습 데이터에서 정확도가 99.9%가 나왔다면, 숙련된 엔지니어는 기뻐하기보다 **"과적합된 것 아닌가?"**라고 의심합니다. 실제 운영 환경(Production)에서 새로운 패턴의 부정 결제가 발생했을 때 모델이 대응하지 못하면 막대한 금전적 손실이 발생하기 때문입니다. 이때 실무자는 `Regularization`(규제) 기법을 적용하거나 하이퍼파라미터를 튜닝하여 모델의 복잡도를 의도적으로 낮춤으로써 안정성을 확보합니다.

---

### 7. 자주 하는 실수

**❌ 테스트 데이터를 튜닝에 사용하는 실수 (Data Leakage)**
가장 위험하고 흔한 실수입니다. `GridSearchCV`를 사용할 때 테스트 셋(`X_test`)을 넣어 최적의 하이퍼파라미터를 찾는 경우가 있습니다.

* **문제점:** 테스트 데이터의 정보가 모델 설정(하이퍼파라미터)에 반영됩니다. 결과적으로 모델이 테스트 데이터에 '맞춤형'으로 제작되어, 실제 배포 후에는 성능이 급락하는 현상이 발생합니다.
* **해결책:** 반드시 **학습 데이터 $\rightarrow$ 검증 데이터(또는 교차 검증) $\rightarrow$ 테스트 데이터** 순서로 엄격히 분리하세요. 테스트 데이터는 모든 튜닝이 끝난 후, 오직 **최종 성능 측정**에만 단 한 번 사용해야 합니다.

---

### 8. 핵심 요약

* **과소적합:** 모델이 너무 단순함 $\rightarrow$ 편향 높음 $\rightarrow$ 학습/테스트 성능 모두 낮음.
* **과적합:** 모델이 너무 복잡함 $\rightarrow$ 분산 높음 $\rightarrow$ 학습 성능은 높으나 테스트 성능 낮음.
* **일반화:** 처음 보는 데이터에서도 일관된 성능을 내는 능력.
* **하이퍼파라미터:** 사용자가 직접 설정하는 값 (예: `max_depth`, `learning_rate`).
* **GridSearchCV:** 가능한 모든 조합을 시도하여 최적의 하이퍼파라미터를 찾는 도구.

---

### 9. 확인 문제

1. 모델이 학습 데이터에서는 매우 높은 성능을 보이지만, 테스트 데이터에서는 성능이 크게 떨어지는 현상을 무엇이라고 하며, 그 원인은 무엇인가요?
2. 파라미터(Parameter)와 하이퍼파라미터(Hyperparameter)의 결정적인 차이점은 무엇인가요?
3. 편향(Bias)과 분산(Variance)의 관계에 대해 설명하고, 최적의 모델이란 어떤 상태인지 서술하세요.

---

### 10. 정답 및 해설

1. **정답:** 과적합(Overfitting)입니다. 원인은 모델이 학습 데이터의 일반적인 패턴뿐만 아니라 무작위한 노이즈까지 모두 학습하여 모델이 지나치게 복잡해졌기 때문입니다.
2. **정답:** 파라미터는 모델이 학습 과정에서 데이터로부터 **스스로** 찾아내는 값(예: 가중치)이며, 하이퍼파라미터는 학습 시작 전에 **사용자가 직접** 설정해주는 값(예: 학습률, 트리 깊이)입니다.
3. **정답:** 편향과 분산은 트레이드오프(Trade-off) 관계입니다. 편향을 낮추면(모델이 복잡해지면) 분산이 높아지고, 분산을 낮추면(모델이 단순해지면) 편향이 높아집니다. 최적의 모델은 이 둘의 합(Total Error)이 최소가 되어 일반화 성능이 극대화된 상태의 모델입니다.

---

### 11. 미니 프로젝트: 과적합 진단 및 치료하기

**목표:** 의도적으로 과적합된 모델을 만들고, 튜닝을 통해 이를 해결하는 과정을 기록하세요.

**미션 가이드:**
1. `sklearn.datasets.load_breast_cancer` (유방암 데이터셋)를 불러오세요.
2. `DecisionTreeClassifier`를 사용하여 `max_depth=None`으로 모델을 학습시키고, Train/Test 정확도를 출력하여 과적합을 확인하세요.
3. `GridSearchCV`를 사용하여 `max_depth`의 범위를 `[1, 2, 3, 4, 5, 10]`으로 설정하고 최적의 값을 찾으세요.
4. 튜닝 전과 후의 **Train-Test 점수 격차(Gap)**가 얼마나 줄어들었는지 비교 분석하여 리포트를 작성하세요.
5. **결론:** "모델의 복잡도를 낮추었을 때 일반화 성능이 어떻게 변했는가?"에 대해 자신의 언어로 정리하세요.