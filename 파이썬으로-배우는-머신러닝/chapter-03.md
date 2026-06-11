# 챕터 3: NumPy와 Pandas

# 3장. NumPy와 Pandas: 머신러닝을 위한 데이터 요리법

머신러닝 모델을 만드는 과정은 흔히 요리에 비유됩니다. 훌륭한 요리를 만들기 위해서는 좋은 재료가 필요하고, 그 재료를 깨끗이 씻고 다듬는 '전처리' 과정이 필수적입니다. 머신러닝에서 '재료'는 바로 **데이터**이며, 이 데이터를 다루는 가장 강력한 도구가 바로 **NumPy**와 **Pandas**입니다.

파이썬의 기본 리스트(List)만으로도 데이터를 다룰 수는 있지만, 수만 개의 데이터를 처리해야 하는 머신러닝 환경에서는 속도가 너무 느리고 불편합니다. 이번 장에서는 데이터를 효율적으로 저장하고 계산하는 NumPy와, 표 형태의 데이터를 자유자재로 다루는 Pandas의 핵심 기능을 살펴보겠습니다.

---

## 1. NumPy: 수치 계산의 초석

### 1.1 NumPy란 무엇인가?

**[비유: 뒤섞인 장난감 상자 vs 정리된 계란판]**
파이썬의 기본 리스트는 '장난감 상자'와 같습니다. 인형, 자동차, 블록 등 서로 다른 종류의 물건을 한꺼번에 넣을 수 있어 편리하지만, 정작 특정 물건을 빠르게 찾거나 전체를 한꺼번에 옮기기에는 효율이 떨어집니다. 

반면, NumPy의 배열(Array)은 '계란판'과 같습니다. 모든 칸에 동일한 크기와 종류의 계란(데이터 타입)만 들어갈 수 있습니다. 제약이 있는 대신, 위치가 정확히 정해져 있어 수천 개의 데이터를 한꺼번에 계산할 때 압도적으로 빠릅니다.

**[그림: 계란판에 데이터가 정렬된 모습 - 각 칸에 동일한 타입의 숫자가 규칙적으로 배치되어 있고, 인덱스로 빠르게 접근하는 모습]**

**[직관]**
머신러닝은 결국 거대한 숫자들의 계산입니다. 이미지 한 장은 수만 개의 픽셀 값(숫자)으로 이루어져 있고, 텍스트 데이터 역시 숫자로 변환되어 처리됩니다. NumPy는 이러한 대량의 숫자 데이터를 **행렬(Matrix)** 형태로 처리하여 계산 속도를 극대화합니다.

**[기술 설명]**
NumPy(Numerical Python)는 파이썬의 과학 계산 라이브러리로, 핵심 객체인 `ndarray`(n-dimensional array)를 제공합니다. `ndarray`는 동일한 자료형의 데이터를 메모리에 연속적으로 배치하여, 파이썬 리스트보다 메모리 사용량이 적고 연산 속도가 훨씬 빠릅니다.

#### NumPy 기본 실습: 배열 생성과 연산

```python
import numpy as np

# 1. 리스트를 NumPy 배열로 변환
data_list = [1, 2, 3, 4, 5]
arr = np.array(data_list)

# 2. 다양한 배열 생성 방법
zeros = np.zeros((2, 3))       # 2행 3열의 0으로 채워진 배열
ones = np.ones((2, 3))        # 2행 3열의 1으로 채워진 배열
arange_arr = np.arange(0, 10, 2) # 0부터 10 미만까지 2씩 증가

print("기본 배열:\n", arr)
print("\n0으로 채워진 배열:\n", zeros)
print("\n범위 배열:", arange_arr)

# 3. 벡터 연산 (Element-wise operation)
# 리스트였다면 for문을 돌려야 했지만, NumPy는 한 번에 계산합니다.
arr_plus_10 = arr + 10 
arr_mul_2 = arr * 2

print("\n모든 요소에 10 더하기:", arr_plus_10)
print("모든 요소에 2 곱하기:", arr_mul_2)
```

