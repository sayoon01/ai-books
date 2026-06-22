# 13. 실전 프로젝트 - 타이타닉 생존자 예측

## 이번 장에서 배우는 내용

지금까지 우리는 머신러닝의 개별 도구들을 하나씩 배웠습니다. 데이터 전처리법, 다양한 모델의 원리, 그리고 모델을 평가하는 방법까지 말이죠. 하지만 실제 현장에서는 이 도구들을 따로 사용하지 않습니다. 데이터 수집부터 최종 예측까지 하나의 유기적인 흐름, 즉 **'파이프라인(Pipeline)'**으로 연결하여 사용합니다.

이번 장에서는 머신러닝의 전 과정을 직접 경험해보기 위해, 데이터 분석의 고전이자 입문 코스인 **'타이타닉 생존자 예측 프로젝트'**를 수행합니다. 단순히 코드를 따라 치는 것이 아니라, 데이터 분석가의 관점에서 가설을 세우고 이를 검증하며 모델을 완성하는 전체 워크플로우를 학습하겠습니다.

---

## 실생활 비유: 데이터 분석가는 '디지털 탐정'이다

머신러닝 프로젝트를 수행하는 과정은 마치 **사건 현장을 조사하는 탐정**의 업무와 비슷합니다.

1.  **현장 조사(EDA):** 사건 현장에 도착해 흩어진 증거물들을 살펴봅니다. "피해자는 누구인가?", "주변에 어떤 흔적이 남아 있는가?"를 파악하며 사건의 윤곽을 잡습니다.
2.  **증거 정제(전처리):** 흙이 묻은 지문이나 찢어진 메모지를 깨끗하게 정리합니다. 쓸모없는 정보는 버리고, 중요한 단서를 명확하게 만듭니다.
3.  **추리 모델 구축(학습):** 수집된 증거들을 바탕으로 "범인은 이런 특성을 가진 사람일 것이다"라는 가설을 세우고 논리를 구성합니다.
4.  **검증 및 추론(평가):** 세운 가설이 실제 사실과 맞는지 대조해보고, 틀린 부분이 있다면 추리 과정을 수정합니다.

우리는 이제 타이타닉이라는 거대한 비극의 데이터를 통해, "과연 어떤 조건의 사람들이 생존 확률이 높았을까?"라는 수수께끼를 푸는 디지털 탐정이 되어볼 것입니다.

---

## 1. 프로젝트 개요 및 데이터 탐색 (EDA)

가장 먼저 할 일은 우리가 다룰 데이터가 어떻게 생겼는지 확인하는 것입니다. 타이타닉 데이터셋에는 승객의 티켓 등급, 성별, 나이, 함께 탄 가족 수 등 다양한 정보가 담겨 있습니다.

### 데이터 구조 파악하기
단순히 데이터를 불러오는 것에 그치지 않고, `info()`와 `describe()`를 통해 데이터의 '건강 상태'를 체크해야 합니다.

```python
import pandas as pd
import seaborn as sns

# 타이타닉 데이터셋 로드 (seaborn 라이브러리 제공)
df = sns.load_dataset('titanic')

# 1. 데이터의 전반적인 구조 확인
print("--- 데이터 기본 정보 ---")
print(df.info())

# 2. 수치형 데이터의 통계적 특성 확인
print("\n--- 수치형 데이터 통계 ---")
print(df.describe())

# 3. 결측치 확인
print("\n--- 결측치 개수 ---")
print(df.isnull().sum())
```

**[실행 결과 해설]**
*   `df.info()`를 통해 `age`, `embarked`, `deck` 컬럼에 결측치(NaN)가 많다는 것을 알 수 있습니다. 특히 `deck`은 결측치가 너무 많아 분석에서 제외하는 것이 좋을 것 같습니다.
*   `df.describe()`를 보면 나이(`age`)의 평균은 약 29세이며, 요금(`fare`)의 편차가 매우 크다는 점을 발견할 수 있습니다. 이는 일부 초부유층 승객이 있었음을 시사합니다.

