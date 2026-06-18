# 챕터 14: 실전 프로젝트 - 집값 예측

# 14장. 실전 프로젝트 - 집값 예측

우리는 지금까지 머신러닝의 기초부터 다양한 알고리즘, 그리고 모델 평가 방법까지 학습했습니다. 이제는 이 모든 조각을 하나로 합쳐 실제 세상의 문제를 해결해 볼 차례입니다. 이번 프로젝트의 주제는 **'집값 예측'**입니다.

부동산 가격을 예측하는 것은 머신러닝의 가장 전형적인 '회귀(Regression)' 문제이자, 실무에서 매우 중요하게 다뤄지는 과제입니다. 단순히 데이터를 모델에 넣는 것이 아니라, 데이터 속에 숨겨진 의미를 찾고 이를 통해 미래의 가치를 예측하는 전체 과정을 경험해 보겠습니다.

---

## 1. 집값 예측, 어떻게 접근해야 할까?

### 🏠 베테랑 공인중개사의 '감'
동네에서 수십 년간 활동한 베테랑 공인중개사에게 특정 집의 적정 가격을 물어본다고 가정해 봅시다. 중개사는 단순히 집의 크기만 보지 않습니다. 

*"이 집은 방이 3개고 넓지만, 역에서 너무 멀어요. 하지만 최근 주변에 대형 쇼핑몰이 들어섰고, 학군이 좋아서 가격이 조금 오를 겁니다. 다만 지은 지 30년이 넘어서 수리비가 들 테니 그 점은 감가해야겠네요."*

중개사는 머릿속에서 수많은 **특성(Feature)**들을 조합하여 가격이라는 **결과(Target)**를 도출합니다. 
- **양적 특성:** 면적, 방 개수, 건축 연도
- **질적 특성:** 역세권 여부, 학군, 주변 편의시설
- **가중치:** 면적보다는 위치가 더 중요하다는 판단, 노후도는 가격을 낮추는 요인이라는 판단

### 💡 머신러닝으로 옮기기
머신러닝 모델이 하는 일은 바로 이 '베테랑 중개사의 감'을 수학적으로 구현하는 것입니다. 

1. **데이터 수집:** 중개사가 경험을 쌓듯, 수많은 집의 특성과 실제 거래 가격 데이터를 수집합니다.
2. **특성 추출:** 가격에 영향을 주는 핵심 요소(면적, 위치, 연식 등)를 선택합니다.
3. **패턴 학습:** "면적이 넓을수록 가격이 오르지만, 연식이 오래될수록 가격이 떨어진다"는 상관관계를 수식으로 찾아냅니다.
4. **예측:** 학습된 수식에 새로운 집의 정보를 넣으면 예상 가격이 출력됩니다.

### 🛠️ 기술적 설계도
이번 프로젝트에서는 다음과 같은 파이프라인을 거쳐 모델을 구축합니다.

| 단계 | 수행 내용 | 주요 도구/기법 |
| :--- | :--- | :--- |
| **데이터 탐색 (EDA)** | 데이터의 분포, 상관관계, 이상치 확인 | Pandas, Seaborn, Matplotlib |
| **데이터 전처리** | 결측치 처리, 특성 스케일링, 변수 선택 | StandardScaler, SimpleImputer |
| **모델 구축** | 기본 모델(선형 회귀) $\rightarrow$ 고성능 모델(랜덤 포레스트) | LinearRegression, RandomForestRegressor |
| **성능 평가** | 예측값과 실제값의 오차 측정 | MSE, RMSE, $R^2$ Score |
| **결과 해석** | 어떤 특성이 집값에 가장 큰 영향을 주었는지 분석 | Feature Importance |

---

## 2. 데이터 탐색 및 분석 (EDA)

실전 프로젝트에서 가장 중요한 것은 모델을 돌리는 것이 아니라 **데이터를 이해하는 것**입니다. 우리는 사이킷런(scikit-learn)에서 제공하는 `California Housing` 데이터셋을 사용하겠습니다. 이 데이터는 캘리포니아 지역의 인구 통계 및 지리적 특성을 바탕으로 집값의 중앙값을 기록한 데이터입니다.

### 📋 데이터셋 변수 정의
분석에 앞서, 데이터셋에 포함된 각 변수가 무엇을 의미하는지 확인해 보겠습니다.

| 변수명 | 의미 | 설명 |
| :--- | :--- | :--- |
| **MedInc** | 중위 소득 | 가구당 소득의 중앙값 |
| **HouseAge** | 집 연식 | 주택 건설 후 경과 연수 (중앙값) |
| **AveRooms** | 평균 방 개수 | 가구당 평균 방 개수 |
| **AveBedrms** | 평균 침실 개수 | 가구당 평균 침실 개수 |
| **Population** | 인구 수 | 해당 구역의 총 인구 수 |
| **AveOccup** | 평균 가구원 수 | 가구당 평균 거주 인원수 |
| **Latitude** | 위도 | 지역의 위도 좌표 |
| **Longitude** | 경도 | 지역의 경도 좌표 |
| **MedHouseVal** | 집값 (Target) | 집값의 중앙값 (단위: 100,000달러) |

