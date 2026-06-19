# 14. 실전 프로젝트 - 집값 예측

## 이번 장에서 배우는 내용

이번 장에서는 지금까지 배운 회귀 분석의 모든 기술을 집약하여, 실제 부동산 데이터를 활용한 **'집값 예측 파이프라인'**을 구축합니다. 단순히 모델에 데이터를 넣고 결과를 확인하는 것이 아니라, 데이터 탐색(EDA)부터 도메인 지식을 반영한 특성 공학, 그리고 모델의 한계를 분석하는 잔차 분석까지의 전 과정을 실습합니다.

- 부동산 데이터의 특성과 다변량 회귀의 이해
- 데이터 시각화를 통한 가설 설정 및 이상치 제거
- 모델의 성능을 극대화하는 특성 공학(Feature Engineering)
- 다양한 회귀 모델 비교 및 Scikit-learn 파이프라인 구축
- RMSE, $R^2$ 및 잔차 분석을 통한 정밀한 모델 평가
- 변수 중요도 확인 및 하이퍼파라미터 튜닝을 통한 개선

---

## 실생활 비유: 베테랑 공인중개사의 감정 평가

여러분 주변에 수십 년 경력의 베테랑 공인중개사가 있다고 가정해 봅시다. 이분은 집값을 매길 때 단순히 "평수가 넓으니 비싸다"라고 말하지 않습니다.

1. **데이터 탐색**: 먼저 주변 시세를 살피고, 최근 거래된 비슷한 집들의 가격을 확인합니다. (EDA)
2. **특성 추출**: "이 집은 지은 지는 오래됐지만, 최근에 리모델링을 했으니 가치가 높겠군", "역세권이라 직장인 수요가 많겠어"라며 단순한 수치 너머의 의미를 찾아냅니다. (특성 공학)
3. **예측**: 자신이 가진 경험(학습된 모델)을 바탕으로 적정 가격을 제시합니다. (모델링)
4. **피드백**: 만약 예측가보다 훨씬 높게 팔렸다면, "내가 놓친 호재가 있었나?"라며 분석합니다. (잔차 분석 및 모델 개선)

머신러닝의 회귀 파이프라인은 바로 이 **'베테랑 중개사의 사고 과정'을 코드로 구현하는 것**과 같습니다.

---

## 부동산 데이터의 특성과 예측의 본질

집값 예측은 머신러닝에서 **다변량 회귀(Multivariate Regression)**의 가장 전형적인 사례입니다. 집값이라는 하나의 결과값(종속 변수)에 영향을 주는 요소(독립 변수)가 매우 다양하기 때문입니다.

### 종속 변수와 독립 변수의 관계
- **종속 변수(Target)**: 우리가 예측하려는 값인 `Price`(집값)입니다.
- **독립 변수(Features)**: 집값에 영향을 주는 `방 개수`, `면적`, `위치`, `건축 연도`, `범죄율` 등이 있습니다.

### 데이터의 왜곡(Skewness) 확인
실제 부동산 데이터를 보면, 대부분의 집은 평균적인 가격대에 몰려 있지만, 극소수의 초고가 펜트하우스들이 가격 분포를 오른쪽으로 길게 늘어뜨리는 경향이 있습니다. 이를 **'오른쪽 꼬리가 긴 분포(Right-Skewed)'**라고 합니다. 

이런 왜곡이 심하면 모델은 극단적인 고가 주택에 영향을 받아 전체적인 예측선을 과도하게 위로 끌어올리게 되고, 결과적으로 일반적인 집값들에 대한 예측력이 떨어지는 '편향'이 발생합니다. 따라서 우리는 데이터를 정규분포 형태로 만들어주는 작업이 필요합니다.

---

## 데이터 탐색 및 가설 설정 (EDA)

데이터를 무작정 모델에 넣기 전에, 어떤 변수가 정말 중요한지 '눈으로 확인'하는 과정이 필요합니다.

### 1. 상관관계 분석 (Heatmap)
어떤 변수가 집값과 강한 상관관계를 갖는지 확인하기 위해 상관계수 행렬을 그리고 히트맵으로 시각화합니다. 예를 들어, '면적'과 '집값'의 상관계수가 0.8이라면 매우 강한 양의 상관관계가 있다고 볼 수 있습니다.

### 2. 선형성 확인 (Scatter plot)
상관계수가 높더라도 실제로 직선의 형태를 띠는지 산점도로 확인해야 합니다. 만약 곡선 형태라면 단순 선형 회귀보다는 더 복잡한 모델이나 데이터 변환이 필요하다는 가설을 세울 수 있습니다.

