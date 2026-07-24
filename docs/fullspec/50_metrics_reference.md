# 시스템 트레이딩 성과 지표 — 수학적 배경 (최종 검증판)

> 백테스트·자동매매 전략 검증에 쓰이는 핵심 성과 지표를 **수학식 · 의미 · 장단점 · 계산 예시 · Python 코드 · 흔한 실수 · 해석 주의사항**으로 정리한 기준 문서.
> 두 초안(ChatGPT·Gemini)을 비교·교차검증한 뒤 모든 수치를 Python(NumPy)으로 재현하여 확정한 버전이다.

---

## 0. 이 문서의 검증 내역

- 모든 거래 단위 지표는 공통 손익 배열 `x`로, 모든 수익률 단위 지표는 공통 월간 수익률 배열 `r`로 계산했고, 본문의 모든 숫자는 NumPy 재현값과 일치한다.
- **두 초안 비교 결과 발견·수정한 오류**
  - **Sortino Ratio (중대 오류):** 한 초안이 하방편차를 `returns[returns<0].std()`(음수 수익률만의 표준편차)로 계산 → 본 예시에서 Sortino 3.39로 **과대평가**. 올바른 하방편차는 `sqrt( mean( min(0, r−T)² ) )`로 **전체 관측 수 N으로** 나눠야 하며 정답은 Sortino 2.49.
  - **Loss Rate:** `1 − Win Rate`는 손익분기(0) 거래가 있으면 틀린다. `p + q + z = 1`로 표기.
  - **Sharpe 분모:** 표본표준편차(`ddof=1`)를 기본으로 통일.
  - **MDD:** 단순 `min(V)/max(V)`가 아니라 **누적 최고점(running max) 이후의 저점** 기준이어야 함을 명시.
- 실무 벤치마크(PF·SQN·Calmar·RoR 권장 임계치)와 강한 10항목 템플릿은 가독성을 위해 채택했다.

---

## 공통 표기와 예시 데이터

거래별 손익:

$$x_i,\quad i=1,\dots,N$$

수익/손실 집합:

$$W=\{i:x_i>0\},\qquad L=\{i:x_i<0\},\qquad N_0=|\{i:x_i=0\}|$$

평균은 **부호 혼동을 막기 위해 손실을 양수 크기로** 정의:

$$\overline{W}=\frac{1}{N_W}\sum_{i\in W}x_i,\qquad \overline{L}=\frac{1}{N_L}\sum_{i\in L}|x_i|$$

**공통 거래 예시:**

$$x=[200,-100,150,-50,300,-120,80,250,-70,180]$$

$$N=10,\quad N_W=6,\quad N_L=4,\quad \text{GP}=1160,\quad \text{GL}=340,\quad \text{Net}=820$$

**공통 월간 수익률 예시:**

$$r=[3\%,-2\%,1.5\%,4\%,-1\%,2.5\%,-3.5\%,2\%,1\%,-1.5\%,3\%,2\%]$$

초기자본 $V_0=100{,}000$ → 최종 $V_T=111{,}235.71$ (12개월 = 1년).

```python
import numpy as np
pnl = np.array([200,-100,150,-50,300,-120,80,250,-70,180], dtype=float)
monthly_returns = np.array([0.03,-0.02,0.015,0.04,-0.01,0.025,
                            -0.035,0.02,0.01,-0.015,0.03,0.02])
```

---

## 권장 해석 조합

하나의 지표로 전략을 판단하지 않는다. 최소한 다음 6개를 함께 본다:

$$\text{Expectancy},\ \text{Profit Factor},\ \text{CAGR},\ \text{MDD},\ \text{Sharpe},\ \text{Risk of Ruin}$$

| 질문 | 핵심 지표 |
|---|---|
| 돈을 버는가? | Net Profit, Expectancy, Profit Factor |
| 거래 1회당 우위가 있는가? | Expectancy per Trade, Payoff Ratio |
| 장기 복리 성과는? | CAGR, Annual Return |
| 변동성 대비 성과는? | Sharpe, Sortino |
| 최대 손실을 견딜 수 있는가? | MDD, Calmar, MAR |
| Drawdown 고통의 크기는? | Ulcer Index |
| 손실 회복력은? | Recovery Factor |
| 거래 품질은? | SQN |
| 베팅 크기는? | Kelly Criterion |
| 파산 가능성은? | Risk of Ruin |

비유로: **Expectancy·PF = 엔진 출력**, **MDD·Sortino·Ulcer = 브레이크**, **Kelly·RoR = 액셀(베팅 비중)**.

### 워크플로 단계별 — 언제 어떤 지표를 쓰나

| 단계 | 목적 | 사용 지표 |
|---|---|---|
| ① 전략 설계 (진입 전) | 손익비·목표가/손절가 구조 점검 | Reward/Risk, Payoff Ratio, 손익분기 승률 |
| ② 1차 스크리닝 | "유효한 전략인가" 빠른 합격/탈락 | Expectancy, Profit Factor, Net Profit |
| ③ 수익 구조 진단 | 승률·손익비·기대값 분해 | Win/Loss Rate, Avg Win/Loss, Payoff |
| ④ 장기·기간 비교 | 다른 전략/벤치마크와 비교 | CAGR, Annual Return |
| ⑤ 위험조정 평가 | 변동성·하방위험 대비 성과 | Sharpe, Sortino, Calmar, MAR |
| ⑥ 경로 위험 점검 | 감내 가능성·회복력 | MDD, Ulcer Index, Recovery Factor |
| ⑦ 신뢰도 검증 | 표본·통계적 유의성 | SQN (N≥30) |
| ⑧ 자금 관리 | 베팅 비중·생존성 결정 | Kelly, Risk of Ruin |

> 운용 순서는 보통 ②→③→④→⑤→⑥→⑦→⑧. ①은 전략을 만드는 단계에서 선행한다.

---

# 1. 거래 단위 지표

## 1.1 Win Rate / Loss Rate

**🎯 언제·왜 쓰나:** 전략의 **성격을 분류**할 때 가장 먼저 본다 — 고승률(평균회귀)인지 저승률(추세추종)인지. 손익분기 승률 $p_{BE}=1/(1+B)$와 비교해 "지금 승률로 우위가 있는가"를 즉시 판정하고, Kelly·Risk of Ruin 계산의 **입력값**으로 쓴다. 단, 절대 단독으로 채택/기각 판단하지 않는다.

**정의:** 전체 거래 중 수익(손실) 거래의 비율.

**공식**

$$p=\frac{N_W}{N},\qquad q=\frac{N_L}{N}$$

손익분기 거래가 있으면 단순히 $q=1-p$가 **아니다**:

$$p+q+z=1,\qquad z=\frac{N_0}{N}$$

손익분기 제외 승률: $p_{\text{ex-zero}}=\dfrac{N_W}{N_W+N_L}$

**의미:** 임의의 한 거래가 수익으로 끝날 경험적 확률.

**장점:** 직관적이다(60%면 10번 중 6번 승).
**단점:** 수익성을 보장하지 않는다. $p=0.9,\overline W=1,\overline L=20$이면 $E=0.9-2=-1.1<0$.

