# 기술적 분석 지표 계산 명세서 (★4 이상)

> **범위**: 1차 마스터 목록에서 신뢰도 ★★★★ 이상으로 판정된 지표(원 저자 실명 + 문서화된 1차 출처)의 **계산 방법**을 플랫폼 독립적으로 기술한다. 이 수록 기준에는 예외가 하나 있다. APO(§2.28)는 원저자를 세울 수 있는 1차 출처가 없어, 이동평균 종류를 파라미터로 남긴 문서화된 정의를 출처로 삼아 수록했다(§13의 27번). 기준을 넓힌 것이 아니라 이 한 항목만 예외로 못박은 것이다. 계산 원본을 정하는 정책의 별도 예외는 §0.12에 한정해 둔다.
> **중복 제거 원칙**: 여러 지표가 공유하는 기초 연산(EMA, SMA, WMA, Wilder 평활, True Range, Typical Price, 표준편차, rolling 최고/최저 등)은 **§0 공유 프리미티브**에 단 한 번만 정의하고, 각 지표는 이를 **참조**한다. 지표 본문에는 그 지표 고유의 계산만 기술한다.
> **표기 규약**: `C`=종가, `O`=시가, `H`=고가, `L`=저가, `V`=거래량, `P`=대상 시계열(문맥상 대개 종가), 아래첨자 `t`=현재 봉, `t-1`=직전 봉. `n`=기간(period).

---

## §0. 공유 계산 프리미티브 (Shared Primitives)

이 계층은 이후 모든 지표가 재사용한다. 지표 본문에서 `SMA(P,n)`, `EMA(P,n)`, `RMA(P,n)`, `TR_t`, `TP_t` 등으로 호출한다.

### 0.1 가격 파생 입력 (Price Inputs)

| 이름 | 기호 | 공식 |
|---|---|---|
| Median Price (중간가) | HL2 | `(H + L) / 2` |
| Typical Price (전형가) | HLC3, TP | `(H + L + C) / 3` |
| Weighted Close (가중종가) | HLCC4 | `(H + L + 2C) / 4` |
| OHLC 평균 | OHLC4 | `(O + H + L + C) / 4` |

### 0.2 SMA — Simple Moving Average

```
SMA(P, n)_t = (1/n) · Σ_{i=0}^{n-1} P_{t-i}
```
- warm-up: 처음 `n-1` 봉은 정의되지 않음(NaN).
- 시간복잡도: 슬라이딩 합 사용 시 O(1)/봉, 전체 O(N).

### 0.3 EMA — Exponential Moving Average
```
α = 2 / (n + 1)
EMA_t = α · P_t + (1 − α) · EMA_{t-1}
```
- **초기값(seed)**: 표준(TA-Lib, TradingView) 방식은 첫 EMA를 **처음 n개의 SMA**로 시딩한 뒤 t=n부터 재귀 적용. 일부 구현(pandas-ta `adjust=False` 기본, 단순 방식)은 첫 값 = 첫 데이터포인트로 시딩 → warm-up 초반 값이 다름.
- pandas-ta `adjust=True`는 유한 급수 가중합으로 계산해 초반 값이 재귀식과 미세하게 다름 → **플랫폼 간 초반 오차의 주원인**.

### 0.4 WMA — Weighted Moving Average (선형가중)
```
WMA(P, n)_t = Σ_{i=1}^{n} (i · P_{t-n+i}) / Σ_{i=1}^{n} i
           = [n·P_t + (n−1)·P_{t-1} + ... + 1·P_{t-n+1}] / [n(n+1)/2]
```
가장 최근 봉에 최대 가중치 `n`, 가장 오래된 봉에 `1`.

### 0.5 RMA / SMMA / Wilder's Smoothing (Wilder 평활)
Wilder(1978)가 RSI·ATR·ADX에 쓴 평활. TradingView `ta.rma`, pandas-ta `rma`, Welles Wilder Smoothing, SMMA와 **수학적으로 동일**.
```
α = 1 / n
RMA_t = α · P_t + (1 − α) · RMA_{t-1}
      = RMA_{t-1} + (P_t − RMA_{t-1}) / n
```
- **초기값(seed)**: 첫 RMA = 처음 n개의 SMA.
- EMA와의 관계: RMA(n) ≡ EMA with `α = 1/n` (즉 EMA의 "유효기간" ≈ `2n−1`). **RMA(14) ≠ EMA(14)** 이므로 혼동 주의.
- Wilder 원서의 "running total" 서술식 `Sum_t = Sum_{t-1} − Sum_{t-1}/n + P_t` 는 위 재귀식과 동치(스케일만 다름).

### 0.6 True Range (TR)
```
TR_t = max( H_t − L_t ,  |H_t − C_{t-1}| ,  |L_t − C_{t-1}| )
```
- 첫 봉(`C_{t-1}` 없음): `TR_0 = H_0 − L_0`.

### 0.7 표준편차 / 분산 (Standard Deviation / Variance)
Bollinger·CCI 등에서 **모표준편차(population, 분모 n)** 사용이 관례.
```
mean = SMA(P, n)_t
Var(P, n)_t = (1/n) · Σ_{i=0}^{n-1} (P_{t-i} − mean)^2
StDev(P, n)_t = sqrt( Var(P, n)_t )
```
- 주의: 일부 통계 라이브러리는 표본표준편차(분모 n−1). 지표용은 관례상 모표준편차.

### 0.8 rolling 최고/최저 (Highest / Lowest)
```
HH(n)_t = max( H_t, H_{t-1}, ..., H_{t-n+1} )
LL(n)_t = min( L_t, L_{t-1}, ..., L_{t-n+1} )
```
(대상 시계열이 종가면 `HH`는 `max(C...)`로 치환.)

### 0.9 누적합 / 누적 (Cumulative)
```
Cum_t = Cum_{t-1} + x_t   (초기 Cum_0 = x_0)
```
OBV·A/D Line·NVI·PVI·누적 델타 등이 사용.

### 0.10 ROC — Rate of Change (기초 모멘텀)
```
ROC(P, n)_t = 100 · (P_t − P_{t-n}) / P_{t-n}
```
(백분율 없는 원시형 `MOM(n) = P_t − P_{t-n}` 도 다수 지표의 부품.)

### 0.11 나눗셈/예외 처리 공통 규약
- **divide-by-zero**: 분모가 0이면 결과를 `0`, `100`(RSI류에서 손실=0), 또는 직전값으로 대체 — 구현체별 상이. 본 문서는 각 지표에서 해당 규약을 명시.
- **NaN 전파**: warm-up 구간은 NaN 유지 권장(0 대체 시 초기 신호 왜곡).
- **실시간(update) vs 배치**: 재귀형(EMA/RMA/SAR/누적)은 확정된 직전값만 사용해야 함 → **미확정(진행 중) 봉으로 상태 갱신 금지**(look-ahead/재계산 오염 방지). 프로젝트 규약 `close_time ≤ T` 준수.

### 0.12 계산 출처 정책 예외 — TA-Lib 함수 아홉 개

일반 정책에서 TA-Lib과 다른 외부 라이브러리는 독립 계산 원본이 아니라 교차대조군이다.
`services/core-lib/tests/indicator_reference/__init__.py`의 "TA-Lib은 대조군이고 계산
원본이 아니다"라는 설명도 이 일반 정책을 가리킨다. 다만 아래 아홉 함수에는 그 정책을
적용하지 않고 **TA-Lib C 구현 자체를 계산 원본으로 삼는다.** 이 예외는 다른 TA-Lib
함수나 다른 지표로 자동 확대되지 않는다.

| 함수 | 고정 원본 파일 |
|---|---|
| `MAMA`와 그 두 출력 `MAMA`, `FAMA` | `src/ta_func/ta_MAMA.c` |
| `HT_SINE` | `src/ta_func/ta_HT_SINE.c` |
| `HT_TRENDLINE` | `src/ta_func/ta_HT_TRENDLINE.c` |
| `HT_DCPERIOD` | `src/ta_func/ta_HT_DCPERIOD.c` |
| `HT_DCPHASE` | `src/ta_func/ta_HT_DCPHASE.c` |
| `HT_PHASOR` | `src/ta_func/ta_HT_PHASOR.c` |
| `HT_TRENDMODE` | `src/ta_func/ta_HT_TRENDMODE.c` |
| `BETA` | `src/ta_func/ta_BETA.c` |
| `CORREL` | `src/ta_func/ta_CORREL.c` |

원본 저장소는 `https://github.com/TA-Lib/ta-lib`, 태그는 `v0.7.1`, 커밋은
`2247d599bddf37ed37e3a709371517e46efc66f6`으로 고정한다. 위 파일들은 원래 경로를
유지한 채 `third_party/ta-lib/src/ta_func/`에 반입한다. Ehlers 원저의 6-tap 계수와
위상 파이프라인 상수를 확보하지 못해 §8.1과 §8.4가 미확정으로 남아 있었고, 상수를
지어내는 대신 공개된 TA-Lib 구현을 계산 원본으로 삼기로 사용자가 확정했기 때문에
이 일곱에 더해, 두 가격 계열의 입력 순서와 0에 가까운 분모 처리를 원본과 같은 값으로
고정해야 하는 BETA와 CORREL도 공개된 TA-Lib 구현을 계산 원본으로 삼는다. 예외는 위 표의
아홉 함수로 닫혀 있다.

`third_party/ta-lib/SHA256SUMS`와
`services/core-lib/tests/test_talib_vendored_sources.py`는 패턴 판정 소스 61개, 공용
소스 2개, Hilbert 지표 소스 7개, 통계 지표 소스 2개의 경로 집합과 개수 및 각 SHA-256을
네트워크 없이 검증한다. 계산 포트는 TA-Lib 0.7.1의 오프라인 포획값과 상대·절대 오차 모두
`1e-9` 이내로 대조하고, 서로 독립인 배치 경로와 상태 경로는 상대·절대 오차 모두
`1e-12` 이내로 대조한다. `HT_TRENDMODE`는 허용오차 없이 정확히 대조한다. 런타임과
지속적 통합 환경은 외부 TA-Lib 설치에 의존하지 않는다.

---

## §1. Trend / Moving Average 계열 (★4↑)

> 아래 이동평균들은 모두 §0.2~0.5의 SMA/EMA/WMA/RMA를 부품으로 조합한다.

### 1.1 DEMA — Double EMA (Mulloy, 1994) ★★★★★
중복 제거: EMA(§0.3)만 사용.
```
EMA1 = EMA(P, n)
EMA2 = EMA(EMA1, n)
DEMA = 2·EMA1 − EMA2
```
목적: 이중 평활의 지연(lag) 감소.

### 1.2 TEMA — Triple EMA (Mulloy, 1994) ★★★★★
```
EMA1 = EMA(P, n);  EMA2 = EMA(EMA1, n);  EMA3 = EMA(EMA2, n)
TEMA = 3·EMA1 − 3·EMA2 + EMA3
```

