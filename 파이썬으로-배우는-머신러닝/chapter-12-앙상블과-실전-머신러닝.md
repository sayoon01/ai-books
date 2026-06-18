# 챕터 12: 앙상블과 실전 머신러닝

# 12장. 앙상블과 실전 머신러닝

단일 모델만으로는 해결하기 어려운 복잡한 문제들이 있습니다. 아무리 뛰어난 전문가라도 혼자서는 놓치는 부분이 있듯이, 머신러닝 모델 하나만으로는 데이터의 모든 패턴을 완벽하게 잡아내기 어렵습니다. 이때 필요한 것이 바로 '앙상블(Ensemble)'입니다. 앙상블은 여러 개의 모델을 결합하여 더 강력한 하나의 모델을 만드는 기법입니다.

## 1. 앙상블의 개념: 집단지성의 힘

### 비유: 심사위원단의 판정
우리가 오디션 프로그램을 본다고 가정해 봅시다. 단 한 명의 심사위원이 합격 여부를 결정한다면, 그 심사위원의 개인적인 취향이나 편견이 결과에 큰 영향을 미칠 것입니다. 하지만 10명의 심사위원이 각각 점수를 매기고 그 평균값으로 합격자를 결정한다면 어떨까요? 특정 심사위원이 너무 엄격하거나 관대하더라도, 다른 심사위원들의 의견이 이를 보완하여 훨씬 객관적이고 정확한 판정이 내려질 가능성이 높습니다.

### 직관: 왜 여러 모델을 합치는가?
머신러닝 모델에는 항상 '편향(Bias)'과 '분산(Variance)'이라는 두 가지 숙제가 있습니다. 
- **편향**은 모델이 너무 단순해서 정답을 제대로 맞히지 못하는 상태(과소적합)를 말합니다.
- **분산**은 모델이 학습 데이터에 너무 과하게 최적화되어 새로운 데이터에서는 엉뚱한 답을 내놓는 상태(과적합)를 말합니다.

앙상블의 핵심 아이디어는 **"서로 다른 약점을 가진 모델들을 모아 그들의 예측값을 평균내거나 투표하게 함으로써, 개별 모델이 가진 오차를 상쇄시키는 것"**입니다.

### 기술 설명: 앙상블의 주요 전략
앙상블 기법은 크게 세 가지 방향으로 나뉩니다.

1.  **배깅(Bagging - Bootstrap Aggregating):** 같은 알고리즘의 모델을 여러 개 만들되, 학습 데이터셋을 서로 다르게 구성하여 병렬적으로 학습시킨 후 결과를 합치는 방식입니다. (예: Random Forest)
2.  **부스팅(Boosting):** 모델을 순차적으로 학습시킵니다. 첫 번째 모델이 틀린 부분을 두 번째 모델이 집중적으로 학습하고, 또 그 틀린 부분을 세 번째 모델이 보완하는 방식입니다. (예: XGBoost, LightGBM)
3.  **스태킹(Stacking):** 서로 다른 종류의 모델(예: SVM, KNN, Decision Tree)들을 학습시킨 뒤, 그 예측값들을 다시 입력 데이터로 사용하여 최종 모델(Meta Learner)이 정답을 예측하게 하는 방식입니다.

---

## 2. 랜덤 포레스트(Random Forest): 든든한 나무들의 숲

### 비유: 전문가 집단의 다수결 투표
결정 트리(Decision Tree) 하나가 '나무'라면, 랜덤 포레스트는 수많은 결정 트리가 모인 '숲'입니다. 각 나무는 데이터의 일부만을 보고 판단을 내립니다. 어떤 나무는 나이와 수입에 집중하고, 어떤 나무는 거주지와 직업에 집중합니다. 이렇게 서로 다른 관점을 가진 나무들이 각자 예측값을 내놓으면, 최종적으로 가장 많은 표를 얻은 결과(다수결)를 선택합니다.

### 직관: 무작위성의 마법
결정 트리는 매우 강력하지만, 학습 데이터에 너무 민감하게 반응하여 과적합(Overfitting)이 일어나기 쉽다는 치명적인 단점이 있습니다. 랜덤 포레스트는 이 문제를 두 가지 '무작위성'으로 해결합니다.
1.  **데이터의 무작위성(Bootstrapping):** 전체 데이터에서 중복을 허용하여 무작위로 샘플을 뽑아 각 나무에게 줍니다. 나무마다 공부하는 교과서의 페이지가 조금씩 다른 셈입니다.
2.  **특성의 무작위성(Feature Randomness):** 나무가 가지를 칠 때 모든 특성을 고려하는 것이 아니라, 무작위로 선택된 일부 특성들 중에서 최적의 분할 기준을 찾습니다. 특정 강력한 특성 하나에 모든 나무가 의존하는 것을 방지하기 위함입니다.