**탐정의 관점:** 여기서 우리는 가설을 세웁니다. *"당시 사회적 분위기상 '여성과 아이'가 먼저 구조되었을 것이고, '1등석 승객'이 생존율이 더 높았을 것이다."* 이 가설이 맞는지 확인하는 것이 이번 프로젝트의 핵심입니다.

---

## 2. 데이터 전처리 및 피처 엔지니어링

머신러닝 모델은 숫자만 이해할 수 있는 '계산지'입니다. 따라서 텍스트로 된 데이터를 숫자로 바꾸고, 빈칸(결측치)을 적절히 채워주는 과정이 필요합니다. **사실 모델 선택보다 더 중요한 것이 바로 이 전처리 과정입니다.**

### 데이터 누수(Data Leakage) 방지하기
전처리를 할 때 가장 주의해야 할 점은 **'미래의 정보'를 미리 가져다 쓰지 않는 것**입니다. 전체 데이터의 중앙값으로 결측치를 채운 뒤 데이터를 나누면, 학습 데이터에 테스트 데이터의 정보가 스며드는 '데이터 누수'가 발생합니다. 따라서 반드시 **데이터를 먼저 분리한 후, 학습 데이터의 통계량만을 사용하여 전처리**해야 합니다.

### 인코딩의 선택: Label vs One-Hot
텍스트를 숫자로 바꿀 때, `LabelEncoder`는 단순히 0, 1, 2와 같은 순서대로 숫자를 부여합니다. 하지만 모델은 숫자 2가 0보다 '크다' 혹은 '중요하다'라고 오해할 수 있습니다.
*   **Label Encoding:** 성별(남/여)처럼 두 가지 값만 있는 경우 효율적입니다.
*   **One-Hot Encoding:** 승선항(S, C, Q)처럼 여러 값이고 순서가 없는 경우, 각각의 값을 독립된 컬럼으로 만들어 가중치 왜곡을 방지하는 것이 더 적합합니다. (본 예제에서는 단순화를 위해 LabelEncoder를 사용하지만, 실무에서는 One-Hot Encoding을 권장합니다.)

```python
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# 1. 분석에 불필요한 컬럼 제거 및 특성 생성
df['family_size'] = df['sibsp'] + df['parch'] + 1
drop_cols = ['deck', 'embark_town', 'alive', 'who', 'adult_male', 'class']
df_cleaned = df.drop(columns=drop_cols)

# 2. 특성(X)과 정답(y) 분리
X = df_cleaned.drop('survived', axis=1)
y = df_cleaned['survived']

# 3. [중요] 데이터 분리 먼저 수행 (데이터 누수 방지)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 4. 학습 데이터의 통계량으로 결측치 처리
age_median = X_train['age'].median()
embarked_mode = X_train['embarked'].mode()[0]

X_train['age'] = X_train['age'].fillna(age_median)
X_test['age'] = X_test['age'].fillna(age_median) # 학습 데이터의 중앙값을 그대로 사용

X_train['embarked'] = X_train['embarked'].fillna(embarked_mode)
X_test['embarked'] = X_test['embarked'].fillna(embarked_mode)

# 5. 범주형 데이터 인코딩
le = LabelEncoder()
for col in ['sex', 'embarked']:
    # 학습 데이터로 fit 하고, 학습/테스트 데이터 모두 transform
    X_train[col] = le.fit_transform(X_train[col])
    X_test[col] = le.transform(X_test[col])

print("전처리가 완료되었습니다. 데이터 누수 없이 분리되었습니다.")
```

---

## 3. 모델 선택 및 학습

이제 준비된 데이터를 모델에게 학습시킬 차례입니다. 이번 프로젝트는 '생존(1)이냐 사망(0)이냐'를 맞추는 **분류(Classification)** 문제입니다.

우리는 여러 개의 결정 트리를 만들어 다수결로 결과를 내는 **랜덤 포레스트(Random Forest)** 모델을 선택하겠습니다. 이 모델은 표 형식의 데이터에서 매우 강력한 성능을 발휘하며, 과적합 위험이 적습니다.