### 1.3 T3 (Tim Tillson, 1998) ★★★★
GD(Generalized DEMA) 3중 적용. `v`=volume factor(기본 0.7).
```
GD(P) = EMA1·(1+v) − EMA2·v,  where EMA1=EMA(P,n), EMA2=EMA(EMA1,n)
T3 = GD( GD( GD(P) ) )
```
전개형 계수(6중 EMA e1..e6, a=v):
```
c1 = −a^3
c2 = 3a^2 + 3a^3
c3 = −6a^2 − 3a − 3a^3
c4 = 1 + 3a + a^3 + 3a^2
T3 = c1·e6 + c2·e5 + c3·e4 + c4·e3
```

### 1.4 HMA — Hull MA (Alan Hull, 2005) ★★★★
중복 제거: WMA(§0.4)만 사용.
```
HMA(n) = WMA( 2·WMA(P, n/2) − WMA(P, n),  round(sqrt(n)) )
```
(`n/2`는 정수화, `sqrt(n)`는 반올림.)

### 1.5 ZLEMA — Zero-Lag EMA (Ehlers & Way) ★★★★
```
lag = floor( (n − 1) / 2 )
P'_t = P_t + (P_t − P_{t-lag})        (지연 보정된 합성가격)
ZLEMA = EMA(P', n)
```

### 1.6 ALMA — Arnaud Legoux MA (2009) ★★★★
가우시안 가중, offset `s`(기본 0.85), sigma `σ`(기본 6), 윈도우 `n`.
```
m = s · (n − 1)
d = n / σ
w_i = exp( −(i − m)^2 / (2·d^2) ),   i = 0..n-1
ALMA_t = Σ_i ( w_i · P_{t-(n-1)+i} ) / Σ_i w_i
```

### 1.7 KAMA — Kaufman Adaptive MA (Perry Kaufman, 1995) ★★★★★
```
Change     = |P_t − P_{t-n}|
Volatility = Σ_{i=0}^{n-1} |P_{t-i} − P_{t-i-1}|
ER = Change / Volatility                          (분모 0 → ER=0)
fastSC = 2/(2+1) ;  slowSC = 2/(30+1)
SC = ( ER·(fastSC − slowSC) + slowSC )^2
KAMA_t = KAMA_{t-1} + SC·(P_t − KAMA_{t-1})
```

### 1.8 VIDYA — Variable Index Dynamic Average (Tushar Chande, 1992) ★★★★
```
k = |CMO(P, m)| / 100          (0~1, m=변동성 산정기간, 흔히 9)
α = 2/(n+1)
VIDYA_t = α·k·P_t + (1 − α·k)·VIDYA_{t-1}
```
- **구현체별 상이**: 원 Chande 버전은 표준편차 비율(단기σ/장기σ)을 k로 사용. TradingView/pandas-ta는 CMO 기반이 흔함 → 채택 구현 명시 필요.

### 1.9 McGinley Dynamic (John McGinley) ★★★★
```
MD_t = MD_{t-1} + (P_t − MD_{t-1}) / ( N · (P_t / MD_{t-1})^4 )
```

### 1.10 Guppy Multiple MA (GMMA, Daryl Guppy) ★★★★
단일 공식 없음 — EMA 집합의 배열.
```
단기군: EMA(3,5,8,10,12,15)
장기군: EMA(30,35,40,45,50,60)
```

### 1.11 TRIMA — Triangular Moving Average ★★★★
중복 제거: SMA(§0.2)만 사용. 창 중앙의 가격에 가장 큰 가중을 주고 양 끝으로 갈수록 선형으로 줄여, 창 앞뒤의 잡음을 함께 눌러 준다.
```
n1 = n/2 ,      n2 = n/2 + 1          (n 짝수)
n1 = n2 = (n + 1)/2                    (n 홀수)
TRIMA(P, n) = SMA( SMA(P, n1), n2 )
```
동치인 가중합 표현(같은 값을 다른 형태로 쓴 것):
```
w_i = min(i + 1, n − i) ,   i = 0..n-1
TRIMA(P, n)_t = Σ_i ( w_i · P_{t-(n-1)+i} ) / Σ_i w_i
```
- 1차 출처: Kaufman, *Trading Systems and Methods*의 "Triangular Weighting" 절과 그 절이 인용하는 J. J. Payne, "A Better Way to Smooth Data", *Technical Analysis of Stocks & Commodities*, 1989년 10월(§13의 5번과 24번). Kaufman은 창의 크기를 `n`으로 명시하고, 가중치가 창 중앙까지 선형으로 커졌다가 창 끝까지 다시 작아진다고 정의한다.
- **짝수 `n`의 분할이 위와 같이 정해지는 근거.** 길이 `a`와 `b`인 두 단순이동평균을 겹치면 결과는 `a + b − 1`봉에 걸친다. 창이 정확히 `n`봉이어야 하므로 `a + b = n + 1`이다. 여기에 위 인용이 정의한 조건, 곧 가중치가 창 중앙까지 선형으로 커졌다가 창 끝까지 다시 작아지는 **삼각형**이어야 한다는 조건을 더한다. 두 단순이동평균을 겹친 가중치는 선형으로 올라간 뒤 `|a − b| + 1`봉 동안 최댓값에 머물다가 다시 선형으로 내려간다. 꼭짓점 바깥으로 평평한 구간이 뻗지 않으려면 그 길이가 두 봉을 넘지 않아야 하므로 `|a − b| ≤ 1`이어야 한다. 이 조건과 `a + b = n + 1`을 함께 풀면 짝수 `n`에서는 `n/2`와 `n/2 + 1`, 홀수 `n`에서는 `(n+1)/2`를 두 번 쓰는 것만 남는다. 이 분할은 명시된 두 조건에서 유도한 결과이며 관례를 임의로 고른 것이 아니다.
  - 걸러 내는 조건이 **삼각형**이지 좌우 대칭이 아니라는 점을 분명히 해 둔다. 두 직사각 창의 합성곱은 `a`와 `b`가 무엇이든 항상 좌우 대칭이므로, 대칭만으로는 후보가 하나도 걸러지지 않는다. `n = 6`을 예로 들면 `a + b = 7`을 만족하는 분할이 셋인데, `(1,6)`의 가중치는 `[1,1,1,1,1,1]`, `(2,5)`는 `[1,2,2,2,2,1]`, `(3,4)`는 `[1,2,3,3,2,1]`로 셋 다 좌우 대칭이고 셋 다 창 길이가 정확히 6이다. 이 가운데 `(1,6)`은 평평하고 `(2,5)`는 사다리꼴이어서 삼각형 조건에서 탈락하고 `(3,4)`만 남는다.
- 확인용 예: `n=4`의 가중치는 1, 2, 2, 1이고 `n=5`는 1, 2, 3, 2, 1, `n=6`은 1, 2, 3, 3, 2, 1이다. 짝수 `n`에서는 꼭짓점이 한 봉이 아니라 두 봉에 걸친 평평한 삼각형이 된다. 한 점 꼭짓점은 홀수 `n`에서만 나온다.
- **갈라지는 다른 규약**: `n`의 홀짝과 무관하게 `SMA(SMA(P, floor(n/2)+1), floor(n/2)+1)`을 쓰는 구현이 있다. 이 방식은 짝수 `n`에서 실효 창이 `n+1`봉이 되어 기간 인자가 가리키는 봉 수와 어긋나므로 이 표준은 채택하지 않는다.
- warm-up: 두 단순이동평균이 겹쳐 처음 `n1 + n2 − 2 = n − 1`봉이 정의되지 않는다. 결과적으로 `SMA(P, n)`과 같은 길이의 warm-up을 갖는다.
- 재귀가 없으므로 §0.11의 확정 캔들 규약 외에 따로 유지할 상태가 없다.

## §2. Momentum / Oscillator 계열 (★4↑)

### 2.1 RSI — Relative Strength Index (Wilder, 1978) ★★★★★
```
Δ_t = C_t − C_{t-1}
Gain_t = max(Δ_t, 0) ;   Loss_t = max(−Δ_t, 0)
AvgGain = RMA(Gain, n) ;  AvgLoss = RMA(Loss, n)   (§0.5, n=14, seed=첫 n개 단순평균)
RS  = AvgGain / AvgLoss
RSI = 100 − 100/(1 + RS)
```
- divide-by-zero: `AvgLoss=0` → RSI=100. `AvgGain=0` → RSI=0.
- 변형: **Cutler's RSI** = RMA 대신 SMA 사용(재귀 없음, 값 다름).

### 2.2 Stochastic — %K/%D (George Lane) ★★★★★
```
%K_raw = 100 · (C_t − LL(n)_t) / (HH(n)_t − LL(n)_t)     (n=14)
Fast %K = %K_raw ;  Fast %D = SMA(%K_raw, 3)
Slow %K = SMA(%K_raw, 3) ;  Slow %D = SMA(Slow %K, 3)
```
- 분모 0(HH=LL) → 직전값 또는 50/100 대체(구현체별).
- **Fast와 Slow는 별개 지표로 세고 별개로 등록한다.** 둘은 `%K_raw`라는 부품을 공유할 뿐 내놓는 두 선이 서로 다르다. Fast는 (`%K_raw`, `SMA(%K_raw,3)`) 쌍을, Slow는 (`SMA(%K_raw,3)`, `SMA(Slow %K,3)`) 쌍을 출력한다. Slow %K가 Fast %D와 같은 값이라는 사실은 계산을 공유하라는 뜻이지 한 항목으로 묶으라는 뜻이 아니다. Fast는 원시 %K의 반응 속도를, Slow는 한 단계 더 평활한 선을 쓰는 서로 다른 신호 체계다.
- 위 규약에 따라 §11 커버리지 집계는 Stochastic Fast와 Stochastic Slow를 2행으로 센다. 등록도 두 조합으로 나눈다.

### 2.3 Stochastic RSI (Chande & Kroll, 1994) ★★★★★
중복 제거: RSI(§2.1) 위에 Stochastic(§2.2) 정규화.
```
StochRSI_t = ( RSI_t − min(RSI, n) ) / ( max(RSI, n) − min(RSI, n) )   (n=14)
%K = SMA(StochRSI·100, 3) ;  %D = SMA(%K, 3)
```

### 2.4 MACD (Gerald Appel) ★★★★★
중복 제거: EMA(§0.3)만 사용.
```
MACD_t   = EMA(C,12) − EMA(C,26)
Signal_t = EMA(MACD, 9)
Hist_t   = MACD_t − Signal_t          (Histogram = Aspray 추가분, ★★★★)
```

### 2.5 PPO — Percentage Price Oscillator ★★★★
MACD의 백분율판(스케일 독립 → 자산 간 비교 가능).
```
PPO_t    = 100 · (EMA(C,12) − EMA(C,26)) / EMA(C,26)
Signal_t = EMA(PPO, 9) ;  Hist = PPO − Signal
```

### 2.6 TRIX (Jack Hutson, 1980s) ★★★★★
중복 제거: EMA 3중.
```
E1 = EMA(C, n) ;  E2 = EMA(E1, n) ;  E3 = EMA(E2, n)     (n=15 흔함)
TRIX_t = 100 · (E3_t − E3_{t-1}) / E3_{t-1}             (1기간 ROC의 퍼센트. TA-Lib 기본=×100. 일부 구현은 ×10000)
```