**계산 예시:** $p=6/10=60\%,\ q=4/10=40\%$

```python
win_rate = np.mean(pnl > 0)   # 0.6
loss_rate = np.mean(pnl < 0)  # 0.4
```

**흔한 실수:** 손익분기 거래의 분모 포함 여부를 명시하지 않음. 추세추종은 승률 30~40%로 낮아도 손익비로 수익을 낸다 — 승률에 집착 금지.
**임계값 표준 (→ `20_thresholds.md`):** Win Rate는 **단독 게이트 아님(성격 참고)**. 밴드 25~45%, >50%면 평균회귀화·우측꼬리 상실 의심, <25%면 거짓돌파·진입품질 의심. 수익성 판정은 E_R/PF.

---

## 1.2 Average Win / Average Loss

**🎯 언제·왜 쓰나:** 전략의 **보상 구조(payoff profile)를 분해**할 때. 익절·손절 폭이 설계 의도대로 실현됐는지 점검하고, Expectancy·Payoff Ratio의 **기초 재료**로 쓴다. 평균이 극단치에 끌려갔는지 보려고 중앙값과 함께 본다.

**정의:** 수익 거래 평균 수익, 손실 거래 평균 손실(양수 크기).

**공식**

$$\overline{W}=\frac{1}{N_W}\sum_{i\in W}x_i,\qquad \overline{L}=\frac{1}{N_L}\sum_{i\in L}|x_i|$$

**계산 예시:** $\overline{W}=1160/6=193.33,\quad \overline{L}=340/4=85$

```python
avg_win  = pnl[pnl > 0].mean()    # 193.333...
avg_loss = -pnl[pnl < 0].mean()   # 85.0
```

**단점:** 극단치 1건에 왜곡됨(예: `[10,10,10,1000]`→평균 257.5). 반드시 **중앙값**과 비교.
**흔한 실수:** ① 분모에 전체 $N$ 사용(올바른 분모는 $N_W,N_L$). ② 평균손실을 음수로 둔 채 이후 식에서 부호가 꼬임.

---

## 1.3 Payoff Ratio

**🎯 언제·왜 쓰나:** 승률과 **결합해 우위(edge)의 존재**를 판단할 때. "승률이 낮아도 손익비로 버는가?"를 $pB>q$로 확인한다. 전략 설계·튜닝 단계에서 손절 대비 익절 목표가 합리적인지 검토하는 기준.

**정의:** 평균 수익 ÷ 평균 손실(둘 다 양수 크기).

**공식**

$$B=\frac{\overline{W}}{\overline{L}}$$

기대값과의 핵심 관계 — $\overline W = B\overline L$이므로:

$$E=p\overline{W}-q\overline{L}=\overline{L}\,(pB-q)\ \Rightarrow\ pB>q \text{ 이면 } E>0$$

**계산 예시:** $B=193.33/85=2.2745$

```python
payoff_ratio = avg_win / avg_loss   # 2.2745
```

**단점:** 평균 기반이라 이상치에 민감. 승률과 **반비례** 경향(크게 먹으려면 승률↓).
**흔한 실수:** 목표가/손절가 비율(=설계값)을 실현 Payoff와 혼동. **0 나눗셈**(전승 시) 방어 필요.
**임계값 표준 (→ 20_threasholds §5):** **형태 의존 지표 — 보편 구속 아님.** 각 전략이 선언한 프로파일 기대 범위(`25_strategy_profiles.md`)와 대조한다. 추세추종 예시 기대 범위는 2~4, 평균회귀는 <1. 실현값이 기대 범위를 크게 이탈하면 구조적 파손 신호(자동 탈락 아님 — Scorecard 경보/기대 범위 재확인). >5+극저승률은 단일거래 의존·이상치 확인. **수익성 판정은 언제나 E_R/PF가 한다.** (구 `Payoff≥2` 보편 구속·`원칙②`는 폐지 — 추세추종 형태값이라 평균회귀를 부당 탈락시켰음.)

---

## 1.4 Reward/Risk Ratio

**🎯 언제·왜 쓰나:** **진입 전 트레이드 설계** 단계에서 목표가·손절가의 합리성을 점검할 때(사전값). 운용 후에는 실현 Payoff Ratio와 비교해 "설계대로 체결됐는가, 트레일링/조기청산으로 새는가"를 추적하는 용도.

**정의:** 한 거래의 위험 대비 보상. **사전(ex-ante)**과 **실현(realized)** 두 의미가 있다.

**공식**

사전(진입 전 설계):

$$\text{RR}_{\text{ex-ante}}=\frac{\text{Target}-\text{Entry}}{\text{Entry}-\text{Stop}}$$

실현(R-multiple 기반, $R_i=x_i/\text{Initial Risk}_i$):

$$\text{RR}_{\text{realized}}=\frac{\overline{R}_{+}}{|\overline{R}_{-}|}$$

**계산 예시:** 진입 100, 손절 95, 목표 110 → $RR=10/5=2$. 거래당 초기위험 100이면 실현 $RR=1.9333/0.85=2.2745$.

```python
rr_ex_ante = (110 - 100) / (100 - 95)   # 2.0
R = pnl / 100
rr_realized = R[R>0].mean() / abs(R[R<0].mean())  # 2.2745
```

**핵심 구분:** **Reward/Risk = 계획**, **Payoff Ratio = 실현 결과**. 트레일링 스탑·조기청산·슬리피지로 1:3 설계가 실현 1:1.5로 떨어지는 경우가 흔하다.

---

# 2. 기대값 · 총수익 지표

## 2.1 Expectancy / Expectancy per Trade

**🎯 언제·왜 쓰나:** 전략 채택의 **1차 관문** — 양수가 아니면 더 볼 것도 없이 기각. 전략 간 **거래당 효율**을 비교하고(특히 R-multiple 기준), 비용 차감 후에도 양수인지 확인하는 핵심 수익성 지표.

**정의:** 거래 1회당 기대 손익. **시스템 트레이딩에서 가장 근본적인 수익성 지표.**

**공식**

$$E[X]=p\overline{W}-q\overline{L},\qquad \widehat{E}=\frac{1}{N}\sum_i x_i=\frac{\text{Net Profit}}{N}$$

R-multiple 기준: $E[R]=p\overline R_{+}-q|\overline R_{-}|$

**계산 예시:** $E=0.6\times193.33-0.4\times85=82$ ( = Net 820 / 10 ).

```python
expectancy = win_rate*avg_win - loss_rate*avg_loss   # 82.0
exp_per_trade = pnl.sum() / len(pnl)                 # 82.0
```

**단점:** 분산·MDD·파산위험·**거래 빈도**를 반영하지 않는다(1년 1회 거래면 무의미).
**흔한 실수:** 수수료·슬리피지·세금·펀딩비 **차감 전** 손익으로 계산해 양수로 착각. 금액/수익률/R-multiple 기준을 구분하라. 몬테카를로로 신뢰구간 확인 권장.

---

## 2.2 Profit Factor

