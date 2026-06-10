# 챕터 12: 앙상블과 실전 머신러닝

# 챕터 12: 앙상블과 실전 머신러닝

단일 모델의 한계를 넘어, 여러 모델의 힘을 합쳐 최상의 성능을 끌어내는 '앙상블(Ensemble)'의 세계에 오신 것을 환영합니다. 앙상블 학습을 통해 "왜 Random Forest가 강력한가?" 그리고 "XGBoost는 어떻게 정답을 찾아가는가?"라는 질문에 데이터 과학자의 관점에서 논리적으로 답변할 수 있게 될 것입니다.

---

### 1. 실생활 비유: "집단지성의 힘"

중요한 투자 결정을 내려야 할 때, 어떤 선택이 가장 안전하고 정확할까요?

1. **독단적인 전문가 한 명**에게만 묻는다. (**단일 모델**) $\rightarrow$ 전문가가 뛰어날 순 있지만, 편향된 시각을 가졌다면 잘못된 결정으로 인해 큰 손실을 볼 위험이 큽니다.
2. **평범한 사람 100명**에게 물어보고 가장 많이 나온 의견(다수결)을 따른다. (**배깅/Random Forest**) $\rightarrow$ 개개인은 부족할 수 있지만, 서로 다른 배경과 관점을 가진 사람들이 모여 투표하면 극단적인 오류가 상쇄되어 안정적인 정답에 가까워집니다.
3. **첫 번째 사람**의 의견을 듣고, **두 번째 사람은 첫 번째 사람이 틀린 부분만 집중적으로 분석**해 보완하고, **세 번째 사람은 앞선 두 사람이 놓친 부분**을 또 보완한다. (**부스팅/XGBoost**) $\rightarrow$ 앞선 사람의 실수를 다음 사람이 교정하는 방식으로, 단계별로 오차를 수정하며 정답을 향해 정교하게 다가가는 전략입니다.

---

### 2. 개념 직관: 약한 학습기를 모아 강한 학습기로!

머신러닝에서 **약한 학습기(Weak Learner)**란, 아주 뛰어나지는 않지만 무작위 추측보다는 조금 더 나은 성능을 내는 모델을 말합니다. 보통 깊이가 얕은 결정 트리(Decision Tree)가 이에 해당합니다.

**앙상블(Ensemble)**은 바로 이 '약한 학습기'들을 여러 개 결합하여, 단일 모델보다 훨씬 강력한 **강한 학습기(Strong Learner)**를 만드는 기법입니다. 

여기서 가장 중요한 키워드는 **'다양성(Diversity)'**입니다. 서로 다른 관점에서 데이터를 바라보는 모델들을 모아야, 한 모델이 실수했을 때 다른 모델이 이를 바로잡아줄 수 있습니다. 즉, **"개별 모델의 오차를 서로 상쇄시켜 전체의 일반화 성능을 높이는 것"**이 앙상블의 핵심 직관입니다.

---

### 3. 기술 설명

#### ① 배깅 (Bagging = Bootstrap Aggregating)
배깅은 여러 모델을 **"병렬적"**으로 학습시켜 결과의 평균을 내는 방식입니다.

* **부트스트랩(Bootstrap):** 전체 데이터셋에서 중복을 허용하여 무작위로 샘플을 뽑아 여러 개의 서로 다른 데이터셋을 만듭니다. 이를 통해 각 모델이 서로 다른 데이터를 학습하게 하여 '다양성'을 확보합니다.
* **어그리게이팅(Aggregating):** 학습된 모델들의 예측 결과를 **투표(Voting)**하거나 **평균**내어 최종 결정합니다.
* **Random Forest:** 배깅의 결정판입니다. 데이터뿐만 아니라 **'특성(Feature)'까지 무작위로 선택**하여 트리를 구성합니다. 이는 특정 강력한 특성에만 의존하는 것을 방지하여 트리 간의 상관관계를 낮추고, 과적합(Overfitting)을 획기적으로 줄입니다.

#### ② 부스팅 (Boosting)
부스팅은 모델을 **"순차적"**으로 학습시키며 이전 모델의 실수를 보완하는 방식입니다.

