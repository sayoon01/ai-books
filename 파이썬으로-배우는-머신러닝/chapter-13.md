# 챕터 13: 실전 프로젝트 - 타이타닉 생존자 예측

# 13장. 실전 프로젝트 - 타이타닉 생존자 예측

지금까지 우리는 머신러닝의 개별 부품들을 하나씩 학습했습니다. 데이터 전처리 방법, 회귀와 분류 알고리즘, 모델 평가 지표, 그리고 성능을 높이는 앙상블 기법까지 말이죠. 하지만 실제 현업에서 머신러닝 엔지니어가 하는 일은 단순히 알고리즘 하나를 실행하는 것이 아닙니다. 

데이터를 처음 마주한 순간부터 최종 예측 결과를 내놓기까지의 전체 과정, 즉 **'머신러닝 파이프라인(ML Pipeline)'**을 설계하고 실행하는 것이 핵심입니다. 이번 장에서는 머신러닝 입문자들의 '통과 의례'라고 불리는 **타이타닉 생존자 예측 프로젝트**를 통해, 지금까지 배운 모든 내용을 하나의 흐름으로 엮어보겠습니다.

---

## 1. 머신러닝 파이프라인: 탐정의 수사 과정

머신러닝 프로젝트를 수행하는 것은 마치 **'오래된 미제 사건을 해결하는 탐정의 수사 과정'**과 매우 비슷합니다. 

### 비유로 이해하기
탐정이 사건을 해결할 때 무턱대고 범인을 지목하지 않습니다. 다음과 같은 단계를 거치죠.
1. **현장 조사 (EDA):** 사건 현장을 둘러보며 어떤 단서가 있는지, 피해자와 가해자의 관계는 어떠했는지 파악합니다.
2. **증거 정제 (Preprocessing):** 훼손된 지문을 복원하거나, 불필요한 잡음을 제거하여 깨끗한 증거물을 만듭니다.
3. **새로운 가설 설정 (Feature Engineering):** "단순히 범인이 누구인가"가 아니라, "범인이 왼손잡이였을 가능성이 높다"라는 새로운 관점의 단서를 찾아냅니다.
4. **추리 및 검증 (Modeling & Evaluation):** 수집한 증거를 바탕으로 범인을 추리하고, 그 추리가 맞는지 기존의 알리바이와 대조하며 검증합니다.

### 직관적으로 이해하기
머신러닝에서도 마찬가지입니다. 원본 데이터(Raw Data)를 그대로 모델에 넣는다고 해서 정답이 나오지 않습니다. 데이터를 이해하고, 다듬고, 의미 있는 특징을 추출하는 과정이 선행되어야 모델이 비로소 '학습'을 할 수 있습니다.

### 기술적 정의: 머신러닝 파이프라인
머신러닝 파이프라인이란 **데이터 수집 $\rightarrow$ 데이터 분석(EDA) $\rightarrow$ 전처리 $\rightarrow$ 특성 공학 $\rightarrow$ 모델 학습 $\rightarrow$ 평가 $\rightarrow$ 배포**로 이어지는 일련의 반복적인 과정을 의미합니다. 

**[그림 13-1. 머신러닝 파이프라인의 전체 흐름]**
*(도식 가이드: 데이터 수집부터 배포까지의 각 단계가 화살표로 연결된 플로우차트. 특히 '평가' 단계에서 성능이 낮을 경우 다시 '전처리'나 '특성 공학' 단계로 돌아가는 피드백 루프가 표현되어야 함)*

이번 프로젝트에서는 다음과 같은 흐름으로 진행합니다.

| 단계 | 주요 작업 | 목적 |
| :--- | :--- | :--- |
| **Step 1: EDA** | 데이터 분포 확인, 상관관계 분석 | 데이터의 특성과 생존 요인 파악 |
| **Step 2: 데이터 분리** | 학습 데이터와 테스트 데이터 분리 | 모델의 일반화 성능을 객관적으로 평가하기 위함 |
| **Step 3: 전처리 및 특성 공학** | 결측치 처리, 인코딩, 변수 생성 | 모델이 학습 가능한 최적의 데이터 형태로 가공 |
| **Step 4: 모델링** | 알고리즘 선택 및 학습 | 생존 여부를 예측하는 최적의 규칙 발견 |
| **Step 5: 평가** | 정확도 측정 및 결과 해석 | 모델이 얼마나 잘 맞히는지 검증 |