### 2.7 TSI — True Strength Index (William Blau, 1991) ★★★★★
```
PC_t = C_t − C_{t-1}                          (모멘텀)
DS  = EMA( EMA(PC, r), s )                     (이중 평활, r=25, s=13)
DA  = EMA( EMA(|PC|, r), s )
TSI = 100 · DS / DA
```

### 2.8 CMO — Chande Momentum Oscillator (Chande, 1994) ★★★★★
```
SU = Σ_{i} max(Δ_i, 0) ;  SD = Σ_{i} max(−Δ_i, 0)   (n기간 합, Δ=C_t−C_{t-1})
CMO = 100 · (SU − SD) / (SU + SD)                    (범위 −100~+100)
```
RSI와 달리 평활 없이 원시 합 사용, 0 중심.

### 2.9 Williams %R (Larry Williams) ★★★★★
```
%R = −100 · (HH(n)_t − C_t) / (HH(n)_t − LL(n)_t)     (n=14, 범위 −100~0)
```
Stochastic %K를 상단 기준으로 뒤집은 형태.

### 2.10 CCI — Commodity Channel Index (Donald Lambert, 1980) ★★★★★
중복 제거: Typical Price(§0.1) + SMA(§0.2).
```
TP_t = (H+L+C)/3
SMA_TP = SMA(TP, n)                                   (n=20)
MeanDev = (1/n)·Σ_{i=0}^{n-1} |TP_{t-i} − SMA_TP_t|   (평균절대편차, ≠ 표준편차)
CCI = (TP_t − SMA_TP_t) / (0.015 · MeanDev)
```
- 상수 0.015: 약 70~80%가 ±100 내에 들도록 하는 Lambert 정규화 상수.

### 2.11 Ultimate Oscillator (Larry Williams, 1976) ★★★★★
```
BP_t = C_t − min(L_t, C_{t-1})                        (Buying Pressure)
TR_t = max(H_t, C_{t-1}) − min(L_t, C_{t-1})          (Wilder TR과 동치)
Avg_p = ΣBP(p) / ΣTR(p)  for p ∈ {7,14,28}
UO = 100 · (4·Avg7 + 2·Avg14 + 1·Avg28) / (4+2+1)
```

### 2.12 Awesome Oscillator (Bill Williams) ★★★★
중복 제거: Median Price(§0.1) + SMA.
```
AO = SMA(HL2, 5) − SMA(HL2, 34)
```

### 2.13 Accelerator Oscillator (Bill Williams) ★★★★
```
AC = AO − SMA(AO, 5)                                  (AO는 §2.12)
```

### 2.14 Fisher Transform (John Ehlers) ★★★★★
중간가를 −1~1로 정규화 후 역쌍곡 변환.
```
X_raw = 2·(HL2_t − LL(n)) / (HH(n) − LL(n)) − 1        (n=9~10)
X_t = 0.33·X_raw + 0.67·X_{t-1}                         (평활, |X|<1로 클램프)
Fisher_t = 0.5·ln((1 + X_t)/(1 − X_t)) + 0.5·Fisher_{t-1}
Signal = Fisher_{t-1}
```

### 2.15 Connors RSI (Larry Connors) ★★★★
중복 제거: RSI(§2.1) 2회 + PercentRank.
```
RSI_price  = RSI(C, 3)
streak = 연속 상승(+)/하락(−) 봉 수 (동일 방향 누적, 방향 바뀌면 리셋)
RSI_streak = RSI(streak, 2)
PctRank = ROC(C,1) 의 최근 100봉 내 백분위(%)
ConnorsRSI = (RSI_price + RSI_streak + PctRank) / 3
```

### 2.16 QStick (Tushar Chande) ★★★★
```
QStick = SMA( (C − O), n )                             (n=8~10, 캔들 몸통 평균)
```

### 2.17 Chande Forecast Oscillator (Chande) ★★★★
중복 제거: 선형회귀(§11) 예측값 사용.
```
CFO = 100 · (C_t − LinRegForecast(C, n)_t) / C_t
```
(`LinRegForecast` = n기간 최소자승 회귀선의 현재봉 추정값.)

### 2.18 DeMarker (Tom DeMark) ★★★★
```
DeMax_t = max(H_t − H_{t-1}, 0)
DeMin_t = max(L_{t-1} − L_t, 0)
DeMarker = SMA(DeMax, n) / ( SMA(DeMax, n) + SMA(DeMin, n) )   (n=14, 범위 0~1)
```

### 2.19 DPO — Detrended Price Oscillator ★★★★
```
shift = floor(n/2) + 1
DPO_t = C_{t-shift} − SMA(C, n)_t
```
추세 제거 → 순환주기 관찰용(선행지표 아님).

### 2.20 Schaff Trend Cycle (Doug Schaff, 1999) ★★★★
중복 제거: MACD(§2.4) → Stochastic(§2.2) 이중 적용.
```
M = MACD(C, 23, 50)                                    (기본 fast23/slow50)
%K1 = Stoch(M, len=10) ; D1 = EMA-smooth(%K1, factor 0.5)
%K2 = Stoch(D1, len=10) ; STC = EMA-smooth(%K2, factor 0.5)
```
- **구현체별 상이**: 내부 평활을 0.5 factor 지수평활로 하는 방식이 원저자 서술. 정확 상수·클램프는 구현 명시 필요.

### 2.21 Relative Vigor Index (RVI, John Ehlers) ★★★★
※ Dorsey의 "Relative Volatility Index"(§3.7)와 약어 충돌 주의.
```
Num = SWMA(C − O)         (SWMA = 대칭가중 4항: (x_t + 2x_{t-1} + 2x_{t-2} + x_{t-3})/6)
Den = SWMA(H − L)
RVI = SMA(Num, n) / SMA(Den, n)                        (n=10)
Signal = SWMA(RVI)
```

### 2.22 Laguerre RSI (John Ehlers) ★★★★
4단 Laguerre 필터(감마 γ, 기본 0.5~0.7)로 지연 제어 후 RSI화.
```
L0_t = (1−γ)·P_t + γ·L0_{t-1}
L1_t = −γ·L0_t + L0_{t-1} + γ·L1_{t-1}
L2_t = −γ·L1_t + L1_{t-1} + γ·L2_{t-1}
L3_t = −γ·L2_t + L2_{t-1} + γ·L3_{t-1}
CU = Σ up-차분 (L0>L1 이면 L0−L1, L1>L2 이면 L1−L2, L2>L3 이면 L2−L3)
CD = Σ down-차분 (반대 경우)
LaguerreRSI = CU / (CU + CD)                            (분모 0 → 0)
```

### 2.23 Pretty Good Oscillator (Mark Johnson) ★★★★
중복 제거: SMA + ATR(§3.1).
```
PGO = (C_t − SMA(C, n)) / ATR(n)                        (n=89 관례)
```

### 2.24 KST — Know Sure Thing (Martin Pring) ★★★★★
중복 제거: ROC(§0.10) 4개 + SMA 평활 가중합.
```
RCMA1 = SMA(ROC(10), 10) · 1
RCMA2 = SMA(ROC(15), 10) · 2
RCMA3 = SMA(ROC(20), 10) · 3
RCMA4 = SMA(ROC(30), 15) · 4
KST = RCMA1 + RCMA2 + RCMA3 + RCMA4
Signal = SMA(KST, 9)
```

### 2.25 Coppock Curve (Edwin Coppock, 1962) ★★★★★
```
Coppock = WMA( ROC(C, 14) + ROC(C, 11),  10 )
```

### 2.26 Special K (Martin Pring) ★★★★
KST 계열 확장 — 단·중·장기 ROC의 가중 평활합(다수 항). 구성 항이 많고 파라미터가 문서마다 상이 → **원 Pring 정의표 참조 필요**(항별 ROC기간·평활기간·가중치 지정 필요).

### 2.27 SMI — Stochastic Momentum Index (William Blau, 1993) ★★★★★
스토캐스틱을 중간가 기준 거리로 재정의 후 이중 평활. 중복 제거: HH/LL(§0.8) + EMA(§0.3).
```
M  = (HH(n) + LL(n)) / 2                                 (n기간 고저 중간점)
D  = C_t − M                                             (중간점으로부터의 거리)
HL = HH(n) − LL(n)                                       (고저 범위)
DS  = EMA( EMA(D,  r), s )                                (이중 평활, r/s = 예: 3/3 또는 25/13)
DHL = EMA( EMA(HL/2, r), s )
SMI = 100 · DS / DHL                                     (범위 −100~+100, 분모 0 → 0)
Signal = EMA(SMI, u)                                      (u=예: 3)
```
- 파라미터(n, r, s)는 문서/플랫폼별 상이(Blau 원안 vs TradingView) → 채택 값 명시 권장.

### 2.28 APO — Absolute Price Oscillator ★★★★
중복 제거: 이동평균 프리미티브(§0.2~0.5) 가운데 파라미터로 지정한 하나만 사용. 길이가 다른 두 이동평균의 차를 가격 단위 그대로 내놓는다.
```
APO_t = MA(P, n_fast)_t − MA(P, n_slow)_t               (n_fast < n_slow)
기본 조합: MA = SMA, n_fast = 12, n_slow = 26, P = C
```
- 출처: 이 지표를 처음 정의한 사람을 특정할 수 있는 1차 자료는 없다. 문서화된 정의 가운데 가장 확립된 것은 플랫폼 문서(Trading Technologies X_STUDY의 Absolute Price Oscillator 정의)이며, 거기서 APO는 "길이가 다른 두 이동평균의 차"로 정의되고 **이동평균 종류는 사용자 파라미터로 열려 있다**. 이 표준도 그에 맞춰 이동평균 종류를 파라미터로 두고 기본값만 고정한다. 원저자를 세울 수 없으므로 제목의 원저자 자리를 비웠고, 별점은 같은 사정인 §2.5 PPO와 같은 기준으로 매겼다.
- **기본 이동평균을 SMA로 고정한 이유.** 종류를 EMA로 두고 기간을 12와 26으로 잡으면 `EMA(C,12) − EMA(C,26)`이 되어 §2.4 MACD 라인과 값이 완전히 같아진다. 같은 값을 두 이름으로 두 번 구현하지 않기 위해 이 표준은 기본 이동평균을 SMA로 고정한다. 사용자가 종류를 EMA로 바꾸면 MACD 라인과 같은 값이 나오는데, 이는 결함이 아니라 정의에서 따라 나오는 결과이며 그 조합이 필요하면 §2.4를 쓰면 된다.
- **§2.5 PPO와 이동평균이 다른 이유.** PPO는 "MACD의 백분율판"이라는 정의 자체가 EMA를 전제하므로 EMA를 쓴다. APO는 이동평균 종류가 열린 일반형이고, 위 이유로 이 표준이 기본값을 SMA로 골랐다. 그래서 이 표준 안에서 APO와 PPO는 서로 다른 이동평균을 쓴다. 두 절을 나란히 읽으면 어긋나 보이지만 의도한 차이다.
- 값의 단위가 가격과 같아 가격대가 다른 자산끼리 직접 비교할 수 없다. 자산 간 비교에는 스케일이 없는 §2.5 PPO를 쓴다.
- 나눗셈이 없어 분모 0 예외가 없다. warm-up은 둘 중 느린 이동평균의 warm-up을 따른다.