**🎯 언제·왜 쓰나:** 자본 규모와 무관하게 **전략 품질을 빠르게 스크리닝**할 때. 여러 전략·파라미터 후보를 1차로 거르는 필터로 쓰고, 동시에 비정상적으로 높은 값(>3.0)으로 **과최적화 경보**를 잡는 용도.

**정의:** 총수익 ÷ 총손실(절대값).

**공식**

$$\text{PF}=\frac{\text{Gross Profit}}{\text{Gross Loss}}=\frac{\sum_{i\in W}x_i}{\sum_{i\in L}|x_i|}$$

Expectancy와의 관계: $E=q\overline{L}(\text{PF}-1)$ → 같은 데이터에서 $\text{PF}>1\Leftrightarrow E>0$.

**계산 예시:** $\text{PF}=1160/340=3.4118$

```python
gp = pnl[pnl>0].sum(); gl = -pnl[pnl<0].sum()
profit_factor = gp / gl   # 3.4118
```

**벤치마크 (임계값 표준 → `20_thresholds.md`):** 측정은 net·가능하면 OOS·N≥30 기준. **통과선 PF < 1.3**(엣지 없음, `PF>1 ⇔ E>0`이므로 사실상 E≤0 영역), **목표선 PF ≥ 1.5**(양호), **과최적화 경보 PF ≥ 3.0**(자동채택 금지 — 거래 수 부족·비용 누락·체결 가정 오류·look-ahead 재검 통과 시에만 인정).
**흔한 실수:** GL을 음수로 둬 PF가 음수로 나옴. 손실 거래가 거의 없는 짧은 구간에서 ∞.

---

## 2.3 Gross Profit / Gross Loss / Net Profit

**🎯 언제·왜 쓰나:** 전략이 **절대 금액 기준으로 돈을 벌었는지** 최종 확인할 때. 그 자체로는 비교 불가능하므로 PF·Expectancy·수익률 지표의 **구성요소**로 쓰고, 반드시 초기자본 대비 수익률·연율화와 함께 본다.

**공식**

$$\text{GP}=\sum_{i\in W}x_i,\quad \text{GL}=\sum_{i\in L}|x_i|,\quad \text{Net}=\text{GP}-\text{GL}=\sum_i x_i$$

**계산 예시:** GP $=1160$, GL $=340$, Net $=820$.

```python
net_profit = pnl.sum()   # 820
```

**단점:** 초기자본·기간·변동성·MDD 미반영 → 전략 간 1:1 비교 불가. 반드시 수익률 $\text{Net}/V_0$ 및 연율화 지표와 함께 본다.
**주의:** 성과통계에서 "Gross"는 보통 **수익 거래 합계**를 뜻한다(거래비용 차감 전이라는 뜻이 아님). 복리/단리 누적을 혼동하지 말 것.

---

## 2.4 CAGR

**🎯 언제·왜 쓰나:** **기간이 다른 전략들**이나 벤치마크(S&P500 등)와 장기 수익률을 공정하게 비교할 때. 복리 효과를 단일 숫자로 환산한다. 단, 경로 위험을 숨기므로 **항상 MDD와 짝**으로 본다.

**정의:** 복리 기준 연평균 성장률.

**공식**

$$\text{CAGR}=\left(\frac{V_T}{V_0}\right)^{1/Y}-1$$

**계산 예시:** $Y=1$이므로 총수익률과 동일 → $111235.71/100000-1=11.2357\%$.

```python
equity = 100000 * np.cumprod(1 + monthly_returns)
years = len(monthly_returns) / 12
cagr = (equity[-1] / 100000) ** (1/years) - 1   # 0.112357
```

**단점:** 경로 위험(중간 MDD)을 숨긴다. **항상 MDD와 함께** 본다.
**흔한 실수:** 단순평균×기간을 CAGR로 착각. 올바른 식은 $\left(\prod(1+r_t)\right)^{K/N}-1$. 연율화 기준일(252 vs 365) 혼동 주의.

---

## 2.5 Annual Return

**🎯 언제·왜 쓰나:** 성과를 **투자자에게 익숙한 연 단위**로 보고·비교할 때. 연도별 성과의 일관성(특정 연도가 전체를 캐리했는지)을 점검하는 용도. 성과 평가의 최종 수치로는 산술이 아닌 **기하 연율화/CAGR**을 쓴다.

**정의/공식** — 세 가지를 구분:

- 특정 연도: $R_{\text{year}}=\dfrac{V_{\text{end}}}{V_{\text{start}}}-1$
- 산술 연율화: $R_{\text{arith}}=K\overline{r}$
- 기하 연율화: $R_{\text{geo}}=\left(\prod_{t}(1+r_t)\right)^{K/N}-1$

**계산 예시:** $\overline r=0.0091667$ → 산술 $12\times0.0091667=11.00\%$, 기하 $=11.2357\%$.

```python
ann_arith = monthly_returns.mean() * 12                                  # 0.1100
ann_geo   = np.prod(1+monthly_returns)**(12/len(monthly_returns)) - 1     # 0.112357
```

**주의:** 성과 평가에는 일반적으로 **기하 연율화 / CAGR**이 적절. 산술 연율화를 복리 성과로 해석하지 말 것.

---

# 3. 위험조정 · Drawdown 지표

## 3.1 Sharpe Ratio

**🎯 언제·왜 쓰나:** **변동성이 다른 전략들을 표준화**해 비교할 때(기관 업계 표준). "같은 수익이면 덜 덜컹대는 전략"을 고르는 용도. 단, fat-tail·옵션매도 전략에서는 위험을 과소평가하므로 Sortino·MDD로 보완.

**정의:** 초과수익률 ÷ 총변동성.

**공식** ($e_t=r_t-r_{f,t}$)

$$\text{Sharpe}=\frac{\overline{e}}{s_e},\qquad \text{Sharpe}_{\text{annual}}=\sqrt{K}\,\frac{\overline{e}}{s_e}$$

$$s_e=\sqrt{\frac{1}{N-1}\sum_t (e_t-\overline e)^2}\quad(\text{표본표준편차, ddof}=1)$$

**계산 예시:** $r_f=0$, $\overline r=0.0091667,\ s=0.0235327$ → $\sqrt{12}\times0.0091667/0.0235327=1.3494$.

```python
ex = monthly_returns - 0.0
sharpe = np.sqrt(12) * ex.mean() / ex.std(ddof=1)   # 1.3494
```

**단점:** 상방 변동성도 위험으로 처벌. 정규분포 아님·자기상관 있으면 왜곡. Fat-tail(옵션 매도 등)에서 위험을 **과소평가**.
**흔한 실수:** 일간을 무조건 $\sqrt{252}$로 연율화(자기상관 시 과대평가). 연율화 누락.
**임계값 표준 (→ `20_thresholds.md`):** Sharpe는 상방변동성을 처벌해 추세추종에 불리하므로 **단독 탈락 금지(참고·목표 지표)**. 목표선 ≥1.0, 경보 >2.5(검증 필요). 구속 판정은 Sortino·Calmar로 한다. 크립토 일봉은 **√365**로 연율화(√252 혼용 금지).

---

## 3.2 Sortino Ratio

