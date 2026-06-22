# 12. 앙상블과 실전 머신러닝

## 이번 장에서 배우는 내용

단일 모델 하나만으로는 해결하기 어려운 복잡한 문제들이 있습니다. 이번 장에서는 여러 개의 모델을 결합해 더 강력한 예측력을 만들어내는 '앙상블(Ensemble)' 기법을 배웁니다.

- **앙상블 학습의 기본 원리**: 왜 여러 모델을 합치면 성능이 올라가는지 이해합니다.
- **배깅(Bagging)과 랜덤 포레스트**: 무작위 샘플링을 통해 모델의 분산을 줄이고 과적합을 방지하는 방법을 배웁니다.
- **부스팅(Boosting)과 XGBoost**: 잔차 학습을 통해 틀린 문제에 집중하며 성능을 끌어올리는 순차적 학습 방식을 배웁니다.
- **실전 구현 및 비교**: 단일 모델과 앙상블 모델의 성능 차이를 직접 확인하고 경향성을 분석합니다.
- **특성 중요도 분석**: 모델이 어떤 데이터를 중요하게 생각했는지 분석하여 데이터 인사이트를 도출하는 방법을 익힙니다.

---

## 집단지성의 힘: 앙상블 학습의 개념

### 실생활 비유: 전문가 위원회의 결정
어떤 어려운 문제를 해결해야 한다고 가정해 봅시다. 한 명의 천재적인 전문가에게 답을 묻는 것도 좋지만, 때로는 여러 명의 평범한 전문가들이 모여 토론하고 다수결로 결정하는 것이 훨씬 더 정확할 때가 많습니다. 한 사람이 가진 편견이나 실수(오류)를 다른 사람들이 보완해주기 때문입니다.

### 개념 설명
머신러닝에서도 이와 같은 **'집단지성'**의 원리를 적용한 것이 바로 **앙상블(Ensemble)**입니다. 앙상블은 하나의 강력한 모델을 만드는 대신, 여러 개의 '약한 학습기(Weak Learner)'를 조합하여 하나의 '강한 학습기(Strong Learner)'를 만드는 기법입니다.

### 기술 설명
앙상블의 핵심 아이디어는 **다양성(Diversity)**과 **결합(Combination)**입니다.

1.  **다양성**: 모든 모델이 똑같이 예측한다면 합치는 의미가 없습니다. 서로 다른 데이터를 학습하거나, 서로 다른 알고리즘을 사용하여 모델들이 각기 다른 관점에서 데이터를 바라보게 해야 합니다.
2.  **결합**: 이렇게 만들어진 여러 모델의 예측 결과를 하나로 합칩니다. 분류 문제에서는 '다수결(Voting)' 방식을, 회귀 문제에서는 '평균(Averaging)' 방식을 주로 사용합니다.

---

## 배깅(Bagging): 무작위로 샘플링하여 분산을 줄여 과적합을 방지하는 방법

### 실생활 비유: 서로 다른 참고서를 본 학생들
시험 공부를 할 때, 한 권의 완벽한 교과서만 판 학생은 그 교과서에만 나온 특이한 유형의 문제에 과하게 집착할 수 있습니다. 이를 머신러닝에서는 '과적합'이라고 합니다. 반면, 여러 명의 학생이 각자 조금씩 다른 참고서를 공부한 뒤 서로 의견을 교환한다면, 특정 참고서의 오류나 편향에 빠지지 않고 더 일반적인 정답을 찾아낼 수 있을 것입니다.

### 개념 설명
**배깅(Bagging)**은 'Bootstrap Aggregating'의 줄임말입니다. 전체 데이터셋에서 무작위로 샘플을 뽑아 여러 개의 작은 데이터셋을 만들고, 각각의 데이터셋으로 모델을 학습시킨 뒤 그 결과를 합치는 방식입니다.

여기서 중요한 개념이 **'편향-분산 트레이드오프'**입니다.
- **편향(Bias)**: 모델이 너무 단순해서 데이터의 본질적인 패턴을 잡지 못하는 상태 (과소적합)
- **분산(Variance)**: 모델이 너무 복잡해서 훈련 데이터의 작은 노이즈까지 학습해버리는 상태 (과적합)

배깅의 핵심 목적은 바로 이 **분산(Variance)을 줄이는 것**입니다. 여러 모델의 예측값을 평균 내어 특정 데이터에 지나치게 민감하게 반응하는 것을 막는 원리입니다.