### 💻 데이터 로드 및 기초 확인

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.datasets import fetch_california_housing

# 1. 데이터 로드
housing = fetch_california_housing()
df = pd.DataFrame(housing.data, columns=housing.feature_names)
df['MedHouseVal'] = housing.target # 타겟 변수(집값) 추가

# 데이터 상위 5개 행 확인
print(df.head())
print("-" * 30)
# 데이터 기본 정보 확인
print(df.info())
print("-" * 30)
# 통계치 확인
print(df.describe())
```

**[실행 결과 예시]**
```text
   MedInc  HouseAge  AveRooms  AveBedrms  Population  AveOccup  Latitude  Longitude  MedHouseVal
0  8.3252      41.0      6.9841     1.0238      322.0      2.559   34.8181  -118.475       4.526
1  8.3014      21.0      6.2381     0.9718      2401.0      2.109   34.8681  -118.442       3.585
2  7.2574      52.0      8.2881     1.0734      466.0      3.070   34.2207  -118.299       3.413
3  5.6431      52.0      5.8179     1.0730      558.0      2.547   34.2535  -118.297       3.422
4  3.8462      52.0      6.2818     1.0810      565.0      2.562   34.2535  -118.297       3.414
------------------------------
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 20640 entries, 0 to 20639
Data columns (total 9 columns):
 #   Column       Non-Null Count  Dtype  
---  ------       --------------  -----  
 0   MedInc       20640 non-null  float64
 1   HouseAge     20640 non-null  float64
 2   AveRooms     20640 non-null  float64
 3   AveBedrms    20640 non-null  float64
 4   Population   20640 non-null  float64
 5   AveOccup    20640 non-null  float64
 6   Latitude     20640 non-null  float64
 7   Longitude    20640 non-null  float64
 8   MedHouseVal  20640 non-null  float64
dtypes: float64(9)
------------------------------
              MedInc  HouseAge  AveRooms  AveBedrms  Population  AveOccup  Latitude  Longitude  MedHouseVal
count  20640.000000  20640.000  20640.000  20640.000  20640.000  20640.000  20640.000  20640.000  20640.000
mean       3.870630     28.639    5.42984     1.1211  1453.534    3.0995    34.0486   -119.439      2.068551
std        1.535261    12.585    1.83864     0.3712    1113.255    2.4011     0.7544      2.2266      1.153954
min        0.521252     1.000    1.00000     0.4000    11.000    1.0000    32.5408  -122.875      0.150000
... (중략) ...
max       15.274711    52.000   140.5959    10.0000  30943.000   1208.00    37.8562  -114.014      5.000000
```

**[결과 해석]**
- `MedHouseVal`은 집값의 중앙값(단위: 100,000달러)입니다.
- 모든 데이터가 숫자형(float64)으로 되어 있어 전처리가 비교적 수월하지만, 각 변수의 단위(Scale)가 매우 다르다는 점을 알 수 있습니다. 예를 들어 `Population`은 수천 단위인 반면, `AveBedrms`는 1 내외의 작은 값을 가집니다.

### 📈 시각화를 통한 인사이트 발견

데이터의 관계를 파악하기 위해 상관계수 히트맵과 산점도를 그려보겠습니다.

```python
# 2. 상관관계 분석
plt.figure(figsize=(10, 8))
sns.heatmap(df.corr(), annot=True, cmap='RdYlGn', fmt=".2f")
plt.title("Feature Correlation Heatmap")
plt.show()