**🎯 언제·왜 쓰나:** **하방 위험 중심**으로 평가하고 싶을 때. 상방 변동성이 큰 추세추종 전략이 Sharpe에서 부당하게 낮게 나올 때, "위로 튀는 건 빼고 아래로 깨질 때만 위험으로" 보아 더 공정하게 평가한다.

**정의:** 초과수익률 ÷ **하방** 변동성. (투자자에게 진짜 문제는 하방 변동성)

**공식** (목표/최소허용수익률 $T$)

$$\sigma_d=\sqrt{\frac{1}{N}\sum_{t=1}^{N}\min(0,\,r_t-T)^2},\qquad \text{Sortino}_{\text{annual}}=\sqrt{K}\,\frac{\overline{r}-T}{\sigma_d}$$

> ⚠️ **핵심 — 분모는 전체 관측 수 $N$으로 나눈다.** `r[r<0].std()`(음수 수익률만의 표준편차)는 **틀린 계산**이며 Sortino를 부풀린다. 본 예시에서 잘못된 방식은 3.39, 올바른 방식은 **2.49**.

**계산 예시:** $T=0$, 하방수익 $[-0.02,-0.01,-0.035,-0.015]$

$$\sigma_d=\sqrt{\frac{0.02^2+0.01^2+0.035^2+0.015^2}{12}}=0.0127475$$
$$\text{Sortino}=\sqrt{12}\times\frac{0.0091667}{0.0127475}=2.4910$$

```python
T = 0.0
downside = np.minimum(monthly_returns - T, 0)
sigma_d = np.sqrt(np.mean(downside**2))          # 0.0127475  (분모 = 전체 N)
sortino = np.sqrt(12) * (monthly_returns.mean() - T) / sigma_d   # 2.4910

# 잘못된 방식 (쓰지 말 것):
# sigma_wrong = monthly_returns[monthly_returns<0].std()   # 0.00935 -> Sortino 3.39 과대평가
```

**주의:** $T$ 설정에 민감. 하방 관측이 적은 짧은 백테스트에서 과대평가. Sharpe보다 항상 우월한 건 아니다.
**임계값 표준 :** **구속 게이트.** 통과선 Sortino < 1.0, 목표선 ≥ 1.5. 분모는 반드시 전체 관측 수 N.

---

## 3.3 Maximum Drawdown (MDD)

**🎯 언제·왜 쓰나:** **포지션 사이징·레버리지 한도**를 결정할 때의 1차 기준. "이 전략을 실행하며 심리적·자금적으로 견뎌야 하는 최악의 고통"을 미리 가늠해, 감당 못 할 전략을 운용 전에 거르는 용도.

**정의:** 누적 최고점 대비 최대 하락률.

**공식**

$$M_t=\max_{s\le t}V_s,\quad DD_t=\frac{V_t}{M_t}-1,\quad \text{MDD}=\min_t DD_t$$

**계산 예시:** 최고점 $108{,}123.91$ → 이후 저점 $104{,}339.57$ → $DD=-3.5\%$.

```python
ec = np.r_[100000, equity]
running_max = np.maximum.accumulate(ec)
drawdown = ec / running_max - 1
mdd = drawdown.min()   # -0.035
```

**흔한 실수:** 단순 $\min(V)/\max(V)-1$ 사용 — **MDD는 반드시 최고점이 먼저, 그 이후 저점**이어야 한다. 종가만 보면 장중 낙폭을 놓침.
**주의:** 백테스트 기간이 길수록 MDD는 커진다. **과거 MDD는 미래 손실의 상한이 아니다** — 미래에 갱신될 수 있다. 포지션 사이징·레버리지 한도의 핵심 기준.
**임계값 표준 (→ `20_thresholds.md`):** 백테스트 MDD **통과선 >30%, 목표선 ≤20%** (실전 감내 45% ÷ 버퍼 1.5). 백테스트값은 하한이므로 **실전 가정 = ×1.5**. MDD<5%+고CAGR은 슬리피지·look-ahead 의심. 통과선 초과 시 신호가 아니라 **risk_per_unit·유닛 한도를 낮춰** 맞춘다.

---

## 3.4 Ulcer Index

**🎯 언제·왜 쓰나:** MDD가 비슷한 두 전략 중 **회복이 빠른 쪽을 가려낼** 때. 장기간 전고점을 회복하지 못하는 횡보·지연형 전략의 취약점을 수치화해, 투자자의 실제 체감 고통을 비교하는 용도.

**정의:** drawdown의 **깊이와 지속성**을 함께 반영(체감 고통).

**공식** (퍼센트포인트 $D_t=100(V_t/M_t-1)$)

$$\text{UI}=\sqrt{\frac{1}{T}\sum_{t=1}^{T}D_t^2}$$

**계산 예시:** $\text{UI}\approx1.3771$ (≈ 1.38%p).

```python
ulcer_index = np.sqrt(np.mean((drawdown*100)**2))   # 1.3771
```

**흔한 실수:** 제곱하지 않고 단순평균. % 대신 금액 낙폭을 넣어 왜곡.
**주의:** MDD가 같아도 회복이 빠른 전략 vs 오래 잠긴 전략을 구분해준다. UI를 분모로 쓰는 **Martin Ratio**와 함께 쓰면 좋다. UI는 낮을수록 좋다.

---

## 3.5 Calmar Ratio / MAR Ratio

**🎯 언제·왜 쓰나:** **낙폭 대비 수익 효율**로 전략을 랭킹할 때(추세추종 CTA가 가장 중시). "최악의 하락 1단위당 연 수익이 얼마인가"로 Sharpe와 다른 각도의 위험조정 성과를 본다. Calmar=최근 36개월, MAR=전체 기간으로 구분해 명시.

**정의/공식** — 둘 다 형태는 동일:

$$\text{Calmar}=\text{MAR}=\frac{\text{CAGR}}{|\text{MDD}|}$$

관례적 차이는 **측정 기간**뿐이다:

$$\text{Calmar}=\frac{\text{최근 36개월 CAGR}}{|\text{최근 36개월 MDD}|},\qquad \text{MAR}=\frac{\text{전체 기간 CAGR}}{|\text{전체 기간 MDD}|}$$

**계산 예시:** $0.112357/0.035=3.2102$ (예시는 1년 전체이므로 둘이 동일).

```python
calmar = cagr / abs(mdd)   # 3.2102
```

**벤치마크 (임계값 표준):** **구속 게이트.** 통과선 Calmar < 0.8, 목표선 ≥ 1.0(우수 ≥2.0). 비정상 고Calmar(얕은 MDD+고CAGR)는 MDD 과소추정·슬리피지 미반영 의심. 추세추종 CTA가 가장 중시.
**주의:** 기간을 명시하지 않고 두 이름을 혼용하지 말 것. 짧은 기간이면 MDD 과소추정 → 과대평가. MDD의 깊이뿐 아니라 **duration**도 함께 본다. 분자·분모 단위(% vs 금액)를 섞지 말 것.

---

## 3.6 Recovery Factor