### 2.29 BOP — Balance of Power (Igor Livshin, 2001) ★★★★
중복 제거: SMA(§0.2). 한 봉 안에서 매수 측과 매도 측이 가격을 각자의 방향으로 밀어낸 정도를 견줘, 그 봉의 주도권이 어느 쪽에 있었는지를 −1에서 +1 사이 값으로 나타낸다.
```
BOP_raw_t = (C_t − O_t) / (H_t − L_t)                   (범위 −1~+1)
BOP_t     = SMA(BOP_raw, n)                             (n=14)
```
1차 출처는 Igor Livshin, "Balance Of Power", *Technical Analysis of Stocks & Commodities* V.19:8(2001년 8월), 18–32쪽이다. 원문은 봉마다 강세 측과 약세 측의 보상을 시가 기준, 종가 기준, 시가-종가 기준 셋으로 나눠 계산한 뒤 두 진영의 평균 보상의 차를 취한다.
```
BullsOnOpen      = (H − O)/(H − L) ;  BearsOnOpen      = (O − L)/(H − L)
BullsOnClose     = (C − L)/(H − L) ;  BearsOnClose     = (H − C)/(H − L)
BullsOnOpenClose = (C > O) ? (C − O)/(H − L) : 0
BearsOnOpenClose = (C < O) ? (O − C)/(H − L) : 0
BOP_raw = (BullsOnOpen + BullsOnClose + BullsOnOpenClose)/3
        − (BearsOnOpen + BearsOnClose + BearsOnOpenClose)/3
```
이 여섯 항을 정리하면 분자가 `3(C − O)`로 모여 위의 `(C_t − O_t)/(H_t − L_t)`와 항등적으로 같아진다. 근사가 아니라 대수적으로 같은 식이다. 저자 본인이 같은 잡지 2001년 10월 독자란에서 두 식이 같음을 확인했으므로, 이 표준은 축약형을 채택하고 여섯 항 전개형은 그 뜻을 밝히는 용도로만 남긴다.

- 평활: 원문은 14봉 단순이동평균으로 평활한 선을 그린다. 평활하지 않은 `BOP_raw`는 봉마다 튀어 읽기 어렵다.
- 분모 0(`H_t = L_t`): §0.11에 따라 그 봉의 `BOP_raw`를 `0`으로 둔다. 고가와 저가가 같은 봉은 시가와 종가도 그 값과 같아 분자도 0이며, 어느 쪽도 가격을 밀어내지 못했다는 뜻이므로 0이 그 상황의 의미와 맞는다. 범위가 무너진 봉을 0으로 두는 것은 §4.2 A/D Line이 Money Flow Multiplier에 쓰는 규약과도 같다.
- 값이 시가와 종가의 차이에만 좌우되므로, 같은 몸통 크기라면 그 몸통이 봉 범위의 위쪽에 있든 아래쪽에 있든 BOP는 같다. 저자도 독자란에서 이 성질을 인정했다.

### 2.30 IMI — Intraday Momentum Index (Tushar Chande, 1994) ★★★★★
중복 제거 없음(시가·종가만 사용). RSI(§2.1)의 구조를 봉과 봉 사이가 아니라 **한 봉 안의 시가에서 종가까지**에 적용한다.
```
Gain_t = max(C_t − O_t, 0)                              (종가가 시가보다 높은 봉의 몸통)
Loss_t = max(O_t − C_t, 0)                              (종가가 시가보다 낮은 봉의 몸통)
ISup   = Σ_{i=0}^{n-1} Gain_{t-i} ;  ISdown = Σ_{i=0}^{n-1} Loss_{t-i}      (n=14)
IMI    = 100 · ISup / (ISup + ISdown)                   (범위 0~100)
```
- 1차 출처: Chande & Kroll, *The New Technical Trader*, 1994(§13의 4번). 원문 표기는 `IMI = [ISup / (ISup + ISdown)] × 100`이다.
- RSI(§2.1)와의 차이는 두 가지다. 첫째, RSI는 직전 봉 종가 대비 변화를 쓰지만 IMI는 같은 봉의 시가 대비 변화를 쓰므로 봉과 봉 사이의 갭이 값에 들어가지 않는다. 둘째, RSI는 Wilder 평활(§0.5)로 상승분·하락분을 재귀 평활하지만 IMI는 n봉 원시 합을 쓴다. 이 점에서 IMI의 합산 구조는 CMO(§2.8)와 같고 정규화 방식만 다르다.
- 분모 0: `ISdown = 0`이면 IMI = 100, `ISup = 0`이면 IMI = 0으로 두어 §2.1 RSI와 같은 규약을 쓴다. 창 안의 모든 봉이 `C = O`여서 두 합이 함께 0이 되면 분모 자체가 0이 되는데, 이때는 §0.11이 허용하는 대체값 중 중립값 `50`을 택한다. 매수 압력도 매도 압력도 없는 상태이므로 중앙값이 그 뜻과 맞는다.
- 과매수·과매도 판단선은 원문 기준 70과 30이다.

## §3. Volatility 계열 (★4↑)

### 3.1 ATR — Average True Range (Wilder, 1978) ★★★★★
중복 제거: TR(§0.6) + RMA(§0.5).
```
ATR = RMA(TR, n)                                       (n=14, seed=첫 n개 TR 단순평균)
```
- 종가로 정규화해 자산 간 비교를 가능하게 한 NATR은 별개 지표로 승격해 §3.11에 따로 적었다. 여기서는 변형으로 취급하지 않는다.

### 3.2 Keltner Channel (Chester Keltner / Linda Raschke 현대판) ★★★★
중복 제거: EMA(§0.3) + ATR(§3.1).
```
Middle = EMA(C, n)                                     (n=20)
Upper  = Middle + mult·ATR(m)                          (mult=2, m=10 또는 20)
Lower  = Middle − mult·ATR(m)
```
- **구현체별 상이**: 원 Keltner는 SMA(Typical Price) ± SMA(H−L). 현대판(TradingView 기본)은 EMA ± ATR.

### 3.3 Donchian Channel (Richard Donchian) ★★★★
중복 제거: HH/LL(§0.8).
```
Upper = HH(n) ;  Lower = LL(n) ;  Middle = (Upper + Lower)/2   (n=20)
```

### 3.4 SuperTrend ★★★★
중복 제거: HL2(§0.1) + ATR(§3.1).
```
basicUpper = HL2 + mult·ATR(n)
basicLower = HL2 − mult·ATR(n)                          (mult=3, n=10 흔함)
finalUpper_t = (basicUpper_t < finalUpper_{t-1} 또는 C_{t-1} > finalUpper_{t-1})
                ? basicUpper_t : finalUpper_{t-1}
finalLower_t = (basicLower_t > finalLower_{t-1} 또는 C_{t-1} < finalLower_{t-1})
                ? basicLower_t : finalLower_{t-1}
추세: C가 finalUpper 상향돌파 → 상승(SuperTrend=finalLower), 하향돌파 → 하락(=finalUpper)
```

### 3.5 Chandelier Exit (Chuck LeBeau) ★★★★
```
Long  = HH(n) − mult·ATR(n)
Short = LL(n) + mult·ATR(n)                             (n=22, mult=3)
```

### 3.6 Ulcer Index (Peter Martin, 1987) ★★★★
```
maxC = HH(C, n)                                         (n기간 최고 종가)
Drawdown%_t = 100 · (C_t − maxC_t) / maxC_t             (≤0)
UlcerIndex = sqrt( (1/n)·Σ_{i=0}^{n-1} Drawdown%_{t-i}^2 )
```
하락 깊이·지속의 RMS → 하방 위험 특화(변동성 대칭 가정 없음).

### 3.7 Relative Volatility Index (RVI, Donald Dorsey, 1993) ★★★★
※ Ehlers "Relative Vigor Index"(§2.21)와 약어 충돌. RSI 구조를 가격변화 대신 **표준편차**에 적용.
```
σ_t = StDev(C, m)                                       (m=10)
Δ_t = C_t − C_{t-1}
Uσ = σ_t if Δ_t>0 else 0 ;  Dσ = σ_t if Δ_t<0 else 0
RVI = 100 · RMA(Uσ, n) / ( RMA(Uσ, n) + RMA(Dσ, n) )    (n=14)
```

### 3.8 Chaikin Volatility (Marc Chaikin) ★★★★
```
HL_EMA = EMA( (H − L), n )                              (n=10)
ChaikinVol = 100 · ( HL_EMA_t − HL_EMA_{t-n} ) / HL_EMA_{t-n}
```

### 3.9 Mass Index (Donald Dorsey, 1992) ★★★★
```
E1 = EMA(H − L, 9) ;  E2 = EMA(E1, 9)
Ratio = E1 / E2
MassIndex = Σ_{i=0}^{24} Ratio_{t-i}                    (25봉 합)
```
"reversal bulge"(27 상향 후 26.5 하향) 신호. 방향 아님·전환 임박만 시사.

### 3.10 Bollinger Bands / %B / BandWidth (John Bollinger, 1980s) ★★★★★
중복 제거: SMA(§0.2) + StDev(§0.7, 모표준편차).
```
Middle = SMA(C, n)                                       (n=20)
σ      = StDev(C, n)                                     (모표준편차, 분모 n)
Upper  = Middle + k·σ                                    (k=2)
Lower  = Middle − k·σ
%B        = (C − Lower) / (Upper − Lower)                (밴드 내 상대위치, 분모 0 → 미정의)
BandWidth = (Upper − Lower) / Middle                     (밴드 폭 정규화, squeeze 탐지)
```
- 주의: σ는 관례상 **모표준편차(분모 n)**. 표본표준편차(n−1) 사용 시 밴드가 약간 넓어짐 → 플랫폼 간 미세 차이 원인.
- %B > 1: 상단 돌파, %B < 0: 하단 돌파. BandWidth 국소 최저 = Bollinger Squeeze.

### 3.11 NATR — Normalized Average True Range (John Forman, 2006) ★★★★
중복 제거: ATR(§3.1). ATR을 종가로 나눠 백분율로 만들어, 가격대가 다른 자산의 변동성을 같은 자로 비교할 수 있게 한다.
```
NATR(n)_t = 100 · ATR(n)_t / C_t                        (n=14)
```
- 1차 출처: John Forman, "Cross-Market Evaluations With Normalized Average True Range", *Technical Analysis of Stocks & Commodities* V.24:5(2006년 5월), 60–63쪽.
- **계산 순서를 지켜야 한다.** True Range를 먼저 n봉 평활해 ATR을 구한 뒤, 그 결과를 현재 종가로 나눈다. 봉마다 TR을 먼저 종가로 나눠 정규화한 다음 평활하는 방식은 Forman의 정의가 아니며 값도 다르다.
- 분모 0(`C_t = 0`): §0.11에 따라 결과를 `0`으로 둔다. 종가가 0인 봉은 정상 시세에 나오지 않으므로 이 대체값은 계산을 멈추지 않기 위한 방어 규약이다. warm-up 구간이 NaN인 것은 ATR(§3.1)에서 그대로 물려받는다.
- §3.1이 ATR의 변형으로 한 줄만 적어 두었던 항목을 독립 절로 올린 것이다. 계산 자체는 §3.1의 ATR을 그대로 쓰고 마지막 정규화 한 단계만 더한다. §11 집계는 ATR과 NATR을 별개 2행으로 센다.