# 3. 가장 상관관계가 높은 특성 시각화 (MedInc vs MedHouseVal)
plt.figure(figsize=(8, 6))
sns.scatterplot(data=df, x='MedInc', y='MedHouseVal', alpha=0.5)
plt.title("Income vs House Value")
plt.xlabel("Median Income")
plt.ylabel("Median House Value")
plt.show()
```

**[결과 해석]**
- **상관관계 히트맵:** `MedInc`(중위 소득)와 `MedHouseVal`(집값) 사이의 상관계수가 매우 높게 나타납니다. 이는 소득 수준이 높은 지역일수록 집값이 비싸다는 직관과 일치합니다.
- **산점도:** 소득이 증가함에 따라 집값이 선형적으로 증가하는 경향이 보입니다. 하지만 집값이 특정 상한선(약 5.0)에 몰려 있는 현상이 발견되는데, 이는 데이터 수집 과정에서 캡핑(Capping, 최대치 제한)이 이루어졌음을 시사합니다.

---

## 3. 데이터 전처리 및 모델 준비

이제 모델이 학습하기 좋은 형태로 데이터를 가공하겠습니다.

### 🛠️ 전처리 전략
1. **특성 선택:** 상관관계가 너무 낮거나 의미 없는 변수는 제외할 수 있습니다. (여기서는 모든 변수를 사용해 봅니다.)
2. **데이터 분할:** 학습 데이터(Train)와 테스트 데이터(Test)를 8:2 비율로 나눕니다.
3. **스케일링:** 특성마다 단위가 다르면(예: 소득은 수천 달러, 방 개수는 1~10개), 모델이 단위가 큰 변수를 더 중요하다고 착각할 수 있습니다. 이를 방지하기 위해 표준화(Standardization)를 진행합니다.

```python
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# 특성과 타겟 분리
X = df.drop('MedHouseVal', axis=1)
y = df['MedHouseVal']

# 1. 학습/테스트 세트 분리
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 2. 특성 스케일링
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

print(f"학습 데이터 크기: {X_train_scaled.shape}")
print(f"테스트 데이터 크기: {X_test_scaled.shape}")
```

> **⚠️ 초보자가 자주 하는 실수: Data Leakage(데이터 누수)**
> 스케일러를 적용할 때 `fit_transform`을 전체 데이터에 먼저 적용하고 나누는 경우가 많습니다. 하지만 이는 테스트 데이터의 정보가 학습 과정에 스며드는 '데이터 누수'를 유발합니다. 반드시 **학습 데이터로만 `fit`을 하고, 테스트 데이터에는 `transform`만 적용**해야 합니다.

---

## 4. 모델 구축 및 학습

우리는 두 가지 모델을 비교해 보겠습니다. 기준점이 되는 **선형 회귀(Linear Regression)**와 성능이 뛰어난 **랜덤 포레스트(Random Forest)**입니다.

### 📉 모델 1: 선형 회귀 (Baseline)
선형 회귀는 데이터의 경향성을 하나의 직선으로 표현하는 가장 단순한 모델입니다.

```python
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score

# 모델 생성 및 학습
lr_model = LinearRegression()
lr_model.fit(X_train_scaled, y_train)

# 예측
lr_pred = lr_model.predict(X_test_scaled)

# 평가
lr_mse = mean_squared_error(y_test, lr_pred)
lr_rmse = np.sqrt(lr_mse)
lr_r2 = r2_score(y_test, lr_pred)

print(f"[Linear Regression] RMSE: {lr_rmse:.4f}, R2 Score: {lr_r2:.4f}")
```

### 🌲 모델 2: 랜덤 포레스트 (Advanced)
랜덤 포레스트는 여러 개의 결정 트리(Decision Tree)를 만들어 그 결과의 평균을 내는 앙상블 모델입니다. 비선형 관계를 훨씬 더 잘 잡아냅니다.

```python
from sklearn.ensemble import RandomForestRegressor

# 모델 생성 및 학습
rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
rf_model.fit(X_train_scaled, y_train)

# 예측
rf_pred = rf_model.predict(X_test_scaled)

# 평가
rf_mse = mean_squared_error(y_test, rf_pred)
rf_rmse = np.sqrt(rf_mse)
rf_r2 = r2_score(y_test, rf_pred)

print(f"[Random Forest] RMSE: {rf_rmse:.4f}, R2 Score: {rf_r2:.4f}")
```

---

## 5. 결과 분석 및 모델 평가

### 📊 성능 비교 결과

| 모델 | RMSE (평균 오차) | $R^2$ Score (설명력) | 비고 |
| :--- | :--- | :--- | :--- |
| **선형 회귀** | 약 0.76 | 약 0.60 | 단순 경향성 파악 가능 |
| **랜덤 포레스트** | 약 0.51 | 약 0.81 | 복잡한 패턴 학습 성공 |

**[결과 해석]**
1. **RMSE (Root Mean Squared Error):** 실제 집값과 예측 집값의 차이를 나타냅니다. 값이 작을수록 정확합니다. 랜덤 포레스트가 선형 회귀보다 오차가 훨씬 적음을 알 수 있습니다.
2. **$R^2$ Score (결정계수):** 모델이 데이터의 변동성을 얼마나 잘 설명하는지를 나타냅니다. 1에 가까울수록 완벽한 모델입니다. 랜덤 포레스트의 $R^2$가 0.8 이상으로 매우 높게 나타났습니다.

**왜 이런 결과가 나왔을까요?**
집값은 단순히 "소득이 높으면 가격이 오른다"는 직선적인 관계만으로 결정되지 않습니다. "특정 지역이면서 동시에 연식이 짧아야 한다"는 식의 **복잡한 상호작용(Interaction)**이 존재합니다. 선형 회귀는 이를 잡아내지 못하지만, 랜덤 포레스트는 데이터를 쪼개어 분석하는 트리 구조를 통해 이러한 복잡한 조건을 학습했기 때문에 성능이 더 높게 나온 것입니다.

### 🔍 어떤 특성이 중요했을까? (Feature Importance)
랜덤 포레스트 모델의 가장 큰 장점 중 하나는 어떤 변수가 예측에 가장 큰 기여를 했는지 알려준다는 점입니다.

```python
# 특성 중요도 추출
importances = rf_model.feature_importances_
feature_names = housing.feature_names
feature_importance_df = pd.DataFrame({'Feature': feature_names, 'Importance': importances})
feature_importance_df = feature_importance_df.sort_values(by='Importance', ascending=False)