---

## 2. Step 1: 데이터 탐색 (EDA) - 현장 조사

먼저 우리가 다룰 데이터를 살펴보겠습니다. 타이타닉 데이터셋은 승객의 성별, 나이, 객실 등급, 요금 등의 정보와 실제 생존 여부(`Survived`)가 포함되어 있습니다.

### 코드 실습: 데이터 불러오기와 기본 분석

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 데이터 로드 (seaborn 라이브러리에서 제공하는 데이터셋 사용)
df = sns.load_dataset('titanic')

# 1. 데이터 상위 5개 행 확인
print("--- Dataset Head ---")
print(df.head())

# 2. 기본 정보 확인 (결측치 및 데이터 타입)
print("\n--- Dataset Info ---")
print(df.info())

# 3. 생존율 확인 (Survived: 0=사망, 1=생존)
print("\n--- Survival Rate ---")
print(df['survived'].value_counts(normalize=True))

# 4. 성별에 따른 생존율 시각화
plt.figure(figsize=(6, 4))
sns.barplot(x='sex', y='survived', data=df)
plt.title('Survival Rate by Gender')
plt.show()

# 5. 객실 등급(pclass)에 따른 생존율 시각화
plt.figure(figsize=(6, 4))
sns.barplot(x='pclass', y='survived', data=df)
plt.title('Survival Rate by Pclass')
plt.show()
```

### 결과 해석
- **데이터 구조:** `survived`가 우리가 예측해야 할 타깃(Target) 변수입니다.
- **성별의 영향:** 시각화 결과, 여성의 생존율이 남성보다 압도적으로 높음을 알 수 있습니다.
- **객실 등급의 영향:** 1등급(1st class) 승객의 생존율이 가장 높고, 3등급으로 갈수록 낮아집니다.
- **결측치 발견:** `age`와 `embarked` 컬럼에 결측치(NaN)가 다수 존재함을 확인했습니다.

---

## 3. Step 2 & 3: 데이터 분리와 전처리 - 증거 정제 및 단서 찾기

여기서 매우 중요한 주의사항이 있습니다. **전처리를 하기 전에 데이터를 먼저 나누어야 합니다.** 모든 데이터의 평균으로 결측치를 채운 뒤 데이터를 나누면, 테스트 데이터의 정보가 학습 데이터에 스며드는 '데이터 누수(Data Leakage)'가 발생하여 평가 결과가 왜곡됩니다.

### 직관적 접근: 학습 데이터의 기준으로만 채우기
우리는 미래의 데이터(테스트 세트)를 미리 알 수 없습니다. 따라서 **학습 데이터에서 계산한 통계량(중앙값 등)을 저장해두었다가, 이를 테스트 데이터에도 동일하게 적용**하는 것이 실무의 정석입니다.

### 코드 실습: 데이터 분리 및 전처리 파이프라인

```python
from sklearn.model_selection import train_test_split

# 1. 분석에 불필요한 컬럼 제거
cols_to_drop = ['deck', 'embark_town', 'alive', 'who', 'adult_male']
df = df.drop(columns=cols_to_drop)

# 2. 특성(X)과 타깃(y) 분리
X = df.drop('survived', axis=1)
y = df['survived']

# 3. [중요] 데이터 분리 (학습 데이터와 테스트 데이터를 먼저 나눕니다)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 4. 전처리 및 특성 공학 (학습 데이터 기반으로 처리)

# [특성 공학] 가족 규모 및 혼자 탑승 여부 생성
for dataset in [X_train, X_test]:
    dataset['family_size'] = dataset['sibsp'] + dataset['parch'] + 1
    dataset['is_alone'] = (dataset['family_size'] == 1).astype(int)

# [결측치 처리] 학습 데이터의 pclass별 나이 중앙값을 계산하여 적용
age_medians = X_train.groupby('pclass')['age'].median()

def fill_age(row):
    return age_medians[row['pclass']] if pd.isna(row['age']) else row['age']

X_train['age'] = X_train.apply(fill_age, axis=1)
X_test['age'] = X_test.apply(fill_age, axis=1)