### 3. 이상치(Outlier) 제거 전략
면적은 매우 좁은데 가격이 말도 안 되게 높거나, 반대로 면적은 엄청나게 넓은데 가격이 매우 낮은 데이터는 모델의 학습을 방해하는 '노이즈'가 됩니다. 이러한 이상치는 제거하거나 보정하는 전략을 세워야 합니다.

---

## 특성 공학: 데이터의 가치를 높이는 과정

특성 공학(Feature Engineering)은 원본 데이터를 모델이 학습하기 좋은 형태로 가공하는 과정입니다. 여기서 **도메인 지식**이 빛을 발합니다.

### 1. 범주형 데이터의 인코딩
컴퓨터는 '강남구', '서초구'라는 글자를 이해하지 못합니다. 이를 `0, 1, 2`로 바꾸는 레이블 인코딩보다는, 각 구를 독립된 열로 만들어 `0` 또는 `1`로 표시하는 **원-핫 인코딩(One-Hot Encoding)**을 사용하여 특정 지역이 갖는 가중치를 독립적으로 학습하게 합니다.

### 2. 로그 변환 (Log Transformation)
앞서 언급한 '왜곡된 분포'를 해결하는 방법입니다. 가격에 로그를 취하면 초고가 주택과 같은 극단적인 값(Outlier)의 영향력을 줄여 모델의 편향을 막을 수 있습니다. 큰 값들은 상대적으로 작게 압축되고, 작은 값들 간의 차이는 유지되어 분포가 정규분포에 가까워지므로 모델의 안정성이 크게 향상됩니다.

### 3. 파생 변수 생성
단순히 `건축 연도`를 넣는 것보다, `현재 연도 - 건축 연도`를 계산해 **`집의 나이(House Age)`**라는 변수를 만드는 것이 훨씬 직관적입니다. 모델 입장에서 "1990년에 지어졌다"보다 "34년 된 집이다"라는 정보가 예측에 더 유리하기 때문입니다.

### 4. 스케일링 (Scaling)
면적은 수천 단위이고, 방 개수는 1~5단위입니다. 단위 차이가 너무 크면 모델이 면적 변수에만 과도하게 반응할 수 있습니다. 이를 방지하기 위해 모든 수치를 일정 범위로 맞추는 **StandardScaler**나 **MinMaxScaler**를 적용합니다.

---

## 파이썬 코드 실습: 집값 예측 파이프라인

이 실습에서는 가상의 부동산 데이터를 생성하여 선형 회귀와 랜덤 포레스트 모델의 성능을 비교하고, 잔차 분석까지 수행하는 전체 파이프라인을 구현해 보겠습니다.

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# 1. 가상 데이터 생성
np.random.seed(42)
n_samples = 1000
data = {
    'Size': np.random.normal(100, 30, n_samples), # 면적
    'Rooms': np.random.randint(1, 6, n_samples),   # 방 개수
    'Age': np.random.randint(0, 50, n_samples),    # 집의 나이
    'Location': np.random.choice(['City', 'Suburb', 'Rural'], n_samples), # 지역
    'Price': 0 # 타겟 변수
}
df = pd.DataFrame(data)
# 집값 결정 로직: 면적*1000 - 나이*500 + 지역가중치 + 노이즈 (비선형성 추가)
loc_map = {'City': 50000, 'Suburb': 20000, 'Rural': 0}
df['Price'] = df['Size']*1000 - (df['Age']**1.5)*100 + df['Location'].map(loc_map) + np.random.normal(0, 5000, n_samples)

# 2. 전처리: 타겟 변수 로그 변환 (왜곡 및 편향 방지)
df['Log_Price'] = np.log1p(df['Price'])

# 3. 특성 및 타겟 분리
X = df[['Size', 'Rooms', 'Age', 'Location']]
y = df['Log_Price']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 4. 전처리 파이프라인 설정
numeric_features = ['Size', 'Rooms', 'Age']
categorical_features = ['Location']
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), numeric_features),
        ('cat', OneHotEncoder(), categorical_features)
    ])

# 5. 모델 비교 분석 (Linear Regression vs Random Forest)
models = [
    ('Linear Regression', LinearRegression()),
    ('Random Forest', RandomForestRegressor(n_estimators=100, random_state=42))
]

results = {}
plt.figure(figsize=(15, 5))