```python
from sklearn.ensemble import RandomForestClassifier

# 모델 생성 및 학습
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

print("모델 학습이 완료되었습니다.")
```

---

## 4. 모델 평가 및 최적화

단순히 "정확도가 80%다"라고 말하는 것은 부족합니다. 모델이 **어떤 데이터를 헷갈려 하는지** 분석해야 합니다.

### 오차 행렬(Confusion Matrix) 분석
오차 행렬을 보면 '살았는데 죽었다고 예측한 경우(FP)'와 '죽었는데 살았다고 예측한 경우(FN)'를 구분해 볼 수 있습니다.

```python
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

# 예측 수행
y_pred = model.predict(X_test)

# 결과 출력
print(f"정확도: {accuracy_score(y_test, y_pred):.4f}")
print("\n--- 오차 행렬 ---")
print(confusion_matrix(y_test, y_pred))
print("\n--- 상세 보고서 ---")
print(classification_report(y_test, y_pred))
```

### 어떤 변수가 중요했을까? (Feature Importance)
랜덤 포레스트의 장점은 모델이 판단을 내릴 때 어떤 변수를 중요하게 생각했는지 알려준다는 점입니다.

```python
import matplotlib.pyplot as plt
import numpy as np

# 변수 중요도 추출
importances = model.feature_importances_
indices = np.argsort(importances)

plt.figure(figsize=(10, 6))
plt.title('Feature Importances')
plt.barh(range(len(indices)), importances[indices], align='center')
plt.yticks(range(len(indices)), [X.columns[i] for i in indices])
plt.xlabel('Relative Importance')
plt.show()
```

**[해설]** 보통 `sex`와 `fare`(또는 `pclass`)가 가장 높은 중요도를 보입니다. 이는 우리의 가설("여성과 부유층이 생존 확률이 높다")이 데이터로 입증되었음을 의미합니다.

### 모델 최적화 (GridSearchCV)
더 높은 성능을 위해 하이퍼파라미터를 튜닝합니다. `GridSearchCV`를 사용해 최적의 `max_depth`와 `n_estimators` 조합을 찾습니다.

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [50, 100, 200],
    'max_depth': [None, 5, 10],
    'min_samples_split': [2, 5, 10]
}

grid_search = GridSearchCV(RandomForestClassifier(random_state=42), param_grid, cv=5)
grid_search.fit(X_train, y_train)

