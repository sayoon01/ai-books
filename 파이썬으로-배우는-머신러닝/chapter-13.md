# 챕터 13: 실전 프로젝트 - 타이타닉 생존자 예측

# 챕터 13: 실전 프로젝트 - 타이타닉 생존자 예측

머신러닝의 개별 부품인 데이터 전처리, 회귀, 분류, 앙상블을 적절한 순서로 조립하여 하나의 '시스템'으로 만드는 능력은 실무에서 매우 중요합니다. 머신러닝의 가장 상징적인 입문 프로젝트인 **'타이타닉 생존자 예측'**을 통해, 데이터 로드부터 모델 평가까지의 전체 파이프라인(End-to-End Pipeline)을 직접 구축해 보겠습니다.

---

## 1. 학습 목표
- **머신러닝 전체 파이프라인**의 흐름을 이해하고 구현합니다.
- **탐색적 데이터 분석(EDA)**을 통해 데이터 속에 숨겨진 생존 패턴을 찾아냅니다.
- **특성 공학(Feature Engineering)**을 통해 모델의 성능을 높이는 새로운 변수를 생성합니다.
- **데이터 누수(Data Leakage)**를 방지하는 올바른 전처리 순서를 익힙니다.
- 실제 데이터를 활용해 **최종 예측 모델**을 만들고 그 결과를 해석합니다.

---

## 2. 개념 이해하기: 비유 $\rightarrow$ 직관 $\rightarrow$ 기술

### 🕵️ 비유: 100년 전의 사건을 추리하는 데이터 탐정
여러분은 지금 1912년 타이타닉호 침몰 사고의 기록물을 넘겨받은 **'데이터 탐정'**입니다. 주어진 것은 승객들의 명단(이름, 성별, 나이, 티켓 등급 등)과 일부 승객들의 생존 여부가 적힌 장부입니다. 사건을 해결하는 과정은 다음과 같습니다.

1. **증거 수집(EDA):** "여성과 아이들이 먼저 구조되었다는데 정말일까?"라며 장부를 훑어보며 경향성을 파악합니다.
2. **단서 정리(전처리):** 기록이 누락된 나이 칸을 주변 정황으로 추론해 채우고, 읽기 어려운 텍스트를 분석 가능한 형태로 바꿉니다.
3. **새로운 가설 세우기(특성 공학):** "단순히 나이보다, 가족이 많았던 사람이 서로를 챙겨서 더 많이 살아남지 않았을까?"라며 '가족 수'라는 새로운 단서를 만들어냅니다.
4. **결론 도출(모델링):** 지금까지의 모든 단서를 종합해, 아직 생존 여부를 모르는 승객들이 살았을지 죽었을지를 최종 예측합니다.

### ⚙️ 직관: 머신러닝은 '조립 라인'이다
머신러닝 프로젝트는 단순히 `model.fit()`이라는 버튼을 누르는 것이 아닙니다. 원재료(Raw Data)가 들어가서 완성품(Prediction)이 나오기까지 거치는 **'공정 라인'**을 설계하는 과정입니다.

만약 공정 순서가 잘못되어 완성 직전의 제품을 다시 원재료 단계로 되돌리거나, 미래에 들어올 제품의 정보를 미리 가져와 현재 제품을 수정한다면 전체 시스템은 붕괴합니다. 따라서 **"데이터의 흐름은 반드시 일방통행이어야 한다"**는 직관이 필요합니다.

### 🛠️ 기술 설명: 머신러닝 파이프라인(ML Pipeline)
기술적으로 머신러닝 파이프라인은 데이터가 모델에 입력되기까지 거치는 일련의 표준화된 단계입니다.

$$\text{데이터 로드} \rightarrow \text{EDA} \rightarrow \text{데이터 전처리} \rightarrow \text{특성 공학} \rightarrow \text{모델 선택/학습} \rightarrow \text{평가} \rightarrow \text{최종 예측}$$

**핵심 기술 포인트:**
1. **탐색적 데이터 분석 (EDA):** 시각화와 통계량을 통해 변수 간의 상관관계를 분석합니다. (예: 성별 $\rightarrow$ 생존율의 상관관계 확인)
2. **특성 공학 (Feature Engineering):** 도메인 지식을 활용해 기존 변수를 조합하여 새로운 변수를 생성합니다.
   - *예: $\text{SibSp(형제/배우자)} + \text{Parch(부모/자녀)} + 1 = \text{FamilySize(가족 규모)}$*