**[실행 결과]**
```text
기본 배열:
 [1 2 3 4 5]

0으로 채워진 배열:
 [[0. 0. 0.]
 [0. 0. 0.]]

범위 배열: [0 2 4 6 8]

모든 요소에 10 더하기: [11 12 13 14 15]
모든 요소에 2 곱하기: [2 4 6 8 10]
```

**[결과 해석]**
- `np.array()`를 통해 파이썬 리스트를 NumPy 배열로 변환했습니다.
- 가장 주목할 점은 `arr + 10` 부분입니다. 파이썬 리스트에 10을 더하면 오류가 발생하거나 리스트가 확장되지만, NumPy 배열은 **브로드캐스팅(Broadcasting)**이라는 기능을 통해 배열 내의 모든 요소에 동일한 연산을 한 번에 적용합니다. 이것이 머신러닝에서 NumPy를 사용하는 핵심 이유입니다.

---

### 1.2 배열의 모양 바꾸기와 슬라이싱

머신러닝 모델에 데이터를 넣을 때 가장 많이 마주치는 에러가 바로 "데이터의 모양(Shape)이 맞지 않는다"는 것입니다. 따라서 배열의 형태를 자유자재로 바꾸는 능력이 필요합니다.

**[비유: 찰흙 덩어리 모양 만들기]**
12개의 찰흙 공이 일렬로 늘어서 있다고 생각해보세요. 이를 3x4 직사각형 모양으로 배치할 수도 있고, 2x6 모양으로 배치할 수도 있습니다. 전체 개수는 변하지 않지만, 배치 방식(Shape)에 따라 사용 용도가 달라집니다.

**[그림: 1차원 배열이 2차원으로 변형되는 과정 - 1x12 형태의 긴 막대 모양 배열이 3x4 형태의 표 모양으로 재배치되는 모습]**

#### NumPy 실습: Shape 조절과 인덱싱

```python
# 1. 1차원 배열 생성 (요소 12개)
arr_1d = np.arange(12)
print("1차원 배열:", arr_1d)
print("Shape:", arr_1d.shape)

# 2. 2차원으로 모양 변경 (Reshape)
arr_2d = arr_1d.reshape(3, 4)
print("\n3x4 배열로 변환:\n", arr_2d)
print("Shape:", arr_2d.shape)

# 3. 특정 데이터 추출 (슬라이싱)
# [행, 열] 순서로 지정합니다.
print("\n첫 번째 행 전체:", arr_2d[0, :])
print("두 번째 열 전체:", arr_2d[:, 1])
print("1행 2열의 값:", arr_2d[1, 2])
```

**[실행 결과]**
```text
1차원 배열: [ 0  1  2  3  4  5  6  7  8  9 10 11]
Shape: (12,)

3x4 배열로 변환:
 [[ 0  1  2  3]
 [ 4  5  6  7]
 [ 8  9 10 11]]
Shape: (3, 4)

첫 번째 행 전체: [0 1 2 3]
두 번째 열 전체: [1 5 9]
1행 2열의 값: 6
```

**[결과 해석]**
- `reshape()` 함수를 통해 데이터의 총 개수를 유지한 채 차원을 변경했습니다. 머신러닝 모델(예: 딥러닝)은 입력 데이터의 차원을 엄격하게 따지기 때문에 이 작업이 매우 빈번하게 일어납니다.
- `arr_2d[:, 1]`과 같이 `:` 기호를 사용하면 "해당 축의 모든 요소"를 가져오겠다는 의미입니다. 즉, 모든 행의 1번 인덱스 열만 가져오게 됩니다.

---

## 2. Pandas: 데이터 분석의 만능 도구

### 2.1 Pandas란 무엇인가?