# 탑승항구(embarked)는 학습 데이터의 최빈값으로 채움
most_freq_embarked = X_train['embarked'].mode()[0]
X_train['embarked'] = X_train['embarked'].fillna(most_freq_embarked)
X_test['embarked'] = X_test['embarked'].fillna(most_freq_embarked)

# [인코딩] 범주형 데이터 변환 (One-Hot Encoding)
# 학습 데이터와 테스트 데이터에 동일한 컬럼이 생성되도록 처리
X_train = pd.get_dummies(X_train, columns=['sex', 'embarked'], drop_first=True)
X_test = pd.get_dummies(X_test, columns=['sex', 'embarked'], drop_first=True)

print("\n--- Preprocessed X_train Head ---")
print(X_train.head())
```

### 결과 해석
- **데이터 누수 방지:** `X_test`의 나이 결측치를 채울 때 `X_test` 자체의 평균이 아닌, `X_train`에서 계산된 `age_medians`를 사용했습니다.
- **특성 생성:** `family_size`와 `is_alone` 변수가 추가되어 모델이 학습할 수 있는 더 풍부한 힌트를 제공합니다.
- **인코딩:** `sex_male` 등 수치형 변수로 변환되어 모델 입력 준비가 완료되었습니다.

---

## 4. Step 4: 모델 학습 - 추리 시작

이제 준비된 데이터를 바탕으로 모델을 학습시키겠습니다. 분류 문제이므로 12장에서 배운 **Random Forest**를 사용하겠습니다.

### 코드 실습: 모델 구축 및 학습

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# 1. 모델 생성 및 학습
# n_estimators: 결정 트리의 개수, max_depth: 트리의 최대 깊이 (과적합 방지)
model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
model.fit(X_train, y_train)

# 2. 예측 수행
y_pred = model.predict(X_test)

# 3. 성능 평가
accuracy = accuracy_score(y_test, y_pred)
print(f"\n모델 정확도(Accuracy): {accuracy:.4f}")
print("\n--- Classification Report ---")
print(classification_report(y_test, y_pred))
```

### 결과 해석
- **정확도(Accuracy):** 약 80~83% 정도의 정확도가 나옵니다. 이는 테스트 데이터 10명 중 8명 이상의 생존 여부를 정확히 맞혔다는 뜻입니다.
- **정밀도와 재현율:** 생존자(1)를 얼마나 정확하게 예측했는지, 실제 생존자를 얼마나 많이 찾아냈는지를 확인할 수 있습니다.

---

## 5. Step 5: 모델 평가와 해석 - 판결 내리기

단순히 정확도 숫자만 보는 것이 아니라, 모델이 **어떤 기준**으로 생존을 예측했는지 분석하는 것이 중요합니다.

### 특성 중요도(Feature Importance) 분석

```python
importances = model.feature_importances_
feature_names = X_train.columns
feature_importance_df = pd.DataFrame({'Feature': feature_names, 'Importance': importances})
feature_importance_df = feature_importance_df.sort_values(by='Importance', ascending=False)

plt.figure(figsize=(10, 6))
sns.barplot(x='Importance', y='Feature', data=feature_importance_df)
plt.title('Feature Importance in Titanic Survival Prediction')
plt.show()
```

### 결과 해석
- 그래프 상단에 위치한 변수(예: `sex_male`, `age`, `fare`)가 생존 예측에 가장 결정적인 역할을 했음을 알 수 있습니다.
- 이는 우리가 EDA 단계에서 파악했던 "여성과 아이, 그리고 부유층이 더 많이 생존했다"는 가설과 일치하며, 모델이 실제 세상의 규칙을 잘 찾아냈음을 의미합니다.

---

## 6. 타이타닉 프로젝트에서 실무로: 분류 파이프라인의 확장

타이타닉 예제는 학습용 데이터셋이지만, 여기서 구축한 **'분류 파이프라인(데이터 분리 $\rightarrow$ 전처리 $\rightarrow$ 특성 공학 $\rightarrow$ 학습 $\rightarrow$ 평가)'**은 실제 현업에서 매우 광범위하게 사용됩니다.

### 실무 적용 사례
이 프로젝트에서 배운 흐름을 그대로 가져가면 다음과 같은 비즈니스 문제를 해결할 수 있습니다.