### 3.12 ACCBANDS — Acceleration Bands (Price Headley, 2002) ★★★★
중복 제거: SMA(§0.2). 봉의 범위를 그 봉의 가격 수준에 대한 비율로 바꿔 밴드 폭을 정하므로, 변동성이 커지면 밴드가 넓어지고 조용해지면 좁아진다.
```
Ratio_t = (H_t − L_t) / (H_t + L_t)                     (봉 범위를 고가와 저가의 합으로 나눈 비율)
Upper  = SMA( H · (1 + 4·Ratio), n )                    (n=20)
Middle = SMA( C, n )
Lower  = SMA( L · (1 − 4·Ratio), n )
```
- 1차 출처: Price Headley, *Big Trends in Trading: Strategies to Master Major Market Moves*, Wiley, 2002, 7장(EasyLanguage 원문은 92쪽). 원문 표기는 `high × (1 + 2 × (((high − low)/((high + low)/2)) × 1000) × 0.001)` 형태다. `((H−L)/((H+L)/2)) × 1000 × 0.001 = 2(H−L)/(H+L)` 이므로 위 계수 `4`는 원문을 약분해 정리한 것이고 값은 원문과 같다. 일부 플랫폼이 노출하는 `factor` 파라미터의 기본값 `0.001`은 이 약분 과정에 흡수된 상수이며, 그 기본값에서 계수는 정확히 `4`가 된다.
- 평활 기간: 원저자는 20봉을 기본으로 쓰고, 더 긴 흐름을 볼 때 80봉을 함께 본다. 이 표준은 기본을 20으로 둔다.
- 분모 0(`H_t + L_t = 0`): §0.11에 따라 `Ratio_t`를 `0`으로 둔다. 그러면 그 봉이 밴드에 넣는 값이 고가와 저가 자체가 되어, 폭을 벌리는 항 없이 `SMA(H, n)`과 `SMA(L, n)`에만 기여한다.
- `Ratio_t`는 봉 범위를 고가와 저가의 합으로 나눈 값이므로 중간가 `HL2`(§0.1) 대비 범위 비율의 절반이다. 원문이 중간가로 나눈 뒤 2를 곱하는 형태를 쓴 것과 위 계수 `4`가 대응하는 지점이 여기다.
- 밴드는 중간선과 정확히 등거리가 아니다. 원저자는 상·하단이 20봉 단순이동평균에서 같은 거리에 놓인다고 서술하지만, 위 식은 상단을 고가에서 위로, 하단을 저가에서 아래로 벌리므로 두 거리가 일반적으로 다르다. 이 표준은 서술이 아니라 원문 식을 채택한다.

## §4. Volume 계열 (★4↑)

### 4.1 OBV — On-Balance Volume (Joseph Granville, 1963) ★★★★★
중복 제거: 누적(§0.9).
```
OBV_t = OBV_{t-1} + { +V_t (C_t>C_{t-1}), −V_t (C_t<C_{t-1}), 0 (동일) }
```

### 4.2 A/D Line — Accumulation/Distribution (Marc Chaikin) ★★★★
```
MFM = ((C − L) − (H − C)) / (H − L)                     (Money Flow Multiplier, H=L → 0)
MFV = MFM · V                                            (Money Flow Volume)
ADL_t = ADL_{t-1} + MFV_t                                (누적)
```

### 4.3 Chaikin Oscillator (Marc Chaikin) ★★★★
중복 제거: ADL(§4.2) + EMA.
```
ChaikinOsc = EMA(ADL, 3) − EMA(ADL, 10)
```

### 4.4 CMF — Chaikin Money Flow (Marc Chaikin) ★★★★
중복 제거: MFV(§4.2).
```
CMF = Σ_{i=0}^{n-1} MFV_{t-i} / Σ_{i=0}^{n-1} V_{t-i}    (n=20)
```

### 4.5 MFI — Money Flow Index (Quong & Soudack) ★★★★
중복 제거: Typical Price(§0.1) — "거래량 가중 RSI".
```
TP_t = (H+L+C)/3 ;  RMF_t = TP_t · V_t                   (Raw Money Flow)
PMF = Σ RMF where TP_t>TP_{t-1} ;  NMF = Σ RMF where TP_t<TP_{t-1}   (n=14)
MFR = PMF / NMF
MFI = 100 − 100/(1 + MFR)
```

### 4.6 Force Index (Alexander Elder) ★★★★★
```
RawFI_t = (C_t − C_{t-1}) · V_t
ForceIndex = EMA(RawFI, n)                               (n=13 흔함)
```

### 4.7 EMV — Ease of Movement (Richard Arms) ★★★★
```
DistanceMoved = HL2_t − HL2_{t-1}
BoxRatio = (V / scale) / (H − L)                          (scale=예: 100000000)
EMV_raw = DistanceMoved / BoxRatio
EMV = SMA(EMV_raw, n)                                     (n=14)
```

### 4.8 Klinger Volume Oscillator (Stephen Klinger) ★★★★
```
dm = H − L
trend_t = +1 if (H+L+C)_t > (H+L+C)_{t-1} else −1
cm_t = (trend_t == trend_{t-1}) ? cm_{t-1} + dm_t : dm_{t-1} + dm_t
VF_t = V_t · |2·(dm_t/cm_t) − 1| · trend_t · 100          (Volume Force)
KVO = EMA(VF, 34) − EMA(VF, 55) ;  Signal = EMA(KVO, 13)
```
- **구현체별 상이**: cm 초기화·VF 절댓값 처리에 이설 있음 → 채택 구현 명시 필요.

### 4.9 NVI — Negative Volume Index (Paul Dysart / Fosback) ★★★★
```
NVI_t = { NVI_{t-1} · (1 + (C_t−C_{t-1})/C_{t-1})   if V_t < V_{t-1}
        { NVI_{t-1}                                  otherwise      (seed=1000)
```

### 4.10 PVI — Positive Volume Index ★★★★
```
PVI_t = { PVI_{t-1} · (1 + (C_t−C_{t-1})/C_{t-1})   if V_t > V_{t-1}
        { PVI_{t-1}                                  otherwise      (seed=1000)
```

## §5. Trend Strength / 방향성 (★4↑)

### 5.1 DMI / ADX 시스템 (Wilder, 1978) ★★★★★
+DI / −DI / ADX / ADXR. 중복 제거: TR(§0.6) + Wilder 평활(§0.5).
```
upMove   = H_t − H_{t-1}
downMove = L_{t-1} − L_t
+DM_t = (upMove > downMove and upMove > 0) ? upMove : 0
−DM_t = (downMove > upMove and downMove > 0) ? downMove : 0

ATR14  = RMA(TR, 14)
+DI = 100 · RMA(+DM, 14) / ATR14
−DI = 100 · RMA(−DM, 14) / ATR14

DX  = 100 · |+DI − −DI| / (+DI + −DI)                    (분모 0 → 0)
ADX = RMA(DX, 14)                                        (seed=첫 14 DX 평균)
ADXR_t = (ADX_t + ADX_{t-n}) / 2                          (n=14)
```
> 카운트 주의: 본 시스템을 구성요소별(+DI, −DI, ADX, ADXR)로 세면 4행, 시스템 1개로 묶으면 1행.

### 5.2 Vortex Indicator (Botes & Siepman, 2010) ★★★★
중복 제거: TR(§0.6).
```
VM+_t = |H_t − L_{t-1}| ;  VM−_t = |L_t − H_{t-1}|
VI+ = Σ_{i=0}^{n-1} VM+_{t-i} / Σ TR_{t-i}                (n=14)
VI− = Σ_{i=0}^{n-1} VM−_{t-i} / Σ TR_{t-i}
```

### 5.3 Aroon (Tushar Chande, 1995) ★★★★★
```
AroonUp   = 100 · (n − (n봉 내 최고고가까지의 경과봉수)) / n
AroonDown = 100 · (n − (n봉 내 최저저가까지의 경과봉수)) / n     (n=25)
AroonOsc  = AroonUp − AroonDown
```

### 5.4 Choppiness Index (E.W. Dreiss) ★★★★
중복 제거: ATR(§3.1, 합) + HH/LL(§0.8).
```
CHOP = 100 · log10( Σ_{i=0}^{n-1} TR_{t-i} / (HH(n) − LL(n)) ) / log10(n)   (n=14)
```
100 근접=횡보(choppy), 0 근접=추세.

### 5.5 QQE — Quantitative Qualitative Estimation (Igor Livshin) ★★★★
중복 제거: RSI(§2.1) + ATR-of-RSI.
```
RsiMa = EMA(RSI(14), 5)                                   (평활 RSI)
AtrRsi_t = |RsiMa_t − RsiMa_{t-1}|
MaAtrRsi = RMA(AtrRsi, 2·14−1=27) ;  dar = RMA(MaAtrRsi, 27) · QQE_factor  (factor=4.236)
→ RsiMa 주위로 ±dar 트레일링 밴드(Fast/Slow TL) 형성, 밴드 교차로 신호
```
- **구현체별 상이**: 트레일링 로직 상세(밴드 락 규칙)는 원 코드 참조 필요.

### 5.6 Random Walk Index (E. Michael Poulos, 1991) ★★★★
중복 제거: ATR(§3.1).
```
RWI_high = ( H_t − L_{t-n} ) / ( ATR(n) · sqrt(n) )
RWI_low  = ( H_{t-n} − L_t ) / ( ATR(n) · sqrt(n) )
```
(여러 lookback n에 대해 최댓값을 취하는 변형 존재.)

## §6. Bill Williams 계열 (★4↑)

### 6.1 Alligator (Bill Williams) ★★★★
중복 제거: SMMA=RMA(§0.5) + Median Price(§0.1). 미래 시프트(offset) 사용.
```
Jaw   = SMMA(HL2, 13), shift +8
Teeth = SMMA(HL2, 8),  shift +5
Lips  = SMMA(HL2, 5),  shift +3
```
> shift는 표시상 미래 이동 — 실거래 계산 시 look-ahead 유의(현재봉 값은 과거 SMMA).

### 6.2 Fractals (Bill Williams) ★★★★
공식 아닌 패턴 규칙(5봉).
```
Up Fractal   : H_{t-2} 가 H_{t-4},H_{t-3},H_{t-1},H_t 보다 모두 높음
Down Fractal : L_{t-2} 가 주변 4봉 저가보다 모두 낮음
```
확정에 중앙봉 기준 +2봉 지연(look-ahead 아님, 지연 신호).

### 6.3 Gator Oscillator (Bill Williams) ★★★★
```
Upper = |Jaw − Teeth| ;  Lower = −|Teeth − Lips|          (Alligator §6.1 기반 히스토그램)
```

### 6.4 Market Facilitation Index (Bill Williams) ★★★★
```
BW MFI = (H − L) / V
```
MFI(§4.5)와 완전히 다른 지표(약어 충돌 주의).