**[비유: 파이썬 속에 들어온 엑셀(Excel)]**
NumPy가 순수한 숫자들의 집합이라면, Pandas는 여기에 '이름'과 '라벨'을 붙인 것입니다. 엑셀 시트를 떠올려 보세요. 맨 위에는 '이름', '나이', '거주지' 같은 열 이름(Column Name)이 있고, 왼쪽에는 1, 2, 3... 같은 행 번호(Index)가 있습니다. Pandas는 이 엑셀과 같은 구조를 파이썬 코드만으로 제어할 수 있게 해줍니다.

**[그림: DataFrame의 구조 - 행(Index)과 열(Column)의 명칭이 표시된 표 형태의 도식]**

**[직관]**
실제 머신러닝 데이터는 숫자만 있는 것이 아니라, 날짜, 텍스트, 범주형 데이터 등이 섞여 있습니다. 이를 효율적으로 관리하기 위해 Pandas는 표 형태의 구조인 **DataFrame**을 제공합니다.

**[기술 설명]**
Pandas의 핵심 구조는 두 가지입니다.
1. **Series**: 1차원 배열 형태의 데이터 구조 (열 하나).
2. **DataFrame**: 여러 개의 Series가 모여 만들어진 2차원 표 형태의 데이터 구조.

#### Pandas 실습 1: Series 생성과 확인

DataFrame을 배우기 전, 그 기본 단위인 Series를 먼저 살펴보겠습니다. Series는 이름표(Index)가 붙은 1차원 리스트라고 생각하면 쉽습니다.

```python
import pandas as pd

# Series 생성 (데이터와 인덱스를 직접 지정)
s = pd.Series([85, 90, 78, 92], index=['Alice', 'Bob', 'Charlie', 'David'])
print("생성된 Series:\n", s)

# 인덱스를 이용한 데이터 접근
print("\nBob의 점수:", s['Bob'])
```

**[실행 결과]**
```text
생성된 Series:
Alice      85
Bob        90
Charlie    78
David      92
dtype: int64

Bob의 점수: 90
```

**[결과 해석]**
- NumPy 배열과 달리, 각 데이터에 'Alice', 'Bob'과 같은 고유한 이름(Index)을 붙일 수 있습니다. 이를 통해 숫자가 아닌 의미 있는 라벨로 데이터를 관리할 수 있게 됩니다.

#### Pandas 실습 2: DataFrame 생성과 조회

이제 여러 개의 Series가 합쳐진 형태인 DataFrame을 만들어 보겠습니다.

```python
# 1. 딕셔너리를 이용한 DataFrame 생성
data = {
    'Name': ['Alice', 'Bob', 'Charlie', 'David'],
    'Age': [25, 30, 35, 40],
    'City': ['Seoul', 'Busan', 'Incheon', 'Daegu'],
    'Score': [85, 90, 78, 92]
}

df = pd.DataFrame(data)
print("생성된 DataFrame:\n", df)

# 2. 데이터 확인하기
print("\n상위 2개 행 확인:\n", df.head(2))
print("\n데이터 요약 정보:\n", df.info())
print("\n수치형 데이터 기초 통계:\n", df.describe())
```

**[실행 결과]**
```text
생성된 DataFrame:
      Name  Age     City  Score
0    Alice   25    Seoul     85
1      Bob   30    Busan     90
2  Charlie   35  Incheon     78
3    David   40    Daegu     92

상위 2개 행 확인:
    Name  Age   City  Score
0  Alice   25  Seoul     85
1    Bob   30  Busan     90

데이터 요약 정보:
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 4 entries, 0 to 3
Data columns (total 4 columns):
 ... (생략) ...

수치형 데이터 기초 통계:
             Age     Score
count  4.000000   4.000000
mean  32.500000  86.250000
std    6.454972   5.767481
min   25.000000  78.000000
max   40.000000  92.000000
```