* **오차 수정 및 가중치:** 첫 번째 모델이 예측하고 틀린 데이터에 대해 더 높은 **가중치**를 부여합니다. 두 번째 모델은 이 '어려운 데이터'를 맞히는 데 집중합니다.
* **잔차 학습(Residual Learning):** 최신 부스팅(Gradient Boosting)은 이전 모델이 예측하고 남은 **잔차(Residual, 실제값 - 예측값)**를 다음 모델이 학습하여 오차를 점진적으로 줄여나갑니다.
* **XGBoost (Extreme Gradient Boosting):** Gradient Boosting을 극도로 최적화한 모델입니다. 시스템 최적화(병렬 처리)를 통해 계산 속도를 높였으며, 자체적으로 과적합을 방지하는 **규제(Regularization)** 기능이 포함되어 있어 실무와 경진대회에서 가장 널리 쓰입니다.

**[배깅 vs 부스팅 비교 요약]**

| 구분 | 배깅 (Random Forest) | 부스팅 (XGBoost) |
| :--- | :--- | :--- |
| **학습 방식** | 병렬적 (독립적 학습) | 순차적 (이전 모델 보완) |
| **핵심 목표** | **분산(Variance) 감소** $\rightarrow$ 과적합 방지 | **편향(Bias) 감소** $\rightarrow$ 정확도 향상 |
| **장점** | 안정적, 하이퍼파라미터 튜닝이 쉬움 | 매우 강력한 예측 성능, 정밀함 |
| **단점** | 부스팅에 비해 정확도가 낮을 수 있음 | 튜닝이 까다롭고 과적합 위험이 있음 |

---

### 4. 파이썬 코드 실습

단일 결정 트리, Random Forest, XGBoost의 성능을 실제 데이터셋으로 비교해 보겠습니다.

```python
import pandas as pd
import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score

# 1. 데이터 로드 (유방암 진단 데이터셋: 이진 분류 문제)
data = load_breast_cancer()
X = pd.DataFrame(data.data, columns=data.feature_names)
y = data.target

# 2. 학습/테스트 데이터 분리 (8:2 비율)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 3. 모델 정의
models = {
    "Decision Tree": DecisionTreeClassifier(random_state=42),
    "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
    "XGBoost": XGBClassifier(n_estimators=100, learning_rate=0.1, random_state=42, 
                             eval_metric='logloss')
}

# 4. 모델 학습 및 평가 수행
results = {}
for name, model in models.items():
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    results[name] = acc
    print(f"{name} 정확도: {acc:.4f}")

# 결과 비교 데이터프레임 생성
df_results = pd.DataFrame.from_dict(results, orient='index', columns=['Accuracy'])
print("\n[최종 성능 비교]")
print(df_results)
```

---

### 5. 실행 결과 및 해석

**예상 출력 결과:**
```text
Decision Tree 정확도: 0.9386
Random Forest 정확도: 0.9649
XGBoost 정확도: 0.9737

[최종 성능 비교]
               Accuracy
Decision Tree  0.9386
Random Forest  0.9649
XGBoost       0.9737
```

**결과 해석:**
1. **Decision Tree (단일 모델):** 세 모델 중 가장 낮은 성능을 보입니다. 이는 단일 트리가 학습 데이터의 노이즈까지 학습하여 과적합될 가능성이 높기 때문입니다.
2. **Random Forest (배깅):** 단일 트리보다 성능이 향상되었습니다. 100개의 트리가 각자 다른 데이터와 특성으로 학습하고 다수결로 결정했기에, 개별 트리의 '튀는 예측(오류)'이 서로 상쇄된 결과입니다.
3. **XGBoost (부스팅):** 가장 높은 정확도를 기록했습니다. 앞선 트리들이 해결하지 못한 오차(잔차)를 다음 트리가 계속해서 정밀하게 보완하며 학습했기 때문에, 데이터의 복잡한 패턴을 가장 정확하게 포착해낸 것입니다.

---

### 6. 실무 활용 사례