**🎯 언제·왜 쓰나:** 전략이 과거 최대 구덩이(MDD)를 **몇 번이나 메우고 초과수익**을 냈는지, 즉 회복 탄력성을 볼 때. 금액 단위라 자본 배분 직관에 맞는다. 기간 의존적이므로 반드시 **동일 기간**으로 비교.

**정의:** 순이익 ÷ 최대낙폭. 회복 탄력성.

**공식**

$$\text{RF}_{\$}=\frac{V_T-V_0}{\max_t(M_t-V_t)},\qquad \text{RF}_{\%}=\frac{V_T/V_0-1}{|\text{MDD}|}$$

**계산 예시:** 금액 MDD $=108123.91-104339.57=3784.34$ → $\text{RF}_{\$}=11235.71/3784.34=2.969$. 비율 $\text{RF}_{\%}=11.2357\%/3.5\%=3.2102$.

```python
mdd_dollar = np.max(running_max - ec)
rf_dollar = (ec[-1] - 100000) / mdd_dollar        # 2.969
rf_pct    = (ec[-1]/100000 - 1) / abs(mdd)         # 3.2102
```

**단점:** 시간 미반영 — 기간이 길수록 누적 순이익으로 값이 계속 커짐. **동일 기간**으로만 비교.
**흔한 실수:** 금액 MDD와 비율 수익률을 섞음 — 분자·분모 단위를 통일하라.

---

# 4. 고급 시스템 평가 · 자금 관리

## 4.1 SQN (System Quality Number)

**🎯 언제·왜 쓰나:** 시스템 **품질을 객관적으로 등급화**하고, 성과가 우연이 아닐 **통계적 유의성**(t-통계량 유사)을 검증할 때. 거래 수를 반영하므로, 표본이 충분한지(N≥30)와 함께 전략의 신뢰도를 판단하는 용도.

**정의:** 반 타프(Van Tharp). 거래별 R-multiple 평균 ÷ 표준편차 × $\sqrt N$. t-통계량과 유사.

**공식** ($R_i=x_i/\text{Initial Risk}_i$)

$$\text{SQN}=\frac{\sqrt{N}\,\overline{R}}{s_R},\qquad s_R=\sqrt{\frac{1}{N-1}\sum_i (R_i-\overline R)^2}$$

**계산 예시:** $R=[2,-1,1.5,-0.5,3,-1.2,0.8,2.5,-0.7,1.8]$, $\overline R=0.82,\ s_R=1.5576$ → $\sqrt{10}\times0.82/1.5576=1.6647$.

```python
R = pnl / 100
sqn = np.sqrt(len(R)) * R.mean() / R.std(ddof=1)   # 1.6647
```

**벤치마크 (임계값 표준 → `20_thresholds.md`):** **신뢰도(유의성) 게이트** — SQN은 t-통계량이라 품질이 아니라 "엣지가 우연이 아닌가"를 본다. 통과선 **SQN < 1.6**(단측 ~94.5% 신뢰), 목표선 **≥ 2.0**(~97.7%), 참고 ≥3.0 우수. **√N의 N은 100으로 캡**(min(N,100))해 거래 수 인플레를 막고, 표본 **N<30이면 무효**. 주의: 큰 승자(우측꼬리)가 $s_R$을 키워 좋은 추세추종도 SQN이 낮아질 수 있으니 **단독 탈락 신중**(Expectancy·Calmar 동반).
**흔한 실수:** 금액 P&L로 계산(반드시 **R-multiple**로 변환). 거래 독립성 가정에 민감.

---

## 4.2 Kelly Criterion

**🎯 언제·왜 쓰나:** 기대값이 양수인 전략에서 **베팅 비중의 상한**을 수학적으로 산출할 때. 단, 추정오차·fat-tail 때문에 그대로 쓰면 위험하므로 실제로는 이 값의 **절반/사분의 일을 한도**로 삼는 기준점으로 쓴다.

**정의:** 장기 로그성장률을 최대화하는 최적 베팅 비율.

**공식** ($B$ = Payoff Ratio)

$$f^*=\frac{Bp-q}{B}=p-\frac{q}{B},\qquad f^*=\arg\max_f E[\log(1+fR)]$$

**계산 예시:** $p=0.6,q=0.4,B=2.2745$ → $f^*=0.6-0.4/2.2745=0.4241$ (자본의 약 42.4%).

```python
kelly = win_rate - loss_rate / payoff_ratio   # 0.4241
half_kelly = 0.5 * kelly                       # 0.2121
```

**단점:** 입력 $p,B$ 추정오차에 극도로 민감. Full Kelly는 실전 drawdown이 매우 크고, 최적값을 **초과 베팅하면 파산**으로 수렴.
**철칙:** 실전에서는 **Half-Kelly 또는 Quarter-Kelly**($f_{\text{used}}=\lambda f^*,\ 0<\lambda<1$). 백테스트 추정값을 확정값처럼 쓰지 말 것 — 레버리지·슬리피지·fat-tail·regime change·연속손실을 고려.

---

## 4.3 Risk of Ruin

**🎯 언제·왜 쓰나:** 전략의 **생존성**을 최종 검증하고 **거래당 최대 위험%**를 설정할 때. "기대값이 좋아도 베팅이 크면 파산한다"를 정량화해, 자금 관리 룰이 안전한지(권장 <0.1%) 판정하는 마지막 관문.

**정의:** 현재 전략·베팅 규모를 유지할 때 계좌가 사전 정의된 파산선에 도달할 확률.

**공식** — 단순 $+1R/-1R$ 베르누이 모형:

$$\text{RoR}=\begin{cases}\left(\dfrac{q}{p}\right)^{B}, & p>q\\[4pt] 1, & p\le q\end{cases},\qquad B=\frac{\text{허용 손실 금액}}{\text{거래당 위험 금액}}$$

> 참고: 흔히 보이는 $\left(\frac{1-\text{Edge}}{1+\text{Edge}}\right)^{U}$ 형태는 $\text{Edge}=2p-1$일 때 $\frac{1-\text{Edge}}{1+\text{Edge}}=\frac{q}{p}$이므로 위 식과 **동일**하다.

일반 R-multiple 분포: $\text{RoR}=P\!\left(\min_t V_t\le V_{\text{ruin}}\right)$ — **몬테카를로**로 추정.

**계산 예시:** $p=0.6,q=0.4$, 거래당 위험 1%, 파산선 −20% → $B=20$ → $(0.4/0.6)^{20}=0.000301=0.0301\%$.

```python
p, q, B = 0.6, 0.4, 20
ror = (q/p)**B if p > q else 1.0   # 0.000301

def mc_risk_of_ruin(R, risk=0.01, ruin=0.20, n_trades=500, n_sims=10000, seed=42):
    rng = np.random.default_rng(seed); R = np.asarray(R); ruined = 0
    for _ in range(n_sims):
        eq = 1.0; level = 1.0 - ruin
        for r in rng.choice(R, size=n_trades, replace=True):
            eq *= (1 + risk * r)
            if eq <= level:
                ruined += 1; break
    return ruined / n_sims
```