### 기술 설명
- **부트스트랩(Bootstrap) 샘플링**: 중복을 허용하여 무작위로 데이터를 추출하는 방식입니다. 이를 통해 각 모델은 전체 데이터의 조금씩 다른 부분을 학습하게 됩니다.
- **랜덤 포레스트(Random Forest)**: 배깅의 가장 대표적인 알고리즘입니다. 수많은 **결정 트리(Decision Tree)**를 만들고, 그 트리들의 예측 결과를 다수결로 통합합니다. 
    - 단순히 데이터만 무작위로 뽑는 것이 아니라, 트리를 만들 때 사용할 **특성(Feature)까지 무작위로 선택**하여 모델 간의 다양성을 극대화합니다.
- **핵심 효과**: 특정 데이터나 특성에 지나치게 의존하는 것을 막아주므로, 단일 결정 트리의 최대 약점인 **과적합(Overfitting)을 효과적으로 방지**합니다.

---

## 부스팅(Boosting): 틀린 문제에 집중하여 점수를 올리는 방법

### 실생활 비유: 오답 노트 작성법
공부를 잘하는 학생들의 비결 중 하나는 '오답 노트'입니다. 처음 문제를 풀고 틀린 문제들을 따로 모아, 왜 틀렸는지 집중적으로 분석하고 다시 공부합니다. 이렇게 '부족한 부분'을 계속해서 보완해 나가면 결국 모든 문제를 맞힐 수 있게 됩니다.

### 개념 설명
**부스팅(Boosting)**은 배깅처럼 동시에 여러 모델을 만드는 것이 아니라, **순차적(Sequential)**으로 모델을 만듭니다. 첫 번째 모델이 틀린 데이터에 대해 가중치를 높여, 두 번째 모델이 그 틀린 부분을 더 잘 맞추도록 학습시키는 방식입니다. 즉, 배깅이 분산을 줄이는 데 집중한다면, 부스팅은 **편향(Bias)을 줄여 예측 성능을 극대화**하는 데 집중합니다.

### 기술 설명
- **순차적 학습과 잔차(Residual)**: $\text{모델 1} \rightarrow \text{모델 2} \rightarrow \text{모델 3} \dots$ 순으로 학습합니다. 핵심은 앞선 모델이 예측한 값과 실제 정답 사이의 차이인 **'잔차(Residual)'**를 다음 모델의 학습 목표로 삼는 것입니다.
    - **예시**: 실제 집값이 **100**인데 모델 1이 **80**으로 예측했다면, 잔차는 **20**이 됩니다. 이때 모델 2는 '100'을 맞추는 것이 아니라, 모델 1이 놓친 **'20'이라는 오차를 예측하도록** 학습합니다. 이렇게 앞선 모델들이 해결하지 못한 '남은 오차'를 다음 모델이 계속해서 메꾸는 방식입니다.
- **XGBoost (Extreme Gradient Boosting)**: 현재 실무와 캐글(Kaggle) 같은 경진대회에서 가장 사랑받는 부스팅 알고리즘입니다. 
    - **정규화(Regularization)**: 모델이 학습 데이터에 너무 과하게 집착하여 복잡해지지 않도록 가중치에 '페널티'를 주는 장치입니다. 구체적으로 **L1, L2 정규화** 기법을 사용하여 불필요한 가지를 쳐내고(Pruning) 모델을 단순하게 유지함으로써, 부스팅의 고질적인 문제인 과적합을 효과적으로 억제합니다.
    - 병렬 처리 최적화가 잘 되어 있어 학습 속도가 매우 빠릅니다.
- **배깅 vs 부스팅 차이점**

| 구분 | 배깅 (Bagging) | 부스팅 (Boosting) |
| :--- | :--- | :--- |
| **학습 방식** | 병렬적 (동시에 여러 모델 학습) | 순차적 (앞선 모델의 오차/잔차 보완) |
| **목적** | 분산 감소 $\rightarrow$ 과적합 방지 | 편향 감소 $\rightarrow$ 예측 성능 극대화 |
| **특징** | 안정적이며 구현이 쉬움 | 매우 강력하지만 과적합 위험이 있음 |
| **대표 모델** | 랜덤 포레스트 (Random Forest) | XGBoost, LightGBM, CatBoost |

---

## 실전! 앙상블 모델로 성능 끌어올리기

이제 실제로 단일 결정 트리와 앙상블 모델(랜덤 포레스트, XGBoost)의 성능을 비교해 보겠습니다. 유방암 진단 데이터셋을 활용하여 암 여부를 예측하는 분류기를 만들어 보겠습니다.

### 파이썬 코드 실습

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score