3. **데이터 누수 (Data Leakage) 방지:** 훈련 데이터(Train set)와 테스트 데이터(Test set)를 엄격히 분리한 후, 전처리에 사용되는 모든 통계량(평균, 중앙값 등)은 오직 **훈련 데이터에서만 산출**하여 테스트 데이터에 적용해야 합니다.

---

## 3. 파이썬 코드 실습

```python
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# 1. 데이터 로드
df = sns.load_dataset('titanic')

# --- [단계 1: EDA] ---
print("--- [EDA] 성별에 따른 생존율 ---")
print(df.groupby('sex')['survived'].mean())

plt.figure(figsize=(6, 4))
sns.barplot(x='sex', y='survived', data=df)
plt.title('Survival Rate by Sex')
plt.show()

# --- [단계 2: 전처리 및 특성 공학] ---
# 불필요하거나 중복된 컬럼 제거
df = df.drop(['who', 'adult_male', 'deck', 'embark_town', 'alive'], axis=1)

# 결측치 처리: 나이는 중앙값으로, 승선항은 최빈값으로 채움
df['age'] = df['age'].fillna(df['age'].median())
df['embarked'] = df['embarked'].fillna(df['embarked'].mode()[0])

# 특성 공학: 가족 수 변수 생성 (형제/배우자 + 부모/자녀 + 본인)
df['family_size'] = df['sibsp'] + df['parch'] + 1

# 범주형 데이터 인코딩 (문자 -> 숫자)
le = LabelEncoder()
df['sex'] = le.fit_transform(df['sex'])       # female: 0, male: 1
df['embarked'] = le.fit_transform(df['embarked'])
df['class'] = le.fit_transform(df['class'])

# --- [단계 3: 데이터 분리 및 스케일링] ---
X = df.drop('survived', axis=1)
y = df['survived']

# 데이터 분리 (훈련 8 : 테스트 2)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 스케일링: 데이터 누수 방지를 위해 X_train으로만 fit 수행
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# --- [단계 4: 모델 학습 및 평가] ---
model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
model.fit(X_train_scaled, y_train)

# 예측 및 결과 확인
y_pred = model.predict(X_test_scaled)
print(f"\n최종 모델 정확도: {accuracy_score(y_test, y_pred):.4f}")
print("\n[상세 분류 보고서]\n", classification_report(y_test, y_pred))

# 변수 중요도 시각화
importances = pd.Series(model.feature_importances_, index=X.columns)
importances.sort_values().plot(kind='barh', figsize=(8, 5))
plt.title('Feature Importances')
plt.show()
```

---

## 4. 실행 결과 및 해석

### 📊 결과 해석
1. **성별 생존율:** EDA 결과, 여성의 생존율이 남성보다 압도적으로 높게 나타납니다. 이는 모델이 `sex` 변수를 가장 강력한 예측 지표로 사용할 것임을 시사합니다.
2. **최종 정확도:** 일반적으로 약 **80% ~ 83%** 사이의 정확도가 도출됩니다. 이는 무작위 예측(50%)보다 훨씬 높으며, 기본적인 특성들만으로도 생존 여부를 상당히 정확히 맞힐 수 있음을 의미합니다.
3. **분류 보고서:** `Precision`(정밀도)과 `Recall`(재현율)을 통해 모델이 생존자(1)와 사망자(0) 중 어느 쪽을 더 잘 예측하는지 확인할 수 있습니다. 보통 사망자 예측의 정밀도가 더 높게 나오는 경향이 있습니다.
4. **변수 중요도:** 그래프 상위권에 `sex`, `age`, `fare`가 위치합니다. 이는 **"여성이고, 나이가 어리며, 비싼 티켓(상류층)을 가진 사람이 살 가능성이 높았다"**는 역사적 사실이 데이터로 증명된 결과입니다.

---

## 5. 실무 활용 사례

이러한 **End-to-End 파이프라인** 구조는 기업의 실제 예측 시스템 구축 시 동일하게 적용됩니다.