### 기술 설명: 랜덤 포레스트의 작동 원리
- **학습 단계:** 
    1. 전체 데이터셋에서 중복 추출(Bootstrap)을 통해 $N$개의 서로 다른 학습 세트를 만듭니다.
    2. 각 세트에 대해 결정 트리를 학습시킵니다. 이때 각 노드에서 분할에 사용할 특성을 무작위로 선택합니다.
- **예측 단계:** 
    - 분류(Classification) 문제 $\rightarrow$ 각 트리의 예측값 중 최빈값(Majority Vote)을 선택합니다.
    - 회귀(Regression) 문제 $\rightarrow$ 각 트리의 예측값의 평균(Average)을 계산합니다.

#### [도식 설명: 랜덤 포레스트 구조]
- **Input Data** $\rightarrow$ (Bootstrapping) $\rightarrow$ **[Tree 1, Tree 2, ..., Tree N]** $\rightarrow$ (Voting/Average) $\rightarrow$ **Final Prediction**
- 각 Tree는 서로 다른 데이터 샘플과 서로 다른 특성 조합을 사용함을 시각적으로 표현합니다.

### 실습: 랜덤 포레스트로 붓꽃(Iris) 분류하기

이제 `scikit-learn`을 사용하여 랜덤 포레스트 모델을 구현해 보겠습니다. 단일 결정 트리와 성능을 비교하여 앙상블의 효과를 확인해 봅시다.

```python
import numpy as np
import pandas as pd
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# 1. 데이터 로드 및 준비
iris = load_iris()
X = iris.data
y = iris.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)

# 2. 단일 결정 트리 모델 생성 및 평가
dt_model = DecisionTreeClassifier(random_state=42)
dt_model.fit(X_train, y_train)
dt_pred = dt_model.predict(X_test)
dt_acc = accuracy_score(y_test, dt_pred)

# 3. 랜덤 포레스트 모델 생성 및 평가
# n_estimators: 만들 나무의 개수
rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
rf_model.fit(X_train, y_train)
rf_pred = rf_model.predict(X_test)
rf_acc = accuracy_score(y_test, rf_pred)

print(f"단일 결정 트리 정확도: {dt_acc:.4f}")
print(f"랜덤 포레스트 정확도: {rf_acc:.4f}")

# 특성 중요도 확인
import matplotlib.pyplot as plt
import seaborn as sns

importances = rf_model.feature_importances_
feature_names = iris.feature_names
feature_importance_df = pd.DataFrame({'Feature': feature_names, 'Importance': importances})
feature_importance_df = feature_importance_df.sort_values(by='Importance', ascending=False)

plt.figure(figsize=(8, 5))
sns.barplot(x='Importance', y='Feature', data=feature_importance_df)
plt.title('Feature Importances in Random Forest')
plt.show()
```

#### 코드 결과 및 해석
- **실행 결과:** 일반적으로 `랜덤 포레스트 정확도`가 `단일 결정 트리 정확도`보다 높거나 비슷하게 나옵니다. 데이터셋이 작을 때는 차이가 적을 수 있지만, 복잡한 데이터일수록 랜덤 포레스트의 안정성이 빛을 발합니다.
- **특성 중요도(Feature Importance):** 랜덤 포레스트는 어떤 특성이 예측에 가장 큰 영향을 주었는지 알려주는 기능을 제공합니다. 위 그래프에서 가장 긴 막대를 가진 특성이 모델이 판단을 내릴 때 가장 중요하게 생각한 기준입니다.

---

## 3. XGBoost: 오답 노트를 활용한 정밀 학습

### 비유: 오답 노트를 쓰는 학생
랜덤 포레스트가 여러 명의 학생이 동시에 시험을 보고 다수결로 답을 정하는 방식이라면, XGBoost는 한 명의 학생이 시험을 보고, 틀린 문제를 오답 노트에 적어 집중 공부한 뒤 다시 시험을 치는 과정을 반복하는 방식입니다.
- **1차 시험:** 기본 모델이 예측을 수행합니다. (당연히 많이 틀립니다.)
- **오답 노트 작성:** 실제 정답과 예측값의 차이(잔차, Residual)를 계산합니다.
- **2차 시험:** "어떻게 하면 이 오차를 줄일 수 있을까?"에 집중해서 새로운 모델을 학습시켜 기존 모델에 더합니다.
- **반복:** 이 과정을 수백 번 반복하여 오차를 극한으로 줄입니다.

### 직관: 점진적인 개선 (Gradient Boosting)
XGBoost의 핵심은 '그라디언트 부스팅(Gradient Boosting)'입니다. 여기서 '그라디언트'는 수학적으로 경사 하강법을 의미하며, 쉽게 말해 **"정답과의 거리(손실 함수)를 줄이는 방향으로 모델을 계속 업데이트한다"**는 뜻입니다. 