# 1. 데이터 로드 및 준비
data = load_breast_cancer()
X = pd.DataFrame(data.data, columns=data.feature_names)
y = data.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 2. 모델 정의
models = {
    "단일 결정 트리": DecisionTreeClassifier(random_state=42),
    "랜덤 포레스트 (Bagging)": RandomForestClassifier(n_estimators=100, random_state=42),
    "XGBoost (Boosting)": XGBClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
}

# 3. 모델 학습 및 성능 평가
results = {}
for name, model in models.items():
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    acc = accuracy_score(y_test, pred)
    results[name] = acc
    print(f"{name} 정확도: {acc:.4f}")

# 4. 결과 비교 시각화
print("\n--- 최종 성능 비교 ---")
for name, acc in results.items():
    print(f"{name}: {acc:.4f}")
```

### 실행 결과 해설
코드를 실행하면 환경이나 무작위 시드(`random_state`)에 따라 수치에 차이가 있을 수 있으나, 일반적인 경향성은 다음과 같습니다.

- **단일 결정 트리 (약 93% 내외)** $\rightarrow$ 학습 데이터에 너무 최적화되어 테스트 데이터에서는 성능이 상대적으로 낮게 나타나는 경향이 있습니다.
- **랜덤 포레스트 (약 96% 내외)** $\rightarrow$ 여러 트리의 의견을 종합하여 단일 트리보다 훨씬 안정적이고 일반화 성능이 높게 나타납니다.
- **XGBoost (약 97% 내외)** $\rightarrow$ 잔차를 학습하며 정밀하게 보완해 나가므로 가장 높은 예측력을 보여주는 경우가 많습니다.

**결론적으로, 단일 모델보다는 앙상블 모델이 데이터의 복잡한 패턴을 더 잘 잡아내며 월등한 예측 성능을 보여주는 경향이 있습니다.**

---

## 앙상블 모델의 해석력과 중요도

앙상블 모델의 큰 장점 중 하나는 **'어떤 특성이 예측에 중요하게 작용했는가'**를 수치로 알려준다는 점입니다. 이를 **특성 중요도(Feature Importance)**라고 합니다.

단일 트리는 가지가 뻗어 나가는 모양을 직접 그려서 볼 수 있지만, 앙상블 모델은 수백 개의 트리가 섞여 있어 그림으로 볼 수 없습니다. 대신, 각 특성이 불순도를 얼마나 많이 낮췄는지를 수치화하여 제공합니다.

### 특성 중요도 분석 실습 코드

```python
# XGBoost 모델의 특성 중요도 추출 및 시각화
xgb_model = XGBClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
xgb_model.fit(X_train, y_train)

# 특성 중요도 가져오기
importances = xgb_model.feature_importances_
feature_df = pd.DataFrame({'Feature': X.columns, 'Importance': importances})
feature_df = feature_df.sort_values(by='Importance', ascending=False).head(5)

# 시각화
plt.figure(figsize=(10, 6))
plt.barh(feature_df['Feature'], feature_df['Importance'], color='skyblue')
plt.xlabel('Importance')
plt.title('Top 5 Important Features (XGBoost)')
plt.gca().invert_yaxis()
plt.show()