- **이탈 고객 예측 (Churn Prediction):**
  - `데이터 로드` $\rightarrow$ `EDA(이탈 고객의 공통점 분석)` $\rightarrow$ `전처리` $\rightarrow$ `특성 공학(최근 7일간 접속 횟수 등 생성)` $\rightarrow$ `모델링` $\rightarrow$ `이탈 확률 예측`.
- **신용 점수 산정 (Credit Scoring):**
  - `금융 기록 로드` $\rightarrow$ `EDA(연체자와 정상인의 차이 분석)` $\rightarrow$ `전처리` $\rightarrow$ `특성 공학(소득 대비 부채 비율 생성)` $\rightarrow$ `모델링` $\rightarrow$ `대출 승인 여부 결정`.

---

## 6. 자주 하는 실수 (Anti-Patterns)

**❌ 실수 1: `fit()`을 테스트 데이터에 적용하는 것**
- `scaler.fit(X_test)`를 호출하는 경우입니다. 이는 테스트 데이터의 정보가 모델에 미리 흘러 들어가는 **데이터 누수(Data Leakage)**를 유발하여, 실제 서비스 적용 시 성능이 급격히 떨어지는 원인이 됩니다.
- **해결:** `fit`은 오직 **훈련 데이터**에만 적용하고, 테스트 데이터에는 `transform`만 적용하십시오.

**❌ 실수 2: EDA 없이 바로 모델링하는 것**
- 변수 간의 관계를 모른 채 모델을 돌리면, 성능이 낮게 나왔을 때 원인을 분석할 수 없습니다. 실무 면접에서 "왜 이 모델과 변수를 썼는가?"라는 질문에 "그냥 돌려보니 정확도가 높아서요"라고 답하는 것은 전문성 부족으로 간주됩니다.

---

## 7. 핵심 요약
1. **ML 파이프라인:** 데이터 로드 $\rightarrow$ EDA $\rightarrow$ 전처리 $\rightarrow$ 특성 공학 $\rightarrow$ 학습 $\rightarrow$ 평가의 일방향 흐름을 갖는다.
2. **EDA의 목적:** 데이터의 특성을 파악하고, 모델링을 위한 가설을 세우기 위함이다.
3. **특성 공학:** 도메인 지식을 활용해 모델이 학습하기 좋은 '강력한 힌트(변수)'를 만드는 과정이다.
4. **데이터 누수 방지:** 훈련 셋에서 학습한 통계량만을 테스트 셋에 적용하는 원칙을 반드시 준수해야 한다.

---

## 8. 확인 문제
**Q. 타이타닉 프로젝트에서 '가족 수(family_size)'라는 새로운 변수를 만든 이유는 무엇이며, 이를 머신러닝 용어로 무엇이라고 하나요?**

**정답 및 해설:** 
단순한 형제 수나 부모 수라는 개별 지표보다, '전체 가족의 규모'가 생존 여부에 더 직관적인 영향을 줄 것이라는 가설을 바탕으로 모델에게 더 유용한 정보를 제공하기 위해서입니다. 이렇게 기존 변수를 조합해 새로운 변수를 만드는 과정을 **특성 공학(Feature Engineering)**이라고 합니다.

---

## 9. 미니 프로젝트: "1%의 성능 향상을 찾아라!"

**미션:** 제공된 코드의 정확도를 1%라도 더 높여보세요.

- **힌트 1 (특성 공학):** 승객의 이름(`name`)에서 'Mr', 'Mrs', 'Miss', 'Master' 같은 호칭(Title)을 추출해 보세요. 사회적 지위가 생존에 영향을 주었을까요?
- **힌트 2 (하이퍼파라미터):** `RandomForestClassifier`의 `max_depth`나 `n_estimators` 값을 조정하며 최적의 값을 찾아보세요.
- **힌트 3 (모델 변경):** `XGBoost`나 `LightGBM` 같은 최신 그래디언트 부스팅 모델을 적용해 보세요.

**결과 기록 양식:**
- 변경 전 정확도: `0.812` $\rightarrow$ 변경 후 정확도: `0.825`
- 변경 내용: `이름에서 Title 추출 및 범주화 적용`