* **금융권 신용 평가 및 이상 거래 탐지(FDS):** 단 한 번의 오판이 큰 금전적 손실로 이어지는 분야입니다. 매우 높은 정밀도가 요구되므로 **XGBoost**나 **LightGBM** 같은 부스팅 모델을 사용하여 예측력을 극대화합니다.
* **이커머스 고객 이탈 예측:** 수많은 변수가 존재하는 고객 데이터에서 빠르게 베이스라인 모델을 구축하고, 과적합 여부를 판단하기 위해 **Random Forest**를 먼저 적용하여 안정적인 성능 지표를 확인합니다.
* **캐글(Kaggle) 등 데이터 경진대회:** 정형 데이터(Tabular Data) 문제의 상위권 솔루션은 대부분 XGBoost, LightGBM, CatBoost를 적절히 섞어서 사용하는 **'앙상블 스태킹(Stacking)'** 기법을 사용합니다.

---

### 7. 자주 하는 실수

**❌ "성능이 무조건 좋으니 항상 XGBoost만 쓰겠다!"**
* **해결:** XGBoost는 강력하지만 하이퍼파라미터 튜닝에 많은 시간이 소요됩니다. 또한 데이터 양이 매우 적을 때는 오히려 Random Forest가 더 일반화 성능이 좋을 수 있습니다. 데이터의 크기와 튜닝 가능 시간을 고려하여 선택하세요.

**❌ "모델 개수(`n_estimators`)를 무조건 늘리면 성능이 올라간다!"**
* **해결:** Random Forest는 트리를 늘릴수록 성능이 수렴하며 안정화되지만, XGBoost는 트리를 너무 많이 늘리면 학습 데이터에 과하게 최적화되어 **과적합(Overfitting)**이 발생합니다. 반드시 `early_stopping` 기능을 사용하여 검증 오차가 증가하기 전의 최적 지점에서 학습을 멈춰야 합니다.

---

### 8. 핵심 요약

1. **앙상블**은 여러 개의 약한 학습기를 결합해 하나의 강한 학습기를 만드는 전략이다.
2. **배깅(Bagging)** $\rightarrow$ **Random Forest**: 병렬 학습 $\rightarrow$ 다수결/평균 $\rightarrow$ **분산 감소 및 과적합 방지**.
3. **부스팅(Boosting)** $\rightarrow$ **XGBoost**: 순차 학습 $\rightarrow$ 오차(잔차) 보완 $\rightarrow$ **편향 감소 및 성능 극대화**.
4. **모델 선택 기준**: 빠른 구축과 안정성이 중요하다면 **Random Forest**, 극한의 예측 성능이 필요하다면 **XGBoost**.

---

### 9. 확인 문제 및 정답

**Q. Random Forest와 XGBoost의 학습 방식 차이점을 '데이터 학습 순서'와 '오차 처리 방식'의 관점에서 설명하시오.**

**정답:**
* **학습 순서:** Random Forest는 여러 개의 트리를 **동시에(병렬적으로)** 독립적으로 학습시키지만, XGBoost는 트리를 **하나씩 순서대로(순차적으로)** 학습시킵니다.
* **오차 처리 방식:** Random Forest는 각 트리가 독립적으로 예측한 후 그 결과들을 **평균 내거나 투표**하여 개별 모델의 변동성(분산)을 줄임으로써 오차를 낮춥니다. 반면, XGBoost는 이전 트리가 예측하고 남은 **오차(잔차)를 다음 트리가 집중적으로 학습**하는 방식으로 오차를 점진적으로 줄여나갑니다.

---

### 10. 미니 프로젝트: "최적의 앙상블 모델 찾기"

**미션:** 사이킷런의 `load_wine` 또는 `load_digits` 데이터셋을 활용하여 아래 프로세스를 수행하고 최적의 모델을 선정하세요.

1. **단일 결정 트리**의 정확도를 측정하여 기준점(Baseline)을 잡으세요.
2. **Random Forest**의 `n_estimators`를 $[10, 100, 1000]$으로 변경하며 성능 변화와 학습 시간의 관계를 관찰하세요.
3. **XGBoost**의 `learning_rate`를 $[0.01, 0.1, 0.3]$으로 변경하며 어떤 값이 가장 높은 성능을 내는지 찾으세요.
4. **최종 보고서 작성:** 이 데이터셋에 가장 적합한 모델은 무엇인지, 그리고 '학습 시간 대비 정확도(Trade-off)' 관점에서 그 이유를 서술하세요.