- **은행의 고객 이탈 예측 (Churn Prediction):** 
  - **데이터:** 고객의 거래 횟수, 상담 내역, 잔액 변화 등
  - **목표:** 고객이 서비스를 해지할지(1) 유지할지(0) 예측 $\rightarrow$ 이탈 가능성이 높은 고객에게 맞춤 혜택 제공
- **이커머스의 구매 전환 예측 (Conversion Prediction):** 
  - **데이터:** 페이지 체류 시간, 클릭 경로, 장바구니 담기 횟수 등
  - **목표:** 방문자가 실제로 구매를 할지(1) 그냥 나갈지(0) 예측 $\rightarrow$ 구매 확률이 높은 사용자에게 타겟 쿠폰 발송
- **의료 데이터의 질병 진단 (Disease Diagnosis):** 
  - **데이터:** 혈압, 혈당, 나이, 가족력 등
  - **목표:** 특정 검사 결과가 양성(1)인지 음성(0)인지 예측 $\rightarrow$ 조기 진단 및 정밀 검사 권고

결국 **"특정 조건(Feature)을 가진 대상이 어떤 결과(Target)를 낼 것인가"**를 맞히는 모든 분류 문제는 타이타닉 프로젝트와 본질적으로 동일한 파이프라인을 가집니다.

---

## 7. 초보자가 자주 하는 실수와 해결 방법

### ❌ 실수 1: 데이터 누수 (Data Leakage)
**상황:** 전처리 단계에서 전체 데이터의 평균값으로 결측치를 채운 뒤, 데이터를 학습/테스트 세트로 나누는 경우.
- **문제:** 테스트 데이터의 정보가 학습 과정에 미리 반영되어, 평가 결과가 비정상적으로 높게 나오는 '낙관적 편향'이 발생합니다.
- **해결:** 반드시 **데이터를 먼저 나누고**, 학습 데이터의 통계량만을 사용하여 학습/테스트 세트를 각각 전처리하세요.

### ❌ 실수 2: 과도한 특성 생성 (Over-engineering)
**상황:** 근거 없이 수십 개의 변수를 억지로 만들어 넣는 경우.
- **문제:** 모델이 훈련 데이터의 특수한 상황까지 암기해버리는 **과적합(Overfitting)**이 발생하여 새로운 데이터에 대한 예측력이 떨어집니다.
- **해결:** EDA를 통해 근거가 확실한 특성만 추가하고, 모델의 `max_depth` 등을 조절해 복잡도를 제어하세요.

### ❌ 실수 3: 원-핫 인코딩의 함정 (Dummy Variable Trap)
**상황:** `sex`를 `sex_male`과 `sex_female` 두 개로 모두 만드는 경우.
- **문제:** 두 변수는 완벽하게 중복된 정보를 가지므로 다중공선성 문제를 일으켜 일부 모델의 성능을 저하시킵니다.
- **해결:** `pd.get_dummies(..., drop_first=True)` 옵션을 사용하여 변수 하나를 제거하세요.

---

## 8. 요약 및 마무리

이번 장에서는 타이타닉 생존자 예측 프로젝트를 통해 머신러닝의 전체 파이프라인을 경험했습니다.

1. **EDA:** 데이터를 시각화하여 성별, 객실 등급이 생존의 핵심 요인임을 파악했습니다.
2. **데이터 분리:** 데이터 누수를 방지하기 위해 전처리 전 학습/테스트 세트를 엄격히 분리했습니다.
3. **전처리 및 특성 공학:** 학습 데이터의 통계량을 기준으로 결측치를 채우고, `family_size` 같은 새로운 변수를 생성했습니다.
4. **모델링 및 평가:** Random Forest를 사용하여 생존 여부를 분류하고, 특성 중요도를 통해 판단 근거를 확인했습니다.

머신러닝은 단순히 `model.fit()`을 호출하는 것이 아니라, **데이터를 깊게 이해하고 가공하는 과정**이 80% 이상을 차지합니다. 이제 여러분은 단순한 코드 작성자를 넘어, 데이터를 통해 문제를 해결하는 '데이터 사이언티스트'의 관점을 갖게 되었습니다.