## §7. Market Breadth (주식, ★4↑)

> 개별 종목이 아닌 **시장 전체 등락 종목수·거래량** 집계 입력. 암호화폐 단일 심볼에는 부적용.

### 7.1 McClellan Oscillator (Sherman & Marian McClellan) ★★★★★
```
Net = Advances − Declines                                 (또는 비율조정판)
McClellanOsc = EMA(Net, 19) − EMA(Net, 39)
```

### 7.2 McClellan Summation Index ★★★★
```
Summation_t = Summation_{t-1} + McClellanOsc_t             (누적, §0.9)
```

### 7.3 TRIN / Arms Index (Richard Arms, 1967) ★★★★
```
TRIN = (Advancing Issues / Declining Issues) / (Advancing Volume / Declining Volume)
```
1 미만=매수 우위, 1 초과=매도 우위(역방향 해석).

## §8. Cycle / Ehlers 계열 (★4↑)

> Ehlers 계열은 DSP 필터 기반이라 구현체별 계수·초기화가 갈린다. §8.1과 §8.4부터
> §8.9까지의 Hilbert 일곱 함수는 §0.12의 예외에 따라 TA-Lib v0.7.1 C 소스를
> 계산 원본으로 고정한다. Center of Gravity와 Roofing Filter에는 일반 출처 정책을
> 계속 적용한다.

Hilbert 일곱 함수의 불안정 기간은 `0`으로 고정한다. 원본의 lookback은 고정 길이에
`TA_GLOBALS_UNSTABLE_PERIOD(...)`를 더하지만, TA-Lib v0.7.1의 기본 전역 설정은
불안정 기간을 `0`으로 초기화한다. 이 저장소는 같은 기본값을 고정해 전역 가변 설정을
두지 않는다. 불안정 기간은 유효 출력 시작점과 부분 구간 계산의 초기화 시작점에
영향을 준다.

이 저장소의 워밍업은 `lookback + 1`이다. 따라서 다음 표의 `lookback` 개수만큼
선행 출력이 NaN이고, `min_history`개째 봉부터 첫 유효 출력이 나온다.

| 함수 | 출력 | lookback | `min_history` |
|---|---|---:|---:|
| `HT_DCPERIOD` | 단일 실수 | 32 | 33 |
| `HT_PHASOR` | `inphase`, `quadrature` | 32 | 33 |
| `MAMA` | `mama`, `fama` | 32 | 33 |
| `HT_DCPHASE` | 단일 실수 | 63 | 64 |
| `HT_SINE` | `sine`, `leadsine` | 63 | 64 |
| `HT_TRENDLINE` | 단일 실수 | 63 | 64 |
| `HT_TRENDMODE` | 단일 상태값 | 63 | 64 |

### 8.1 MAMA / FAMA — MESA Adaptive MA (John Ehlers, 2001) ★★★★★
계산 원본은 `ta_MAMA.c`다. §8.5의 공통 Hilbert 코어에서 갈라져 `I1`과 `Q1`의
위상 변화속도로 α를 정하고 원가격 `P`를 적응 평활한다.
```
Phase_t = atan(Q1_t / I1_t) · 180/π   if I1_t != 0
Phase_t = 0                            if I1_t == 0
DeltaPhase = Phase_{t-1} − Phase_t
if DeltaPhase < 1.0: DeltaPhase = 1.0
if DeltaPhase > 1.0:
    α = fastlimit / DeltaPhase
    if α < slowlimit: α = slowlimit
else:
    α = fastlimit
MAMA_t = α·P_t + (1−α)·MAMA_{t-1}
FAMA_t = 0.5·α·MAMA_t + (1−0.5·α)·FAMA_{t-1}
```
위상은 도 단위다. `I1`이 정확히 `0`이면 위상도 `0`으로 둔다. 특히 위상차를
`1.0`으로 아래에서 물린 직후 곧바로 `> 1.0`으로 다시 시험한다. 따라서 원래
위상차가 `1.0` 이하이면 α는 나눗셈 결과가 아니라 `fastlimit`이다. 이 조건 순서를
일반적인 구간 클램프로 바꾸면 경계값이 달라진다.

두 파라미터의 기본값은 `fastlimit=0.5`, `slowlimit=0.05`다. C 함수가 각각 허용하는
범위는 양 끝을 포함한 `[0.01, 0.99]`다. TA-Lib은 `fastlimit`가 `slowlimit`보다
큰지 따로 검증하지 않으므로 이 표준도 원본 동등성 계층에서 별도의 대소관계 조건을
추가하지 않는다. 출력은 `mama`와 `fama` 두 선이며, lookback은 32이고
`min_history`는 33이다.

### 8.2 Center of Gravity Oscillator (John Ehlers, 2002) ★★★★
```
Num = Σ_{i=0}^{n-1} (1 + i) · P_{t-i}
Den = Σ_{i=0}^{n-1} P_{t-i}
CG = − Num / Den + (n + 1)/2                              (n=10)
```

### 8.3 Roofing Filter (John Ehlers) ★★★★
High-Pass 필터(저주파 추세 제거) + Super Smoother(2-pole 고주파 잡음 제거).
- **검증 필요**: HP cutoff(예 48봉)와 SuperSmoother 계수(a1,b1,c1..)는 Ehlers 원문(*Cycle Analytics for Traders*, 2013)의 정확한 수치가 있어야 하며, 상수 재현은 원문 대조 전 "미확정".

### 8.4 Sinewave / Instantaneous Trendline (John Ehlers) ★★★★
이 개념 항목은 원본 C에서 **두 함수로 나뉜다.** `ta_HT_SINE.c`의 `HT_SINE`은
§8.7의 지배 주기 위상으로 `sine = sin(DCPhase)`와
`leadsine = sin(DCPhase + 45°)` 두 출력을 만든다. `ta_HT_TRENDLINE.c`의
`HT_TRENDLINE`은 `N = int(smoothPeriod + 0.5)`봉의 원가격 평균을 구한 뒤, 현재
평균과 직전 세 평균에 각각 4, 3, 2, 1의 가중치를 주고 10으로 나눈
Instantaneous Trendline 한 선을 출력한다. 추세선 평균에는 Hilbert 전단의 평활가격이
아니라 원가격을 사용한다. 두 함수 모두 lookback은 63이고 `min_history`는 64다.

### 8.5 공통 Hilbert 전단

일곱 함수가 공유하는 코어의 경계는 **4봉 가중 평활, Hilbert 변환, `Re`와 `Im`,
그리고 `period` 계산까지**다.

```
smoothPrice_t = (4·P_t + 3·P_{t-1} + 2·P_{t-2} + P_{t-3}) / 10
adjustedPrevPeriod = 0.075·period_{t-1} + 0.54
H(x)_t = (0.0962·x_t + 0.5769·x_{t-2}
          − 0.5769·x_{t-4} − 0.0962·x_{t-6}) · adjustedPrevPeriod
detrender_t = H(smoothPrice)_t
Q1_t = H(detrender)_t
I1_t = detrender_{t-3}
jI_t = H(I1)_t
jQ_t = H(Q1)_t
I2_t = 0.2·(I1_t − jQ_t) + 0.8·I2_{t-1}
Q2_t = 0.2·(Q1_t + jI_t) + 0.8·Q2_{t-1}
Re_t = 0.2·(I2_t·I2_{t-1} + Q2_t·Q2_{t-1}) + 0.8·Re_{t-1}
Im_t = 0.2·(I2_t·Q2_{t-1} − Q2_t·I2_{t-1}) + 0.8·Im_{t-1}
```

`Im`과 `Re`가 모두 0이 아닐 때 후보 주기를
`360 / (atan(Im/Re) · 180/π)`로 구한다. 후보를 직전 주기의 1.5배 이하와 0.67배
이상으로 차례로 제한하고, 다시 `[6, 50]`으로 제한한 뒤
`period_t = 0.2·candidate + 0.8·period_{t-1}`로 평활한다. 이 `period` 계산까지가
공통 코어다.

상태 초기화는 비대칭이다. 먼저 4봉 WMA용 표본을 채우고, 이어지는 아홉 봉에서는
Hilbert 계산 없이 WMA만 진행한 뒤 본 루프에 들어간다. Hilbert 순환 버퍼는 짝수 봉과
홀수 봉을 분리하고 하나의 `hilbertIdx`를 공유하되, 인덱스는 짝수 갈래에서만 증가한다.
이 홀짝 구분과 증가 위치는 계산의 일부다.

두 번째 주기 평활인
`smoothPeriod_t = 0.33·period_t + 0.67·smoothPeriod_{t-1}`는 일곱 함수 중
`HT_DCPERIOD`, `HT_DCPHASE`, `HT_SINE`, `HT_TRENDLINE`, `HT_TRENDMODE` 다섯만
사용하므로 공통 코어에 포함하지 않는다. `HT_PHASOR`는 홀짝 갈래 안에서 `I1`과
`Q1`을 내보내고, `MAMA`는 같은 자리에서 위상과 α를 계산하므로 둘은
`smoothPeriod` 이전에 갈라진다. 두 함수도 다음 봉의 공통 상태를 위해 `period`
계산 자체는 계속 수행한다.

선택 계층별 추가 상태는 다음과 같다.

| 함수 | 공통 코어 뒤 또는 갈래 안의 추가 상태와 출력 |
|---|---|
| `HT_DCPERIOD` | `smoothPeriod`를 유지하고 그 값을 출력한다. |
| `HT_DCPHASE` | `smoothPeriod`와 평활가격 50칸 버퍼로 지배 주기 위상을 출력한다. |
| `HT_PHASOR` | 홀짝 갈래 안에서 `I1`과 `Q1`을 각각 `inphase`, `quadrature`로 출력한다. |
| `HT_SINE` | `smoothPeriod`, 평활가격 50칸 버퍼, 지배 주기 위상으로 두 sine 선을 출력한다. |
| `HT_TRENDLINE` | `smoothPeriod`, 최대 50봉의 원가격, 직전 세 주기 평균으로 추세선을 출력한다. |
| `HT_TRENDMODE` | 위상, 두 sine 선, 추세선, `daysInTrend` 상태로 국면을 출력한다. |
| `MAMA` | 홀짝 갈래 안의 위상, α, 직전 MAMA와 FAMA로 두 적응평균을 출력한다. |

### 8.6 HT_DCPERIOD

계산 원본은 `ta_HT_DCPERIOD.c`다. §8.5의 공통 `period`에 선택 계층의
`smoothPeriod_t = 0.33·period_t + 0.67·smoothPeriod_{t-1}`를 적용한 값을 지배
주기로 출력한다. 출력은 단일 실수이며, lookback은 32이고 `min_history`는 33이다.

### 8.7 HT_DCPHASE