**단점:** 분포 가정에 매우 민감(IID·정규 가정은 fat-tail·regime change·연쇄폭락을 무시 → 실전보다 낮게 계산).
**흔한 실수:** 승률만으로 계산. 실제 RoR은 최소 $p,\overline W,\overline L,\sigma,f,\text{tail risk}$에 의존.
**기준:** 수용 가능 RoR은 보통 **0.1% 미만**. 단일 숫자를 맹신하지 말고 여러 가정으로 stress test.
**임계값 표준 (→ `20_thresholds.md`):** 수용선 **RoR < 0.1%**, 파산선 **60%**(회복불가선; MDD 감내 45% 운영중단선과 분리). 단순 공식 $(q/p)^B$는 추세추종(p<q)에서 **무조건 RoR=1**을 줘 무효 → **R-multiple 분포 MC 필수**(fat-tail·상관→1 stress). RoR가 사이징을 묶는다 — **1R(2N 손절) ≤ 1%**(risk_per_unit ≤ 0.5%/N).

---

# 5. 지표 간 관계 · 해석적 차이

**Win Rate ↔ Payoff Ratio (시소 관계)**
승률을 올리려면 익절을 짧게 → Payoff↓(평균회귀). 크게 먹으려 버티면 승률 30%↓이지만 Payoff 3.0↑(추세추종). 기대값은 둘의 결합으로 결정된다. 손익분기 승률:

$$p_{\text{BE}}=\frac{1}{1+B}=\frac{1}{1+2.2745}=30.54\%\ (<60\%\ \text{이므로 } E>0)$$

**Profit Factor vs Expectancy**
PF는 **비율**($p\overline W/q\overline L$), Expectancy는 **금액/R 단위**. 관계 $E=q\overline{L}(\text{PF}-1)$. PF 2.0이라도 거래당 \$10 시스템과 \$1000 시스템은 경제적 의미가 전혀 다르다 → 함께 본다.

**Sharpe vs Sortino**
분모가 총변동성 $\sigma$ vs 하방변동성 $\sigma_d$. 상방 변동성이 큰 추세추종은 Sharpe가 억울하게 낮게 나오고 Sortino가 더 공정하다.

**Payoff Ratio vs Reward/Risk**
Payoff = 사후(ex-post) 실현 결과, Reward/Risk = 사전(ex-ante) 설계값. 설계 1:3이 실현 1:1.5로 떨어지는 일이 흔하다.

**Calmar vs MAR**
공식 동일($\text{CAGR}/\text{MDD}$). 차이는 기간(Calmar 최근 36개월, MAR 전체 기간)뿐.

**MDD vs Ulcer Index**
MDD는 최악의 한 점, UI는 전체 drawdown 경로. 둘 다 −20%여도 하루 만에 회복 vs 1년간 잠김이면 UI는 후자가 훨씬 높다.

**Recovery Factor vs Calmar**
RF는 전체기간 회복 효율(금액·시간 미반영), Calmar는 연율화 위험조정 성과.

**SQN vs Sharpe**
SQN은 **거래 단위 R-multiple**(거래 품질), Sharpe는 **시간 단위 수익률**(포트폴리오 성과).

**Kelly vs Risk of Ruin**
Kelly는 성장률 최대화, RoR은 생존 확률. Kelly가 높을수록 기대 성장↑이지만 drawdown·심리부담↑ → 실무는 Fractional Kelly.

---

# 6. 백테스트 공통 실수 체크리스트

1. **비용 전 손익으로 계산** — 반드시 반영:
   $$x_i^{\text{net}}=x_i^{\text{gross}}-\text{commission}-\text{slippage}-\text{tax}-\text{borrow fee}-\text{funding}$$
2. **Look-ahead bias** — 당일 종가 신호로 같은 종가 체결 가정 등 미래정보 사용.
3. **Survivorship bias** — 생존 종목만으로 백테스트 → 상폐 손실 누락 → 과대평가.
4. **단위 혼합** — CAGR(%) / Dollar MDD처럼 비율·금액 혼용.
5. **거래 수 부족** — PF·SQN·Sharpe·Win Rate 모두 불안정(SQN은 N≥30).
6. **과최적화(Curve-fitting)** — 백테스트 구간에서만 작동하는 파라미터. PF>3.0이면 의심.
7. **포지션 크기 혼동** — 고정 수량/금액/위험비율 혼동 시 Net·MDD·CAGR 왜곡.

---

# 7. 실전 해석 순서

1. **수익성:** Net > 0, PF > 1, Expectancy > 0
2. **수익 구조:** $p,q,\overline W,\overline L,$ Payoff
3. **시간 성과:** CAGR, Annual Return
4. **위험조정:** Sharpe, Sortino, Calmar, MAR
5. **경로 위험:** MDD, Ulcer Index, Recovery Factor
6. **운용 가능성:** SQN, Kelly, Risk of Ruin

핵심: 하나의 지표로 판단하지 않고 **Expectancy · PF · CAGR · MDD · Sharpe · RoR**를 함께 보아 수익성·안정성·경로위험·생존성을 동시에 평가한다.

---

# 8. 누락 지표 보강 (전략 구축 시 추가 필수)

성과지표 사전(1~4)은 "평균적으로 좋은가"를 본다. 실전 운용은 "**최악의 순간을 견디는가**"가 핵심이라 다음 지표가 반드시 더 필요하다.

## 8.1 Max Consecutive Losses (최대 연속 손실)

**🎯 언제·왜 쓰나:** 자금 관리와 **심리 설계**의 핵심. 백테스트에서 10연패가 나왔다면 실전에선 12~15연패를 각오해야 한다. Risk of Ruin·베팅 크기 한도와 직결.

$$\text{MCL}=\max\{\text{연속된 손실 거래의 길이}\}$$

```python
def max_consec(mask):
    m = c = 0
    for v in mask:
        c = c + 1 if v else 0
        m = max(m, c)
    return m
mcl = max_consec(pnl < 0)   # 예시: 1 (연속 손실 없음)
mcw = max_consec(pnl > 0)   # 예시: 2
```

**주의:** 백테스트 MCL은 **하한**으로 간주. 한 번의 연속 손실 구간을 견딜 수 있는 자본·심리 버퍼가 없으면 기대값이 양수여도 중도 이탈한다.

## 8.2 Drawdown Duration / Time to Recovery (낙폭 지속·회복 기간)

**🎯 언제·왜 쓰나:** MDD는 "얼마나 깊었나"만, 이것은 "**얼마나 오래 잠겼나**"를 본다. 전고점 회복까지 2년 걸리는 전략은 깊이가 같아도 실전에서 버티기 어렵다.

$$\text{DD Duration}=\max\{\text{연속으로 } V_t<M_t \text{ 인 구간의 길이}\}$$

```python
running_max = np.maximum.accumulate(ec)
underwater = ec < running_max
dd_duration = max_consec(underwater)   # 예시: 4개월
```

**주의:** Calmar·MDD와 함께 본다. "MDD −15% / 회복 3개월" vs "MDD −15% / 회복 18개월"은 완전히 다른 전략이다.

## 8.3 Volatility (연율화 변동성)