print(feature_df)
```

### 데이터 인사이트 도출하기
이 수치는 단순히 모델의 성능을 확인하는 것을 넘어 매우 중요한 비즈니스 가치를 제공합니다. 우리는 이 분석을 통해 "암 진단에 있어서 어떤 지표(예: 최악 면적, 최악 반지름 등)가 가장 결정적인 요인이었는가"를 정량적으로 파악할 수 있습니다.

단순히 예측만 하는 것이 아니라, 어떤 변수가 결과에 결정적인 영향을 주었는지 분석함으로써 **도메인 지식을 발견**하고, 이를 바탕으로 **구체적인 비즈니스 전략이나 의료 가이드라인을 세우는 등** 실질적인 인사이트를 얻을 수 있습니다.

---

## 실무 활용 사례

앙상블 모델은 높은 예측력 덕분에 실제 산업 현장에서 매우 광범위하게 사용됩니다.

1.  **랜덤 포레스트 (금융권 신용 평가)**: 고객의 소득, 직업, 기존 대출 이력 등 수많은 변수를 종합하여 대출 승인 여부를 결정합니다. 특정 변수 하나에 휘둘리지 않고 안정적인 판단을 내려야 하는 신용 평가 모델에 적합합니다.
2.  **XGBoost (이커머스 고객 이탈 예측)**: 고객의 접속 빈도, 구매 주기, 장바구니 담기 횟수 등을 분석해 이탈 가능성이 높은 고객을 정밀하게 찾아냅니다. 아주 작은 패턴의 차이로 성능이 갈리는 타겟 마케팅이나 추천 시스템의 랭킹 모델에서 주로 사용됩니다.

---

## 앙상블 모델 사용 시 주의사항과 실수

성능이 좋다고 해서 무조건 앙상블 모델만 사용하는 것이 정답은 아닙니다.

1.  **연산 비용의 증가**: 모델 하나를 돌릴 때보다 수백 개의 모델을 돌려야 하므로 학습 시간과 메모리 사용량이 크게 증가합니다. 실시간 응답이 중요한 시스템에서는 부담이 될 수 있습니다.
2.  **블랙박스(Black Box) 특성**: 모델이 '왜' 그런 결과를 내놓았는지 논리적으로 설명하기가 매우 어렵습니다. 의료나 금융처럼 '설명 가능성'이 중요한 분야에서는 단일 트리나 선형 모델이 더 선호될 수 있습니다.
3.  **부스팅 모델의 과적합 위험**: 부스팅은 오답(잔차)에 계속 집중하기 때문에, 학습 데이터의 노이즈(이상치)까지 학습해버릴 위험이 있습니다. 따라서 `learning_rate`(학습률)나 `max_depth`(트리 깊이) 같은 하이퍼파라미터 튜닝에 매우 민감하므로 주의가 필요합니다.

---

## 핵심 요약
- **앙상블**은 여러 약한 모델을 결합해 강한 모델을 만드는 집단지성 기법이다.
- **배깅(Bagging)**은 무작위 샘플링을 통해 **분산을 줄여 과적합을 방지**하며, 대표적으로 **랜덤 포레스트**가 있다.
- **부스팅(Boosting)**은 잔차를 학습하며 순차적으로 오차를 보완해 **편향을 줄이고 성능을 극대화**하며, 대표적으로 **XGBoost**가 있다.
- 앙상블 모델은 성능은 뛰어나지만 **연산 비용이 높고 해석력이 낮아지는** 트레이드-오프가 존재한다.

## 확인 문제
1. 배깅과 부스팅의 가장 근본적인 학습 방식의 차이는 무엇인가요?
2. 랜덤 포레스트가 단일 결정 트리보다 과적합에 강한 이유는 무엇인가요?
3. XGBoost 모델을 사용할 때, 학습 데이터에 너무 과하게 최적화되었다면 어떤 조치를 취해야 할까요?

**정답 및 해설**
1. 배깅은 여러 모델을 독립적으로 동시에 학습시키는 병렬 방식이고, 부스팅은 이전 모델의 오차(잔차)를 보완하며 순차적으로 학습시키는 방식입니다.
2. 부트스트랩 샘플링과 특성 무작위 선택을 통해 모델 간의 다양성을 확보하고, 이들의 결과를 평균/다수결로 합쳐 특정 데이터에 대한 의존도(분산)를 낮추기 때문입니다.
3. 학습률(`learning_rate`)을 낮추거나, 트리의 최대 깊이(`max_depth`)를 제한하거나, 내장된 정규화 파라미터를 조정하여 모델의 복잡도를 낮춰야 합니다.

## 미니 프로젝트: 우리 동네 집값 예측 앙상블 모델 만들기

**목표**: Scikit-learn에서 제공하는 **California Housing dataset**을 활용하여 단일 결정 트리, 랜덤 포레스트, XGBoost 모델의 예측 성능(RMSE)을 비교하고, 집값에 가장 큰 영향을 주는 상위 5개 특성을 찾아 리포트를 작성해 보세요.

**가이드라인 및 실습 팁**:
1. **데이터 로드**: `from sklearn.datasets import fetch_california_housing`를 사용하여 데이터를 불러오세요.
2. **전처리**: 데이터를 훈련 세트와 테스트 세트로 분리하세요.
3. **모델 학습**: 
    - `DecisionTreeRegressor`
    - `RandomForestRegressor`
    - `XGBRegressor` 세 가지 모델을 각각 학습시키세요.
4. **성능 평가**: `mean_squared_error`를 사용하여 RMSE(Root Mean Squared Error)를 계산하고 어떤 모델이 가장 오차가 적은지 비교하세요.
5. **분석**: `feature_importances_`를 통해 집값에 가장 큰 영향을 주는 변수(예: 소득 수준, 집의 연식 등) 상위 5개를 시각화하세요.

**시작 코드 예시**:
```python
from sklearn.datasets import fetch_california_housing
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor

# 데이터 로드
housing = fetch_california_housing()
X, y = housing.data, housing.target

# 이후 과정은 위에서 배운 파이프라인(분리 -> 학습 -> 평가 -> 분석)을 적용해 보세요!
```