XGBoost(Extreme Gradient Boosting)는 기존의 부스팅 알고리즘을 극도로 최적화하여 다음과 같은 강점을 가집니다.
1.  **속도:** 병렬 처리를 지원하여 매우 빠릅니다.
2.  **규제(Regularization):** 모델이 너무 복잡해지지 않도록 제어하는 기능이 있어 과적합을 효과적으로 방지합니다.
3.  **결측치 처리:** 데이터에 빈 값이 있어도 스스로 처리하는 알고리즘이 내장되어 있습니다.

### 기술 설명: XGBoost의 핵심 메커니즘
- **잔차 학습:** $Y_{new} = Y_{old} + \text{Learning Rate} \times \text{New Model}(\text{Residuals})$
- **학습률(Learning Rate):** 새로운 모델이 정답에 너무 급격하게 다가가지 않도록 조절하는 값입니다. 너무 크면 정답을 지나칠 수 있고(Overshooting), 너무 작으면 학습 시간이 너무 오래 걸립니다.
- **조기 종료(Early Stopping):** 검증 데이터의 성능이 더 이상 좋아지지 않으면 학습을 자동으로 멈춰 과적합을 막습니다.

### 실습: XGBoost로 고객 이탈 예측하기

이번에는 실무에서 많이 쓰이는 '고객 이탈 예측' 가상 시나리오를 통해 XGBoost를 적용해 보겠습니다.

```python
# XGBoost 라이브러리 설치 필요: pip install xgboost
import xgboost as xgb
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

# 1. 가상 데이터 생성 (고객 1000명, 특성 20개)
X, y = make_classification(
    n_samples=1000, n_features=20, 
    n_informative=15, random_state=42
)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 2. XGBoost 모델 생성
# n_estimators: 반복 횟수 (오답 노트 횟수)
# learning_rate: 학습률 (보폭)
# max_depth: 각 나무의 최대 깊이
xgb_model = xgb.XGBClassifier(
    n_estimators=100, 
    learning_rate=0.1, 
    max_depth=5, 
    random_state=42,
    use_label_encoder=False,
    eval_metric='logloss'
)

# 3. 모델 학습
xgb_model.fit(X_train, y_train)

# 4. 예측 및 평가
y_pred = xgb_model.predict(X_test)

print("--- XGBoost 성능 평가 ---")
print(classification_report(y_test, y_pred))

# 혼동 행렬 시각화
import matplotlib.pyplot as plt
import seaborn as sns

cm = confusion_matrix(y_test, y_pred)
plt.figure(figsize=(6, 4))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
plt.xlabel('Predicted')
plt.ylabel('Actual')
plt.title('Confusion Matrix - XGBoost')
plt.show()
```

#### 코드 결과 및 해석
- **Classification Report:** Precision(정밀도), Recall(재현율), F1-Score를 통해 모델의 성능을 다각도로 분석할 수 있습니다. 특히 이탈 예측에서는 '이탈할 사람을 놓치지 않는 것(Recall)'이 중요하므로 이 지표를 유심히 살펴야 합니다.
- **Confusion Matrix:** 
    - **True Positive(TP):** 이탈할 사람을 이탈한다고 잘 맞힘.
    - **False Positive(FP):** 유지할 사람을 이탈한다고 잘못 예측 (마케팅 비용 낭비).
    - **False Negative(FN):** 이탈할 사람을 유지한다고 잘못 예측 (고객 상실 - 가장 위험!).

---

## 4. 배깅(Random Forest) vs 부스팅(XGBoost) 비교

두 기법 모두 앙상블이지만 작동 방식과 목적이 다릅니다. 이를 표로 정리하면 다음과 같습니다.

| 구분 | 랜덤 포레스트 (Bagging) | XGBoost (Boosting) |
| :--- | :--- | :--- |
| **학습 방식** | 병렬적 (동시에 여러 나무 학습) | 순차적 (앞선 모델의 실수를 보완) |
| **주요 목표** | **분산(Variance) 감소** $\rightarrow$ 과적합 방지 | **편향(Bias) 감소** $\rightarrow$ 정확도 향상 |
| **데이터 사용** | 무작위 샘플링 (Bootstrapping) | 가중치 부여 (틀린 데이터에 집중) |
| **학습 속도** | 빠름 (병렬 처리 가능) | 상대적으로 느림 (순차 처리) |
| **하이퍼파라미터** | 튜닝이 비교적 쉬움 (`n_estimators` 등) | 튜닝이 까다로움 (`learning_rate`, `max_depth` 등) |
| **추천 상황** | 데이터에 노이즈가 많고 과적합이 걱정될 때 | 최고의 예측 성능을 끌어내야 할 때 |

---

## 5. 실무 활용 사례: 신용 점수 예측 시스템