**🎯 언제·왜 쓰나:** Sharpe의 분모이자 **변동성 타게팅** 포지션 사이징의 입력값. 목표 변동성(예: 연 10%)에 맞춰 레버리지를 역산할 때 쓴다.

$$\sigma_{\text{annual}}=\sigma_{\text{period}}\sqrt{K}$$

```python
ann_vol = monthly_returns.std(ddof=1) * np.sqrt(12)   # 예시: 0.0815 (8.15%)
```

## 8.4 VaR / CVaR (꼬리 위험)

**🎯 언제·왜 쓰나:** "정상 범위 최악 손실"(VaR)과 "그 선을 넘었을 때 평균 손실"(CVaR=Expected Shortfall)을 본다. **익스포저 한도·일일 손실 한도** 설정의 근거.

$$\text{VaR}_\alpha=-Q_{1-\alpha}(r),\qquad \text{CVaR}_\alpha=-\,\mathbb{E}[\,r\mid r\le Q_{1-\alpha}(r)\,]$$

```python
a = 0.95
q = np.percentile(monthly_returns, (1-a)*100)
var95  = -q                                          # 예시: 0.0267 (2.67%)
cvar95 = -monthly_returns[monthly_returns <= q].mean()  # 예시: 0.035 (3.5%)
```

**주의:** 역사적 VaR은 과거에 없던 사건을 못 잡는다. CVaR이 항상 VaR보다 크며(꼬리), fat-tail 시장에선 CVaR을 더 신뢰.

## 8.5 Exposure / Turnover / 평균 보유기간

**🎯 언제·왜 쓰나:** **자본 효율과 비용**을 본다. 시장에 노출된 시간(Exposure)이 짧은데 수익이 같다면 자본 효율이 높다. Turnover가 높으면 수수료·슬리피지가 성과를 갉아먹으므로 비용 모델(10절)과 직결.

$$\text{Exposure}=\frac{\text{포지션 보유 기간}}{\text{전체 기간}},\quad \text{Turnover}=\frac{\sum|\Delta \text{포지션}|}{\text{평균 자본}}$$

**주의:** 회전율이 높은 전략은 백테스트 수익이 좋아도 실거래 비용 반영 후 음수가 되기 쉽다.

## 8.6 Gain-to-Pain / Tail Ratio (보조 지표)

**🎯 언제·왜 쓰나:** 분포의 비대칭을 빠르게 본다. Gain-to-Pain(= 총수익 / 총손실 절대값, 월 기준)은 Jack Schwager가 즐겨 쓰며 1.0 이상이면 양호. Tail Ratio는 상위 5% 이익 대 하위 5% 손실의 크기 비.

```python
gain_to_pain = monthly_returns.sum() / abs(monthly_returns[monthly_returns<0].sum())  # 1.375
tail_ratio   = abs(np.percentile(monthly_returns,95)) / abs(np.percentile(monthly_returns,5))  # 1.29
```

---

# 9. 전략 검증 방법론 (과최적화 방어 — 가장 중요)

지표값이 좋은 것과 **그 값이 우연·과최적화가 아닌 것**은 다르다. 백테스트-실전 괴리의 최대 원인이 여기 있다.

## 9.1 In-Sample / Out-of-Sample 분리

데이터를 학습(IS)·검증(OOS)으로 나눠, 파라미터는 IS에서만 정하고 성과는 **건드리지 않은 OOS**에서 측정한다. OOS 성과가 IS 대비 급락하면 과최적화.

$$\text{Degradation}=1-\frac{\text{OOS 성과}}{\text{IS 성과}}\quad(\text{보통 }>50\%\text{면 위험})$$

## 9.2 Walk-Forward Analysis

IS→OOS 창을 시간순으로 굴려가며 반복(예: 12개월 학습 → 3개월 검증 → 3개월 전진). 여러 OOS 구간을 이어 붙인 곡선이 실전에 가장 근접한 추정치다. **정기 재최적화 주기를 정하는 근거**가 된다.

## 9.3 몬테카를로 시뮬레이션

거래 순서를 무작위로 섞거나(복원추출) 부트스트랩해 **수천 개의 가상 자산곡선**을 만든다. 단일 백테스트의 MDD·CAGR이 운에 얼마나 좌우되는지, 그 분포의 5/95 백분위를 본다(Risk of Ruin 4.3의 MC 코드와 동일 원리).

```python
def mc_paths(R, n_trades=None, n_sims=5000, seed=42):
    rng = np.random.default_rng(seed); R = np.asarray(R)
    n = n_trades or len(R); mdds = []
    for _ in range(n_sims):
        eq = np.cumprod(1 + rng.choice(R, size=n, replace=True))
        rmx = np.maximum.accumulate(eq); mdds.append((eq/rmx - 1).min())
    return np.percentile(mdds, [5,50,95])   # 최악 5% MDD까지 확인
```

## 9.4 파라미터 민감도 (Robustness)

최적 파라미터 한 칸 옆도 성과가 유지돼야 진짜다. 파라미터 평면을 히트맵으로 그렸을 때 **고원(plateau)** 위에 있어야 하고, 뾰족한 봉우리(spike) 하나면 과최적화다.

## 9.5 Deflated / Probabilistic Sharpe Ratio (다중검정 보정)

**🎯 왜 필요한가:** 백테스트를 수백 개 돌리면 그중 하나는 **순전히 운으로** Sharpe 2.0이 나온다(데이터 스누핑). 시도 횟수를 보정하지 않은 Sharpe는 신뢰할 수 없다.

**Probabilistic Sharpe Ratio** — 관측 Sharpe $\widehat{SR}$가 기준 $SR^*$를 진짜로 초과할 확률(왜도 $\gamma_3$·첨도 $\gamma_4$ 반영):

$$\text{PSR}(SR^*)=\Phi\!\left(\frac{(\widehat{SR}-SR^*)\sqrt{N-1}}{\sqrt{1-\gamma_3 \widehat{SR}+\frac{\gamma_4-1}{4}\widehat{SR}^2}}\right)$$

**Deflated Sharpe Ratio**는 위 $SR^*$를 "시도 횟수 $M$개 중 우연히 나올 기대 최대 Sharpe"로 설정해 다중검정을 보정한다.

```python
import math
r = monthly_returns; n = len(r)
sr = r.mean()/r.std(ddof=1)                 # 0.3895 (월간)
s = r.std(ddof=0); z=(r-r.mean())/s
skew = np.mean(z**3); kurt = np.mean(z**4)  # -0.568, 2.062
denom = math.sqrt(1 - skew*sr + ((kurt-1)/4)*sr**2)
psr = 0.5*(1+math.erf((sr*math.sqrt(n-1)/denom)/math.sqrt(2)))
print(psr)   # 0.875  -> SR>0일 확률 87.5% (N=12로 낮음, 표본 부족)
```

**주의:** PSR이 0.95 미만이면 표본이 부족하거나 우위가 약한 것. 거래/관측 수가 적을수록 PSR은 낮아진다 — **N을 늘리거나 전략을 보류**.

## 9.6 최소 거래 수 / 신뢰구간