**[결과 해석]**
- `pd.DataFrame()`을 통해 표 형태의 데이터를 만들었습니다.
- `head()`는 데이터가 너무 많을 때 상위 일부만 확인하는 용도로 사용합니다.
- `describe()`는 머신러닝 전처리 단계에서 매우 중요합니다. 평균(`mean`), 표준편차(`std`), 최솟값(`min`), 최댓값(`max`) 등을 한눈에 보여주어 데이터의 분포를 빠르게 파악하게 해줍니다.

---

### 2.2 데이터 필터링과 가공

머신러닝의 핵심은 "필요한 데이터만 골라내어 학습시키는 것"입니다. Pandas의 강력한 필터링 기능을 활용해 보겠습니다.

**[비유: 거름망으로 알갱이 골라내기]**
수많은 모래와 자갈이 섞인 통에서 특정 크기 이상의 자갈만 골라내고 싶을 때 거름망을 사용합니다. Pandas의 **불리언 인덱싱(Boolean Indexing)**이 바로 이 거름망 역할을 합니다.

**[그림: 전체 데이터셋에서 'Age >= 30'이라는 거름망을 통과하여 조건에 맞는 행들만 아래로 추출되는 모습]**

#### Pandas 실습: 조건부 필터링과 열 조작

```python
# 1. 조건에 맞는 데이터 필터링 (Age가 30세 이상인 사람만)
over_30 = df[df['Age'] >= 30]
print("30세 이상 사용자:\n", over_30)

# 2. 새로운 열 추가 (합격 여부 판단)
# Score가 80점 이상이면 'Pass', 아니면 'Fail'
df['Result'] = df['Score'].apply(lambda x: 'Pass' if x >= 80 else 'Fail')
print("\n결과 열이 추가된 DataFrame:\n", df)

# 3. 특정 열만 선택하여 추출
subset = df[['Name', 'Result']]
print("\n이름과 결과만 추출:\n", subset)
```

**[실행 결과]**
```text
30세 이상 사용자:
      Name  Age     City  Score
1      Bob   30    Busan     90
2  Charlie   35  Incheon     78
3    David   40    Daegu     92

결과 열이 추가된 DataFrame:
      Name  Age     City  Score Result
0    Alice   25    Seoul     85   Pass
1      Bob   30    Busan     90   Pass
2  Charlie   35  Incheon     78   Fail
3    David   40    Daegu     92   Pass

이름과 결과만 추출:
      Name Result
0    Alice   Pass
1      Bob    Pass
2  Charlie   Fail
3    David   Pass
```

**[결과 해석]**
- `df[df['Age'] >= 30]` 구문은 `df['Age'] >= 30`이라는 조건문이 `True`인 행만 남기는 방식입니다.
- `.apply(lambda x: ...)`를 사용하면 열의 모든 값에 특정 함수를 적용하여 새로운 데이터를 생성할 수 있습니다. 이는 머신러닝에서 데이터를 수치화(Encoding)할 때 매우 유용하게 쓰입니다.

---

## 3. 실무 활용 사례: CSV 파일 분석하기

실무에서는 데이터를 직접 입력하지 않고 `.csv` (Comma Separated Values) 파일 형태로 제공받습니다. Pandas는 이를 읽어 들이는 최적의 기능을 갖추고 있습니다.

**[시나리오]**
당신은 부동산 가격 예측 모델을 만들려고 합니다. `house_data.csv`라는 파일에 집의 크기, 방 개수, 가격 데이터가 들어있다고 가정해 봅시다.