계산 원본은 `ta_HT_DCPHASE.c`다. `N = int(smoothPeriod + 0.5)`로 두고 최근
`N`개의 평활가격을 50칸 순환 버퍼에서 읽어 sine 가중합 `realPart`와 cosine 가중합
`imagPart`를 만든다. `imagPart`가 0이 아니면 `atan(realPart / imagPart)`를 도 단위로
바꾼다. 정확히 0이면 직전 `DCPhase`에서 시작해 `realPart < 0`일 때 90도를 빼고
`realPart > 0`일 때 90도를 더하는 원본 분기를 따른다. 이어 90도와 WMA의 한 봉
지연 보정 `360 / smoothPeriod`를 더한다. `imagPart < 0`이면 180도를 더하고, 결과가
315도보다 크면 360도를 뺀 값이 `DCPhase`다. 출력은 단일 실수이며, lookback은
63이고 `min_history`는 64다.

### 8.8 HT_PHASOR

계산 원본은 `ta_HT_PHASOR.c`다. §8.5의 홀짝 갈래 안에서 3봉 지연된 detrender인
`I1`을 `inphase`로, 6-tap 사분 필터 출력 `Q1`을 `quadrature`로 내보낸다.
`smoothPeriod`와 지배 주기 위상 계층은 사용하지 않는다. 두 출력의 lookback은 32이고
`min_history`는 33이다.

### 8.9 HT_TRENDMODE

계산 원본은 `ta_HT_TRENDMODE.c`다. §8.7의 위상과 §8.4의 sine 두 선 및 추세선을
함께 계산한다. 기본 상태는 추세 국면 `1`이다. sine과 leadsine이 교차하면
`daysInTrend`를 0으로 되돌리고 순환 국면 `0`으로 바꾼다. `daysInTrend`가
`0.5·smoothPeriod`보다 작거나, 위상 변화가
`0.67·360/smoothPeriod`보다 크면서 `1.5·360/smoothPeriod`보다 작으면 `0`이다.
평활가격과 추세선의 상대 차이 절댓값이 0.015 이상이면 마지막에 다시 `1`로 정한다.

플랫폼 출력은 실수 정책에 맞춘 `0.0` 또는 `1.0`이며 방향 부호는 붙이지 않는다.
성숙 전 63봉은 NaN이고 그 뒤의 상태값은 TA-Lib 정수 출력과 허용오차 없이 정확히
일치해야 한다. lookback은 63이고 `min_history`는 64다.

## §9. 기타 주요 시스템 (★4↑)

### 9.1 Parabolic SAR (Wilder, 1978) ★★★★★
```
초기: 추세 방향 가정, EP=해당 방향 극값, AF=0.02
SAR_{t+1} = SAR_t + AF · (EP − SAR_t)
- 새 EP 갱신 시(상승추세서 신고가 등) AF += 0.02, 상한 AFmax=0.20
- SAR가 직전 2봉 가격범위를 침범하면 해당 봉 극값으로 클램프
- 가격이 SAR를 관통하면 추세 반전: SAR=직전 EP, AF 리셋(0.02), EP=새 극값
```

### 9.2 Ichimoku Kinko Hyo (Goichi Hosoda, 1969 공표) ★★★★★
중복 제거: HH/LL(§0.8).
```
Tenkan-sen  = (HH(9)  + LL(9))  / 2
Kijun-sen   = (HH(26) + LL(26)) / 2
Senkou A    = (Tenkan + Kijun)/2,  미래 +26 시프트
Senkou B    = (HH(52) + LL(52))/2, 미래 +26 시프트         (구름 = A~B)
Chikou Span = C, 과거 −26 시프트
```
> Senkou 미래 시프트/Chikou 과거 시프트는 **표시 규약**. 실거래 신호 계산 시 확정봉 기준으로 정렬해야 look-ahead 방지.

### 9.3 Elder Ray (Alexander Elder) ★★★★★
중복 제거: EMA(§0.3).
```
BullPower = H − EMA(C, 13)
BearPower = L − EMA(C, 13)
```

### 9.4 Elder Impulse System (Alexander Elder) ★★★★
공식 아닌 색상 규칙(EMA 기울기 + MACD 히스토그램 기울기 조합).
```
EMA13 상승 AND MACD-Hist 상승 → 녹색(강세 임펄스)
EMA13 하락 AND MACD-Hist 하락 → 적색(약세 임펄스)
그 외 → 청색(중립)
```

### 9.5 TD Sequential (Tom DeMark) ★★★★
공식 아닌 카운트 규칙 시스템.
```
Setup: 연속 9봉, 각 C_t 가 C_{t-4} 대비 일관 방향(매수셋업=하락, 매도셋업=상승)
Countdown: Setup 완료 후 13 카운트 (C_t vs C_{t-2} 조건 충족 봉 누적)
9-13 완성 지점을 반전 후보로 사용
```
> 규칙 세부(완전성 조건, TDST 지지/저항)는 DeMark 원저서 정의를 그대로 코딩해야 함.

### 9.6 Woodies CCI (Ken Wood) ★★★★
중복 제거: CCI(§2.10). 공식 아닌 CCI 기반 패턴 시스템.
```
CCI(14) + CCI Turbo(6) 병행 표시 + ±100/±200 존 + zero-line 패턴(ZLR, TLB, GB100 등)
```
단일 계산식 아님 — 판정 규칙 집합.

### 9.7 통계 / 회귀 계열 (Statistics / Regression)

이 장의 두 지표는 마감 시각이 같은 두 가격 계열을 한 쌍으로 받는다. `X`는 기준 종목의
가격이고 `Y`는 실행 주 종목의 가격이다. 두 배열의 같은 index는 같은 마감 시각을 가리키며,
한쪽에만 있는 봉은 입력에 반복하거나 0으로 채우지 않는다. 아래의 `n`은 1 이상 100000 이하인
정수다.

#### 9.7.1 BETA — 두 수익률 계열의 회귀 기울기

계산 원본은 TA-Lib v0.7.1의 `src/ta_func/ta_BETA.c`다. 원본의 실행되는 산술은 첫 입력
`inReal0`을 `X`, 둘째 입력 `inReal1`을 `Y`로 놓고 `Y`의 수익률을 `X`의 수익률로 설명하는
회귀 기울기를 구한다. 원본의 설명 주석 중 배열의 종목 역할을 적은 문장과 그 뒤의 `x`·`y`
설명은 서로 어긋나므로, 이 표준은 주석의 종목 이름이 아니라 실제 산술 순서를 따른다.
플랫폼은 기준 종목을 `X`에, 실행 주 종목을 `Y`에 넣는다.

먼저 연속한 두 가격의 단순 수익률을 만든다. 직전 가격의 절댓값이 원본의
`TA_EPSILON = 10^-14`보다 작으면 그 수익률은 0이다.

```text
x_i = 0                                      if |X_{i-1}| < 10^-14
x_i = (X_i - X_{i-1}) / X_{i-1}            otherwise

y_i = 0                                      if |Y_{i-1}| < 10^-14
y_i = (Y_i - Y_{i-1}) / Y_{i-1}            otherwise
```

최근 수익률 `n`쌍에서 아래 합을 구한다.

```text
S_xx = sum(x_i^2)
S_xy = sum(x_i * y_i)
S_x  = sum(x_i)
S_y  = sum(y_i)
D    = n * S_xx - S_x^2
```

`|D| < 10^-14`이면 결과는 `0.0`이고, 아니면 아래 회귀 기울기를 낸다.

```text
BETA = (n * S_xy - S_x * S_y) / D
```

다음 봉에서는 새 수익률 한 쌍을 합에 더하고 가장 오래된 수익률 한 쌍을 뺀다. 기본 `n`은
5다. 수익률 `n`개를 만들려면 가격 쌍 `n+1`개가 필요하므로 lookback은 `n`이고
`min_history`는 `n+1`이다.

#### 9.7.2 CORREL — Pearson 상관계수

계산 원본은 TA-Lib v0.7.1의 `src/ta_func/ta_CORREL.c`다. BETA와 달리 수익률로 바꾸지 않고
최근 가격 `n`쌍을 그대로 사용한다.

```text
S_x  = sum(X_i)
S_y  = sum(Y_i)
S_xx = sum(X_i^2)
S_yy = sum(Y_i^2)
S_xy = sum(X_i * Y_i)

V_x = S_xx - S_x^2 / n
V_y = S_yy - S_y^2 / n
D   = V_x * V_y
```

원본의 `TA_IS_ZERO_OR_NEG` 판정에 따라 `D < 10^-14`이면 결과는 `0.0`이고, 아니면
아래 값을 낸다.

```text
CORREL = (S_xy - S_x * S_y / n) / sqrt(D)
```

다음 봉에서는 새 가격 쌍을 합에 더하고 가장 오래된 가격 쌍을 뺀다. 기본 `n`은 30이다.
가격 쌍 `n`개에서 첫 값이 나오므로 lookback은 `n-1`이고 `min_history`는 `n`이다.

## §10. 중복 제거 의존성 맵 (Dependency Map)

각 지표가 어떤 공유 프리미티브를 재사용하는지 — 계산 로직 중복을 프리미티브 계층으로 흡수한 결과.

```mermaid
graph LR
    subgraph Primitives["§0 공유 프리미티브"]
        SMA[SMA]
        EMA[EMA]
        WMA[WMA]
        RMA["RMA / Wilder / SMMA"]
        TR[True Range]
        TP[Typical Price]
        HL2[Median HL2]
        STD[StDev]
        HHLL["HH / LL rolling"]
        CUM[Cumulative]
        ROC[ROC / MOM]
    end

    EMA --> MACD --> PPO
    EMA --> TRIX
    EMA --> DEMA --> TEMA
    EMA --> T3
    EMA --> TSI --> SMI
    EMA --> KST
    EMA --> ForceIndex
    EMA --> ElderRay
    EMA --> Keltner
    EMA --> ChaikinOsc
    EMA --> McClellan
    EMA --> ZLEMA
    EMA --> QQE

    WMA --> HMA
    WMA --> Coppock

    RMA --> RSI --> StochRSI
    RSI --> ConnorsRSI
    RSI --> QQE
    RMA --> ATR
    RMA --> DMI["DMI / ADX / ADXR"]
    RMA --> RVIvol["RVI(Dorsey)"]
    RMA --> DeMarker

    SMA --> TRIMA
    SMA --> APO
    SMA --> BOP
    SMA --> ACCBANDS["Acceleration Bands"]

    TR --> ATR
    ATR --> NATR
    ATR --> Keltner
    ATR --> SuperTrend
    ATR --> Chandelier
    ATR --> PGO
    ATR --> RWI
    ATR --> Choppiness
    TR --> Vortex
    TR --> Choppiness

    TP --> CCI
    TP --> MFI
    CCI --> WoodiesCCI

    HL2 --> AO --> AC
    HL2 --> Alligator --> Gator
    HL2 --> Ichimoku
    HL2 --> SuperTrend
    HL2 --> Fisher

    STD --> RVIvol
    STD --> Bollinger

    HHLL --> Stochastic --> SchaffTC
    MACD --> SchaffTC
    HHLL --> WilliamsR
    HHLL --> Donchian
    HHLL --> Aroon
    HHLL --> Chandelier
    HHLL --> Ichimoku
    HHLL --> UltimateOsc

    CUM --> OBV
    CUM --> ADL --> ChaikinOsc
    ADL --> CMF
    CUM --> NVI
    CUM --> PVI
    CUM --> McClellanSum["McClellan Summation"]

    ROC --> KST
    ROC --> Coppock
    ROC --> DPO
    ROC --> SpecialK
    ROC --> ConnorsRSI
```