지표는 점추정일 뿐 신뢰구간이 있다. SQN은 N≥30, Sharpe·Win Rate도 거래 수가 적으면 ±폭이 크다. 부트스트랩으로 각 지표의 95% 신뢰구간을 함께 보고하라.

---

# 10. 비용·체결 모델 (암호화폐 특화)

백테스트가 "이론가 즉시 전량 체결"을 가정하면 실전과 크게 어긋난다. 거래별 손익은 반드시 다음을 반영한다(2.1·6절 보강).

## 10.1 수수료 (Maker / Taker)

지정가(maker)와 시장가(taker) 수수료가 다르다. 회전율 높은 전략은 taker 수수료만으로 우위가 사라질 수 있다.

$$x_i^{\text{net}}=x_i^{\text{gross}} - \text{fee}_{\text{entry}} - \text{fee}_{\text{exit}},\quad \text{fee}=\text{notional}\times\text{fee rate}$$

## 10.2 슬리피지 · 시장 충격

체결가가 신호가와 벌어지는 정도. 주문 크기가 호가창 깊이 대비 크면 **시장 충격**으로 더 나빠진다.

$$\text{slippage}\approx \underbrace{\text{spread}/2}_{\text{기본}} + \underbrace{k\cdot\frac{\text{주문량}}{\text{호가 유동성}}}_{\text{시장 충격}}$$

**점검:** 백테스트에 보수적 슬리피지(예: 왕복 0.1~0.3%)를 넣어도 전략이 살아남는지 스트레스 테스트.

## 10.3 펀딩비 (무기한 선물)

무기한 선물은 8시간마다 펀딩비를 주고받는다. 포지션 방향·보유시간에 따라 **누적되면 성과를 좌우**한다.

$$\text{funding}_i = \text{notional}\times \text{funding rate}\times \frac{\text{보유시간}}{8\text{h}}$$

**주의:** 롱 편향 전략이 펀딩비 양(+) 구간에 오래 머물면 지속적 비용. 펀딩비 차익 자체를 전략화하기도 한다.

## 10.4 청산 (Liquidation)

레버리지 포지션은 손절 전에 **청산가**에 닿으면 강제 청산되고 수수료·슬리피지가 가중된다. 백테스트의 손절 가정이 청산가보다 멀면 비현실적.

$$\text{청산가}_{\text{long}}\approx \text{Entry}\times\!\left(1-\frac{1}{\text{leverage}}+\text{maintenance margin}\right)$$

## 10.5 거래소 차이 · 레이턴시 · 부분체결

- **거래소 간 가격·유동성·수수료 차이** — 한 거래소 데이터로 백테스트하고 다른 곳에서 실행하면 괴리.
- **레이턴시** — 신호~주문~체결 지연. 고빈도일수록 치명적.
- **부분체결** — 원하는 수량이 다 안 채워짐. 유동성 얕은 알트코인에서 빈번.
- **거래소 다운타임 / API 장애** — 청산 못 하는 리스크. 백테스트엔 안 잡힘.

**핵심 원칙:** 비용·체결 가정은 항상 **보수적으로**. "비용 0 가정에서만 수익"인 전략은 실전에서 손실이다.

---

# 부록. 전체 재현 코드

```python
import numpy as np

# ---- 1. 거래 단위 ----
pnl = np.array([200,-100,150,-50,300,-120,80,250,-70,180], dtype=float)
N = len(pnl); wins = pnl[pnl>0]; losses = pnl[pnl<0]
win_rate = len(wins)/N; loss_rate = len(losses)/N
avg_win = wins.mean(); avg_loss = -losses.mean()
gross_profit = wins.sum(); gross_loss = -losses.sum(); net_profit = pnl.sum()
payoff_ratio = avg_win/avg_loss
expectancy = win_rate*avg_win - loss_rate*avg_loss
expectancy_per_trade = net_profit/N
profit_factor = gross_profit/gross_loss
R = pnl/100
reward_risk_realized = R[R>0].mean()/abs(R[R<0].mean())
sqn = np.sqrt(N)*R.mean()/R.std(ddof=1)
kelly = win_rate - loss_rate/payoff_ratio
ror_simple = (loss_rate/win_rate)**20 if win_rate>loss_rate else 1.0

# ---- 2. 수익률 단위 ----
mr = np.array([0.03,-0.02,0.015,0.04,-0.01,0.025,-0.035,0.02,0.01,-0.015,0.03,0.02])
ic = 100_000
equity = ic*np.cumprod(1+mr); ec = np.r_[ic, equity]
total_return = ec[-1]/ic - 1
years = len(mr)/12
cagr = (ec[-1]/ic)**(1/years) - 1
ann_arith = mr.mean()*12
ann_geo = np.prod(1+mr)**(12/len(mr)) - 1
sharpe = np.sqrt(12)*mr.mean()/mr.std(ddof=1)
downside = np.minimum(mr, 0)
sigma_d = np.sqrt(np.mean(downside**2))          # 분모 = 전체 N (중요)
sortino = np.sqrt(12)*mr.mean()/sigma_d
running_max = np.maximum.accumulate(ec)
drawdown = ec/running_max - 1
mdd = drawdown.min()
calmar = cagr/abs(mdd); mar = calmar
ulcer_index = np.sqrt(np.mean((drawdown*100)**2))
mdd_dollar = np.max(running_max - ec)
recovery_dollar = (ec[-1]-ic)/mdd_dollar
recovery_pct = total_return/abs(mdd)

for k,v in {
 "Win Rate":win_rate,"Loss Rate":loss_rate,"Avg Win":avg_win,"Avg Loss":avg_loss,
 "Payoff":payoff_ratio,"Reward/Risk(realized)":reward_risk_realized,
 "Expectancy":expectancy,"Exp/Trade":expectancy_per_trade,
 "Gross Profit":gross_profit,"Gross Loss":gross_loss,"Net Profit":net_profit,
 "Profit Factor":profit_factor,"SQN":sqn,"Kelly":kelly,"RoR(simple)":ror_simple,
 "Total Return":total_return,"CAGR":cagr,"Ann(arith)":ann_arith,"Ann(geo)":ann_geo,
 "Sharpe":sharpe,"Sortino":sortino,"MDD":mdd,"Calmar":calmar,"MAR":mar,
 "Ulcer":ulcer_index,"Recovery($)":recovery_dollar,"Recovery(%)":recovery_pct,
}.items():
    print(f"{k:24s}: {v:.6f}")
```

**검증된 출력값 (요약)**

| 지표 | 값 | 지표 | 값 |
|---|---|---|---|
| Win Rate | 0.60 | CAGR | 11.2357% |
| Payoff Ratio | 2.2745 | Sharpe | 1.3494 |
| Expectancy | 82.0 | **Sortino (정답)** | **2.4910** |
| Profit Factor | 3.4118 | MDD | −3.50% |
| SQN | 1.6647 | Calmar / MAR | 3.2102 |
| Kelly | 0.4241 | Ulcer Index | 1.3771 |
| RoR (B=20) | 0.0301% | Recovery Factor | 2.969 ($) / 3.2102 (%) |