for i, (name, model) in enumerate(models):
    # 파이프라인 구축 및 학습
    pipeline = Pipeline(steps=[('preprocessor', preprocessor), ('regressor', model)])
    pipeline.fit(X_train, y_train)
    
    # 예측 및 역변환
    y_pred_log = pipeline.predict(X_test)
    y_test_exp = np.expm1(y_test)
    y_pred_exp = np.expm1(y_pred_log)
    
    # 지표 계산
    mae = mean_absolute_error(y_test_exp, y_pred_exp)
    rmse = np.sqrt(mean_squared_error(y_test_exp, y_pred_exp))
    r2 = r2_score(y_test_exp, y_pred_exp)
    results[name] = {'MAE': mae, 'RMSE': rmse, 'R2': r2}
    
    # 실제값 vs 예측값 시각화
    plt.subplot(1, 2, i+1)
    plt.scatter(y_test_exp, y_pred_exp, alpha=0.5)
    plt.plot([y_test_exp.min(), y_test_exp.max()], [y_test_exp.min(), y_test_exp.max()], 'r--')
    plt.title(f'{name}: Actual vs Predicted')
    plt.xlabel('Actual Price')
    plt.ylabel('Predicted Price')

plt.tight_layout()
plt.show()

# 결과 출력
print(pd.DataFrame(results).T)

# 6. 잔차 분석 (최종 선택된 Random Forest 기준)
final_pipeline = Pipeline(steps=[('preprocessor', preprocessor), ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))])
final_pipeline.fit(X_train, y_train)
y_pred_final_log = final_pipeline.predict(X_test)
y_pred_final_exp = np.expm1(y_pred_final_log)
y_test_exp = np.expm1(y_test)

residuals = y_test_exp - y_pred_final_exp