print(f"최적 파라미터: {grid_search.best_params_}")
print(f"최적 모델 정확도: {grid_search.best_score_:.4f}")
```

---

## 5. 실무 활용 사례: 이진 분류 모델의 확장

타이타닉 생존자 예측은 전형적인 **'이진 분류(Binary Classification)'** 문제입니다. 실무에서 이러한 구조의 모델은 매우 광범위하게 사용됩니다.

*   **고객 이탈 예측 (Churn Prediction):** 고객의 이용 패턴(접속 빈도, 결제 금액 등) 데이터를 분석하여, 이 고객이 서비스를 해지할 것인지(1) 유지할 것인지(0)를 예측합니다. 이를 통해 이탈 가능성이 높은 고객에게만 맞춤 쿠폰을 발송하는 전략을 세울 수 있습니다.
*   **금융 신용 등급 평가 (Credit Scoring):** 대출 신청자의 소득, 직업, 기존 연체 기록 등을 분석하여 대출금을 상환할 수 있을지(1) 없을지(0)를 판단하여 대출 승인 여부를 결정합니다.
*   **질병 진단 (Medical Diagnosis):** 환자의 검사 수치, 증상 데이터를 바탕으로 특정 질병이 양성(1)인지 음성(0)인지를 판별하는 보조 도구로 활용됩니다.

---

## 6. 프로젝트 마무리: 인사이트 도출 및 회고

### 최종 결과 해석
우리는 타이타닉 데이터를 통해 다음과 같은 결론을 얻었습니다.
1.  **성별(Sex)**은 생존을 결정짓는 가장 압도적인 요인이었습니다.
2.  **객실 등급(Pclass)**과 **요금(Fare)** 또한 중요한 변수였으며, 이는 사회적 지위가 생존율에 영향을 미쳤음을 보여줍니다.
3.  **가족 규모(FamilySize)**는 너무 적거나 너무 많을 때보다 적당한 규모일 때 생존율에 긍정적인 영향을 주는 경향이 있었습니다.

### 머신러닝 파이프라인 흐름도
이번 프로젝트를 통해 경험한 전체 흐름은 다음과 같습니다.

**[데이터 수집]** $\rightarrow$ **[EDA(가설 설정)]** $\rightarrow$ **[데이터 분리]** $\rightarrow$ **[전처리(결측치/인코딩)]** $\rightarrow$ **[특성 생성]** $\rightarrow$ **[모델 학습]** $\rightarrow$ **[평가(오차 행렬)]** $\rightarrow$ **[최적화(튜닝)]** $\rightarrow$ **[인사이트 도출]**

### 자주 하는 실수
*   **데이터 누수(Data Leakage):** 전처리를 할 때 `X_test`의 정보를 미리 사용하여 `X_train`의 결측치를 채우는 실수를 합니다. 반드시 학습 데이터의 통계량(중앙값 등)만 사용하여 테스트 데이터를 처리해야 합니다.
*   **정확도 맹신:** 정확도가 높다고 해서 좋은 모델은 아닙니다. 생존자와 사망자의 비율이 불균형하다면, 정밀도(Precision)와 재현율(Recall)을 함께 살펴봐야 합니다.

---

## 확인 문제

1.  데이터 전처리 과정에서 `train_test_split`을 수행하기 전에 전체 데이터의 중앙값으로 결측치를 채우면 어떤 문제가 발생하나요?
2.  `LabelEncoder`를 사용할 때, 범주가 3개 이상인 데이터(예: 승선항)에 적용할 경우 발생할 수 있는 위험성은 무엇인가요?
3.  모델의 성능을 평가할 때 '정확도(Accuracy)'만으로 판단하기 어려운 이유는 무엇인가요?

---

## 정답 및 해설

1.  **정답:** 데이터 누수(Data Leakage)가 발생합니다. 테스트 데이터의 정보가 학습 과정에 포함되어, 실제 환경보다 성능이 과하게 높게 측정되는 '낙관적 편향'이 생길 수 있습니다.
2.  **정답:** 모델이 숫자의 크기(0 < 1 < 2)를 순서나 가중치로 인식하여, 실제로는 관계가 없는 범주 간에 서열이 있다고 잘못 판단할 수 있습니다. 이를 방지하기 위해 원-핫 인코딩(One-Hot Encoding)을 사용합니다.
3.  **정답:** 데이터 불균형 문제 때문입니다. 예를 들어 생존자가 10%뿐인 데이터에서 모두 '사망'이라고만 예측해도 정확도는 90%가 나오지만, 정작 중요한 '생존자'는 한 명도 맞추지 못한 쓸모없는 모델이 될 수 있습니다.

---

## 미니 프로젝트: 나만의 생존 예측 파이프라인 구축하기

**목표:** 지금까지 배운 과정을 스스로 구현하여, 데이터 전처리부터 평가까지의 전체 파이프라인을 구축해 보세요.

**과제:**
1.  `seaborn`의 `titanic` 데이터셋을 다시 로드하세요.
2.  **새로운 가설 세우기:** "나이가 아주 어리거나(아동) 아주 많은(노인) 사람이 더 많이 생존했을 것이다"라는 가설을 검증하기 위해 `is_child` 또는 `is_senior`라는 새로운 특성을 만들어 보세요.
3.  **파이프라인 구현:** 
    *   데이터 분리 $\rightarrow$ 결측치 처리(학습 데이터 기준) $\rightarrow$ 인코딩 $\rightarrow$ 모델 학습 $\rightarrow$ 평가 순으로 코드를 작성하세요.
4.  **결과 분석:** 새로 만든 특성이 `feature_importances_`에서 얼마나 중요한 비중을 차지하는지 확인하고, 자신의 가설이 맞았는지 결론을 내리세요.