# 시각화
plt.figure(figsize=(10, 6))
sns.barplot(x='Importance', y='Feature', data=feature_importance_df)
plt.title("Feature Importance for House Price Prediction")
plt.show()
```

**[분석 결과]**
시각화 결과, `MedInc`(중위 소득)가 압도적으로 높은 중요도를 보입니다. 그 뒤를 이어 `AveRooms`(평균 방 개수)나 `HouseAge`(집 연식) 등이 영향을 주는 것을 볼 수 있습니다. 이는 우리가 초반 EDA 단계에서 확인했던 상관관계 분석 결과와 일맥상통합니다.

---

## 6. 실무 적용 시 고려사항 및 문제 해결

실제 현업에서 집값 예측 모델을 구축할 때는 단순히 알고리즘을 돌리는 것보다 더 까다로운 문제들이 발생합니다.

### 🚩 자주 발생하는 문제와 해결 방법

**1. 이상치(Outlier)의 영향**
- **문제:** 아주 드물게 나타나는 초고가 저택(궁전 같은 집)이 데이터에 포함되어 있으면, 선형 회귀 모델의 직선이 위로 끌려 올라가 전체적인 예측력이 떨어집니다.
- **해결:** IQR(Interquartile Range) 방식을 사용하여 극단적인 이상치를 제거하거나, 로그 변환(Log Transformation)을 통해 데이터의 분포를 정규분포 형태로 만들어 줍니다.

**2. 시계열 특성 무시**
- **문제:** 집값은 시간에 따라 변합니다. 2020년 데이터로 학습한 모델로 2024년 집값을 예측하면 큰 오차가 발생합니다.
- **해결:** '거래 시점' 데이터를 추가하거나, 최근 데이터에 더 높은 가중치를 주는 가중 학습(Weighted Learning) 방식을 도입해야 합니다.

**3. 외부 변수 누락**
- **문제:** 현재 데이터셋에는 '학군', '지하철역과의 거리', '강남/강북 같은 지역적 특성' 같은 핵심 정보가 부족합니다.
- **해결:** 외부 API(네이버 지도, 공공데이터 포털 등)를 통해 추가적인 특성(Feature)을 수집하여 모델에 입력하는 **특성 공학(Feature Engineering)** 과정이 필요합니다.

---

## 7. 요약 및 마무리

이번 장에서는 실제 부동산 데이터를 활용하여 집값을 예측하는 전체 머신러닝 파이프라인을 구축해 보았습니다.

1. **EDA(탐색적 데이터 분석):** 시각화를 통해 소득(`MedInc`)이 집값의 핵심 변수임을 파악했습니다.
2. **전처리:** 데이터 누수를 방지하기 위해 학습/테스트 셋을 분리하고, 표준 스케일링을 적용했습니다.
3. **모델 비교:** 단순한 선형 회귀보다 복잡한 비선형 관계를 학습할 수 있는 랜덤 포레스트의 성능이 훨씬 뛰어남을 확인했습니다.
4. **해석:** 특성 중요도(Feature Importance)를 통해 모델이 어떤 근거로 가격을 예측했는지 분석했습니다.

**핵심 포인트:**
- 머신러닝 모델의 성능은 단순히 알고리즘의 선택보다 **데이터를 어떻게 이해하고 전처리하느냐**에 더 큰 영향을 받습니다.
- 단순한 모델(Baseline)을 먼저 만들어 기준을 잡고, 점진적으로 복잡한 모델로 개선하는 접근 방식이 효율적입니다.
- 예측 결과가 왜 그렇게 나왔는지 분석하는 과정(Feature Importance 등)이 있어야 모델의 신뢰성을 확보할 수 있습니다.

이제 여러분은 실제 데이터를 가지고 문제를 정의하고, 해결책을 찾아내며, 그 결과를 분석하는 능력을 갖추게 되었습니다. 이 과정은 앞으로 여러분이 마주할 모든 머신러닝 프로젝트의 기본 뼈대가 될 것입니다.