```python
# (실습을 위해 임시 CSV 파일을 생성합니다)
import pandas as pd
import numpy as np

# 임시 데이터 생성 및 저장
raw_data = {
    'Size': [50, 80, 120, 60, 150],
    'Rooms': [1, 2, 3, 2, 4],
    'Price': [5000, 8000, 12000, 6500, 16000]
}
temp_df = pd.DataFrame(raw_data)
temp_df.to_csv('house_data.csv', index=False)

# --- 여기서부터 실제 분석 과정 ---

# 1. CSV 파일 읽기
df_house = pd.read_csv('house_data.csv')

# 2. 데이터 탐색: 평당 가격(Price per Size) 계산 열 추가
df_house['Price_per_Size'] = df_house['Price'] / df_house['Size']

# 3. 평균 평당 가격보다 비싼 집만 추출
avg_price_per_size = df_house['Price_per_Size'].mean()
expensive_houses = df_house[df_house['Price_per_Size'] > avg_price_per_size]

print(f"평균 평당 가격: {avg_price_per_size:.2f}")
print("\n평균보다 비싼 집 목록:\n", expensive_houses)
```

**[실행 결과]**
```text
평균 평당 가격: 103.00

평균보다 비싼 집 목록:
    Size  Rooms  Price  Price_per_Size
3     60      2   6500       108.333333
4    150      4  16000       106.666667
```

**[해석]**
실무에서 Pandas는 단순히 데이터를 보는 도구가 아니라, **특성 공학(Feature Engineering)**의 도구입니다. 위 예제에서 `Price_per_Size`라는 새로운 열을 만든 것처럼, 기존 데이터를 조합해 모델이 학습하기 좋은 새로운 지표를 만들어내는 과정이 머신러닝 성능 향상의 핵심입니다.

---

## 4. 초보자가 자주 하는 실수와 해결 방법

### ❌ 실수 1: NumPy 배열과 파이썬 리스트의 연산 혼동
- **현상**: 리스트에 숫자를 더하려다 `TypeError`가 발생하거나, `+` 연산자로 리스트가 합쳐지는 현상.
- **해결**: 수치 계산이 필요하다면 반드시 `np.array()`로 변환 후 연산하세요.

### ❌ 실수 2: DataFrame 슬라이싱 시 `SettingWithCopyWarning` 발생
- **현상**: `df[df['Age'] > 30]['Score'] = 100` 처럼 필터링 후 바로 값을 수정하려 할 때 경고가 발생합니다.
- **해결**: `.loc`를 사용하세요. `df.loc[df['Age'] > 30, 'Score'] = 100`으로 작성하면 안전하게 값이 수정됩니다.

### ❌ 실수 3: 데이터 타입 불일치
- **현상**: 숫자가 들어있어야 할 열이 문자열(`object`) 타입으로 인식되어 계산이 안 되는 경우.
- **해결**: `df.info()`로 타입을 확인하고, `df['column'].astype(float)`를 통해 타입을 강제로 변환하세요.

---

## 5. 요약 및 마무리

이번 장에서는 머신러닝의 기초 체력이라고 할 수 있는 NumPy와 Pandas를 학습했습니다.

| 도구 | 핵심 개념 | 비유 | 주 용도 |
| :--- | :--- | :--- | :--- |
| **NumPy** | `ndarray`, Vectorization | 계란판 | 고속 수치 계산, 행렬 연산 |
| **Pandas** | `DataFrame`, `Series` | 엑셀 시트 | 데이터 전처리, 분석, 필터링 |

**핵심 흐름 요약:**
1. **NumPy**를 통해 데이터를 효율적인 행렬 구조로 만들고, 브로드캐스팅을 통해 빠르게 계산합니다.
2. **Pandas**를 통해 실제 데이터 파일(CSV 등)을 읽어오고, 표 형태로 관리하며, 필요한 조건으로 필터링합니다.
3. **전처리** 과정을 통해 모델이 학습하기 좋은 형태로 데이터를 가공합니다.

이제 여러분은 데이터를 다루는 '요리 도구'를 갖추게 되었습니다. 다음 장에서는 이렇게 준비된 데이터를 가지고 실제로 머신러닝 모델이 어떻게 학습하는지, 그 원리를 살펴보겠습니다.