## §11. 커버리지 집계 (본 명세서 수록 지표 수)

| 카테고리 | 수록 지표 | 개수 |
|---|---|---|
| §1 Trend / MA | DEMA, TEMA, T3, HMA, ZLEMA, ALMA, KAMA, VIDYA, McGinley, Guppy, TRIMA | 11 |
| §2 Momentum / Oscillator | RSI, Stochastic Fast, Stochastic Slow, StochRSI, MACD(+Hist), PPO, APO, TRIX, TSI, SMI, CMO, Williams %R, CCI, Ultimate Osc, AO, AC, Fisher, ConnorsRSI, QStick, Chande Forecast, DeMarker, DPO, Schaff TC, RVI(Ehlers), Laguerre RSI, PGO, KST, Coppock, Special K, BOP, IMI | 31 |
| §3 Volatility | ATR, NATR, Bollinger Bands, %B, BandWidth, Keltner, Donchian, SuperTrend, Chandelier, Ulcer, RVI(Dorsey), Chaikin Vol, Mass Index, Acceleration Bands | 14 |
| §4 Volume | OBV, A/D Line, Chaikin Osc, CMF, MFI, Force Index, EMV, Klinger, NVI, PVI | 10 |
| §5 Trend Strength | DMI/ADX 시스템, Vortex, Aroon, Choppiness, QQE, RWI | 6 |
| §6 Bill Williams | Alligator, Fractals, Gator, Market Facilitation Index | 4 |
| §7 Market Breadth | McClellan Osc, McClellan Summation, TRIN | 3 |
| §8 Cycle / Ehlers | MAMA/FAMA, Center of Gravity, Roofing Filter, Sinewave/ITrend, HT_DCPERIOD, HT_DCPHASE, HT_PHASOR, HT_TRENDMODE | 8 |
| §9 기타 시스템 | Parabolic SAR, Ichimoku, Elder Ray, Elder Impulse, TD Sequential, Woodies CCI | 6 |
| §9.7 Statistics / Regression | BETA, CORREL | 2 |
| **합계** | | **95** |

> 세는 규칙 명시: 위 표는 "시스템/지표 단위"로 **95개**(11+31+14+10+6+4+3+8+6+2=95)를 수록한다.
> 이번에 §8에서 확정하거나 신설한 제목은 §8.1과 §8.4부터 §8.9까지 일곱이지만 **집계가 늘어난 것은 넷**이다. MAMA/FAMA(§8.1)와 Sinewave/ITrend(§8.4)는 이전부터 집계에 있던 항목이고 이번에 계산 원본만 확정했으므로 다시 세지 않는다. §8.5 공통 Hilbert 전단은 여러 지표가 공유하는 계산 단계이지 독립 지표가 아니므로 세지 않는다. §8.4의 `HT_SINE`과 `HT_TRENDLINE`은 함수가 둘이지만 Sinewave/ITrend 한 항목으로 센다. 따라서 새로 더해진 넷은 HT_DCPERIOD, HT_DCPHASE, HT_PHASOR, HT_TRENDMODE다.
> - DMI/ADX를 구성요소(+DI, −DI, ADX, ADXR) 4개로 펼치면 3개가 늘어 98개다.
> - Bollinger를 밴드 1개로 묶고 %B·BandWidth를 파생으로 빼면 2개가 줄어 93개다.
> - Stochastic의 Fast와 Slow를 한 시스템으로 묶으면 1개가 줄어 94개다. §2.2는 둘을 별개로 세고 별개로 등록한다.
> - ATR과 NATR을 한 항목으로 묶으면 1개가 줄어 94개다. §3.11은 NATR을 독립 지표로 센다.
> - `HT_SINE`과 `HT_TRENDLINE`을 별개로 세면 1개가 늘어 96개다. §8.4는 둘을 한 항목으로 센다.
> - MACD와 MACD Histogram을 분리하면 1개가 늘어 96개다.
>
> **crypto 미수록(의도적 제외)**: Wilder의 Swing Index / ASI / CSI / Volatility Stop은 ★5이나 암호화폐 적용성이 낮아 제외했다. Swing Index·ASI는 "limit move" 파라미터가 무기한 시장에 정의되지 않고, Volatility Stop은 §3.5 Chandelier Exit(ATR 스톱)로 사실상 대체된다. 필요 시 별도 추가 가능.

## §12. 검증 필요 / 미확정 항목 (원문 대조 대상)

아래 항목은 계산의 **뼈대(알고리즘)는 확정**했으나, 상수·초기화·평활 규칙이 구현체별로 갈려 원저자 1차 출처 대조가 필요하다. 이 부분은 추측하지 않고 명시적으로 남긴다.

| 지표 | 미확정 부분 | 대조할 1차 출처 |
|---|---|---|
| VIDYA | k 정의(CMO vs σ비율) | Chande, *Technical Analysis of Stocks & Commodities* (1992) |
| Schaff Trend Cycle | 내부 이중 스토캐스틱 평활 상수/클램프 | Doug Schaff 원자료 |
| Klinger VO | cm 초기화·VF 절댓값 처리 | Klinger 원자료 |
| QQE | 트레일링 밴드 락 규칙 | Igor Livshin 원 코드 |
| Roofing Filter | HP cutoff·SuperSmoother 계수 | Ehlers, *Cycle Analytics for Traders* (2013) |
| Special K | 항별 ROC기간·평활·가중치표 | Pring 원자료 |
| Keltner | 원형(SMA+range) vs 현대형(EMA+ATR) | Keltner(1960) / Raschke |

QQE, Roofing Filter, Special K는 TA-Lib v0.7.1에 대응 계산 함수가 없으므로 §0.12의
예외로 확정할 수 없고 미확정 목록에 남는다.

## §13. 참고 문헌 (1차 출처)

1. J. Welles Wilder Jr., *New Concepts in Technical Trading Systems*, 1978. — RSI, ATR, ADX/DMI, Parabolic SAR, Wilder 평활
2. Gerald Appel, *Technical Analysis: Power Tools for Active Investors*, 2005. — MACD
3. John Bollinger, *Bollinger on Bollinger Bands*, 2001. — Bollinger Bands, %B, BandWidth
4. Tushar Chande & Stanley Kroll, *The New Technical Trader*, 1994. — CMO, StochRSI, VIDYA, Aroon, IMI
5. Perry Kaufman, *Trading Systems and Methods*. — KAMA(Adaptive MA), 삼각가중(Triangular Weighting)
6. John F. Ehlers, *Rocket Science for Traders*, 2001 / *Cybernetic Analysis for Stocks and Futures*, 2004 / *Cycle Analytics for Traders*, 2013. — Fisher, MAMA/FAMA, Laguerre RSI, RVI, CG, Roofing/Sinewave
7. William Blau, *Momentum, Direction, and Divergence*, 1995. — TSI, SMI
8. Martin Pring, *Technical Analysis Explained*. — KST, Special K
9. Alexander Elder, *Trading for a Living*, 1993. — Elder Ray, Force Index, Elder Impulse
10. Bill Williams, *Trading Chaos*, 1995. — AO, AC, Alligator, Fractals, Gator, MFI
11. Patrick Mulloy, "Smoothing Data with Faster Moving Averages", *TASC*, 1994. — DEMA, TEMA
12. Tim Tillson, "Better Moving Averages", *TASC*, 1998. — T3
13. Alan Hull, 2005. — Hull MA
14. Arnaud Legoux & Dimitrios Kouzis-Loukas, 2009. — ALMA
15. Etienne Botes & Douglas Siepman, "The Vortex Indicator", *TASC*, 2010. — Vortex
16. Donald Dorsey, "The Mass Index" / "The Relative Volatility Index", *TASC*, 1992–1993.
17. Donald Lambert, "Commodity Channel Index", *Commodities*, 1980. — CCI
18. Sherman & Marian McClellan. — McClellan Oscillator/Summation
19. Richard W. Arms Jr., 1967. — TRIN(Arms Index)
20. Tom DeMark, *The New Science of Technical Analysis*, 1994. — TD Sequential, DeMarker
21. Goichi Hosoda(一目山人), 1969. — Ichimoku Kinko Hyo
22. **라이브러리 교차대조**: TA-Lib(ta-lib.org), pandas-ta(github.com/twopirllc/pandas-ta), Tulip Indicators(tulipindicators.org), TradingView Pine 내장 함수 문서. 다만 §0.12의 아홉 함수는 명시한 고정 TA-Lib C 구현을 계산 원본으로 쓰는 제한적 예외다.
23. Igor Livshin, "Balance Of Power", *Technical Analysis of Stocks & Commodities* V.19:8, 2001년 8월, 18–32쪽. — BOP(§2.29). 축약형이 원문 전개형과 같음을 저자가 확인한 서신은 같은 잡지 2001년 10월 독자란.
24. J. J. Payne, "A Better Way to Smooth Data", *Technical Analysis of Stocks & Commodities*, 1989년 10월. — 삼각가중(TRIMA, §1.11). 위 5번 Kaufman의 "Triangular Weighting" 절이 이 글을 1차 출처로 인용한다.
25. John Forman, "Cross-Market Evaluations With Normalized Average True Range", *Technical Analysis of Stocks & Commodities* V.24:5, 2006년 5월, 60–63쪽. — NATR(§3.11)
26. Price Headley, *Big Trends in Trading: Strategies to Master Major Market Moves*, Wiley, 2002, 7장. — Acceleration Bands(§3.12)
27. Trading Technologies, X_STUDY "Absolute Price Oscillator" 정의 문서. — APO(§2.28). 원저자를 세울 수 있는 1차 출처가 아니라, 이동평균 종류를 사용자 파라미터로 남긴 문서화된 정의로서 인용한다. APO는 이 명세서에서 1차 출처가 없는 유일한 항목이다.

## §14. 부록 A — 추가 참조 프리미티브

일부 지표(§2.17 Chande Forecast Osc 등)가 참조하는 **선형회귀(Linear Regression)** 프리미티브:
```
n기간 최소자승 회귀: y = a + b·x  (x=0..n−1, y=P)
b = [ n·Σ(x·y) − Σx·Σy ] / [ n·Σ(x^2) − (Σx)^2 ]
a = ( Σy − b·Σx ) / n
LinRegForecast(P,n)_t = a + b·(n−1)          (현재봉 위치 추정값)
LinRegSlope = b ;  LinRegIntercept = a
```

---

*본 명세서는 1차 마스터 목록의 ★4 이상 지표에 대한 계산 계층이다. 계산의 뼈대는 원저자 1차 출처 기준으로 확정하되 §0.12의 아홉 함수만 고정 TA-Lib C 구현을 계산 원본으로 삼는다. 구현체별로 갈리는 나머지 상수는 §12에 "검증 필요"로 명시하여 추측을 배제했다. 각 지표의 의사코드(반복문 포함)·시간복잡도·NaN/오버플로 처리·플랫폼별 수치 검증은 후속 상세 문서 단계에서 지표별로 확장한다.*