실제 금융권에서는 고객의 신용 점수를 예측하여 대출 승인 여부를 결정할 때 앙상블 모델을 적극적으로 사용합니다.

**[실무 파이프라인 예시]**
1.  **데이터 수집:** 고객의 연 소득, 기존 대출 금액, 연체 횟수, 직업, 거주지 등의 데이터를 수집합니다.
2.  **데이터 전처리:** 결측치를 처리하고, 범주형 변수(직업 등)를 인코딩합니다.
3.  **모델 선택:** 
    - 초기 단계에서는 **랜덤 포레스트**를 사용하여 어떤 변수가 신용 점수에 가장 큰 영향을 주는지(Feature Importance) 분석합니다.
    - 최종 서비스 단계에서는 **XGBoost**나 **LightGBM**을 사용하여 예측 정확도를 극대화합니다.
4.  **검증:** K-폴드 교차 검증을 통해 모델이 특정 데이터셋에만 최적화되지 않았는지 확인합니다.
5.  **해석:** SHAP(SHapley Additive exPlanations) 같은 라이브러리를 사용하여 "왜 이 고객의 신용 점수가 낮게 나왔는지"에 대한 근거를 제시합니다. (금융 서비스에서는 '설명 가능성'이 매우 중요하기 때문입니다.)

---

## 6. 초보자가 자주 하는 실수와 해결 방법

앙상블 모델을 사용할 때 입문자들이 흔히 겪는 시행착오들입니다.

### 1) "나무를 많이 만들수록(n_estimators $\uparrow$) 무조건 성능이 좋아지겠지?"
- **실수:** `n_estimators` 값을 10,000개, 100,000개로 무작정 높이는 경우.
- **결과:** 랜덤 포레스트는 어느 시점 이후 성능 향상이 멈추고 메모리만 많이 사용하게 됩니다. XGBoost의 경우 너무 많은 나무를 만들면 결국 학습 데이터에 과적합되어 테스트 성능이 떨어집니다.
- **해결:** 적절한 값을 찾기 위해 `GridSearchCV`나 `RandomizedSearchCV`를 사용하여 최적의 개수를 찾거나, XGBoost의 경우 `early_stopping_rounds` 옵션을 사용하여 성능 향상이 멈추는 지점에서 학습을 종료하세요.

### 2) "XGBoost 학습률(learning_rate)을 너무 높게 잡았어요."
- **실수:** `learning_rate=0.5` 또는 `1.0`으로 설정하는 경우.
- **결과:** 모델이 정답을 향해 너무 크게 점프하여 최적의 지점을 지나쳐 버립니다(Overshooting). 결과적으로 학습이 불안정하고 성능이 낮게 나옵니다.
- **해결:** 일반적으로 `0.01`에서 `0.1` 사이의 작은 값을 설정하고, 대신 `n_estimators`를 충분히 늘려 천천히 정밀하게 학습시키는 것이 정석입니다.

### 3) "데이터 스케일링을 안 했는데 괜찮을까요?"
- **궁금증:** "앞 장에서 배운 표준화(Standardization)를 해야 하나요?"
- **답변:** 랜덤 포레스트와 XGBoost 같은 **트리 기반 모델은 데이터의 스케일에 영향을 받지 않습니다.** 
- **이유:** 트리는 "값이 얼마인가"가 아니라 "특정 기준값보다 큰가 작은가"라는 이분법적 질문으로 데이터를 나누기 때문입니다. 따라서 스케일링을 하지 않아도 성능 차이가 거의 없습니다. (단, SVM이나 KNN과 함께 앙상블을 구성한다면 스케일링이 필수입니다.)

---

## 요약 및 마무리

이번 장에서는 단일 모델의 한계를 극복하는 **앙상블(Ensemble)** 기법에 대해 배웠습니다.

- **앙상블**은 여러 모델의 예측을 결합해 더 정확하고 안정적인 결과를 얻는 '집단지성' 전략입니다.
- **랜덤 포레스트**는 배깅(Bagging)의 대표 주자로, 무작위 샘플링과 특성 선택을 통해 과적합을 방지하고 안정적인 성능을 냅니다.
- **XGBoost**는 부스팅(Boosting)의 진화 형태로, 이전 모델의 오차를 보완하며 순차적으로 학습하여 매우 높은 예측 정확도를 자랑합니다.
- **실무**에서는 데이터의 특성과 목표(안정성 vs 정확도)에 따라 두 모델을 선택하거나 함께 활용합니다.

이제 여러분은 단일 모델을 넘어, 현대 머신러닝 경진대회(Kaggle 등)와 실무 현장에서 가장 널리 쓰이는 강력한 무기들을 갖추게 되었습니다. 데이터를 분석하고, 모델을 구축하고, 앙상블을 통해 성능을 끌어올리는 이 일련의 과정이 바로 머신러닝 엔지니어가 수행하는 핵심 작업입니다.