plt.figure(figsize=(8, 6))
plt.scatter(y_pred_final_exp, residuals, alpha=0.5)
plt.axhline(y=0, color='r', linestyle='--')
plt.title('Residual Plot (Random Forest)')
plt.xlabel('Predicted Price')
plt.ylabel('Residuals (Actual - Predicted)')
plt.show()
```

### 실행 결과 해설

**1. 모델 비교 분석**
- **Linear Regression**: 데이터가 완벽한 직선 관계일 때 유리합니다. 하지만 실제 집값은 나이의 제곱에 비례하거나 지역별 특성이 복잡하게 얽혀 있어 $R^2$ 점수가 상대적으로 낮게 나올 수 있습니다.
- **Random Forest**: 트리 기반 모델은 데이터의 비선형적인 관계(예: 나이가 많아질수록 가격이 급격히 떨어지는 구간 등)를 훨씬 더 잘 잡아냅니다. 따라서 일반적으로 선형 회귀보다 MAE와 RMSE가 낮고 $R^2$가 높게 나타납니다.

**2. 성능 지표 해석**
- **MAE / RMSE**: 실제 가격과 예측 가격의 평균적인 오차입니다. RMSE가 MAE보다 훨씬 크다면, 일부 매물에서 예측이 크게 빗나갔음을 의미합니다.
- **$R^2$ Score**: 1에 가까울수록 모델이 집값의 변동성을 잘 설명하고 있다는 뜻입니다.

**3. 잔차 분석(Residual Plot) 해석**
- **그래프 확인법**: x축(예측값)에 따라 y축(잔차)의 점들이 **0을 중심으로 위아래로 무작위하게(Randomly)** 퍼져 있는지 확인해야 합니다.
- **정상**: 특정 패턴 없이 고르게 퍼져 있다면, 모델이 데이터의 주요 패턴을 모두 학습했고 남은 오차는 단순한 '노이즈'라는 뜻입니다.
- **비정상**: 만약 잔차가 U자나 역U자 형태의 곡선을 그린다면, 모델이 아직 잡아내지 못한 비선형 패턴이 남아 있다는 신호입니다. 이때는 특성 공학을 통해 새로운 변수를 추가하거나 더 정교한 모델을 검토해야 합니다.

---

## 모델 성능 평가 및 결과 해석

회귀 모델에서는 단순히 "정확도가 몇 %다"라고 말할 수 없습니다. 따라서 더 정밀한 분석이 필요합니다.

### 잔차 분석의 실무적 의미
잔차 분석은 모델의 '사각지대'를 찾는 과정입니다. 예를 들어, 저가 주택에서는 예측이 잘 되는데 고가 주택으로 갈수록 잔차가 커진다면, "고가 주택에만 영향을 주는 특수 변수(예: 브랜드 가치, 조망권)가 누락되었다"는 인사이트를 얻을 수 있습니다.

---

## 실전적 관점의 모델 개선 및 마무리

모델의 수치만 낮추는 것이 아니라, **"왜 이런 결과가 나왔는가"**를 분석하는 것이 실무의 핵심입니다.

### 1. 중요 변수 확인 (Feature Importance)
랜덤 포레스트와 같은 트리 기반 모델은 어떤 변수가 예측에 가장 큰 기여를 했는지 알려줍니다. 만약 `Location`의 중요도가 압도적으로 높다면, 지역별 세부 데이터를 더 보강하여 모델을 개선할 수 있습니다.

### 2. 하이퍼파라미터 튜닝
`GridSearchCV` 등을 사용하여 결정 트리의 깊이(`max_depth`)나 나무의 개수(`n_estimators`)를 최적화해 과적합을 방지하고 일반화 성능을 높입니다.

### 3. 비즈니스적 가치 해석
최종적으로 "이 모델을 통해 집값을 예측했을 때 오차 범위가 $\pm 5\%$ 이내이므로, 실제 매물 가격 산정의 기초 자료로 활용 가능하다"라는 비즈니스적 결론을 내리는 것이 프로젝트의 완성입니다.

---

## 자주 하는 실수

- **데이터 누수(Data Leakage)**: 전체 데이터에 대해 스케일링을 먼저 하고 데이터를 나누는 실수입니다. 반드시 **학습 데이터로만 스케일러를 학습(`fit`)시키고**, 테스트 데이터에는 적용(`transform`)만 해야 합니다. (이를 위해 위 코드에서 `Pipeline`을 사용했습니다.)
- **로그 변환 후 역변환 망각**: 타겟 변수에 로그를 취했다면, 최종 결과값은 반드시 `np.expm1()` 등을 통해 원래 단위로 되돌려야 합니다. 그렇지 않으면 예측값이 수천만 원이 아니라 '15.4' 같은 로그값으로 출력됩니다.
- **과도한 변수 추가**: 무조건 변수를 많이 넣는다고 성능이 좋아지지 않습니다. 서로 상관관계가 너무 높은 변수들이 많으면 '다중공선성' 문제가 발생해 모델이 불안정해질 수 있습니다.

---

## 핵심 요약
- **회귀 파이프라인**: EDA $\rightarrow$ 특성 공학 $\rightarrow$ 모델링 $\rightarrow$ 평가 $\rightarrow$ 개선의 반복 과정이다.
- **특성 공학**: 로그 변환으로 극단적 값의 영향력을 줄여 편향을 막고, 원-핫 인코딩으로 범주형 데이터를 처리하며, 도메인 지식으로 파생 변수를 만든다.
- **모델 평가**: MAE, RMSE로 오차의 크기를 측정하고, $R^2$로 설명력을 확인하며, 잔차 분석으로 모델의 편향과 패턴 누락을 체크한다.
- **파이프라인**: `Pipeline`을 사용하면 전처리부터 예측까지의 과정을 하나로 묶어 데이터 누수를 방지하고 관리를 효율화할 수 있다.

---

## 확인 문제
1. 집값 데이터처럼 한쪽으로 치우친 분포에서 초고가 주택과 같은 극단적인 값이 모델의 예측선을 과도하게 끌어올리는 것을 방지하기 위해 사용하는 변환 기법은 무엇인가요?
2. '건축 연도'라는 변수보다 '집의 나이'라는 변수가 모델에 더 유리한 이유는 무엇인가요?
3. 회귀 모델의 잔차 분석 그래프에서 점들이 0을 중심으로 무작위하게 퍼져 있지 않고 특정한 패턴(예: 곡선)을 보인다면, 이는 무엇을 의미하나요?

**정답 및 해설**
1. **로그 변환(Log Transformation)**: 큰 값을 상대적으로 작게 압축하여 분포의 왜곡(Skewness)을 줄이고 모델의 편향을 방지합니다.
2. **직관적인 특성 제공**: 모델이 '현재 시점으로부터 얼마나 오래되었는가'라는 상대적 가치를 더 쉽게 학습할 수 있기 때문입니다.
3. **모델의 패턴 학습 미흡**: 모델이 데이터 내의 특정 비선형 관계나 중요한 변수 간의 상호작용을 제대로 학습하지 못했음을 의미하며, 특성 추가나 모델 변경이 필요합니다.

---

## 미니 프로젝트: 나만의 집값 예측 모델 고도화
제공된 코드를 바탕으로 다음 기능을 추가하여 모델을 고도화해 보세요.
1. **새로운 파생 변수 추가**: 예를 들어 `면적 / 방 개수` (방 하나당 평균 면적) 변수를 만들어 성능이 향상되는지 확인하세요.
2. **모델 비교 확장**: `XGBoost`나 `GradientBoostingRegressor`를 추가하여 랜덤 포레스트보다 성능이 더 좋아지는지 비교해 보세요.
3. **하이퍼파라미터 튜닝**: `GridSearchCV`를 사용하여 랜덤 포레스트의 최적 파라미터를 찾아보고, 튜닝 전후의 $R^2$ 점수 차이를 기록해 보세요.