# 캔들스틱 패턴 판정 명세서

> **범위**: TA-Lib이 `CDL` 접두사로 제공하는 캔들스틱 패턴 61종의 **판정 방법**을 플랫폼
> 독립적으로 기술한다. 판정 규칙은 원저자 정의에서 가져왔고, TA-Lib의 함수 목록은 무엇을
> 구현할지 정하는 데만 쓰였다. TA-Lib은 값을 맞대어 보는 대조군이며 계산식의 원천이 아니다.
> **기존 지표 표준과의 관계**: 이 문서는 `technical_indicators_calc_spec.md`(89종)와 **나란히
> 서는 별개의 표준**이다. 그 89라는 집계에 더하지 않으며 그 문서에 절을 덧붙이지도 않는다.
> 패턴은 자체 레지스트리를 가지며 `DEFAULT_REGISTRY`에 등록되지 않는다.
> **표기 규약**: `O`=시가, `H`=고가, `L`=저가, `C`=종가. 아래첨자 `t`=현재 봉, `t-1`=직전 봉.
> 패턴이 `k`봉을 걸칠 때 **첫날**은 가장 이른 봉이고 **마지막 날**은 판정이 실리는 봉이다.

---

## §0. 이 표준이 소유하는 것과 소유하지 않는 것

**소유하는 것.** 61종 각각의 판정 규칙, 그 규칙이 쓰는 캔들 파생량과 척도의 정의, 직전
추세의 판정식, 부등식과 경계의 규약, 출력 네 키의 계약, 패턴별 `min_history`다.

**소유하지 않는 것.** 패턴을 어느 패키지에 두는지, 레지스트리를 어떻게 배선하는지, 상태
객체를 어떤 자료구조로 만드는지는 구조 설계의 몫이며 `docs/candlestick-patterns/analysis-2-corelib-structure.md`가
다룬다. 전략이 패턴을 어떻게 쓰는지도 이 표준 밖이다.

### 0.1 원전과 판

판정 규칙의 출처는 세 편이며 **모두 초판이 아니다.** 인용을 다시 확인할 때 이 사실이
중요하다.

| 기호 | 저작 | 판 |
|---|---|---|
| `[N]` | Steve Nison, *Japanese Candlestick Charting Techniques* | 2판(2001) |
| `[M]` | Gregory L. Morris, *Candlestick Charting Explained* | 3판(2006) |
| `[Ch]` | Daniel L. Chesler, "Trading False Moves with the Hikkake Pattern", *Active Trader* | 2004년 4월호 |

Nison의 *Beyond Candlesticks*(1994)는 구하지 못했고 근거로 삼은 항목이 하나도 없다.
Nison 2판 본문은 스캔 문자인식 결과이므로 **어떤 낱말이 나온다는 것은 강한 증거지만 나오지
않는다는 것은 약한 증거다.** 아래에서 "Nison에 없다"고 적은 것은 "읽은 2판 본문에서 찾지
못했다"는 뜻이다.

### 0.2 원전이 비운 자리를 우리가 채웠다는 사실과 그 표시

원전은 "긴 실체", "거의 같은 종가", "아주 짧은 그림자" 같은 정성적 표현을 자주 쓰고 숫자를
주지 않는다. 값을 비워 두면 패턴을 구현할 수 없으므로 **이 표준이 값을 정한다.** 다만 그
값이 원저자의 정의인 것처럼 읽히면 표준이 소유권을 잃으므로, 자리마다 다음 표시를 붙인다.

- **【원전】** — 원전이 그 숫자를 직접 준 자리다. 인용 위치를 함께 적는다.
- **【우리 규약】** — 원전이 비운 자리를 이 표준이 채운 것이다. **원저자의 정의가 아니다.**
  왜 그 값인지 근거를 반드시 함께 적는다.
- **【우리 규약·유도】** — 원전의 다른 서술에서 논리적으로 따라 나오는 값이다. 원전이 그
  숫자를 직접 적지는 않았으므로 역시 우리 규약이지만, 근거가 원전 안에 있다.

TA-Lib은 `BodyLong`, `BodyShort`, `Near`, `Far`, `Equal` 등 열한 개의 자체 임계표를 갖고
있으나 **이 표준은 그것을 승계하지 않는다.** 값이 우연히 비슷해지더라도 그것은 우리가 근거를
대고 고른 결과이지 TA-Lib에서 가져온 것이 아니다.

### 0.3 사용자가 확정한 전제

이 표준은 아래를 전제로 쓰였고 본문에서 다시 열지 않는다. 전문은
`docs/candlestick-patterns/README.md`에 있다.

| 결정 | 내용 |
|---|---|
| A | 원전에 수치가 있으면 그대로 쓴다. 비운 자리는 우리가 정하되 **우리 규약임을 명시**한다 |
| B | 직전 추세는 패턴이 직접 판정한다. **10기간 지수이동평균**과 **패턴 첫날 범위의 중간값** 비교다 |
| C | 충돌하면 좁고 엄격한 쪽이다. Morris 안에서는 규칙 절이 규범이고 유연성 절은 주석이다 |
| D | 갭 정의를 바꾸지 않는다. 실체 사이의 갭은 실체 사이의 갭으로 둔다 |
| F | 출력은 **성립·방향·강도·확인** 네 키다 |
| G | 패턴 이름은 지표 이름과 겹치지 않는다 |

---

## §1. 공유 캔들 프리미티브 (Shared Candle Primitives)

이 계층은 이후 모든 패턴이 재사용한다. 패턴 본문에서 `Body_t`, `US_t`, `LS_t`, `Range_t`
등으로 호출한다. 기존 지표 표준 §0이 하는 일과 같은 자리다.

### 1.1 기본 파생량

| 이름 | 기호 | 공식 |
|---|---|---|
| 실체 크기 (real body) | `Body_t` | `abs(C_t − O_t)` |
| 실체 상단 | `BodyTop_t` | `max(O_t, C_t)` |
| 실체 하단 | `BodyBot_t` | `min(O_t, C_t)` |
| 실체 중간점 | `BodyMid_t` | `(O_t + C_t) / 2` |
| 위그림자 (upper shadow) | `US_t` | `H_t − BodyTop_t` |
| 아래그림자 (lower shadow) | `LS_t` | `BodyBot_t − L_t` |
| 고저 범위 | `Range_t` | `H_t − L_t` |
| 범위 중간값 | `RangeMid_t` | `(H_t + L_t) / 2` |

항등식 하나가 뒤의 유도에 쓰인다. `Range_t = US_t + Body_t + LS_t`이며 세 항이 모두
0 이상이다.

### 1.2 색

| 이름 | 기호 | 정의 |
|---|---|---|
| 양봉 (white) | `White_t` | `C_t > O_t` |
| 음봉 (black) | `Black_t` | `C_t < O_t` |
| 무색 | — | `C_t = O_t`. 양봉도 음봉도 아니다 |

**`C_t = O_t`인 봉은 양봉도 음봉도 아니다.** 색을 요구하는 규칙은 그 봉에서 성립하지 않는다.
다만 색을 묻지 않고 도지만 요구하는 규칙(도지 계열, 별의 가운데 봉)은 그대로 성립한다.
이 구분이 §2.7의 퇴화 봉 규약과 맞물린다.

### 1.3 갭

결정 D에 따라 원전이 정한 갭의 종류를 바꾸지 않는다. 이 표준이 쓰는 갭은 셋이며 서로 다른
것이다.

| 이름 | 기호 | 정의 |
|---|---|---|
| 실체 상방 갭 | `GapUpBody(t-1, t)` | `BodyBot_t > BodyTop_{t-1}` |
| 실체 하방 갭 | `GapDnBody(t-1, t)` | `BodyTop_t < BodyBot_{t-1}` |
| 고저 상방 갭 | `GapUpRange(t-1, t)` | `L_t > H_{t-1}` |
| 고저 하방 갭 | `GapDnRange(t-1, t)` | `H_t < L_{t-1}` |
| 단순 시가 상방 갭 | `GapUpOpen(t-1, t)` | `O_t > C_{t-1}` |
| 단순 시가 하방 갭 | `GapDnOpen(t-1, t)` | `O_t < C_{t-1}` |

세 종류를 패턴마다 어느 것으로 읽는지는 §7의 각 절이 원전 인용과 함께 밝힌다. 원문이 갭의
종류를 구분하지 않은 다섯 패턴의 처리는 §2.8에 있다.

> **대상 시장에 대한 메모.** 이 표준의 대상은 24시간 무기한 선물이므로 시가가 직전 종가와
> 사실상 같고, 갭을 요구하는 패턴의 발생 빈도가 일간 주식 자료보다 크게 낮다. 결정 D는 그
> 낮은 빈도를 받아들이기로 했다. 정의를 느슨하게 바꿔 빈도를 올리지 않는다. 실제 빈도는
> 구현 뒤 자료로 재어 보고한다.

### 1.4 나눗셈과 정의역 공통 규약

기존 지표 표준 §0.11이 같은 일을 하는 자리다. **패턴 판정에서 0으로 나누는 자리는 모두
아래 규약으로 닫으며, 패턴 본문에서 다시 정하지 않는다.**

- **`Range_t = 0`인 봉** (네 값이 모두 같은 봉). 고저 범위를 분모로 쓰는 모든 비율이
  정의되지 않는다. **그 봉이 관여하는 모든 패턴은 판정 결과 불성립(0.0)이며 NaN이 아니다.**
  판정을 수행했고 성립하지 않았다는 뜻이다. 근거는 §2.7에 적었다.
- **`Body_t = 0`인 봉** (시가와 종가가 같은 봉). 실체를 분모로 쓰는 그림자 배수가 정의되지
  않는다. **그림자와 실체의 비를 다음과 같이 확장해 정의하고, 비교의 방향에 따라 결과가
  갈린다.**

  ```
  ShadowRatio(shadow, Body) = shadow / Body                 (Body > 0)
                            = +∞                            (Body = 0 이고 shadow > 0)
                            = 정의되지 않음                  (Body = 0 이고 shadow = 0)
  ```

  - **하한 비교** `shadow ≥ m · Body`는 `ShadowRatio ≥ m`으로 읽는다. `Body = 0`이고
    그림자가 양수이면 **참**이고, 그림자도 0이면 **거짓**이다.
  - **상한 비교** `shadow ≤ m · Body`는 `ShadowRatio ≤ m`으로 읽는다. `Body = 0`이고
    그림자가 양수이면 **거짓**이고, 그림자도 0이면 **거짓**이다.

  **두 방향을 가르는 까닭은 하한 쪽 규약의 의도가 상한에 그대로 옮겨지지 않기 때문이다.**
  하한 쪽은 실체가 0인 잠자리형 도지가 Takuri와 Hammer의 모양 요건을 통과하게 하려고 둔
  것인데, 같은 문장을 상한에 그대로 쓰면 "그림자가 아무리 길어도 상한을 만족한다"는 뜻이 되어
  상한이 상한 노릇을 하지 못한다. 비를 무한대로 확장해 읽으면 두 방향이 자연히 갈린다.
  근거는 §2.7에 적었다.

  **현재 §7의 어느 패턴도 상한 형태를 쓰지 않는다.** §2.4가 밝히듯 상한을 쓰던 유일한 자리인
  Inverted Hammer가 그 조건을 경향으로 내렸기 때문이다. 이 정의는 규칙의 완결성을 위해 남긴다.
- **NaN 전파.** 워밍업 구간은 NaN을 유지한다. 0으로 대체하지 않는다. **0.0과 NaN의 구분은
  §5.3의 계약이며 이 표준 전체에서 지켜진다.**
- **실시간과 배치.** 재귀형(§3의 지수이동평균)은 확정된 직전값만 쓴다. **미확정(진행 중) 봉으로
  상태를 갱신하지 않는다.** 프로젝트 규약 `close_time ≤ T`를 따른다.

---

## §2. 척도 (Scales)

결정 A가 적용되는 자리다. 원전이 정성적으로만 적은 표현을 여기서 숫자로 닫는다. **척도는
일곱이고 §7의 모든 패턴이 이 일곱만 참조한다.** 패턴 절에서 새 척도를 만들지 않는다.

**분모를 하나로 통일한 이유를 먼저 적는다.** Morris는 6장에서 긴 날을 재는 세 방법(가격 수준
대비, 그 봉의 고저 범위 대비, 최근 N봉 평균 대비)을 나란히 주고 하나로 정하지 않았다. 이
표준은 **그 봉의 고저 범위를 분모로 삼는 방법**을 고른다. 근거는 셋이다. 첫째, 종목과 가격
수준에 무관하므로 심볼마다 값을 달리 잡을 필요가 없다. 둘째, **과거 봉을 참조하지 않으므로
척도 때문에 생기는 워밍업이 0이다.** 이 성질이 §6의 `min_history`를 단순하게 만들고,
"평균이 그 봉 자신을 포함하는가"라는 한 봉 어긋남의 위험을 아예 없앤다. 셋째, Morris가 여러
패턴의 유연성 절에서 되풀이한 구체적 수치가 이 분모를 쓴다. **【우리 규약】** — 분모의 선택은
우리 것이다. Morris는 세 방법을 모두 허용했을 뿐 하나를 고르지 않았다.

### 2.1 긴 실체 (Long Body)

```
LongBody(t)  ⇔  Body_t > 0.50 · Range_t
```

**【원전】** Morris는 여러 패턴의 `Pattern Flexibility`에서 "A long body is a body that
occupies more than 50% of the high-low range"라고 되풀이해 적는다. 번역하면 긴 실체는 고저
범위의 50퍼센트를 넘게 차지하는 실체다.

> 결정 C는 Morris 안에서 규칙 절이 규범이고 유연성 절은 주석이라고 정했다. 그것은 **한 패턴의
> 판정 규칙**이 두 절에서 어긋날 때의 규칙이다. 여기서 인용한 것은 특정 패턴의 판정 규칙이
> 아니라 Morris가 책 전체에서 되풀이한 **용어의 정의**이므로 그 우선순위 규칙의 대상이
> 아니다. 이 구분을 흐리지 않기 위해 밝혀 둔다.

부등식은 **엄격**하다. 원문이 "more than"이다.

### 2.2 짧은 실체 (Short Body)

```
ShortBody(t)  ⇔  Body_t < (1/3) · Range_t
```

**【우리 규약·유도】** 원전은 짧은 실체에 숫자를 주지 않는다. Morris 6장은 "짧은 날은 긴 날과
같은 방법에 최소 퍼센트 대신 최대 퍼센트를 쓴다"고 형식만 준다. 값은 **Morris 자신의 Spinning
Top 규칙에서 유도한다.** 그는 팽이형을 "small real bodies with upper and lower shadows that
are of greater length than the body's length", 곧 위아래 그림자가 **모두** 실체보다 긴 캔들로
정의한다. §1.1의 항등식 `Range = US + Body + LS`에 `US > Body`와 `LS > Body`를 넣으면
`Range > 3 · Body`, 곧 `Body < Range / 3`이 따라 나온다. **곧 Morris가 "작은 실체"라고 부르는
영역의 상한이 고저 범위의 3분의 1이다.**

이 값을 고르면 결과가 하나 더 맞아떨어진다. Morris 2장은 "There are also numerous days that
do not fall into any of these two categories", 곧 긴 날에도 짧은 날에도 들지 않는 날이 많다고
적는다. 긴 실체를 50퍼센트 초과로, 짧은 실체를 33.3퍼센트 미만으로 두면 그 사이의 띠가 어느
쪽도 아닌 영역이 되어 그 서술과 어긋나지 않는다. 긴 실체의 여집합을 짧은 실체로 삼았다면 그
서술과 충돌했을 것이다.

부등식은 **엄격**하다. 유도의 출발점인 팽이형 규칙이 "greater than"이기 때문이다.

### 2.3 도지 (Doji)

```
Doji(t)  ⇔  Body_t ≤ 0.03 · Range_t
```

**【원전 형식·우리 규약 값】** Morris 6장은 형식과 권장 범위를 함께 준다. "Doji Body / High to
Low Range − Maximum (0 to 100%)"이라는 형식을 세우고 "A value in the neighborhood of 1 to 3%
seems to work quite well", 곧 1에서 3퍼센트 정도가 꽤 잘 듣는다고 적는다. **형식은 원전에서
그대로 가져왔고, 그 범위 안에서 3퍼센트를 고른 것이 우리 규약이다.**

범위의 위쪽 끝을 고른 근거는 대상 시장이다. 24시간 무기한 선물은 시가와 종가가 정확히 같은
봉이 드물고 짧은 주기일수록 고저 범위가 좁아 비율이 커진다. 범위의 아래쪽 끝인 1퍼센트를
고르면 도지를 요구하는 12종이 실질적으로 성립하지 않는다. **저자가 스스로 잘 듣는다고 밝힌
범위를 벗어나지 않으면서 대상 시장에서 신호가 나오는 값이 3퍼센트다.**

Morris 2장이 말한 다른 기준, 곧 "시가와 종가의 차이가 몇 틱 안이면 충분하다"는 종목마다
호가 단위를 알아야 하고 심볼별로 결과가 달라지므로 채택하지 않는다. 주석으로만 남긴다.

부등식은 **등호를 허용한다.** 원문이 "Maximum"이다.

### 2.4 긴 그림자 (Long Shadow)

```
LongUpperShadow(t)  ⇔  US_t ≥ 2.0 · Body_t
LongLowerShadow(t)  ⇔  LS_t ≥ 2.0 · Body_t
```

**【원전】** 이 자리는 원전이 숫자를 주었다. Nison 4장은 Hammer의 아래그림자를 "at least twice
the height of the real body", 곧 실체 높이의 최소 두 배로 적는다. Morris 3장의 Hammer 해설도
"the lower shadow of a Hammer is a minimum of only twice the length of the body"라고 적어
같다. **분모가 실체인 것도 원전 그대로다.** 이 자리만은 §2 앞머리에서 고른 고저 범위 분모를
쓰지 않는데, 원전이 실체를 분모로 못박았기 때문이다.

배수가 2가 아닌 자리가 둘 있고 모두 원전이 그 값을 준다. Takuri는 아래그림자가 실체의 **세
배 이상**이고(Morris 3장, "at least three times the length of the body"), Shooting Star는
위그림자가 실체의 **세 배 이상**이다(Morris 3장). 이 배수들은 §7의 해당 절에 그대로 적었고
여기서 다시 정하지 않는다.

Morris는 Inverted Hammer의 위그림자에 "usually no more than two times"라는 **상한**도 적지만,
§7.1.9가 밝히듯 "usually"를 경향으로 읽어 요건에서 뺐다. **그 결과 §7의 어느 패턴도 상한
형태를 쓰지 않는다.** §1.4가 상한 방향을 정의해 두는 것은 규칙의 완결성을 위한 것이며, 앞으로
상한을 쓰는 패턴이 더해지면 그 정의가 그대로 적용된다.

`Body_t = 0`인 봉의 처리는 §1.4와 §2.7에 있다. 부등식은 **등호를 허용한다.** 원문이
"at least"다.

### 2.5 매우 짧은 그림자 (Very Short Shadow)

```
NoUpperShadow(t)  ⇔  US_t ≤ 0.10 · Range_t
NoLowerShadow(t)  ⇔  LS_t ≤ 0.10 · Range_t
```

**【원전 형식·우리 규약 값】** 원전은 "없거나 매우 짧은 그림자"에 숫자를 주지 않는다. Morris
6장은 형식과 예시값을 준다. "Umbrella Upper Shadow / High to Low Range (0 to 100%)"라는
형식을 세우고 "A value of 10 means that the upper shadow is only 10% (or less) of the high-low
range", 곧 값 10은 위그림자가 고저 범위의 10퍼센트 이하라는 뜻이라고 적는다. **형식과 예시값을
그대로 가져왔으나, Morris가 그것을 예시로만 제시했으므로 값의 채택은 우리 규약이다.**

10퍼센트를 그대로 쓴 근거는 둘이다. 첫째, 저자가 스스로 든 유일한 구체 값이고 다른 값을
고를 근거가 원전 안에 없다. 둘째, §2.2의 짧은 실체 상한(33.3퍼센트)보다 뚜렷하게 작아
"그림자가 거의 없다"는 원전의 어감과 어긋나지 않는다.

**"고가에 또는 고가 가까이 마감한다"는 원전 표현은 이 척도로 옮긴다.** 종가가 고가 가까이
있다는 것은 위그림자가 매우 짧다는 것과 같은 말이기 때문이다. 별도의 척도를 만들지 않는다.

부등식은 **등호를 허용한다.** 원문이 "or less"다.

### 2.6 "같다"와 "가깝다"

두 표현은 원전에서 서로 다른 낱말이고 이 표준도 갈라 정의한다.

```
Equal(x, y, t)  ⇔  abs(x − y) ≤ 0.03 · Range_t
Near(x, y, t)   ⇔  abs(x − y) ≤ 0.10 · Range_t
SimilarBody(a, b) ⇔ min(Body_a, Body_b) ≥ 0.50 · max(Body_a, Body_b)
```

**`Equal` — 【원전 지시·우리 규약 값】.** Morris 6장은 값이 같아야 하는 자리를 따로 다루며
"The same concept used in determining a Doji day can be used here as well", 곧 도지 날을
정할 때 쓴 개념을 여기에도 쓸 수 있다고 **명시적으로 지시한다.** 그 지시를 그대로 따라
§2.3의 도지 허용오차와 같은 값을 쓴다. `Range_t`는 두 값 가운데 뒤에 오는 봉의 고저 범위다.

Morris가 Matching High 항목에서 쓴 더 좁은 기준, 곧 "두 종가는 둘째 날 종가가 첫날 종가의
1/1000 안이면 같다고 본다"는 채택하지 않고 주석으로 남긴다. 그 값을 모든 "같다"에 적용하면
Separating Lines, Matching Low, Stick Sandwich, Identical Three Crows가 실질적으로 성립하지
않으며, Morris 자신이 6장에서 도지 개념을 쓰라고 지시한 것과도 어긋난다.

**`Near` — 【우리 규약】.** "가까이 열린다", "한가운데에 있다" 같은 표현에는 **어느 원전도
숫자를 주지 않는다.** §2.5의 매우 짧은 그림자와 같은 10퍼센트를 쓴다. 근거는 두 표현이
원전에서 같은 뜻으로 쓰인다는 점이다. "종가가 고가 가까이 있다"와 "위그림자가 매우 짧다"가
같은 사태를 가리키므로, 두 자리에 서로 다른 임계를 두면 같은 사태가 척도에 따라 갈리게 된다.

**`SimilarBody` — 【우리 규약】.** "두 캔들의 크기가 비슷하다"에도 원전이 숫자를 주지 않는다.
**작은 쪽이 큰 쪽의 절반 이상**이면 비슷하다고 본다. 절반을 고른 근거는 이 조건이 두 실체의
비를 2배 이내로 묶는다는 점이며, 그보다 느슨하면 육안으로 "비슷하다"고 부르기 어려운 쌍이
들어오고 그보다 엄격하면 Tasuki Gap과 Side-by-side White Lines가 거의 성립하지 않는다.
분모가 고저 범위가 아니라 상대 비인 것은 원전 표현이 두 실체를 서로 견주기 때문이다.

세 관계 모두 **등호를 허용한다.**

### 2.7 퇴화 봉 (Degenerate Bars)

원전은 이 경우를 다루지 않는다. **【우리 규약】** 아래 둘로 닫는다.

**`Range_t = 0`인 봉.** 네 값이 모두 같은 봉이다. 고저 범위를 분모로 쓰는 척도(§2.1, §2.2,
§2.3, §2.5, §2.6의 `Equal`과 `Near`)가 모두 정의되지 않는다. **그 봉이 관여하는 패턴은
불성립(0.0)으로 판정한다.** NaN이 아니다. 근거는 이 봉이 자료 오류이거나 거래가 전혀 없었던
봉이며, Morris 2장도 Four Price Doji를 두고 "It is so rare that one should suspect data
errors"라고 적어 같은 성격으로 본다는 점이다. 판정을 수행했고 성립하지 않았다는 뜻이므로
0.0이 맞고, 아직 판정할 수 없다는 뜻인 NaN은 틀리다.

**`Body_t = 0`이고 `Range_t > 0`인 봉.** 실체가 없는 도지다. 실체를 분모로 쓰는 그림자 배수
(§2.4)가 정의되지 않으므로 **§1.4의 `ShadowRatio` 확장을 쓰며, 비교의 방향에 따라 결과가
갈린다.**

- **하한 비교에서는 참이다.** 실체가 0인 봉의 아래그림자가 양수이면 "아래그림자가 실체의
  두 배 이상"과 "세 배 이상"이 모두 참이다. 이 규약이 없으면 잠자리형 도지가 Takuri의 모양
  요건을 통과하지 못하는데, Morris 2장이 Takuri를 **Tonbo(잠자리형 도지)의 한 갈래**로
  정의하므로 원전과 정면으로 어긋난다.
- **상한 비교에서는 거짓이다.** 곧 실체가 0인 봉의 위그림자가 양수이면 "위그림자가 실체의
  두 배 이하"는 거짓이다. 현재 §7의 어느 패턴도 상한을 쓰지 않으므로 이 규약은 지금 쓰이는
  자리가 없으며, 규칙의 완결성을 위해 정의해 둔다.
- **그림자도 0이면 두 방향 모두 거짓이다.**

**`Body_t = 0`인 봉의 색.** §1.2에 따라 양봉도 음봉도 아니다. 색을 요구하는 규칙은 성립하지
않는다. 이 규약과 위 그림자 규약은 서로 다른 자리에 걸리므로 충돌하지 않는다. 도지를
요구하는 규칙은 색을 묻지 않기 때문이다.

**척도 함수 자체가 무엇을 돌려주는지도 여기서 정한다.** 위의 "패턴이 불성립"이라는 규정만으로는
구현이 서지 않는다.

- **고저 범위를 분모로 쓰는 척도(§2.1, §2.2, §2.3, §2.5, §2.6의 `Equal`과 `Near`)는
  `Range_t = 0`인 봉에서 모두 거짓을 돌려준다.** 그냥 계산하게 두면 `Doji`와 `NoUpperShadow`와
  `NoLowerShadow`가 동시에 참이 되어 퇴화 봉이 성립 쪽으로 새어 들어간다.
- **그와 별도로, 패턴은 판정에 들어가기 전에 자기 창의 모든 봉을 검사해 퇴화 봉이 하나라도
  있으면 불성립으로 끝낸다.** 척도의 거짓 반환만으로는 충분하지 않다. 척도를 **부정으로**
  쓰는 규칙(예: §7.5.3 Ladder Bottom 규칙 3의 `¬NoUpperShadow`)에서는 거짓 반환이 오히려
  조건을 만족시켜 버리기 때문이다.

**둘 다 있어야 안전하다.** 어느 하나만으로는 막히지 않는다.

**확인 봉도 같은 검사를 받는다.** 위의 두 장치는 판정 창 안의 봉만 막는다. 성립 이후에
오는 확인 봉은 판정 창 밖에 있으므로 따로 막아야 한다. 규칙과 근거는 §5.5에 적는다.

### 2.8 원문이 갭의 종류를 구분하지 않은 자리

§1.3의 세 갈래 가운데 어느 것인지 원문이 밝히지 않은 패턴이 다섯 있다. `Kicking`,
`Kicking by Length`, `Tri Star`, `Concealing Baby Swallow`, `Up/Down-gap Side-by-side White
Lines`다.

**【우리 규약】 다섯 모두 실체 사이의 갭으로 읽는다.** 근거는 둘이다. 첫째, 원전이 갭의
종류를 명시한 패턴 열둘 가운데 열하나가 실체 기준이므로 명시되지 않은 자리를 실체 기준으로
읽는 것이 이웃과 일관된다. 둘째, `Kicking`은 두 봉이 모두 Marubozu여서 실체와 고저 범위가
일치하므로 실질적 차이가 없고, 나머지 넷에서만 차이가 나는데 그 넷도 모두 실체를 언급하는
문맥 안에 있다.

이 규약은 결정 D를 어기지 않는다. **결정 D는 원전이 정한 갭을 바꾸지 않는다고 했을 뿐,
원전이 아예 구분하지 않은 자리까지 정해 주지는 않는다.**

---

## §3. 직전 추세 (Prior Trend)

결정 B가 적용되는 자리다. **61종 가운데 45종이 직전 추세를 요구하고 16종은 요구하지
않는다.** 요구 여부는 §7의 각 절에 적었고 §8에 집계했다.

### 3.1 판정식

```
TrendEMA_t = EMA(RangeMid, 10)_t          (기존 지표 표준 §0.3의 EMA를 그대로 호출)

패턴이 인덱스 i에서 판정되고 k봉을 걸칠 때, 첫날의 인덱스는 f = i − (k − 1)이다.

UpTrend(i)   ⇔  RangeMid_f >  TrendEMA_f
DownTrend(i) ⇔  RangeMid_f <  TrendEMA_f
```

**【원전】** Morris 6장은 "the exponential period of 10 days seemed to work as well as any",
곧 지수 기간 10일이 어느 값 못지않게 잘 듣는다고 적고, 개별 패턴 해설에서 "The midpoint of
the range of the first day is above a 10-period moving average. This means that an uptrend
has been in place", 곧 첫날 범위의 중간값이 10기간 이동평균 위에 있으면 상승 추세가 자리잡고
있었다는 뜻이라고 쓴다. **기간 10과 비교 대상(범위 중간값)과 비교 봉(패턴 첫날)이 모두
원전에서 왔다.**

**비교 봉은 패턴의 첫날이며 판정 봉이 아니다.** 이 자리를 선택으로 열어 두지 않는다. 단일
봉 패턴에서는 첫날이 곧 판정 봉이므로 둘이 같다.

`RangeMid_f = TrendEMA_f`인 경우는 상승도 하락도 아니다. 추세를 요구하는 패턴은 그 봉에서
성립하지 않는다. **【우리 규약】** 원전이 다루지 않은 자리이며, 등호를 어느 한쪽에 붙이면
근거 없이 한 방향을 넓히게 되므로 양쪽 모두에서 빼는 쪽을 골랐다.

### 3.2 지수이동평균의 시드와 워밍업

기존 지표 표준 §0.3의 규약을 그대로 쓴다. **첫 10개 값의 단순평균으로 재귀를 시드하며,
인덱스 0부터 8까지는 정의되지 않고(NaN) 인덱스 9에서 처음 값을 낸다.** 등록된
`EMA(period=9)`의 `min_history`가 9인 것과 같은 규약이다.

`TrendEMA`의 입력은 종가가 아니라 **범위 중간값 `RangeMid`**다. 원전이 그렇게 적었기
때문이며, 이 점을 놓치면 값이 조용히 달라진다.

### 3.3 판정 시점에 필요한 이동평균은 현재 값이 아니다

패턴이 인덱스 `i`에서 판정될 때 필요한 것은 `TrendEMA_i`가 아니라 **`TrendEMA_f`**, 곧
`k − 1`봉 전의 값이다. 그러므로 상태는 지수이동평균 하나만 들어서는 안 되고 **최근 `k`개의
이동평균 값을 보관**해야 한다. `k`가 최대 5이므로 보관량은 상수다. 이 요구는 구조 설계가
받아 가며 `analysis-2-corelib-structure.md` 4.2절과 4.3.2절에 적혀 있다.

---

## §4. 부등식과 경계 (Inequalities and Boundaries)

원전이 부등식의 엄격성을 밝힌 자리는 드물다. **이 절이 하나의 규약으로 닫으며 §7의 패턴
본문은 여기를 참조한다.**

### 4.1 원전이 명시한 자리는 원전을 따른다

**Engulfing과 Harami 두 곳뿐이다.** Morris는 Engulfing 규칙 2에서 "This does not mean,
however, that either the top or the bottom of the two bodies cannot be equal; it just means
the both tops and both bottoms cannot be equal", 곧 두 실체의 위쪽 끝이나 아래쪽 끝 가운데
어느 한쪽이 같은 것은 허용하고 양쪽이 모두 같은 것만 배제한다고 적는다. Harami 규칙 3도
"Just like the Engulfing day, the tops or bottoms of the bodies can be equal, but both tops
and both bottoms cannot be equal"이라고 같은 말을 한다.

**한 식으로 쓰면 이렇다.** 둘째 실체가 첫 실체를 감쌀 때,

```
Engulf(prev, cur) ⇔ BodyBot_cur ≤ BodyBot_prev
                 ∧ BodyTop_cur ≥ BodyTop_prev
                 ∧ ¬(BodyBot_cur = BodyBot_prev ∧ BodyTop_cur = BodyTop_prev)
```

곧 두 비교를 모두 **비엄격**으로 두되 양 끝이 함께 일치하는 경우만 배제한다. 포함 관계인
Harami는 방향을 뒤집어 같은 형태로 쓴다.

```
Contain(prev, cur) ⇔ BodyBot_cur ≥ BodyBot_prev
                  ∧ BodyTop_cur ≤ BodyTop_prev
                  ∧ ¬(BodyBot_cur = BodyBot_prev ∧ BodyTop_cur = BodyTop_prev)
```

### 4.2 원전이 밝히지 않은 자리의 규약

**【우리 규약】** 자리의 성격에 따라 셋으로 나눈다. 하나의 임계로 통일하지 않은 까닭은,
"감싼다"와 "같다"와 "꼬리가 없다"가 서로 다른 종류의 관계여서 같은 규칙을 씌우면 어느
한쪽이 반드시 뒤틀리기 때문이다.

| 자리의 성격 | 규약 | 근거 |
|---|---|---|
| 포함과 감쌈 | §4.1의 `Engulf`와 `Contain`을 그대로 확장 적용 | 원전이 명시한 유일한 자리의 규칙을 같은 종류의 관계에 넓힌다 |
| "같다", "닿는다", "같은 값에서 열린다" | §2.6의 `Equal` | 원전이 정확한 일치를 요구하는 것처럼 보여도 실무에서 성립하지 않으므로 허용오차가 필요하다 |
| "꼬리가 없다", "고가에서 마감한다" | §2.5의 `NoUpperShadow` / `NoLowerShadow` | 정확한 등호를 요구하면 Marubozu와 Belt-hold가 사실상 성립하지 않는다 |
| 크기 비교("보다 길다", "보다 낮다") | **엄격 부등식** | 원전이 "greater than", "lower than"으로 적은 자리다 |
| 배수 비교("최소 두 배") | **등호 허용** | 원전이 "at least", "no more than"으로 적은 자리다 |

### 4.3 중간점 비교

Piercing과 Dark Cloud Cover와 Thrusting이 첫 실체의 중간점을 기준으로 갈린다. 원전이 값을
주었으므로 **【원전】**이다. Nison 4장은 Piercing을 "closes more than halfway into the prior
black candlestick's real body"로, Dark Cloud Cover를 "more than a 50-percent penetration"으로
적는다. Morris는 Thrusting을 "does not close above the midpoint"로 적는다.

```
BodyMid_prev = (O_prev + C_prev) / 2

Piercing:        C_cur > BodyMid_prev  ∧  C_cur < O_prev
DarkCloudCover:  C_cur < BodyMid_prev  ∧  C_cur > O_prev
Thrusting:       C_cur ≤ BodyMid_prev  (그리고 첫 실체 안)
```

**중간점에 정확히 닿는 경우는 Piercing도 Dark Cloud Cover도 아니고 Thrusting이다.**
**【우리 규약】** 원전이 이 경계를 다루지 않았으나, Piercing과 Dark Cloud Cover가 "more
than"으로 적혀 있고 Thrusting이 "does not close above"로 적혀 있으므로 세 규칙을 그대로
읽으면 등호가 Thrusting 쪽으로 떨어진다. 규칙을 지어낸 것이 아니라 원문의 부등식을 그대로
합친 결과다.

---

## §5. 출력 규약 (Output Contract)

결정 F가 적용되는 자리다. **패턴 하나가 네 개의 키를 낸다.** 정보를 버리지 않으므로 나중에
다른 표현으로 접는 것이 가능하다.

### 5.1 네 키

| 키 | 뜻 | 값 |
|---|---|---|
| `<name>` | **성립.** 이 봉에서 패턴이 성립했는가 | `1.0` 성립, `0.0` 불성립, `NaN` 아직 판정 불가 |
| `<name>_dir` | **방향.** 성립했다면 강세인가 약세인가 | `+1.0` 강세, `−1.0` 약세, `0.0` 방향 없음 또는 불성립, `NaN` 판정 불가 |
| `<name>_strength` | **강도.** 경계에 걸친 성립인가 온전한 성립인가 | `1.0` 온전, `0.5` 경계, `0.0` 불성립, `NaN` 판정 불가 |
| `<name>_confirm` | **확인.** 원전이 확인을 요구하는 패턴에서 확인까지 끝났는가 | `1.0` 확인이 일어난 봉, `0.0` 그 밖의 모든 봉, `NaN` 판정 불가 |

**`_confirm`이 `1.0`인 봉과 `<name>`이 `1.0`인 봉은 서로 다른 봉이다.** §5.4가 정하듯 확인은
패턴이 성립한 봉보다 뒤에서 일어나므로, 확인 봉에서는 그 봉 자체에 패턴이 성립하지 않아
`<name>`이 `0.0`인 채로 `<name>_confirm`만 `1.0`이 된다. **이 조합은 정상이며 금지되지
않는다.** `_confirm`의 `0.0`을 "불성립"이라고만 읽어 두 키가 반드시 같은 봉에서 올라간다고
가정하면 확인 봉을 잘못 처리하게 된다.

`<name>`은 결정 G에 따라 기존 지표 이름과 겹치지 않는다. 이 표준은 패턴 이름을 `pat_`로
시작하는 소문자 밑줄 표기로 적는다. 예를 들어 Hammer는 `pat_hammer`이고 네 키는
`pat_hammer`, `pat_hammer_dir`, `pat_hammer_strength`, `pat_hammer_confirm`이다.

### 5.2 방향이 없는 패턴에서 `_dir`

Doji, Long-Legged Doji, Rickshaw Man, Spinning Top, High-Wave, Marubozu, Closing Marubozu,
Long Line, Short Line은 방향성이 없는 **캔들 선**이다. 이 아홉에서 `_dir`은 성립해도
`0.0`이다. 봉의 색을 방향으로 쓰지 않는다. **근거는 원전이 이들을 방향 신호가 아니라 모양의
이름으로 다룬다는 점이다.** 색을 알아야 하는 소비자는 원본 캔들에서 직접 읽을 수 있다.

Dragonfly Doji, Gravestone Doji, Takuri는 원전이 방향 함의를 밝힌 도지이므로 `_dir`을
낸다. 개별 값은 §7의 해당 절에 적었다.

### 5.3 `0.0`과 `NaN`의 구분

**이 구분은 계약이다.**

- **`0.0`은 "판정했고 성립하지 않았다"**를 뜻한다. 워밍업이 끝난 뒤의 모든 평가 봉은 네 키에
  유한값을 갖는다.
- **`NaN`은 "아직 판정할 수 없다"**를 뜻하며 **워밍업 구간에만 나타난다.** 인덱스가
  `min_history − 1`보다 작은 구간이다.

퇴화 봉(§2.7)에서 값을 내지 못하는 것은 **판정 불가가 아니라 불성립**이므로 `0.0`이다.
NaN을 쓰지 않는다. 이 구분이 무너지면 Evidence 완결성 검사가 워밍업과 불성립을 갈라내지
못한다.

### 5.4 정렬 규약 — 어느 봉이 어느 값을 싣는가

`docs/roadmap-stage-3-0-plan.md` 7.4.1절이 이미 정한 규약을 **그대로 따르며 새로 만들지
않는다.**

> 반환 계열의 인덱스는 차트에 그려지는 위치를 뜻하고, **인덱스 `t`의 값은 `t`까지의 캔들만으로
> 결정될 때에만 실린다.** 차트 위치가 그 값을 결정하는 캔들보다 앞서면, 결정될 때까지 정확히
> 그만큼 발표를 늦춘다.

패턴에 적용하면 이렇다.

- **확인이 필요 없는 패턴.** 패턴의 마지막 봉에 네 키가 실린다. 그 봉까지의 캔들만으로
  결정되므로 늦출 것이 없다.
- **확인이 필요한 패턴.** 성립 여부는 패턴의 마지막 봉에서 이미 정해지므로 `<name>`,
  `<name>_dir`, `<name>_strength`는 그 봉에 실린다. **`<name>_confirm`은 확인이 일어난
  봉에서 `1.0`이 된다.** 확인 봉은 패턴의 마지막 봉보다 뒤이므로, 확인 결과를 패턴 봉으로
  되돌려 적지 않는다. 되돌려 적으면 인덱스 `t`의 값이 `t` 이후 캔들을 읽게 되어 규약을
  깬다.
- 곧 확인이 필요한 패턴에서 `<name>`이 `1.0`인 봉과 `<name>_confirm`이 `1.0`인 봉은 **서로
  다른 봉이며, 소비자는 둘을 함께 읽어야 한다.** 확인 기한 안에 확인이 오지 않으면
  `<name>_confirm`은 그 구간 내내 `0.0`으로 남는다.

### 5.5 확인의 내용과 기한

**원전이 내용과 기한을 모두 준 자리가 넷 있고 그 넷은 결정 대상이 아니다.**

| 패턴 | 확인의 내용 | 기한 | 출처 |
|---|---|---|---|
| Hikkake | 강세 설정이면 가격이 인사이드 바의 고가 위로, 약세 설정이면 저가 아래로 움직임 | **3봉** | `[Ch]` |
| Modified Hikkake | 위와 같다 | **3봉** | `[Ch]` |
| Hanging Man | 다음 봉 종가가 패턴 봉 실체 아래에서 마감 | **1봉** | `[N]` 4장 |
| Inverted Hammer | 다음 봉 종가가 패턴 봉 실체 위에서 마감 | **1봉** | `[N]` 5장 |

Nison은 Hanging Man과 Inverted Hammer에 대해 최소 요건(다음 봉 **시가**가 실체 밖에서
열림)과 권장 요건(다음 봉 **종가**가 실체 밖에서 마감)을 함께 적는다. **이 표준은 권장
요건을 채택한다. 【우리 규약】** 근거는 Nison 자신이 "I usually recommend a close beneath
the hanging man", 곧 종가 쪽을 권한다고 적었고, 결정 C가 좁고 엄격한 쪽을 규범으로 삼기
때문이다. 최소 요건은 주석으로 남긴다.

**나머지 자리는 Morris가 등급만 매기고 내용도 기한도 적지 않았다.** Morris는 머리말
`Confirmation:` 필드에 `Required`, `Suggested`, `No` 셋 가운데 하나를 89개 항목 전부에
적었으나, 무엇이 확인인지는 시나리오 절의 흩어진 문장에만 나오고 기한은 한 곳도 적지 않았다.

**【우리 규약】 나머지 패턴의 확인은 다음과 같이 정한다.**

```
확인의 내용:  강세 패턴이면  C_{m+1} > C_m
              약세 패턴이면  C_{m+1} < C_m
              (m = 패턴의 마지막 봉)
기한:         1봉
```

내용을 다음 봉 종가 비교로 통일한 근거는 둘이다. 첫째, Morris가 시나리오 절에서 확인을
말할 때 쓰는 문장이 대체로 종가 조건이다. Harami에 대해 "Confirmation on the third day
would be a lower close", Hammer에 대해 "it is best to wait for a confirming close on the
following day"라고 적는다. 둘째, 원전이 내용을 준 Hanging Man과 Inverted Hammer도 종가
조건을 권장 요건으로 삼으므로 규칙이 하나로 모인다.

기한을 1봉으로 정한 근거는 Morris와 Nison의 서술이 모두 "다음 날" 또는 "셋째 날"을 가리켜
바로 다음 봉을 뜻한다는 점이다. Chesler의 3봉은 Hikkake 두 종에만 적용하며 다른 패턴으로
유추하지 않는다. 근거가 다른 저작에 있기 때문이다.

**확인 봉이 퇴화 봉일 때. 【우리 규약】** 기한 안의 어떤 봉이 §2.7의 `Range = 0`인 퇴화
봉이면 **그 봉은 확인 봉이 될 수 없다.** 기한이 3봉인 Hikkake 두 종에서는 남은 봉이 여전히
확인 봉이 될 수 있고, 기한이 1봉인 나머지 패턴에서는 확인되지 못한 채로 기한이 닫혀
`<name>_confirm`이 `0.0`으로 남는다.

근거는 §2.7이 그런 봉을 자료 오류이거나 거래가 전혀 없었던 봉으로 보아 판정에서 배제한다는
데 있다. 판정에서 신뢰하지 않는 봉의 종가를 확인 신호로는 받아들이면 같은 근거가 두 자리에서
서로 다르게 적용된다. **배제의 근거가 척도의 정의 가능성이 아니라 봉의 신뢰성이라는 점을
분명히 해 둔다.** 확인 조건은 종가 비교뿐이어서 척도가 정의되지 않는 문제는 애초에 생기지
않으며, 그래서 §2.7의 두 장치 어느 것도 이 자리를 막지 못한다.

**등급이 `No`인 자리는 확인을 계산하지 않는다. 【우리 규약】** 원전이 확인을 요구하지도 권하지도
않았다는 뜻이므로 `<name>_confirm`이 성립 이후에도 `0.0`으로 남는다. 계산해 두고 소비자가 무시하게
하는 것과 아예 계산하지 않는 것 가운데 뒤를 고른 근거는, 확인이 원전에 근거를 둔 사건이지 모든
패턴에 기계적으로 붙는 파생값이 아니기 때문이다.

**확인 등급이 방향마다 다른 절이 있다. 【우리 규약】** Morris는 같은 절의 강세형과 약세형에 다른
등급을 매긴 자리가 있고, §7에 그런 절이 열여섯이다. **이 경우 등급이 있는 방향에서만 확인을
계산한다.** 곧 강세형이 `No`이고 약세형이 `Required`인 절에서는 강세형으로 성립한 봉의
`<name>_confirm`이 `0.0`으로 남고, 약세형으로 성립한 봉에서만 다음 봉의 종가 조건을 따진다.
근거는 위의 `No` 규약을 방향별 등급에 그대로 적용한 것이며, 등급이 방향마다 다르다는 사실 자체가
원전이 두 방향을 다르게 보았다는 뜻이기 때문이다.

**확인 등급의 처리.** Morris의 `Required`와 `Suggested`는 §7의 각 절에 그대로 적는다.
**`Required`인 패턴은 `<name>_confirm`이 `1.0`이 되기 전에는 소비자가 진입 신호로 쓰지
않아야 한다.** 이 표준은 그 계약을 명시하되 `<name>` 자체를 확인 뒤로 늦추지는 않는다.
성립과 확인은 서로 다른 사건이고 §5.4의 정렬 규약이 둘을 다른 봉에 싣기 때문이다.

### 5.6 강도

`<name>_strength`가 `0.5`가 되는 자리는 **§4.1의 감쌈과 포함에서 한쪽 끝이 정확히 일치하는
경우**뿐이다. 원전이 그 경우를 명시적으로 허용하되 온전한 감쌈과 구별했으므로 값을 갈라
싣는다. 그 밖의 모든 성립은 `1.0`이다. **【우리 규약】** 원전이 강도라는 개념을 두지는
않았으나, 결정 F가 경계 강도를 보존하라고 정했고 원전이 구별한 유일한 경계가 이 자리다.

---

## §6. `min_history`

`min_history`는 **그 패턴이 유효한 값을 낼 수 있는 첫 시점에 필요한 확정 캔들 수**다. 특정
사건이 언제 확인되어 발표되는가와는 다른 것이며, §5.4의 정렬 규약이 그 둘을 갈라 다룬다.

기호를 정한다. `k`는 패턴이 걸치는 봉 수이고, `P = 10`은 §3의 지수이동평균 기간이다.

**§2가 모든 척도의 분모를 그 봉의 고저 범위로 통일했으므로 척도에서 오는 워밍업은 0이다.**
따라서 `min_history`는 두 갈래로만 갈린다.

```
추세를 요구하지 않는 패턴:  min_history = k
추세를 요구하는 패턴:       min_history = P + k − 1 = k + 9
```

**추세형 식의 유도.** 패턴이 인덱스 `i`에서 판정될 때 첫날의 인덱스는 `f = i − (k − 1)`이고,
§3.2에 따라 그 봉에서 지수이동평균이 유효하려면 `f ≥ P − 1`이어야 한다. 곧
`i ≥ P + k − 2`이므로 첫 유효 인덱스가 `P + k − 2`이고 `min_history = P + k − 1`이다.

단일 봉 패턴에서 `k = 1`이므로 추세형은 `min_history = 10`, 비추세형은 `min_history = 1`이다.

**확인 지연은 `min_history`에 더하지 않는다.** 확인은 성립과 다른 사건이고 §5.4가 다른 봉에
싣기 때문이다. `min_history`는 네 키가 처음으로 유한값을 갖는 시점을 뜻하며, 확인이 아직
오지 않은 구간의 `<name>_confirm`은 NaN이 아니라 `0.0`이다.

패턴별 값은 §7의 각 절에 적었고 §8에 모았다.

---

## §7. 패턴 61종

이 장이 문서의 본체다. 절마다 다음을 적는다. 통용 이름과 TA-Lib 함수 이름과 이 표준이 쓰는
출력 이름, 원전과 인용 위치, 추세 요구 여부, 원전의 확인 등급, 번호를 붙인 판정 규칙,
출력 네 키, `min_history`, 그리고 **우리가 정한 것의 표시**다.

**판정 규칙을 읽는 법.** 규칙은 §2의 척도와 §3의 추세와 §4의 부등식 규약을 **이름으로만**
참조한다. 절 안에서 새 임계를 세우지 않는다. 봉의 번호는 패턴 안에서 1부터 세며, `k`봉짜리
패턴에서 마지막 봉이 판정이 실리는 봉이다. 방향이 갈리는 패턴은 강세형을 적고 약세형은
좌우를 뒤집는다고만 밝히며, 뒤집는 방식이 대칭이 아닌 경우에만 따로 적는다.

### 7.1 단일 캔들 가운데 도지 계열과 우산형 (11종)

#### 7.1.1 Doji — `CDLDOJI` → `pat_doji`

**원전.** `[M]` 2장 DOJI 절, `[N]` 3장·8장·용어사전. Nison 용어사전은 "A session in which
the open and close are the same (or almost the same)"이라고 적는다.
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. `Doji(t)` — §2.3.

**출력.** `pat_doji` = 1.0. `_dir` = 0.0 (§5.2의 방향 없는 캔들 선). `_strength` = 1.0.
`_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** 도지 허용오차를 고저 범위의 3퍼센트로 정했다(§2.3). 원전은 형식과
1~3퍼센트라는 범위만 주었다.

#### 7.1.2 Long-Legged Doji — `CDLLONGLEGGEDDOJI` → `pat_long_legged_doji`

**원전.** `[M]` 2장, `[N]` 8장·용어사전. Nison은 "A doji with very long shadows"라고 적고
Morris는 "long upper and lower shadows in the middle of the day's trading range"라고 적는다.
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. `Doji(t)` — §2.3.
2. `LongUpperShadow(t)` **그리고** `LongLowerShadow(t)` — §2.4. 두 그림자가 모두 길다.

**출력.** `pat_long_legged_doji` = 1.0. `_dir` = 0.0. `_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** 도지 허용오차(§2.3). "긴 그림자"의 배수 2는 §2.4의 원전 값이다. 실체가
0인 봉에서 배수 비교가 참이 되는 것은 §2.7의 우리 규약이다.

#### 7.1.3 Rickshaw Man — `CDLRICKSHAWMAN` → `pat_rickshaw_man`

**원전.** `[N]` 8장·용어사전. **Morris 3판에는 `rickshaw`라는 낱말이 한 번도 나오지 않는다.**
Nison은 "If the opening and closing of a long-legged doji session are in the middle of the
session's range, the line is called a rickshaw man"이라고 적는다.
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. 7.1.2 Long-Legged Doji의 규칙 1과 2를 만족한다.
2. `Near(BodyMid_t, RangeMid_t, t)` — §2.6. 실체의 중간점이 고저 범위의 한가운데에 있다.

**출력.** `pat_rickshaw_man` = 1.0. `_dir` = 0.0. `_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** "한가운데"를 §2.6의 `Near`(고저 범위의 10퍼센트)로 옮겼다. **원전은 이
표현에 숫자를 주지 않는다.**

#### 7.1.4 Dragonfly Doji — `CDLDRAGONFLYDOJI` → `pat_dragonfly_doji`

**원전.** `[M]` 2장, `[N]` 8장·용어사전. Nison은 "A doji with a long lower shadow and where
the open, high, and close are at the session's high"라고 적어 시가와 고가와 종가가 모두
세션 고가에 있다고 말하고, Morris는 시가와 종가만 말한다. **결정 C에 따라 조건이 더 많은
Nison을 채택한다.**
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. `Doji(t)` — §2.3.
2. `NoUpperShadow(t)` — §2.5. 시가와 종가와 고가가 사실상 같다.
3. `LongLowerShadow(t)` — §2.4.

**출력.** `pat_dragonfly_doji` = 1.0. `_dir` = **+1.0**. Nison 용어사전이 이 도지를
Gravestone Doji의 반대형으로 두고 Gravestone을 천정 반전 신호로 적으므로 바닥 쪽이다.
`_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** 규칙 2의 "고가에 있다"를 정확한 등호가 아니라 §2.5의 매우 짧은 그림자로
옮겼다(§4.2). 정확한 등호를 요구하면 이 패턴이 사실상 성립하지 않는다.

#### 7.1.5 Gravestone Doji — `CDLGRAVESTONEDOJI` → `pat_gravestone_doji`

**원전.** `[M]` 2장, `[N]` 8장·용어사전. Nison은 "A doji in which the opening and closing
are at the low of the session"이라고 적어 정확한 일치를 요구하고, Morris는 "at, or very
near, the low of the day"라고 적어 근접을 허용한다. **결정 C에 따라 좁은 쪽인 Nison을
채택한다.**
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. `Doji(t)` — §2.3.
2. `NoLowerShadow(t)` — §2.5.
3. `LongUpperShadow(t)` — §2.4.

**출력.** `pat_gravestone_doji` = 1.0. `_dir` = **−1.0**. Nison 용어사전이 "It is a reversal
signal at tops"라고 적는다. `_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** 7.1.4와 같은 이유로 규칙 2를 §2.5로 옮겼다. Morris의 근접 허용은
결정 C에 따라 채택하지 않고 주석으로만 남긴다.

#### 7.1.6 Takuri — `CDLTAKURI` → `pat_takuri`

**원전.** `[M]` 3장 Hammer 절 해설. **원전이 배수를 직접 준 자리다.** "A Takuri line has a
lower shadow at least three times the length of the body, whereas the lower shadow of a
Hammer is a minimum of only twice the length of the body." Morris 2장은 Takuri를 Tonbo
(잠자리형 도지)의 한 갈래로 두고 "A Takuri line at the end of a down trend is extremely
bullish"라고 적는다.
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. 7.1.4 Dragonfly Doji의 규칙 1과 2를 만족한다.
2. `LS_t ≥ 3.0 · Body_t` — **【원전】** 세 배는 Morris가 준 값이다. 등호를 허용한다
   ("at least").

**출력.** `pat_takuri` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** 없다. 배수는 원전이 주었고, 실체가 0인 봉에서 이 비교가 참이 되는 것은
§2.7의 규약인데 그 규약이 없으면 Morris가 Takuri를 잠자리형 도지의 갈래로 정의한 것과
어긋난다.

#### 7.1.7 Hammer — `CDLHAMMER` → `pat_hammer`

**원전.** `[M]` 3장(머리말과 규칙), `[N]` 4장. Morris 머리말은 `Trend Required = Yes`,
`Confirmation = Required`다.
**추세.** **하락**을 요구한다(§3). **확인.** `Required`.

**판정 규칙** (`k = 1`)

1. `DownTrend(t)` — §3.1. 단일 봉이므로 첫날이 곧 판정 봉이다.
2. `ShortBody(t)` — §2.2. 실체의 색은 묻지 않는다.
3. `NoUpperShadow(t)` — §2.5. 실체가 거래 범위의 위쪽 끝에 있다.
4. `LS_t ≥ 2.0 · Body_t` — **【원전】** Nison 4장 "at least twice the height of the real
   body"와 Morris 3장 해설이 같은 값을 준다. 등호를 허용한다.

**출력.** `pat_hammer` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가가 이 봉 종가보다 높으면 1.0 (§5.5의 일반 규약, 기한 1봉).
**`min_history`** = 10 (`k + 9`).
**우리가 정한 것.** 짧은 실체 임계(§2.2)와 "위쪽 끝"을 §2.5로 옮긴 것, 그리고 확인의 내용과
기한(§5.5)이다. 아래꼬리 배수 2는 원전 값이다.

> Morris 규칙 절은 아래꼬리를 "usually two or three times"라고 열어 두지만, 같은 장의 해설이
> "a minimum of only twice"로 못박고 그 문장이 Takuri의 세 배와 대비되므로 두 배를 채택한다.
> 규칙 절의 "두 배에서 세 배"는 주석으로만 남긴다.

#### 7.1.8 Hanging Man — `CDLHANGINGMAN` → `pat_hanging_man`

**원전.** `[M]` 3장(규칙은 Hammer와 한 묶음), `[N]` 4장. **확인 등급에서 두 원전이 반대로
말한다.** Morris 머리말은 `Confirmation = No`이고 Nison 4장은 "A hanging man should be
confirmed, while a hammer need not be"라고 적는다. **결정 C에 따라 조건이 더 많은 Nison을
채택한다.**
**추세.** **상승**을 요구한다(§3). **확인.** **필요**(Nison 채택).

**판정 규칙** (`k = 1`)

1. `UpTrend(t)` — §3.1.
2. 7.1.7 Hammer의 규칙 2, 3, 4와 같다.

**출력.** `pat_hanging_man` = 1.0. `_dir` = **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가가 이 봉의 실체 하단(`BodyBot_t`)보다 낮으면 1.0 (§5.5의 원전
지정 자리, 기한 1봉).
**`min_history`** = 10.
**우리가 정한 것.** Hammer와 같다. 다만 **확인의 내용은 원전이 주었다.** Nison 4장은 최소
요건을 다음 날 시가가 실체 아래에서 열리는 것으로, 권장 요건을 다음 날 종가가 실체 아래에서
마감하는 것으로 적으며, §5.5가 권장 요건을 채택했다.

#### 7.1.9 Inverted Hammer — `CDLINVERTEDHAMMER` → `pat_inverted_hammer`

**원전.** `[M]` 3장(규칙은 Shooting Star와 한 묶음), `[N]` 5장. Morris 머리말은
`Confirmation = No`이나 Nison 5장이 "the inverted hammer needs bullish confirmation"이라고
적으므로 **결정 C에 따라 Nison을 채택한다.**
**추세.** **하락**을 요구한다(§3). **확인.** **필요**(Nison 채택).

**판정 규칙** (`k = 1`)

1. `DownTrend(t)` — §3.1.
2. `ShortBody(t)` — §2.2.
3. `NoLowerShadow(t)` — §2.5. 실체가 가격 범위의 아래쪽 부분에 있다.
4. **갭을 요구하지 않는다.** Morris 규칙 2가 "No gap down is required"라고 명시한다.

> **Morris 규칙 3의 위그림자 상한은 요건으로 채택하지 않는다.** 원문은 "The upper shadow is
> **usually** no more than two times as long as the body"인데, 이 표준은 §7.3.14에서 Nison의
> "(usually a small one)"을 두고 **"usually"는 요건이 아니라 경향이므로 결정 C의 대상이
> 아니다**라고 이미 정했다. 같은 낱말을 한 곳에서는 버리고 다른 곳에서는 경성 요건으로 쓰면
> 표준이 자기모순에 빠지므로, 여기서도 경향으로 내리고 주석으로만 남긴다.
>
> **채택했을 때의 결과가 그 판단을 뒷받침한다.** 상한을 요건으로 두면 `Range = US + Body + LS`에
> 규칙 3(`LS ≤ 0.10 · Range`)과 상한(`US ≤ 2 · Body`)을 넣었을 때 `Body ≥ 0.30 · Range`가
> 따라 나오고, 여기에 규칙 2의 `Body < (1/3) · Range`가 겹쳐 **실체가 고저 범위의 30퍼센트
> 이상 33.3퍼센트 미만인 3.3퍼센트포인트 띠에서만** 패턴이 성립한다. 사실상 죽은 패턴이 된다.
>
> **원전과의 정합도 이쪽이 낫다.** Nison 5장은 역해머를 "a candlestick line that has a **long
> upper shadow** and a small real body at the lower end of the session"이라고 적는다. 상한을
> 걸면 위그림자가 짧아져 그 서술과 어긋난다. 상한을 빼면 남은 규칙만으로
> `US_t ≥ 0.567 · Range_t`가 따라 나와 위그림자가 저절로 길어진다.
>
> **따라오는 결과 하나를 밝혀 둔다.** 도지는 §2.2의 짧은 실체에 포함되므로, 묘비형 도지 모양의
> 봉이 하락 추세에서 나오면 이 패턴이 성립한다. §7.1.5 Gravestone Doji와 같은 봉에서 함께
> 성립할 수 있다는 뜻이다. 이것은 결함이 아니라 원전이 말하는 바다. Nison은 역해머가 슈팅스타와
> **모양이 같고 직전 추세로만 갈린다**고 적고, Morris 2장도 묘비형 도지가 바닥에서는 강세
> 신호일 수 있다고 적는다.

**출력.** `pat_inverted_hammer` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가가 이 봉의 실체 상단(`BodyTop_t`)보다 높으면 1.0 (§5.5의 원전
지정 자리, 기한 1봉).
**`min_history`** = 10.
**우리가 정한 것.** 짧은 실체 임계, "아래쪽 부분"을 §2.5로 옮긴 것, 그리고 **Morris의
위그림자 상한을 경향으로 읽어 요건에서 뺀 것**이다. 확인의 내용은 원전이 주었다.

#### 7.1.10 Shooting Star — `CDLSHOOTINGSTAR` → `pat_shooting_star`

**원전.** `[M]` 3장, `[N]` 5장. **갭 요건에서 두 원전이 갈린다.** Morris 규칙 1은 "Prices
gap open after an uptrend"라고 갭을 요구하고 Nison 용어사전은 요구하지 않는다. **결정 C에
따라 조건이 더 많은 Morris를 채택한다.**
**추세.** **상승**을 요구한다(§3). **확인.** `Required`.

**판정 규칙** (`k = 2`. 갭을 재려면 앞 봉이 필요하다)

1. `UpTrend(t)` — §3.1. 첫날은 갭의 기준이 되는 앞 봉이므로 `f = t − 1`이다.
2. `GapUpOpen(t−1, t)` — §1.3. **단순 시가 갭**이다. Morris가 "Prices gap open"이라고만
   적고 실체 기준인지 고저 기준인지 구분하지 않으므로 앞 봉 종가 대비 시가의 위치로만 읽는다.
3. `ShortBody(t)` — §2.2.
4. `NoLowerShadow(t)` — §2.5.
5. `US_t ≥ 3.0 · Body_t` — **【원전】** Morris 규칙 3 "at least three times as long as the
   body". 등호를 허용한다.

**출력.** `pat_shooting_star` = 1.0. `_dir` = **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가가 이 봉 종가보다 낮으면 1.0 (§5.5의 일반 규약, 기한 1봉).
**`min_history`** = 11 (`k + 9`, `k = 2`).
**우리가 정한 것.** 짧은 실체 임계와 "아래쪽 부분"의 옮김이다. 위꼬리 배수 3과 갭 요건은
원전이 주었다.

#### 7.1.11 Spinning Top — `CDLSPINNINGTOP` → `pat_spinning_top`

**원전.** `[M]` 2장, `[N]` 3장. Morris는 "small real bodies with upper and lower shadows
that are of greater length than the body's length"라고 적는다.
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. `US_t > Body_t` **그리고** `LS_t > Body_t`. **엄격 부등식**이다. 원문이 "greater than"이다.
2. 실체의 색은 묻지 않는다.

**출력.** `pat_spinning_top` = 1.0. `_dir` = 0.0. `_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** **규칙에 §2.2의 짧은 실체를 따로 넣지 않았다.** Morris 자신이 "The small
body relative to the shadows is what makes the spinning top"이라고 적어 작은 실체 조건이
그림자 비교에 흡수된다고 밝히므로, 규칙 1이 이미 `Body_t < Range_t / 3`을 함의한다(§2.2의
유도와 같은 계산이다). 조건을 두 번 걸지 않는다. **`Body_t = 0`인 봉에서는 규칙 1이 그림자가
양수여야 참이므로 §2.7의 규약이 그대로 적용된다.**

### 7.2 단일 캔들 가운데 몸통과 그림자의 형태 (6종)

#### 7.2.1 High-Wave Candle — `CDLHIGHWAVE` → `pat_high_wave`

**원전.** `[N]` 용어사전. "A candle with very long upper and lower shadows and a small real
body. It shows that the market is losing its direction." **Morris 3판에는 이 단일 캔들
항목이 없다.** Sakata 장의 "HIGH WAVES"는 여러 봉의 위꼬리가 만드는 다른 형태이므로 이
패턴의 원전이 아니다.
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. `ShortBody(t)` — §2.2.
2. `LongUpperShadow(t)` **그리고** `LongLowerShadow(t)` — §2.4. 두 그림자가 모두 실체의
   두 배 이상이다.

**출력.** `pat_high_wave` = 1.0. `_dir` = 0.0. `_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** **Spinning Top과의 경계를 여기서 정한다.** 두 패턴은 원전에서 모두
"작은 실체와 긴 그림자"로 적혀 구별이 서지 않는다. 이 표준은 **Spinning Top을 그림자가
실체보다 긴 것으로, High-Wave를 그림자가 실체의 두 배 이상인 것으로** 갈랐다. 근거는
High-Wave의 원전 표현이 "very long"이어서 Spinning Top의 "greater than"보다 한 단계 강하고,
§2.4가 이미 "긴 그림자"를 두 배로 정의했으므로 새 임계를 만들지 않아도 된다는 점이다.
**두 패턴은 포함 관계이며 High-Wave가 성립하면 Spinning Top도 성립한다.**

#### 7.2.2 Marubozu — `CDLMARUBOZU` → `pat_marubozu`

**원전.** `[M]` 2장. "there is no shadow extending from the body at either the open or the
close, or at both." **Nison 2판에는 `marubozu`라는 낱말이 나오지 않으며** 같은 개념을 3장에서
shaven head와 shaven bottom으로 부른다.
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. `LongBody(t)` — §2.1.
2. `NoUpperShadow(t)` **그리고** `NoLowerShadow(t)` — §2.5. 양쪽 그림자가 모두 없다.
3. 색은 묻지 않는다. 양봉이면 White Marubozu, 음봉이면 Black Marubozu다.

**출력.** `pat_marubozu` = 1.0. `_dir` = 0.0 (§5.2). `_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** 긴 실체 임계(§2.1)와, "꼬리가 없다"를 정확한 등호가 아니라 §2.5의 매우
짧은 그림자로 옮긴 것(§4.2)이다. 정확한 등호를 요구하면 이 패턴이 사실상 성립하지 않는다.

#### 7.2.3 Closing Marubozu — `CDLCLOSINGMARUBOZU` → `pat_closing_marubozu`

**원전.** `[M]` 2장. "A Closing Marubozu has no shadow extending from the close end of the
body."
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. `LongBody(t)` — §2.1.
2. 양봉이면 `NoUpperShadow(t)`, 음봉이면 `NoLowerShadow(t)` — §2.5. 곧 종가 쪽 그림자가 없다.
3. 반대쪽 그림자는 있어도 된다.

**출력.** `pat_closing_marubozu` = 1.0. `_dir` = 0.0. `_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** 7.2.2와 같다.

> Morris는 같은 절에서 Opening Marubozu도 정의하나 TA-Lib이 함수를 두지 않으므로 이 표준도
> 절을 두지 않는다. 다만 7.2.4 Belt-hold가 시가 쪽을 보는 같은 모양이다.

#### 7.2.4 Belt-hold — `CDLBELTHOLD` → `pat_belt_hold`

**원전.** `[M]` 3장(머리말과 규칙), `[N]` 6장. Nison은 강세형을 "opens on the low of the
session ... and closes at, or near, the session highs", 약세형을 "opens on the high of the
session ... and continues lower"라고 적고 "The longer the height of the belt-hold candle
line, the more significant it becomes"라고 덧붙인다.
**추세.** 요구한다(§3). **강세형은 하락 추세 뒤, 약세형은 상승 추세 뒤다.**
**확인.** 강세형 `Suggested`, 약세형 `Required`.

**판정 규칙** (`k = 1`. 강세형 기준)

1. `DownTrend(t)` — §3.1.
2. `White_t` **그리고** `LongBody(t)` — §1.2, §2.1.
3. `NoLowerShadow(t)` — §2.5. 시가가 저가와 사실상 같다.
4. `NoUpperShadow(t)` — §2.5. 종가가 고가에 또는 그 가까이 있다.

약세형은 `UpTrend(t)`, `Black_t`, `NoUpperShadow(t)`를 요구한다. **규칙 4는 대칭이 아니다.**
Nison이 약세형에 대해서는 종가 위치를 적지 않고 "continues lower through the session"이라고만
쓰므로, **약세형에는 종가 조건을 넣지 않는다.** 원문의 비대칭을 그대로 둔다.

**출력.** `pat_belt_hold` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가가 방향대로 움직이면 1.0 (§5.5의 일반 규약, 기한 1봉).
**`min_history`** = 10.
**우리가 정한 것.** 긴 실체 임계와 "꼬리 없음"의 옮김, 그리고 강세형 종가의 "고가 가까이"를
§2.5로 옮긴 것이다.

> **Nison의 허용오차는 채택하지 않았다.** Nison은 강세형에 "or with a very small lower
> shadow", 약세형에 "or within a few ticks of the high"라는 여지를 두는데, 이는 Morris의
> 무꼬리 요건을 **넓히는** 것이므로 결정 C에 따라 기각하고 주석으로만 남긴다. 반대로 Nison이
> **더한** 조건인 종가 위치와 실체 길이는 채택했다.

#### 7.2.5 Long Line Candle — `CDLLONGLINE` → `pat_long_line`

**원전.** `[M]` 2장과 6장. 패턴이 아니라 **캔들 선**이므로 Morris 머리말 필드가 없다.
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. `LongBody(t)` — §2.1.

**출력.** `pat_long_line` = 1.0. `_dir` = 0.0. `_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** 긴 실체 임계(§2.1)다. **이 패턴은 판정 규칙 전체가 곧 척도이므로 §2.1을
정하는 것이 이 패턴을 정하는 것이다.**

> TA-Lib은 이 함수에서 긴 실체와 짧은 그림자를 함께 요구하지만 **Morris의 Long Days 서술에는
> 꼬리 요건이 없다.** 이 표준은 원전을 따라 꼬리 요건을 넣지 않는다.

#### 7.2.6 Short Line Candle — `CDLSHORTLINE` → `pat_short_line`

**원전.** `[M]` 2장과 6장. 6장은 "The exact same concept for determining long days is used
for short days with one exception; instead of minimum percentages, maximum percentages are
used"라고 적는다.
**추세.** 요구하지 않는다. **확인.** 원전이 등급을 두지 않는다.

**판정 규칙** (`k = 1`)

1. `ShortBody(t)` — §2.2.

**출력.** `pat_short_line` = 1.0. `_dir` = 0.0. `_strength` = 1.0. `_confirm` = 0.0.
**`min_history`** = 1.
**우리가 정한 것.** 짧은 실체 임계(§2.2)다. 7.2.5와 마찬가지로 꼬리 요건은 넣지 않는다.

### 7.3 두 캔들과 그에 준하는 패턴 (16종)

#### 7.3.1 Engulfing — `CDLENGULFING` → `pat_engulfing`

**원전.** `[M]` 3장, `[N]` 4장. **원전이 부등식의 엄격성을 명시한 유일한 자리다**(§4.1).
**추세.** 요구한다. **강세형은 하락 추세 뒤, 약세형은 상승 추세 뒤다.**
**확인.** 강세형 `Suggested`, 약세형 `Required`.

**판정 규칙** (`k = 2`. 강세형 기준)

1. `DownTrend(t)` — §3.1. 첫날은 `f = t − 1`이다.
2. `Black_{t−1}` — 첫날은 음봉이다.
3. `White_t` — 둘째 날은 양봉이다.
4. `Engulf(t−1, t)` — §4.1. 둘째 실체가 첫 실체를 감싼다. 두 실체의 위쪽 끝이나 아래쪽 끝
   **가운데 하나는 같아도 되지만 둘 다 같아서는 안 된다.**
5. 꼬리는 감쌀 필요가 없다.

약세형은 좌우를 뒤집는다.

**출력.** `pat_engulfing` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**.
`_strength` = 한쪽 끝이 정확히 일치하면 **0.5**, 양끝이 모두 엄격히 넘어서면 **1.0** (§5.6).
`_confirm` = 다음 봉 종가가 방향대로 움직이면 1.0.
**`min_history`** = 11.
**우리가 정한 것.** **없다.** 척도를 쓰지 않고 등호 처리까지 원전이 명시했다. 추세 판정만
§3에서 온다.

> Morris의 인쇄된 규칙 2는 감싸는 쪽과 감싸이는 쪽을 뒤바꾼 오식이다. 같은 책의 유연성 절
> ("no part of the first day's real body is equal to or outside of the second day's real
> body")과 시나리오 절, 그리고 Nison 4장("a white bullish real body wraps around, or engulfs,
> the prior period's black real body")이 모두 위의 방향을 못박는다. 유연성 절이 덧붙인
> "30퍼센트 이상 감싸면 더 강하다"와 "꼬리까지 감싸면 성공률이 높다"는 결정 C에 따라 주석으로만
> 남긴다.

#### 7.3.2 Harami — `CDLHARAMI` → `pat_harami`

**원전.** `[M]` 3장, `[N]` 6장.
**추세.** 요구한다. **강세형은 하락 추세 뒤, 약세형은 상승 추세 뒤다.**
**확인.** 강세형 `No`, 약세형 `Required`.

**판정 규칙** (`k = 2`. 강세형 기준)

1. `DownTrend(t)` — §3.1.
2. `LongBody(t−1)` — §2.1. 첫날이 긴 날이다.
3. `ShortBody(t)` — §2.2. 둘째 날이 짧은 날이다.
4. `Contain(t−1, t)` — §4.1. 둘째 실체가 첫 실체 안에 완전히 들어간다. 한쪽 끝의 등호는
   허용하고 양끝 동시 일치만 배제한다.
5. 둘째 날은 첫날과 **반대색**이다.

약세형은 좌우를 뒤집는다.

**출력.** `pat_harami` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**.
`_strength` = 한쪽 끝 일치면 0.5, 아니면 1.0. `_confirm` = 다음 봉 종가 조건.
**`min_history`** = 11.
**우리가 정한 것.** 긴 실체와 짧은 실체의 임계(§2.1, §2.2)다. 포함 관계의 등호는 원전이
명시했다.

> Morris 규칙 2는 첫날의 색을 "not as important, but it is best if it reflects the trend"라고
> 적어 **필수가 아니라 권고**로 둔다. 이 표준은 규칙 5의 반대색 요건만 필수로 두고 첫날 색을
> 따로 요구하지 않는다. 강세형에서 첫날이 음봉인 것은 규칙 5에서 따라 나온다.

#### 7.3.3 Harami Cross — `CDLHARAMICROSS` → `pat_harami_cross`

**원전.** `[M]` 3장, `[N]` 6장. Nison 용어사전은 "A harami with a doji on the second session
instead of a small real body"라고 적는다.
**추세.** 요구한다. **강세형은 하락 추세 뒤, 약세형은 상승 추세 뒤다.**
**확인.** 강세형 `No`, 약세형 `Required`.

**판정 규칙** (`k = 2`. 강세형 기준)

1. `DownTrend(t)` — §3.1.
2. `LongBody(t−1)` — §2.1.
3. `Doji(t)` — §2.3.
4. `Contain(t−1, t)` — §4.1.

**출력.** `pat_harami_cross` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**.
`_strength` = 한쪽 끝 일치면 0.5, 아니면 1.0. `_confirm` = 다음 봉 종가 조건.
**`min_history`** = 11.
**우리가 정한 것.** 긴 실체 임계, 도지 허용오차, 그리고 **규칙 4의 포함 기준**이다.

> **【우리 규약】 원문 구조가 모호한 자리다.** Morris 규칙 3은 "The second-day Doji is within
> the range of the previous long day"라고 적어 그냥 `range`라고만 쓰는데, Harami 규칙 3은
> "within the body range"라고 못박는다. 이 표준은 **실체 범위**로 읽는다. 근거는 Nison
> 용어사전이 이 패턴을 "하라미의 둘째 봉이 작은 실체 대신 도지인 것"이라고 정의해 하라미의
> 포함 관계를 그대로 물려받게 하기 때문이다. 고저 범위로 읽으면 하라미와 다른 패턴이 되어
> 그 정의와 어긋난다. **원문의 낱말 차이를 존중해 고저 범위로 읽는 것도 가능한 읽기이며,
> 이 선택은 되돌릴 수 있다.**

#### 7.3.4 Doji Star — `CDLDOJISTAR` → `pat_doji_star`

**원전.** `[M]` 3장, `[N]` 5장·용어사전. Nison 용어사전은 "A doji that gaps from a long
white or black candle's real body"라고 적어 **갭의 기준이 실체임을 밝힌다.**
**추세.** 요구한다. **강세형은 하락 추세 뒤, 약세형은 상승 추세 뒤다.**
**확인.** 강세형 `No`, 약세형 `Suggested`.

**판정 규칙** (`k = 2`. 강세형 기준)

1. `DownTrend(t)` — §3.1.
2. `LongBody(t−1)` — §2.1.
3. `GapDnBody(t−1, t)` — §1.3. **실체 사이의 갭**이며 추세 방향이다.
4. `Doji(t)` — §2.3.

약세형은 `UpTrend`와 `GapUpBody`로 뒤집는다.

**경향(규범 아님).** Morris 규칙 4는 도지 날의 그림자가 "should not be excessively long,
especially in the bullish case"라고 적는다. **이 표준은 이 문장을 규범으로 삼지 않는다.**

이전 판은 이 문장을 §2.4의 긴 그림자의 부정, 곧 `¬LongUpperShadow(t) ∧ ¬LongLowerShadow(t)`로
옮겨 규칙 5로 두었다. **그 규칙은 어떤 봉도 성립시키지 못한다.** §2.4는 그림자를 **실체의
배수**로 재는데, 규칙 4가 요구하는 도지는 실체가 거의 0이라 실체 배수라는 척도 자체가 무너지기
때문이다. 산술로 적으면 이렇다. 두 그림자가 각각 실체의 두 배 미만이면 `Range = US + Body + LS`
항등식에서 `Range < 5 · Body`가 된다. 그런데 §2.3의 도지는 `Body ≤ 0.03 · Range`, 곧
`Range ≥ 33.3 · Body`를 뜻한다. 두 부등식을 동시에 만족하는 실체는 없다. 실체가 정확히 0인
봉도 탈출구가 아니다. §1.4의 하한 규약에 따라 그림자가 양수이면 "실체의 두 배 이상"이 참이
되므로 부정이 거짓이 되고, 그림자마저 0이면 고저 범위가 0이 되어 §2.7의 퇴화 봉으로 걸린다.

**규범에서 뺀 근거는 셋이다.** 첫째, 위와 같이 규칙으로 두면 패턴이 공집합이 되어 원전이
실재한다고 기술한 패턴을 표준이 소멸시킨다. 둘째, Morris가 숫자를 주지 않았고 "especially"라는
강조어를 붙였다. 이것은 §7.1.9의 위그림자 상한과 §7.3.14의 "usually"를 경향으로 읽은 것과 같은
문형이므로, 세 자리를 같은 규칙으로 처리해야 표준이 일관된다. 셋째, 실체 상대 척도를 작은 실체
요건과 **부정으로** 결합하면 언제나 이런 모순이 생긴다. §7의 나머지 절은 같은 결합을 긍정으로만
쓰므로(§7.1.2, §7.1.4, §7.1.5, §7.2.1, §7.4.14) 이 문제가 이 절에만 있다.

**Doji Star는 갭을 요구하므로 이 규칙 없이도 Harami Cross와 구별된다.** Harami Cross는 포함
관계를 요구하고 갭을 요구하지 않는다.

**출력.** `pat_doji_star` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**. `_strength` = 1.0.
`_confirm` = **강세형은 0.0**(등급이 `No`다), 약세형은 다음 봉 종가 조건. §5.5의 방향별 등급
규약을 따른다.
**`min_history`** = 11.
**우리가 정한 것.** 긴 실체 임계와 도지 허용오차다. Morris의 그림자 문장을 경향으로 내린 것도
이 표준의 판단이다. 원전이 강세형에만 강조를 둔 비대칭은 따르지 않았는데, 경향으로 내린 뒤에는
양쪽 모두 판정에 쓰이지 않으므로 비대칭 자체가 사라진다.

#### 7.3.5 Piercing Line — `CDLPIERCING` → `pat_piercing`

**원전.** `[M]` 3장, `[N]` 4장. **침투 깊이를 원전이 주었다**(§4.3).
**추세.** **하락**을 요구한다. **확인.** `Suggested`.

**판정 규칙** (`k = 2`)

1. `DownTrend(t)` — §3.1.
2. `Black_{t−1}` **그리고** `LongBody(t−1)` — 첫날은 긴 음봉이다.
3. `White_t` — 둘째 날은 양봉이다.
4. `O_t < L_{t−1}` — 둘째 날이 **앞날의 저가 아래에서** 열린다. Morris가 "that's low, not
   close"라고 괄호로 못박는다. **엄격 부등식**이다. 갭이 아니라 시가의 위치 비교다.
5. `C_t > BodyMid_{t−1}` **그리고** `C_t < O_{t−1}` — §4.3. 앞 실체의 중간점 위이면서 실체
   안에서 마감한다.

**출력.** `pat_piercing` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0. `_confirm` = 다음 봉
종가 조건.
**`min_history`** = 11.
**우리가 정한 것.** 긴 실체 임계뿐이다. 침투 기준은 원전이 주었다.

#### 7.3.6 Dark Cloud Cover — `CDLDARKCLOUDCOVER` → `pat_dark_cloud_cover`

**원전.** `[M]` 3장, `[N]` 4장. **시가 기준에서 두 원전이 갈린다.** Morris는 "the open above
the previous day's high (that's the high, not the close)"라고 고가로 못박고 Nison은 "above
the prior session's high (or close)"라고 종가도 허용한다. **결정 C에 따라 좁은 쪽인 Morris를
채택한다.**
**추세.** **상승**을 요구한다. **확인.** `Required`.

**판정 규칙** (`k = 2`)

1. `UpTrend(t)` — §3.1.
2. `White_{t−1}` **그리고** `LongBody(t−1)` — 첫날은 긴 양봉이다.
3. `Black_t` — 둘째 날은 음봉이다.
4. `O_t > H_{t−1}` — 둘째 날이 **앞날의 고가 위에서** 열린다. **엄격 부등식**이다.
5. `C_t < BodyMid_{t−1}` **그리고** `C_t > O_{t−1}` — §4.3.

**출력.** `pat_dark_cloud_cover` = 1.0. `_dir` = **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건.
**`min_history`** = 11.
**우리가 정한 것.** 긴 실체 임계뿐이다. 침투 50퍼센트와 시가 기준은 원전이 주었다.

#### 7.3.7 Counterattack (Meeting Lines) — `CDLCOUNTERATTACK` → `pat_counterattack`

**원전.** `[M]` 3장 Meeting Lines, `[N]` 6장. Nison은 둘째 날 시가에 대해 "should open
robustly higher (bearish) or sharply lower (bullish)"라고 적고 약세형에 대해 "should ideally
open above the prior day's high"라고 덧붙인다. **결정 C에 따라 Nison의 시가 조건을 채택한다.**
**추세.** 요구한다. **강세형은 하락 추세 뒤, 약세형은 상승 추세 뒤다.**
**확인.** 강세형 `Suggested`, 약세형 `Required`.

**판정 규칙** (`k = 2`. 강세형 기준)

1. `DownTrend(t)` — §3.1.
2. `Black_{t−1}` **그리고** `LongBody(t−1)`.
3. `White_t` **그리고** `LongBody(t)` — 두 날 모두 긴 날이다.
4. `O_t < L_{t−1}` — 둘째 날 시가가 첫날의 **저가 아래**다. **엄격 부등식**이다.
5. `Equal(C_t, C_{t−1}, t)` — §2.6. 두 날의 종가가 같다.

약세형은 `UpTrend`, 첫날 양봉, 둘째 날 음봉, `O_t > H_{t−1}`로 뒤집는다.

**출력.** `pat_counterattack` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**.
`_strength` = 1.0. `_confirm` = 다음 봉 종가 조건.
**`min_history`** = 11.
**우리가 정한 것.** 긴 실체 임계와 "같다"의 허용오차(§2.6)다.

> **규칙 4에 별도의 "크게"라는 임계를 만들지 않았다.** Nison의 "sharply lower"와 "robustly
> higher"를 **앞날의 저가 아래(또는 고가 위)**라는 원전 자신의 문장으로 옮겼기 때문이다.
> Nison이 약세형에 "open above the prior day's high"라고 구체적으로 적었으므로 그 형태를
> 강세형에 대칭으로 적용했다. 이 대칭 적용이 【우리 규약】이다.

#### 7.3.8 Separating Lines — `CDLSEPARATINGLINES` → `pat_separating_lines`

**원전.** `[M]` 4장, `[N]` 7장·용어사전. 유형은 **지속형**이다.
**추세.** 요구한다. **강세형은 상승 추세 뒤, 약세형은 하락 추세 뒤다**(지속형이므로 추세가
이어진다).
**확인.** 강세형 `No`, 약세형 `Required`.

**판정 규칙** (`k = 2`. 강세형 기준)

1. `UpTrend(t)` — §3.1.
2. `Black_{t−1}` — 첫날은 **현재 추세와 반대색**이다.
3. `White_t` — 둘째 날은 첫날과 반대색이며 곧 추세색이다.
4. `Equal(O_t, O_{t−1}, t)` — §2.6. 두 실체가 **시가에서 만난다.**

약세형은 좌우를 뒤집는다.

**출력.** `pat_separating_lines` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**.
`_strength` = 1.0. `_confirm` = 다음 봉 종가 조건.
**`min_history`** = 11.
**우리가 정한 것.** "같다"의 허용오차(§2.6)다. Morris 규칙에는 길이 요건이 없으므로 넣지
않는다.

#### 7.3.9 Kicking — `CDLKICKING` → `pat_kicking`

**원전.** `[M]` 3장. **Nison 2판에는 `kicking`이 나오지 않는다.** Morris 머리말은
**`Trend Required = No`**이며 **89개 항목 가운데 추세를 요구하지 않는 둘 가운데 하나다.**
해설은 "The market direction is not as important with this pattern as it is with most other
candle patterns"라고 적는다.
**추세.** **요구하지 않는다.** **확인.** `Required`.

**판정 규칙** (`k = 2`. 강세형 기준)

1. 첫날이 **Black Marubozu**다. 곧 7.2.2의 규칙을 만족하고 음봉이다.
2. 둘째 날이 **White Marubozu**다.
3. `GapUpBody(t−1, t)` — §1.3. 두 선 사이에 갭이 **반드시** 있어야 한다.

약세형은 White Marubozu 뒤에 Black Marubozu가 오고 `GapDnBody`다.

**출력.** `pat_kicking` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건.
**`min_history`** = **2** (추세를 요구하지 않으므로 `k`와 같다).
**우리가 정한 것.** Marubozu 판정에 쓰는 긴 실체와 무꼬리 임계(§2.1, §2.5), 그리고 **갭의
종류**다. 원문이 "a gap must occur between the two lines"라고만 적어 종류를 구분하지 않으므로
§2.8의 규약에 따라 **실체 사이의 갭**으로 읽는다. 두 봉이 Marubozu이므로 실체와 고저 범위가
사실상 같아 이 선택의 실질적 영향은 작다.

#### 7.3.10 Kicking by Length — `CDLKICKINGBYLENGTH` → `pat_kicking_by_length`

**원전.** `[M]` 3장 Kicking 해설. **방향 규칙은 원전에 있다.** "Some Japanese theory says
that future movement will be in the direction of the longer side of the two candles,
regardless of the price trend." 다만 Morris는 이것을 자기 규칙으로 채택하지 않고 **전언으로
소개**했고, **별개 패턴으로 세운 것은 TA-Lib이다.**
**추세.** **요구하지 않는다.** **확인.** `Required`.

**판정 규칙** (`k = 2`)

1. 7.3.9 Kicking의 규칙 1부터 3까지를 만족한다.
2. 방향은 **두 Marubozu 가운데 실체가 더 긴 쪽의 색**으로 정한다. 가격 추세는 보지 않는다.
3. `Body_{t−1} = Body_t`이면 방향을 정할 수 없으므로 **불성립**이다.

**출력.** `pat_kicking_by_length` = 1.0. `_dir` = 더 긴 실체가 양봉이면 **+1.0**, 음봉이면
**−1.0**. `_strength` = 1.0. `_confirm` = 다음 봉 종가 조건.
**`min_history`** = 2.
**우리가 정한 것.** 셋이다. 첫째, **"더 긴 쪽"을 실체 길이로 읽었다.** 원문은 "the longer
side"라고만 적는다. 두 봉이 엄격한 Marubozu라면 실체와 고저 범위가 같아 차이가 없지만,
§2.5가 무꼬리에 허용오차를 두므로 둘이 갈릴 수 있다. **실체를 고른 근거는 Marubozu의 정의가
실체 중심이고 §2.1의 긴 실체 척도도 실체를 재기 때문이다.** 둘째, **동률을 불성립으로
정했다.** 원전이 다루지 않으며, 방향을 임의로 한쪽에 주는 것보다 성립시키지 않는 편이
정보를 왜곡하지 않는다. 셋째, **패턴 이름이 TA-Lib에서 왔다는 사실**이다.

#### 7.3.11 Homing Pigeon — `CDLHOMINGPIGEON` → `pat_homing_pigeon`

**원전.** `[M]` 3장. **Nison 2판에는 나오지 않는다.**
**추세.** **하락**을 요구한다. **확인.** `No`.

**판정 규칙** (`k = 2`)

1. `DownTrend(t)` — §3.1.
2. `Black_{t−1}` **그리고** `LongBody(t−1)`.
3. `Black_t` **그리고** `ShortBody(t)` — **두 날이 같은 색이다.** 하라미와 다른 점이 이것뿐이다.
4. `Contain(t−1, t)` — §4.1.

**출력.** `pat_homing_pigeon` = 1.0. `_dir` = **+1.0**. `_strength` = 한쪽 끝 일치면 0.5,
아니면 1.0. `_confirm` = **0.0**(등급이 `No`다 — §5.5).
**`min_history`** = 11.
**우리가 정한 것.** 긴 실체와 짧은 실체의 임계, 그리고 **포함 관계의 등호 처리를 §4.1의
`Contain`으로 확장 적용한 것**(§4.2)이다. 원전은 이 패턴에서 등호를 밝히지 않았다.

#### 7.3.12 Matching Low — `CDLMATCHINGLOW` → `pat_matching_low`

**원전.** `[M]` 3장. **Nison 2판에는 나오지 않는다.**
**추세.** **하락**을 요구한다. **확인.** `No`.

**판정 규칙** (`k = 2`)

1. `DownTrend(t)` — §3.1.
2. `Black_{t−1}` **그리고** `LongBody(t−1)`.
3. `Black_t` — 둘째 날도 음봉이다.
4. `Equal(C_t, C_{t−1}, t)` — §2.6. 두 날의 종가가 같다.

**출력.** `pat_matching_low` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0.
`_confirm` = **0.0**(등급이 `No`다 — §5.5).
**`min_history`** = 11.
**우리가 정한 것.** 긴 실체 임계와 "같다"의 허용오차다.

> Morris는 짝이 되는 Matching High 항목에서 "1/1000 안이면 같다"는 훨씬 좁은 값을 준다. §2.6이
> 밝힌 대로 이 표준은 그 값을 채택하지 않고 Morris 6장이 지시한 도지 개념을 쓴다. 1/1000을
> 쓰면 이 패턴이 실질적으로 성립하지 않는다.

#### 7.3.13 In-Neck Line — `CDLINNECK` → `pat_in_neck`

**원전.** `[M]` 4장, `[N]` 4장. Nison은 "The in-neck pattern's white candle closes slightly
into the prior real body (**it should also be a small white candle**)"라고 적어 둘째 봉의
크기 조건을 더한다. **결정 C에 따라 채택한다.** 유형은 **지속형**이다.
**추세.** 요구한다. **약세형은 하락 추세 뒤, 강세형은 상승 추세 뒤다.**
**확인.** 양쪽 모두 `Required`.

**판정 규칙** (`k = 2`. 약세형 기준)

1. `DownTrend(t)` — §3.1.
2. `Black_{t−1}` — 첫날은 음봉이다.
3. `White_t` **그리고** `ShortBody(t)` — 둘째 날은 **작은 양봉**이다(Nison 채택).
4. `O_t < L_{t−1}` — 둘째 날이 앞날의 저가 아래에서 열린다. **엄격 부등식**이다.
5. `C_t > C_{t−1}` **그리고** `Equal(C_t, C_{t−1}, t)` — 종가가 첫 실체 안으로 들어가되
   **아주 조금만** 들어간다.

강세형은 첫날이 긴 양봉이고 둘째 날이 음봉이며 앞날 고가 위에서 열린다. **Morris는 강세형에만
"long white day"를 두므로 그 비대칭을 그대로 둔다.**

**출력.** `pat_in_neck` = 1.0. `_dir` = 약세형 **−1.0**, 강세형 **+1.0**(지속형이므로 추세
방향이다). `_strength` = 1.0. `_confirm` = 다음 봉 종가 조건.
**`min_history`** = 11.
**우리가 정한 것.** **규칙 5의 "아주 조금만"을 §2.6의 `Equal`로 옮겼다.** 근거는 Morris
자신이 "For all practical purposes, the closes are equal", 곧 실질적으로 두 종가가 같다고
적었다는 점이다. 별도의 침투 상한을 새로 만들지 않았다. 짧은 실체와 긴 실체의 임계도
우리 것이다.

#### 7.3.14 On-Neck Line — `CDLONNECK` → `pat_on_neck`

**원전.** `[M]` 4장, `[N]` 4장. 유형은 **지속형**이다.
**추세.** 요구한다. **약세형은 하락 추세 뒤, 강세형은 상승 추세 뒤다.**
**확인.** 약세형 `Required`, 강세형 `No`.

**판정 규칙** (`k = 2`. 약세형 기준)

1. `DownTrend(t)` — §3.1.
2. `Black_{t−1}` **그리고** `LongBody(t−1)`.
3. `White_t` — 둘째 날은 양봉이다. **길이 요건이 없다.** Morris가 "This day does not need to
   be a long day"라고 명시적으로 배제한다.
4. `O_t < L_{t−1}` — **엄격 부등식**이다.
5. `Equal(C_t, L_{t−1}, t)` — 둘째 날이 **첫날의 저가에서** 마감한다.

강세형은 좌우를 뒤집어 둘째 날이 앞날의 **고가에서** 마감한다.

**출력.** `pat_on_neck` = 1.0. `_dir` = 약세형 **−1.0**, 강세형 **+1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건.
**`min_history`** = 11.
**우리가 정한 것.** 긴 실체 임계와 "같다"의 허용오차다.

> Nison은 On-Neck의 양봉을 "(usually a small one)"이라고 적으나 **"usually"는 요건이 아니라
> 경향이므로 결정 C의 대상이 아니다.** 7.3.13 In-Neck에서 Nison이 "it should also be"라고
> 적은 것과 강도가 다르며, 그 차이를 그대로 둔다. 곧 둘째 봉에 크기 요건을 넣지 않는다.

#### 7.3.15 Thrusting Line — `CDLTHRUSTING` → `pat_thrusting`

**원전.** `[M]` 4장, `[N]` 4장. Nison은 "The thrusting pattern should be a longer white
candle that is stronger than the in-neck pattern, but still does not close above the middle
of the prior black real body"라고 적는다. 유형은 **지속형**이다.
**추세.** 요구한다. **약세형은 하락 추세 뒤, 강세형은 상승 추세 뒤다.**
**확인.** 약세형 `Suggested`, 강세형 `No`.

**판정 규칙** (`k = 2`. 약세형 기준)

1. `DownTrend(t)` — §3.1.
2. `Black_{t−1}` — 첫날은 음봉이다.
3. `White_t` — 둘째 날은 양봉이다.
4. `O_t < L_{t−1}` — 둘째 날이 첫날의 저가보다 낮게 열린다. **엄격 부등식**이다.
5. `C_t > C_{t−1}` **그리고** `¬Equal(C_t, C_{t−1}, t)` — 첫 실체 안으로 **In-Neck보다 깊이**
   들어간다.
6. `C_t ≤ BodyMid_{t−1}` — §4.3. **중간점을 넘지 않는다. 중간점에 정확히 닿는 경우는
   Thrusting이다.**

강세형은 좌우를 뒤집으며 첫날이 긴 양봉이다.

**출력.** `pat_thrusting` = 1.0. `_dir` = 약세형 **−1.0**, 강세형 **+1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건.
**`min_history`** = 11.
**우리가 정한 것.** 둘이다. 첫째, **In-Neck과 Thrusting의 경계를 규칙 5로 정했다.** Nison이
"stronger than the in-neck pattern"이라고만 적어 상대적 표현을 남겼으므로, **In-Neck이
`Equal`로 정의된 자리를 그대로 뒤집어 `¬Equal`을 Thrusting의 하한으로 삼았다.** 이렇게 두면
두 패턴이 겹치지 않고 빈틈도 없다. 둘째, **"considerably lower"에 별도 임계를 만들지
않았다.** 규칙 4의 "앞날 저가 아래"와 규칙 5의 침투 하한이 함께 걸리면 시가가 충분히 낮아야
하므로 원전의 뜻이 이미 담긴다. 임계를 새로 지어내지 않기 위한 선택이다.

#### 7.3.16 Stick Sandwich — `CDLSTICKSANDWICH` → `pat_stick_sandwich`

**원전.** `[M]` 3장. **Nison 2판에는 나오지 않는다.** **강세형과 약세형의 구조가 원전에서
서로 다르며 대칭이 아니다.**
**추세.** 요구한다. **강세형은 하락 추세 뒤, 약세형은 상승 추세 뒤다.**
**확인.** 강세형 `No`, 약세형 `Suggested`. 세 봉짜리이나 두 캔들 묶음에 함께 둔다.

**판정 규칙** (`k = 3`)

강세형.

1. `DownTrend(t)` — §3.1. 첫날은 `f = t − 2`다.
2. `Black_{t−2}` — 첫날은 음봉이다.
3. `White_{t−1}` **그리고** `L_{t−1} > C_{t−2}` — 둘째 날 양봉이 첫 음봉의 종가 위에서
   거래된다.
4. `Black_t` **그리고** `Equal(C_t, C_{t−2}, t)` — 셋째 날은 음봉이며 **종가가 첫날과 같다.**

약세형(원전 그대로 비대칭이다).

1. `UpTrend(t)`.
2. `White_{t−2}` — 첫날은 양봉이다.
3. `Black_{t−1}` **그리고** `O_{t−1} < C_{t−2}` **그리고** `C_{t−1} < O_{t−2}`.
4. `White_t` **그리고** `Engulf(t−1, t)` — 셋째 날 양봉이 둘째 음봉의 실체를 감싼다.
   **약세형에는 "종가가 같다"는 조건이 없다.**

**출력.** `pat_stick_sandwich` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**.
`_strength` = 약세형에서 감쌈의 한쪽 끝이 일치하면 0.5, 아니면 1.0. `_confirm` = 다음 봉
종가 조건.
**`min_history`** = 12.
**우리가 정한 것.** "같다"의 허용오차(강세형)와 감쌈의 등호 처리(약세형)다. **두 방향의
구조가 다른 것은 우리가 만든 비대칭이 아니라 Morris 본문 그대로다.**

### 7.4 세 캔들 (18종)

#### 7.4.1 Morning Star — `CDLMORNINGSTAR` → `pat_morning_star`

**원전.** `[M]` 3장, `[N]` 5장·용어사전. Morris 규칙 2가 "always gapped from the **body** of
the first day"라고 적어 **갭의 기준이 실체임을 밝힌다.** Nison은 셋째 날에 대해 "closes well
into the first session's black real body"라고 적어 **침투를 요구하는데 Morris의 네 규칙에는
그 요건이 아예 없다.** 결정 C에 따라 조건이 더 많은 Nison을 채택해 **침투를 필수로 둔다.**
**추세.** **하락**을 요구한다. **확인.** `Required`.

**판정 규칙** (`k = 3`)

1. `DownTrend(t)` — §3.1. 첫날은 `f = t − 2`다.
2. `Black_{t−2}` **그리고** `LongBody(t−2)` — 첫날은 긴 음봉이다.
3. `ShortBody(t−1)` **그리고** `GapDnBody(t−2, t−1)` — 둘째 날은 작은 실체이며 첫 실체
   **아래로 실체 갭**을 이룬다. **색은 묻지 않는다.**
4. `White_t` — 셋째 날은 양봉이다.
5. `C_t > BodyMid_{t−2}` — 셋째 날이 첫 실체의 **중간점 위로** 마감한다. 침투 깊이는 바로
   아래의 규약이다.

**출력.** `pat_morning_star` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0. `_confirm` = 다음
봉 종가 조건.
**`min_history`** = 12.
**우리가 정한 것.** 긴 실체와 짧은 실체의 임계, 그리고 **침투 깊이 50퍼센트**다.

> **【우리 규약】 별 계열 넷의 침투 깊이.** Nison은 Piercing과 Dark Cloud Cover에 50퍼센트를
> 주지만 별 계열에는 "well into"라고만 적고 숫자를 주지 않는다. **원전 안에서 끌어올 수 있는
> 값이 이웃 패턴의 50퍼센트뿐이므로 그것을 유추 적용한다.** 이 값은 원저자가 별 계열에 대해
> 적은 것이 아니다. TA-Lib의 `penetration` 기본값 0.3은 출처를 찾지 못했고 결정 A가 승계를
> 금지했으므로 쓰지 않는다. 이 규약은 7.4.2, 7.4.3, 7.4.4에도 같이 적용된다.

#### 7.4.2 Evening Star — `CDLEVENINGSTAR` → `pat_evening_star`

**원전.** 7.4.1과 같은 묶음이다(`[M]` 3장, `[N]` 5장).
**추세.** **상승**을 요구한다. **확인.** `Required`.

**판정 규칙** (`k = 3`) — 7.4.1의 좌우를 뒤집는다.

1. `UpTrend(t)`.
2. `White_{t−2}` **그리고** `LongBody(t−2)`.
3. `ShortBody(t−1)` **그리고** `GapUpBody(t−2, t−1)`. 색은 묻지 않는다.
4. `Black_t`.
5. `C_t < BodyMid_{t−2}`.

**출력.** `pat_evening_star` = 1.0. `_dir` = **−1.0**. `_strength` = 1.0. `_confirm` = 다음
봉 종가가 이 봉 종가보다 낮으면 1.0(§5.5의 일반 규약, 기한 1봉). **`min_history`** = 12.
**우리가 정한 것.** 7.4.1과 같다.

#### 7.4.3 Morning Doji Star — `CDLMORNINGDOJISTAR` → `pat_morning_doji_star`

**원전.** `[M]` 3장, `[N]` 5장. Morris 규칙 2는 "The second day must be a Doji Star (a Doji
that gaps)"라고 적어 **7.3.4 Doji Star의 정의를 그대로 물려받는다.**
**추세.** **하락**을 요구한다. **확인.** `Suggested`.

**판정 규칙** (`k = 3`)

1. `DownTrend(t)`.
2. `Black_{t−2}` **그리고** `LongBody(t−2)`.
3. `Doji(t−1)` **그리고** `GapDnBody(t−2, t−1)`.
4. `White_t`.
5. `C_t > BodyMid_{t−2}` — 7.4.1의 침투 규약이다.

**경향(규범 아님).** 이전 판은 규칙 3에 "도지의 그림자가 지나치게 길지 않다(7.3.4 규칙 5와
같다)"를 함께 두었다. **7.3.4가 바로 그 문장을 규범에서 빼 경향으로 내렸으므로 이 절도 같이
따른다.** 근거는 7.3.4에 적어 둔 산술이 이 절에도 그대로 걸린다는 데 있다. 규칙 3의 도지가
`Range ≥ 33.3 · Body`를 뜻하는데 §2.4의 긴 그림자를 부정하면 `Range < 5 · Body`가 되어, 조건을
남겨 두면 이 절과 7.4.4가 함께 공집합이 된다.

**출력.** `pat_morning_doji_star` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0. `_confirm` =
다음 봉 종가가 이 봉 종가보다 높으면 1.0(§5.5의 일반 규약, 기한 1봉). **`min_history`** = 12.
**우리가 정한 것.** 긴 실체 임계, 도지 허용오차, 도지 그림자 상한, 침투 깊이다.

#### 7.4.4 Evening Doji Star — `CDLEVENINGDOJISTAR` → `pat_evening_doji_star`

**원전.** 7.4.3과 같은 묶음이다.
**추세.** **상승**을 요구한다. **확인.** `Required`.

**판정 규칙** (`k = 3`) — 7.4.3의 좌우를 뒤집는다. `UpTrend`, 첫날 긴 양봉,
`GapUpBody`, 셋째 날 음봉, `C_t < BodyMid_{t−2}`다.

**출력.** `pat_evening_doji_star` = 1.0. `_dir` = **−1.0**. `_strength` = 1.0. `_confirm` =
다음 봉 종가가 이 봉 종가보다 낮으면 1.0(§5.5의 일반 규약, 기한 1봉). **`min_history`** = 12.
**우리가 정한 것.** 7.4.3과 같다.

#### 7.4.5 Abandoned Baby — `CDLABANDONEDBABY` → `pat_abandoned_baby`

**원전.** `[M]` 3장, `[N]` 용어사전. **갭의 기준이 꼬리를 포함한다는 점을 양 원전이 모두
명시한다.** Morris 규칙 2는 "a Doji whose shadow gaps above or below the previous day's
upper or lower shadow", 규칙 4는 "gaps in the opposite direction with no shadows
overlapping"이라고 적고, Nison 용어사전은 "gaps away (including shadows)"라고 적는다.
**추세.** 요구한다. **강세형은 하락 추세 뒤, 약세형은 상승 추세 뒤다.**
**확인.** 강세형 `Suggested`, 약세형 `Required`.

**판정 규칙** (`k = 3`. 강세형 기준)

1. `DownTrend(t)`.
2. `Black_{t−2}` — 첫날이 앞선 추세를 반영한다.
3. `Doji(t−1)` **그리고** `GapDnRange(t−2, t−1)` — §1.3. **꼬리를 포함한 고저 범위 갭**이다.
4. `White_t` — 셋째 날은 첫날과 반대색이다.
5. `GapUpRange(t−1, t)` — 셋째 날이 반대 방향으로 갭을 이루며 **꼬리가 전혀 겹치지 않는다.**

약세형은 좌우를 뒤집는다.

**출력.** `pat_abandoned_baby` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**.
`_strength` = 1.0. `_confirm` = 다음 봉 종가 조건. **`min_history`** = 12.
**우리가 정한 것.** 도지 허용오차뿐이다. **갭의 종류는 원전이 주었고 이 패턴만 꼬리 기준이다.**
침투 조건은 원전에 없으므로 넣지 않는다.

#### 7.4.6 Tri Star — `CDLTRISTAR` → `pat_tri_star`

**원전.** `[M]` 3장, `[N]` 8장·용어사전. Nison은 "Three doji that have the same formation as
a morning or evening star pattern. An extraordinarily rare pattern"이라고 적는다.
**추세.** 요구한다. **강세형은 하락 추세 뒤, 약세형은 상승 추세 뒤다.**
**확인.** 강세형 `Suggested`, 약세형 `Required`.

**판정 규칙** (`k = 3`. 강세형 기준)

1. `DownTrend(t)`.
2. `Doji(t−2)` **그리고** `Doji(t−1)` **그리고** `Doji(t)` — 세 날이 모두 도지다.
3. `GapDnBody(t−2, t−1)` **그리고** `GapUpBody(t−1, t)` — 가운데 날이 앞뒤 두 날 **아래로**
   갭을 이룬다.

약세형은 가운데 날이 위로 갭을 이룬다.

**출력.** `pat_tri_star` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건. **`min_history`** = 12.
**우리가 정한 것.** 도지 허용오차와 **갭의 종류**다. 원문이 갭의 기준을 밝히지 않으므로
§2.8의 규약에 따라 **실체 사이의 갭**으로 읽는다. 세 봉이 모두 도지여서 실체가 매우 작으므로
이 선택이 실질적으로 큰 차이를 만든다는 점을 밝혀 둔다.

#### 7.4.7 Two Crows — `CDL2CROWS` → `pat_two_crows`

**원전.** `[M]` 3장(규칙과 그 앞의 해설). 해설이 갭의 기준과 둘째 날 종가 위치를 구체화하므로
결정 C에 따라 채택한다. "The next day gaps much higher, but closes near its low, which is
still above the body of the first day. The next (third) day opens inside the body of the
second black day, then sells off into the body of the first day. This has closed the gap."
**추세.** **상승**을 요구한다. **확인.** `Required`.

**판정 규칙** (`k = 3`)

1. `UpTrend(t)`.
2. `White_{t−2}` **그리고** `LongBody(t−2)` — 첫날은 긴 양봉이다.
3. `Black_{t−1}` **그리고** `GapUpBody(t−2, t−1)` **그리고** `C_{t−1} > BodyTop_{t−2}` —
   둘째 날은 첫 실체 위로 **실체 갭**을 이루는 음봉이며 그 **종가가 첫 실체 위에 남는다.**
4. `Black_t` **그리고** `BodyBot_{t−1} < O_t < BodyTop_{t−1}` — 셋째 날은 둘째 실체
   **안에서 열린다.**
5. `BodyBot_{t−2} < C_t < BodyTop_{t−2}` — 셋째 날이 첫 실체 **안에서 마감한다.** 이로써
   갭이 메워진다.

**출력.** `pat_two_crows` = 1.0. `_dir` = **−1.0**. `_strength` = 1.0. `_confirm` = 다음 봉
종가 조건. **`min_history`** = 12.
**우리가 정한 것.** 긴 실체 임계와, **규칙 4와 5의 "안에서"를 엄격 부등식으로 읽은 것**이다.
§4.2가 크기 비교를 엄격으로 두므로 그 규약을 따랐다.

#### 7.4.8 Upside Gap Two Crows — `CDLUPSIDEGAP2CROWS` → `pat_upside_gap_two_crows`

**원전.** `[M]` 3장, `[N]` 6장. Nison이 **갭이 실체 사이의 갭임을 명시한다.** "The upside-gap
refers to the gap between the real body of the small black real body and the real body
preceding it." 이어 "An ideal upside-gap two crows has the second black real body opening
above the first black real body's open. It then closes under the first black candle's close"
라고 적어 셋째 날의 시가와 종가 위치를 밝힌다.
**추세.** **상승**을 요구한다. **확인.** `Required`.

**판정 규칙** (`k = 3`)

1. `UpTrend(t)`.
2. `White_{t−2}` **그리고** `LongBody(t−2)`.
3. `Black_{t−1}` **그리고** `GapUpBody(t−2, t−1)` — **실체 사이의 갭**이다.
4. `Black_t` **그리고** `O_t > O_{t−1}` **그리고** `C_t < C_{t−1}` — 셋째 음봉이 둘째 음봉의
   **시가 위에서 열려 종가 아래에서 마감한다.** 곧 그 실체가 둘째 실체를 감싼다.
5. `C_t > C_{t−2}` — 셋째 날의 **종가가 첫 양봉의 종가보다 위에 남는다.** 이 규칙이 7.4.7
   Two Crows와 이 패턴을 가른다.

**출력.** `pat_upside_gap_two_crows` = 1.0. `_dir` = **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건. **`min_history`** = 12.
**우리가 정한 것.** 긴 실체 임계뿐이다. 갭의 종류와 규칙 4와 5는 원전이 주었다.

#### 7.4.9 Three Advancing White Soldiers — `CDL3WHITESOLDIERS` → `pat_three_white_soldiers`

**원전.** `[M]` 3장, `[N]` 6장.
**추세.** **하락**을 요구한다(강세 반전형이다). **확인.** `No`.

**판정 규칙** (`k = 3`)

1. `DownTrend(t)`.
2. `White_{t−2}`, `White_{t−1}`, `White_t` **그리고** 셋 모두 `LongBody` — 연속된 긴 양봉
   셋이다.
3. `C_{t−1} > C_{t−2}` **그리고** `C_t > C_{t−1}` — 종가가 잇달아 높아진다. **엄격 부등식**이다.
4. `BodyBot_{t−1} < O_{t−1} < BodyTop_{t−1}`를 앞 실체에 대해 읽어, 각 봉이 **앞 실체
   안에서** 열린다. 곧 `BodyBot_{t−2} < O_{t−1} < BodyTop_{t−2}`이고
   `BodyBot_{t−1} < O_t < BodyTop_{t−1}`이다.
5. `NoUpperShadow` — 세 봉이 각각 그날의 **고가에 또는 고가 가까이** 마감한다(§2.5).

**출력.** `pat_three_white_soldiers` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0.
`_confirm` = **0.0**(등급이 `No`다 — §5.5). **`min_history`** = 12.
**우리가 정한 것.** 긴 실체 임계와, **"고가에 또는 가까이"를 §2.5의 매우 짧은 위그림자로
옮긴 것**이다.

#### 7.4.10 Three Black Crows — `CDL3BLACKCROWS` → `pat_three_black_crows`

**원전.** `[M]` 3장, `[N]` 6장. **삼백병과 대칭이 아니다.** Morris는 삼흑병에만 "Each day
closes at a new low"라는 규칙을 더한다.
**추세.** **상승**을 요구한다. **확인.** `Required`.

**판정 규칙** (`k = 3`)

1. `UpTrend(t)`.
2. `Black_{t−2}`, `Black_{t−1}`, `Black_t` **그리고** 셋 모두 `LongBody`.
3. `C_{t−1} < C_{t−2}` **그리고** `C_t < C_{t−1}` — 각 날이 **새 저점에서** 마감한다.
4. 각 봉이 앞 실체 안에서 열린다(7.4.9 규칙 4의 좌우 대칭).
5. `NoLowerShadow` — 각 봉이 그날의 **저가에 또는 저가 가까이** 마감한다(§2.5).

**출력.** `pat_three_black_crows` = 1.0. `_dir` = **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건. **`min_history`** = 12.
**우리가 정한 것.** 7.4.9와 같다.

#### 7.4.11 Identical Three Crows — `CDLIDENTICAL3CROWS` → `pat_identical_three_crows`

**원전.** `[M]` 3장. 다른 항목과 머리말 형식이 다르며 본문에 "Bearish reversal pattern.
**No confirmation is required.**"라고 적혀 있다. **Nison 2판에는 나오지 않는다.**
**추세.** **상승**을 요구한다. **확인.** **`No`**(본문이 명시).

**판정 규칙** (`k = 3`)

1. `UpTrend(t)`.
2. `Black_{t−2}`, `Black_{t−1}`, `Black_t` **그리고** 셋 모두 `LongBody` — 계단처럼
   내려간다. 곧 `C_{t−1} < C_{t−2}`이고 `C_t < C_{t−1}`이다.
3. `Equal(O_{t−1}, C_{t−2}, t−1)` **그리고** `Equal(O_t, C_{t−1}, t)` — 둘째 날과 셋째 날의
   **시가가 각각 앞날의 종가와 같다.**

**출력.** `pat_identical_three_crows` = 1.0. `_dir` = **−1.0**. `_strength` = 1.0.
`_confirm` = 0.0 (원전이 확인을 요구하지 않는다). **`min_history`** = 12.
**우리가 정한 것.** 긴 실체 임계와 "같다"의 허용오차다.

> Morris 해설은 "open at or near the previous day's close"라고 근접을 허용하지만 **규칙 절은
> 등호를 말한다.** 결정 C에 따라 Morris 안에서는 규칙 절이 규범이므로 등호를 채택하고 해설의
> 근접은 주석으로만 남긴다. 다만 §2.6의 `Equal`이 이미 허용오차를 갖고 있으므로 실무에서는
> 두 읽기의 차이가 크지 않다.

#### 7.4.12 Advance Block — `CDLADVANCEBLOCK` → `pat_advance_block`

**원전.** `[M]` 3장, `[N]` 용어사전. Nison은 약해짐이 "tall upper shadows **or** progressively
smaller real bodies"로 나타날 수 있다고 두 갈래로 적으나, **Morris 규칙 절은 긴 위꼬리
하나로 정한다.** 결정 C의 첫째 층에 따라 규칙 절을 규범으로 삼는다.
**추세.** **상승**을 요구한다. **확인.** `Required`.

**판정 규칙** (`k = 3`)

1. `UpTrend(t)`.
2. `White_{t−2}`, `White_{t−1}`, `White_t` **그리고** `C_{t−1} > C_{t−2}`,
   `C_t > C_{t−1}` — 잇달아 더 높게 마감하는 양봉 셋이다. **길이 요건이 없다.** 삼백병과
   다른 점이 이것이다.
3. 각 날이 앞날의 실체 안에서 열린다(7.4.9 규칙 4와 같다).
4. `LongUpperShadow(t−1)` **그리고** `LongUpperShadow(t)` — 둘째 날과 셋째 날에 **긴
   위꼬리**가 있다(§2.4).

**출력.** `pat_advance_block` = 1.0. `_dir` = **−1.0**. `_strength` = 1.0. `_confirm` = 다음
봉 종가 조건. **`min_history`** = 12.
**우리가 정한 것.** **"긴 위꼬리"를 §2.4의 긴 그림자(실체의 두 배 이상)로 옮긴 것**이다.
Morris 유연성 절이 함께 말하는 실체 축소는 결정 C에 따라 주석으로만 남긴다.

#### 7.4.13 Stalled Pattern (Deliberation) — `CDLSTALLEDPATTERN` → `pat_stalled_pattern`

**원전.** `[M]` 3장 Deliberation, `[N]` 6장. Nison은 "If the last two candles are long white
ones that make a new high followed by a small white candle, it is called a stalled
pattern"이라고 적어 **셋째 봉의 색을 양봉으로 못박고 새 고점 조건을 더한다.** 결정 C에 따라
채택한다.
**추세.** 요구한다. **약세형은 상승 추세 뒤, 강세형은 하락 추세 뒤다.**
**확인.** 강세형 `No`, 약세형 `Suggested`.

**판정 규칙** (`k = 3`. 약세형 기준)

1. `UpTrend(t)`.
2. `White_{t−2}` **그리고** `White_{t−1}` **그리고** 둘 다 `LongBody` **그리고**
   `H_{t−1} > H_{t−2}` — 긴 양봉 둘이며 둘째 날이 **새 고점**을 만든다.
3. `White_t` **그리고** `ShortBody(t)` — 셋째 날은 **작은 양봉**이다(Nison 채택).
4. `Near(O_t, C_{t−1}, t)` — 셋째 날이 둘째 날의 종가 **가까이에서** 열린다(§2.6).

강세형은 Morris 규칙 그대로 좌우를 뒤집되, **Nison이 강세형을 따로 적지 않으므로 셋째 봉의
색 조건을 대칭으로 넣지 않는다.**

**출력.** `pat_stalled_pattern` = 1.0. `_dir` = 약세형 **−1.0**, 강세형 **+1.0**.
`_strength` = 1.0. `_confirm` = 다음 봉 종가 조건. **`min_history`** = 12.
**우리가 정한 것.** 긴 실체와 짧은 실체의 임계, 그리고 **"가까이"를 §2.6의 `Near`로 옮긴
것**이다. 갭은 Nison도 "either ... or"로 선택으로 두므로 **필수가 아니며 규칙에 넣지 않는다.**

#### 7.4.14 Three Stars in the South — `CDL3STARSINSOUTH` → `pat_three_stars_in_the_south`

**원전.** `[M]` 3장. **Nison 2판에는 나오지 않는다.**
**추세.** **하락**을 요구한다. **확인.** `Suggested`.

**판정 규칙** (`k = 3`)

1. `DownTrend(t)`.
2. `Black_{t−2}` **그리고** `LongLowerShadow(t−2)` — 첫날은 아래꼬리가 긴 음봉이며 해머와
   비슷한 모양이다.
3. `Black_{t−1}` **그리고** `LongLowerShadow(t−1)` **그리고** `Body_{t−1} < Body_{t−2}`
   **그리고** `L_{t−1} > L_{t−2}` — 둘째 날은 첫날과 같은 모양이되 **더 작고** 저가가 앞날
   저가보다 **위**에 있다.
4. `Black_t` **그리고** `Body_t < Body_{t−1}` **그리고** `NoUpperShadow(t)` **그리고**
   `NoLowerShadow(t)` — 셋째 날은 **앞날보다 더 작은, 꼬리 없는 음봉**이다.
5. `L_{t−1} ≤ L_t` **그리고** `H_t ≤ H_{t−1}` — 셋째 날이 앞날의 **고저 범위 안에서** 열고
   닫는다.

**출력.** `pat_three_stars_in_the_south` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건. **`min_history`** = 12.
**크기 조건을 봉 사이의 비교로 옮긴 자리 둘. 【우리 규약】** 이전 판은 규칙 2에 `LongBody(t−2)`를,
규칙 4에 `ShortBody(t)`를 두었다. **둘 다 어떤 봉도 성립시키지 못했다.**

규칙 2에서는 §2.1의 긴 실체가 `Body > 0.50 · Range`이고 §2.4의 긴 아래그림자가 `LS ≥ 2 · Body`라,
둘을 합치면 `LS > Range`가 되어 아래그림자 하나가 고저 범위 전체를 넘어야 한다. 규칙 4에서는
§2.2의 짧은 실체가 `Body < Range/3`이고 §2.5의 무그림자가 각각 `0.10 · Range` 이하라, `Range =
US + Body + LS`에 넣으면 `Range < 0.533 · Range`가 된다.

**원인은 원전이 아니라 이 표준의 분모 통일이다.** §2는 모든 척도의 분모를 그 봉의 고저 범위로
맞췄는데, Morris는 실체의 크기를 **최근 봉들의 평균 실체**에 견주어 재므로 원문에는 모순이 없다.

**규칙 2에서는 `LongBody`를 뺐고, 규칙 4에서는 `ShortBody`를 `Body_t < Body_{t−1}`로 바꿨다.**
두 자리를 다르게 처리한 근거가 있다. 규칙 2의 "길다"를 살리려면 범위에 견주는 긴 그림자 척도가
있어야 하는데 §2에 없고, 만들면 값을 지어내는 것이 되어 §0을 어긴다. 반면 규칙 4의 "작다"는
**같은 절의 규칙 3이 이미 쓰고 있는 어법**인 실체끼리의 비교로 옮길 수 있다. 그렇게 하면 세 날의
실체가 차례로 작아진다는 Morris의 서술이 그대로 남고 새 값도 생기지 않는다.

**우리가 정한 것.** 넷이다. 긴 그림자와 무꼬리의 임계, **"더 작다"를 실체 크기의 엄격 비교로
옮긴 것**(규칙 3과 규칙 4 둘 다), 위에 적은 크기 조건의 이동, 그리고 **규칙 5의 "range" 해석**이다.

> **【우리 규약】 원문 구조가 모호한 자리다.** Morris 규칙 3은 "opens and closes inside the
> previous day's range"라고 적어 그냥 `range`라고만 쓴다. 이 표준은 **고저 범위**로 읽는다.
> 근거는 같은 절의 규칙 2가 저가를 따로 말해 이 절이 고저를 다루고 있고, Morris가 실체 범위를
> 뜻할 때는 다른 패턴에서 "body range"라고 못박기 때문이다. **실체 범위로 읽는 것도 가능한
> 읽기이며 이 선택은 되돌릴 수 있다.**

#### 7.4.15 Three Inside Up / Down — `CDL3INSIDE` → `pat_three_inside`

**원전.** `[M]` 3장. **Morris가 창안한 패턴이다.** 본문에 "The Three Inside Up and Three
Inside Down patterns are not found in any Japanese literature. We developed them to assist in
improving the overall results of the Harami pattern"이라고 적혀 있다.
**추세.** 요구한다(하라미에서 물려받는다). **확인.** Up은 `No`, Down은 `Required`.

**판정 규칙** (`k = 3`. Three Inside Up 기준)

1. `t−2`와 `t−1`이 **7.3.2 강세형 Harami의 규칙 전부**를 만족한다. 추세 조건도 함께 물려받으며
   첫날은 `f = t − 2`다.
2. `C_t > C_{t−1}` — 셋째 날의 **종가가 둘째 날의 종가보다 높다.** **엄격 부등식**이다.

Three Inside Down은 약세형 하라미를 쓰고 `C_t < C_{t−1}`이다.

**출력.** `pat_three_inside` = 1.0. `_dir` = Up **+1.0**, Down **−1.0**. `_strength` =
하라미의 포함에서 한쪽 끝이 일치하면 0.5, 아니면 1.0. `_confirm` = 다음 봉 종가 조건.
**`min_history`** = 12.
**우리가 정한 것.** 하라미가 쓰는 긴 실체와 짧은 실체의 임계, 그리고 **규칙 2의 비교
대상**이다. Morris 해설이 "A bullish Harami followed by a third day that closes higher"라고
적어 하라미 **다음** 날을 가리키므로 비교 대상을 둘째 날의 종가로 읽었다.

#### 7.4.16 Three Outside Up / Down — `CDL3OUTSIDE` → `pat_three_outside`

**원전.** `[M]` 3장. **Morris가 창안한 패턴이다.** 규칙의 제목이 다른 항목과 달리
`Pattern Recognition`이다. 본문에 "not found in any Japanese literature. We developed them to
assist in improving the overall results of the Engulfing pattern"이라고 적혀 있다.
**추세.** 요구한다(장악형에서 물려받는다). **확인.** Up은 `No`, Down은 `Required`.

**판정 규칙** (`k = 3`. Three Outside Up 기준)

1. `t−2`와 `t−1`이 **7.3.1 강세형 Engulfing의 규칙 전부**를 만족한다.
2. `C_t > C_{t−1}` — 셋째 날의 **종가가 둘째 날의 종가보다 높다.**

Three Outside Down은 약세형 장악형을 쓰고 `C_t < C_{t−1}`이다.

**출력.** `pat_three_outside` = 1.0. `_dir` = Up **+1.0**, Down **−1.0**. `_strength` =
장악형의 감쌈에서 한쪽 끝이 일치하면 0.5, 아니면 1.0. `_confirm` = 다음 봉 종가 조건.
**`min_history`** = 12.
**우리가 정한 것.** **없다.** 장악형이 척도를 쓰지 않고 등호 처리도 원전이 명시했으며, 규칙
2의 비교 대상은 Morris 해설이 준다. 추세 판정만 §3에서 온다.

> Morris는 "Confirmation patterns do not have any more flexibility than the underlying
> pattern"이라고 적어 확인 패턴이 바탕 패턴보다 느슨해질 수 없다고 밝힌다. 규칙 1이 장악형의
> 규칙을 **전부** 물려받는 것이 그 뜻이다.

#### 7.4.17 Unique Three River Bottom — `CDLUNIQUE3RIVER` → `pat_unique_three_river`

**원전.** `[M]` 3장. **Nison 2판에는 나오지 않는다.**
**추세.** **하락**을 요구한다. **확인.** `Required`.

**판정 규칙** (`k = 3`)

1. `DownTrend(t)`.
2. `Black_{t−2}` **그리고** `LongBody(t−2)` — 첫날은 긴 음봉이다.
3. `Black_{t−1}` **그리고** `Contain(t−2, t−1)` — 둘째 날은 하라미이되 **실체도 음봉**이다.
   포함 관계는 §4.1을 따른다.
4. `L_{t−1} < L_{t−2}` — 둘째 날의 아래꼬리가 **새 저점**을 만든다. 규칙 3의 포함이 실체에만
   걸리므로 꼬리는 밖으로 나갈 수 있다.
5. `White_t` **그리고** `ShortBody(t)` — 셋째 날은 짧은 양봉이다.
6. `BodyTop_t < BodyBot_{t−1}` — 셋째 날의 실체가 **가운데 날의 실체보다 아래**에 있다.

**출력.** `pat_unique_three_river` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건. **`min_history`** = 12.
**우리가 정한 것.** 긴 실체와 짧은 실체의 임계, 그리고 **규칙 6의 비교 대상**이다.

> **【우리 규약】 원문 구조가 모호한 자리다.** Morris 규칙 4는 "a short white day that is
> below the middle day"라고만 적어 **무엇이 무엇보다 아래인지**를 정하지 않는다. 셋째 날의
> 실체 전체가 가운데 날의 실체 아래인지, 종가끼리 비교하는지, 저가끼리 비교하는지 세 읽기가
> 있다. 이 표준은 **실체 전체가 아래**라는 가장 강한 읽기를 골랐다. 근거는 "below the middle
> day"가 봉 전체를 가리키는 표현이고, 종가만 비교하면 두 실체가 겹쳐도 성립해 "아래"라는
> 낱말과 어긋나기 때문이다. **이 선택은 되돌릴 수 있다.**

#### 7.4.18 Concealing Baby Swallow — `CDLCONCEALBABYSWALL` → `pat_concealing_baby_swallow`

**원전.** `[M]` 3장. **Nison 2판에는 나오지 않는다.** 네 봉짜리이나 세 캔들 묶음에 함께 둔다.
**추세.** **하락**을 요구한다. **확인.** `No`.

**판정 규칙** (`k = 4`)

1. `DownTrend(t)`. 첫날은 `f = t − 3`이다.
2. `t−3`과 `t−2`가 각각 **Black Marubozu**다(7.2.2의 규칙에 음봉).
3. `Black_{t−1}` **그리고** `GapDnBody(t−2, t−1)` **그리고** `H_{t−1} > BodyBot_{t−2}`
   **그리고** `LongUpperShadow(t−1)` — 셋째 날은 갭 하락으로 열리되 앞날의 실체 안까지
   거래되어 **긴 위꼬리**를 만든다.
4. `Black_t` **그리고** `H_t ≥ H_{t−1}` **그리고** `L_t ≤ L_{t−1}` — 넷째 날 음봉이 셋째
   날을 **꼬리까지 포함해 완전히 감싼다.** 원문이 "including the shadow"라고 명시하므로
   §4.1의 실체 감쌈이 아니라 고저 범위 감쌈이다.

**출력.** `pat_concealing_baby_swallow` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0.
`_confirm` = 0.0 (원전이 확인을 요구하지 않는다). **`min_history`** = 13.
**우리가 정한 것.** Marubozu 판정에 쓰는 임계, "긴 위꼬리"의 §2.4 적용, 그리고 **갭의
종류**다. 원문이 "a down gap open"이라고만 적으므로 §2.8의 규약에 따라 **실체 사이의 갭**으로
읽는다.

### 7.5 네 봉 이상과 갭 지속형 (10종)

#### 7.5.1 Three-Line Strike — `CDL3LINESTRIKE` → `pat_three_line_strike`

**원전.** `[M]` 4장. 규칙 절은 "Three days resembling Three White Soldiers"라고 느슨하게
적으나 **바로 앞의 해설이 구체적이다.** "Three white days with consecutively higher highs are
followed by a long black day. This long black day opens at a new high and then plummets to a
lower low than the first white day of the pattern." 결정 C에 따라 해설을 규범으로 채택한다.
유형은 **지속형**이다.
**추세.** 요구한다. **강세형은 상승 추세 뒤, 약세형은 하락 추세 뒤다.**
**확인.** 강세형 `No`, 약세형 `Suggested`.

**판정 규칙** (`k = 4`. 강세형 기준)

1. `UpTrend(t)`. 첫날은 `f = t − 3`이다.
2. `White_{t−3}`, `White_{t−2}`, `White_{t−1}` **그리고** `H_{t−2} > H_{t−3}`,
   `H_{t−1} > H_{t−2}` — 양봉 셋이 이어지며 **고가가 잇달아 높아진다.** **엄격 부등식**이다.
3. `Black_t` **그리고** `LongBody(t)` — 넷째 날은 **긴 음봉**이다.
4. `O_t > H_{t−1}` — 넷째 날이 **새 고점에서** 열린다.
5. `L_t < L_{t−3}` **그리고** `C_t < O_{t−3}` — 넷째 날의 저가가 첫 양봉의 저가보다 낮고
   종가가 첫 양봉의 시가 아래다.

약세형은 좌우를 뒤집으며 넷째 날이 **첫 음봉의 고가 위로** 마감한다. 원문이 약세형에서
"close above the high of the first black day"라고 적어 시가가 아니라 고가를 말하므로 그
비대칭을 그대로 둔다.

**출력.** `pat_three_line_strike` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**(지속형이므로
추세 방향이다). `_strength` = 1.0. `_confirm` = 다음 봉 종가 조건. **`min_history`** = 13.
**우리가 정한 것.** 긴 실체 임계뿐이다. 나머지는 해설이 준다.

#### 7.5.2 Breakaway — `CDLBREAKAWAY` → `pat_breakaway`

**원전.** `[M]` 3장. **약세형은 Morris가 만든 것이다.** "Japanese literature does not discuss
a bearish version of the Breakaway pattern. I decided to test such a pattern and have found
that it works quite well."
**추세.** 요구한다. **강세형은 하락 추세 뒤, 약세형은 상승 추세 뒤다.**
**확인.** 양쪽 모두 `Suggested`.

**판정 규칙** (`k = 5`. 강세형 기준)

1. `DownTrend(t)`. 첫날은 `f = t − 4`다.
2. `Black_{t−4}` **그리고** `LongBody(t−4)` — 첫날은 추세색의 긴 날이다.
3. `Black_{t−3}` **그리고** `GapDnBody(t−4, t−3)` — 둘째 날은 같은 색이며 **실체가 추세
   방향으로 갭**을 이룬다.
4. `C_{t−2} < C_{t−3}` **그리고** `C_{t−1} < C_{t−2}` — 셋째 날과 넷째 날이 추세 방향을
   이어 가며 종가가 잇달아 낮아진다. **색은 요구하지 않는다.** Morris가 "It is better if"로
   적어 권고로 두기 때문이다.
5. `White_t` **그리고** `LongBody(t)` **그리고** `BodyTop_{t−3} < C_t < BodyBot_{t−4}` —
   다섯째 날은 **반대색의 긴 날**이며 첫날과 둘째 날이 만든 **갭 안에서** 마감한다.

약세형은 좌우를 뒤집는다.

**출력.** `pat_breakaway` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건. **`min_history`** = 14.
**우리가 정한 것.** 긴 실체 임계뿐이다.

> **봉 수는 다섯으로 고정한다.** Morris 유연성 절은 "There could be more than three days
> after the gap ... It is also possible to have at least two days after the gap"이라고 적어
> 봉 수를 넓히지만, **결정 C의 첫째 층에 따라 Morris 안에서는 규칙 절이 규범이므로 유연성
> 절은 주석으로만 남긴다.** 이 고정이 §6의 `min_history`와 상태 상한을 확정한다.

#### 7.5.3 Ladder Bottom — `CDLLADDERBOTTOM` → `pat_ladder_bottom`

**원전.** `[M]` 3장. **Nison 2판에는 나오지 않는다.**
**추세.** **하락**을 요구한다. **확인.** `No`.

**판정 규칙** (`k = 5`)

1. `DownTrend(t)`. 첫날은 `f = t − 4`다.
2. `Black_{t−4}`, `Black_{t−3}`, `Black_{t−2}` **그리고** 셋 모두 `LongBody` **그리고**
   `O_{t−3} < O_{t−4}`, `O_{t−2} < O_{t−3}`, `C_{t−3} < C_{t−4}`, `C_{t−2} < C_{t−3}` —
   시가와 종가가 잇달아 낮아지는 **긴 음봉 셋**이다.
3. `Black_{t−1}` **그리고** `¬NoUpperShadow(t−1)` — 넷째 날은 **위꼬리가 있는** 음봉이다.
4. `White_t` **그리고** `O_t > BodyTop_{t−1}` — 마지막 날은 양봉이며 **앞날의 실체 위에서**
   열린다. 갭이 아니라 시가의 위치 비교다.

**출력.** `pat_ladder_bottom` = 1.0. `_dir` = **+1.0**. `_strength` = 1.0. `_confirm` = 0.0
(원전이 확인을 요구하지 않는다). **`min_history`** = 14.
**우리가 정한 것.** 긴 실체 임계와, **규칙 3의 "위꼬리가 있다"를 §2.5의 부정으로 옮긴
것**이다. 곧 위꼬리가 고저 범위의 10퍼센트를 넘으면 "있다"고 본다. 원전은 이 자리에 크기를
주지 않으며, 단순히 `US > 0`으로 읽으면 부동소수 잡음이 그대로 통과한다.

> Morris 유연성 절은 네 음봉의 길이 요건을 완화하고 연속 하락 종가와 마지막 종가 조건을
> 더하지만, **결정 C의 첫째 층에 따라 넓히든 좁히든 모두 주석으로만 남긴다.**

#### 7.5.4 Mat Hold — `CDLMATHOLD` → `pat_mat_hold`

**원전.** `[M]` 4장. 규칙 절의 강세형은 "almost a starlike day"처럼 정성적이나 **해설이
구체적이다.** "The first three days start out like the Upside Gap Two Crows, with the
exception that the second black body (third day) dips into the body of the first long white
day. This is followed by another small black body that closes even lower, but still within
the range of the first white body. The fifth day sees a large gap opening, with a strong rise
to a close above the high of the highest of the three black days." 결정 C에 따라 해설을
규범으로 채택한다. 유형은 **지속형**이다.
**추세.** 요구한다. **강세형은 상승 추세 뒤, 약세형은 하락 추세 뒤다.**
**확인.** 강세형 `No`, 약세형 `Suggested`.

**판정 규칙** (`k = 5`. 강세형 기준)

1. `UpTrend(t)`. 첫날은 `f = t − 4`다.
2. `White_{t−4}` **그리고** `LongBody(t−4)` — 첫날은 긴 양봉이다.
3. `Black_{t−3}` **그리고** `GapUpBody(t−4, t−3)` — 둘째 날은 첫 실체 위로 **실체 갭**을
   이루는 음봉이다.
4. `Black_{t−2}` **그리고** `C_{t−2} < BodyTop_{t−4}` **그리고** `C_{t−2} > BodyBot_{t−4}` —
   셋째 날은 음봉이며 **첫 양봉의 실체 안으로 파고든다.**
5. `Black_{t−1}` **그리고** `ShortBody(t−1)` **그리고** `C_{t−1} < C_{t−2}` **그리고**
   `L_{t−1} ≥ L_{t−4}` — 넷째 날은 **작은 음봉**이며 셋째 날보다 낮게 마감하되 **첫 양봉의
   고저 범위 안**에 머문다.
6. `White_t` **그리고** `C_t > max(H_{t−3}, H_{t−2}, H_{t−1})` — 다섯째 날은 양봉이며 **세
   음봉의 최고 고가 위에서** 마감한다.

약세형은 규칙 절이 이미 구체적이므로 그것을 그대로 좌우 대칭으로 쓴다.

**출력.** `pat_mat_hold` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건. **`min_history`** = 14.
**우리가 정한 것.** 긴 실체와 짧은 실체의 임계뿐이다. **TA-Lib의 `penetration` 0.5는 원전에
근거를 찾지 못했으므로 쓰지 않는다.**

> 해설이 규칙 절의 "새 종가 고점"을 "세 음봉의 최고 고가 위"로 바꾸므로 어느 쪽을 쓰는지
> 밝혀 둔다. **결정 C에 따라 더 좁은 해설 쪽을 쓴다.**

#### 7.5.5 Rising / Falling Three Methods — `CDLRISEFALL3METHODS` → `pat_rise_fall_three_methods`

**원전.** `[M]` 4장, `[N]` 7장. **작은 캔들의 개수를 Nison이 유한 범위로 닫는다.** "The ideal
number of small candles is three but two or more than three are also acceptable if they hold
within the long white candle's high-low range"라고 적고, 이어 "Nonetheless, from my
experience, two and up to five small real bodies work fine"이라고 적는다. 유형은 **지속형**이다.
**추세.** 요구한다. **강세형은 상승 추세 뒤, 약세형은 하락 추세 뒤다.**
**확인.** Rising은 `No`, Falling은 `Suggested`.

**판정 규칙** (`k = n + 2`, `n`은 작은 캔들의 수이며 **2 이상 5 이하**다. 강세형 기준)

1. `UpTrend(t)`. 첫날은 `f = t − (n + 1)`이다.
2. `White_f` **그리고** `LongBody(f)` — 현재 추세를 나타내는 긴 양봉이다.
3. 이어지는 `n`개 봉이 모두 `ShortBody`다. **색은 요구하지 않는다.** Morris가 "It is best
   if they are opposite in color"로 적어 권고로 두기 때문이다.
4. 그 `n`개 봉이 모두 **첫날의 고저 범위 안에 머문다.** 곧 각 봉 `j`에 대해 `H_j ≤ H_f`이고
   `L_j ≥ L_f`다. Morris 규칙 3이 "the high-low range of the first day"라고 못박는다.
5. `White_t` **그리고** `LongBody(t)` **그리고** `C_t > C_f` — 마지막 날은 **강한 날**이며
   첫날의 종가 바깥에서 원래 추세 방향으로 마감한다.

약세형은 좌우를 뒤집는다.

**출력.** `pat_rise_fall_three_methods` = 1.0. `_dir` = 강세형 **+1.0**, 약세형 **−1.0**.
`_strength` = 1.0. `_confirm` = 다음 봉 종가 조건.
**`min_history`** = **13** (`n = 2`, 곧 `k = 4`일 때 첫 판정이 가능하다). 상태는 최대
`k = 7`봉을 보관한다.

> **이 패턴만 `min_history`의 뜻이 인덱스에 따라 다르다는 점을 밝혀 둔다.** 봉 수가 범위인
> 유일한 패턴이기 때문이다. 인덱스 12에서는 `n = 2` 형태만 검사할 수 있고, 봉이 쌓이면서
> `n = 3`, `n = 4`, `n = 5`가 차례로 검사 가능해져 **인덱스 15부터 다섯 형태가 모두 검사된다.**
> 곧 인덱스 12부터 14까지의 `0.0`은 "그 시점에 검사할 수 있었던 형태 가운데 성립하는 것이
> 없다"는 뜻이고, 인덱스 15 이후의 `0.0`은 "허용된 다섯 형태 가운데 성립하는 것이 없다"는
> 뜻이다. **가장 짧은 형태를 기준으로 `min_history`를 잡은 것은 신호를 늦추지 않기 위해서다.**
> 가장 긴 형태를 기준으로 16을 잡으면 인덱스 12부터 15까지 실제로 성립한 `n = 2` 형태를
> 놓치게 되며, 놓치는 쪽이 뜻이 균일한 것보다 나쁘다고 보았다. 소비자가 이 차이를 알아야
> 하므로 여기에 적는다.
**우리가 정한 것.** 셋이다.

> **첫째, 작은 캔들의 수를 2 이상 5 이하로 정했다.** Nison이 "two and up to five ... work
> fine"이라고 적은 범위를 그대로 쓴다. **상한 없는 범위는 쓰지 않는다.** 원전이 상한을
> 주었기 때문이며, 이 확정이 창 길이를 유한하게 만들어 상태 보관량과 `min_history`를
> 확정한다. 여러 `n`이 동시에 성립하면 **가장 작은 `n`**을 채택한다. 같은 봉에서 패턴이 두
> 번 성립하지 않게 하기 위한 규약이다.
> **둘째, "강한 날"을 §2.1의 긴 실체로 옮겼다.** 원전이 "a strong day"라고만 적고 숫자를
> 주지 않으므로, 이 표준이 이미 가진 척도 가운데 "강하다"에 가장 가까운 것을 썼다.
> **셋째, 긴 실체와 짧은 실체의 임계**다.

#### 7.5.6 Up/Down-gap Side-by-side White Lines — `CDLGAPSIDESIDEWHITE` → `pat_gap_side_by_side_white`

**원전.** `[M]` 4장, `[N]` 7장·용어사전. **시가 조건에서 두 원전이 갈린다.** Nison은 "Two
consecutive white candlesticks that have the **same open**"이라고 못박고 Morris는 "opens at
about the same price"라고 느슨하게 둔다. **결정 C에 따라 좁은 쪽인 Nison을 채택한다.**
유형은 **지속형**이다.
**추세.** 요구한다. **상승 갭 형은 상승 추세 뒤, 하락 갭 형은 하락 추세 뒤다.**
**확인.** 강세형 `Suggested`, 약세형 `Required`.

**판정 규칙** (`k = 3`. 상승 갭 형 기준)

1. `UpTrend(t)`. 첫날은 `f = t − 2`다.
2. `GapUpBody(t−2, t−1)` — 첫날과 둘째 날 사이에 **추세 방향으로 실체 갭**이 있다.
3. `White_{t−1}` **그리고** `White_t` — 둘째 날과 셋째 날이 모두 양봉이다.
4. `Equal(O_t, O_{t−1}, t)` — 두 날의 **시가가 같다**(§2.6).
5. `SimilarBody(t−1, t)` — 두 실체의 **크기가 서로 비슷하다**(§2.6).

하락 갭 형은 갭의 방향과 추세만 뒤집고 **두 봉은 그대로 양봉이다.** Nison이 "In a downtrend,
these side-by-side white lines are still considered bearish (in spite of their white
candles)"라고 적기 때문이다.

**출력.** `pat_gap_side_by_side_white` = 1.0. `_dir` = 상승 갭 형 **+1.0**, 하락 갭 형
**−1.0**. `_strength` = 1.0. `_confirm` = 다음 봉 종가 조건. **`min_history`** = 12.
**우리가 정한 것.** "같다"의 허용오차, "비슷한 크기"의 기준(§2.6), 그리고 **갭의 종류**다.
원문이 "A gap is made in the direction of the trend"라고만 적어 종류를 구분하지 않으므로
§2.8의 규약에 따라 **실체 사이의 갭**으로 읽는다.

#### 7.5.7 Tasuki Gap — `CDLTASUKIGAP` → `pat_tasuki_gap`

**원전.** `[M]` 4장, `[N]` 7장·용어사전. **Nison이 조건 둘을 더한다.** "The two candles of
the tasuki should be about the same size"와 "The close on the black candle day is the fight
point. If the market closes under the bottom of the window, the bullish outlook of the upward
gap tasuki is voided." **결정 C에 따라 둘 다 채택한다.** 유형은 **지속형**이다.
**추세.** 요구한다. **상승 타스키는 상승 추세 뒤, 하락 타스키는 하락 추세 뒤다.**
**확인.** 상승형 `Suggested`, 하락형 `Required`.

**판정 규칙** (`k = 3`. 상승 타스키 기준)

1. `UpTrend(t)`. 첫날은 `f = t − 2`다.
2. `White_{t−2}` **그리고** `White_{t−1}` **그리고** `GapUpBody(t−2, t−1)` — 같은 색 캔들
   둘 사이에 **실체 갭**이 있고 그 색이 추세를 나타낸다.
3. `SimilarBody(t−2, t−1)` — 두 캔들의 **실체 크기가 서로 비슷하다**(§2.6, Nison 채택).
4. `Black_t` **그리고** `BodyBot_{t−1} < O_t < BodyTop_{t−1}` — 셋째 날은 반대색이며
   **둘째 날의 실체 안에서** 열린다.
5. `C_t < BodyBot_{t−1}` **그리고** `C_t > BodyTop_{t−2}` — 셋째 날의 종가가 갭 안으로
   들어오되 **갭의 반대쪽 끝을 넘지 않는다.** 종가가 창의 아래쪽 밑으로 내려가면 무효다
   (Nison 채택).

하락 타스키는 좌우를 뒤집는다.

**출력.** `pat_tasuki_gap` = 1.0. `_dir` = 상승형 **+1.0**, 하락형 **−1.0**. `_strength` = 1.0.
`_confirm` = 다음 봉 종가 조건. **`min_history`** = 12.
**우리가 정한 것.** **"비슷한 크기"의 기준(§2.6)뿐이다.** 갭의 종류와 무효화 기준은 원전이
주었다.

#### 7.5.8 Upside / Downside Gap Three Methods — `CDLXSIDEGAP3METHODS` → `pat_gap_three_methods`

**원전.** `[M]` 4장. 규칙 절 앞의 해설이 셋째 날을 구체화한다. "The third day opens within
the body of the second candlestick and then closes within the body of the first candlestick
(bridging the first and second candles), which would also make it the opposite color of the
first two days." 결정 C에 따라 해설을 규범으로 채택한다. **Nison 2판에는 나오지 않는다.**
유형은 **지속형**이다.
**추세.** 요구한다. **Upside는 상승 추세 뒤, Downside는 하락 추세 뒤다.**
**확인.** Upside는 `No`, Downside는 `Required`.

**판정 규칙** (`k = 3`. Upside 기준)

1. `UpTrend(t)`. 첫날은 `f = t − 2`다.
2. `White_{t−2}` **그리고** `White_{t−1}` **그리고** 둘 다 `LongBody` **그리고**
   `GapUpBody(t−2, t−1)` — **긴 양봉 둘** 사이에 실체 갭이 있다.
3. `Black_t` **그리고** `BodyBot_{t−1} < O_t < BodyTop_{t−1}` — 셋째 날은 음봉이며 둘째
   실체 **안에서 열린다.**
4. `BodyBot_{t−2} < C_t < BodyTop_{t−2}` — 셋째 날이 첫 실체 **안에서 마감한다.** 이것이
   원전이 말하는 "갭을 메운다"의 뜻이다.

Downside는 좌우를 뒤집는다.

**출력.** `pat_gap_three_methods` = 1.0. `_dir` = Upside **+1.0**, Downside **−1.0**.
`_strength` = 1.0. `_confirm` = 다음 봉 종가 조건. **`min_history`** = 12.
**우리가 정한 것.** 긴 실체 임계뿐이다.

#### 7.5.9 Hikkake — `CDLHIKKAKE` → `pat_hikkake`

**원전.** `[Ch]`. **이 패턴은 일본식 캔들 패턴이 아니다.** Chesler는 서양 용어로 "inside day
false breakout"이 옳은 이름이라고 적고, **시가와 종가를 쓰지 않는다**고 못박는다. "the basic
hikkake pattern ignores the open-to-close relationship, also known in candlestick terminology
as the 'real body' portion of the price bar."
**추세.** **요구하지 않는다.** 기사는 이 패턴이 반전형과 지속형 양쪽으로 기능한다고 적는다.
**확인.** **필수이며 기한이 3봉이다**(원전이 준다).

**판정 규칙** (`k = 3`. 강세 설정 기준)

1. `H_{t−1} < H_{t−2}` **그리고** `L_{t−1} > L_{t−2}` — `t−1`이 **인사이드 바**다. 앞 봉보다
   고가가 낮고 저가가 높다. **엄격 부등식**이다.
2. `L_t < L_{t−1}` **그리고** `H_t < H_{t−1}` — 강세 설정은 인사이드 바보다 저가와 고가가
   **모두 낮다.** 약세 설정은 둘 다 높다. **극성이 뒤집혀 있다는 점을 놓치기 쉽다.** 위로
   뚫고 나가는 것이 약세 설정이다.
3. **확인.** 강세 설정이면 이후 어느 봉의 가격이 **인사이드 바의 고가 위로** 올라설 때,
   약세 설정이면 **저가 아래로** 내려갈 때 확인이 일어난다.
4. **확인은 패턴으로부터 3봉 안에 일어나야 하며, 그렇지 않으면 그 패턴은 무시한다.**

**출력.** `pat_hikkake` = 1.0(설정이 성립한 봉, 곧 `t`). `_dir` = 강세 설정 **+1.0**, 약세
설정 **−1.0**. `_strength` = 1.0. `_confirm` = 확인이 일어난 봉에서 1.0이며 그 봉은 `t`보다
뒤다(§5.4). 3봉 안에 오지 않으면 그 구간 내내 0.0으로 남는다.
**`min_history`** = **3** (추세를 요구하지 않으므로 `k`와 같다).
**우리가 정한 것.** **없다.** 척도를 쓰지 않고 확인의 내용과 기한을 원전이 모두 주었다.

> **입력으로 필요한 봉은 셋이다.** Chesler가 설정을 두 봉이라 부르지만 첫 봉이 인사이드
> 바인지 판단하려면 그 앞 봉이 있어야 한다. 확인까지 보면 최대 여섯 봉이 필요하나, §6이
> 밝힌 대로 확인 지연은 `min_history`에 더하지 않는다.

#### 7.5.10 Modified Hikkake — `CDLHIKKAKEMOD` → `pat_hikkake_modified`

**원전.** `[Ch]`. 기본형에 **인사이드 바 바로 앞 봉**에 대한 요건 둘을 더한다. "1. The bar
must close at the top of its range (for bearish patterns) or the low of its range (for
bullish patterns). 2. The range must be less than the range of the previous bar." 기사는 이
변형이 기본형보다 훨씬 드물며 주로 추세 반전형으로 기능한다고 덧붙인다.
**추세.** **요구하지 않는다.** **확인.** **필수이며 기한이 3봉이다.**

**판정 규칙** (`k = 4`. 강세 설정 기준)

1. 7.5.9 Hikkake의 규칙 전부를 만족한다. 인사이드 바는 `t−1`이고 맥락 봉은 `t−2`다.
2. `C_{t−2} = L_{t−2}` — 강세형이면 맥락 봉이 자기 범위의 **바닥에서** 마감한다. 약세형이면
   `C_{t−2} = H_{t−2}`, 곧 **꼭대기에서** 마감한다.
3. `Range_{t−2} < Range_{t−3}` — 맥락 봉의 고저 범위가 **그 바로 앞 봉의 고저 범위보다
   작다.** **엄격 부등식**이다.

**출력.** `pat_hikkake_modified` = 1.0(설정이 성립한 봉 `t`). `_dir` = 강세 설정 **+1.0**,
약세 설정 **−1.0**. `_strength` = 1.0. `_confirm` = 확인이 일어난 봉에서 1.0이며 그 봉은
`t`보다 뒤다(§5.4). 3봉 안에 오지 않으면 그 구간 내내 0.0으로 남는다.
**`min_history`** = **4**.
**우리가 정한 것.** **없다.** Chesler가 "The bar **must** close at the top of its range"라고
**단정**하므로 규칙 2는 등호이며 근접 허용오차를 두지 않는다.

> **원문이 단정이므로 §4.2의 "꼬리가 없다" 규약을 여기에 적용하지 않는다.** 그 결과 종가와
> 고가(또는 저가)가 정확히 같은 봉이 드물어 발생 빈도가 매우 낮아진다. Chesler 자신도 "This
> version occurs far less frequently in the data than the basic hikkake pattern"이라고 적어
> 그 점을 예고한다. **빈도가 낮다는 이유로 허용오차를 도입하는 것은 원전을 바꾸는 것이므로
> 하지 않는다.**

---

## §8. 커버리지 집계

### 8.1 계열별 수록 패턴

| 계열 | 수록 패턴 | 개수 |
|---|---|---|
| §7.1 도지 계열과 우산형 | Doji, Long-Legged Doji, Rickshaw Man, Dragonfly Doji, Gravestone Doji, Takuri, Hammer, Hanging Man, Inverted Hammer, Shooting Star, Spinning Top | 11 |
| §7.2 몸통과 그림자의 형태 | High-Wave, Marubozu, Closing Marubozu, Belt-hold, Long Line, Short Line | 6 |
| §7.3 두 캔들과 그에 준하는 것 | Engulfing, Harami, Harami Cross, Doji Star, Piercing, Dark Cloud Cover, Counterattack, Separating Lines, Kicking, Kicking by Length, Homing Pigeon, Matching Low, In-Neck, On-Neck, Thrusting, Stick Sandwich | 16 |
| §7.4 세 캔들 | Morning Star, Evening Star, Morning Doji Star, Evening Doji Star, Abandoned Baby, Tri Star, Two Crows, Upside Gap Two Crows, Three White Soldiers, Three Black Crows, Identical Three Crows, Advance Block, Stalled Pattern, Three Stars in the South, Three Inside, Three Outside, Unique Three River, Concealing Baby Swallow | 18 |
| §7.5 네 봉 이상과 갭 지속형 | Three-Line Strike, Breakaway, Ladder Bottom, Mat Hold, Rising/Falling Three Methods, Gap Side-by-side White Lines, Tasuki Gap, Gap Three Methods, Hikkake, Modified Hikkake | 10 |
| **합계** | | **61** |

> **이 61은 기존 지표 표준의 89에 더하지 않는다.** 두 표준은 나란히 서는 별개의 문서이고
> 패턴은 자체 레지스트리를 가지며 `DEFAULT_REGISTRY`에 등록되지 않는다.
> `services/core-lib/tests/test_indicator_registry.py`가 붙들고 있는 89라는 숫자는 이 표준으로
> 움직이지 않는다.
>
> **세는 규칙 명시.** 위 표는 TA-Lib의 `CDL` 함수 하나를 한 항목으로 센다. 방향이 갈리는
> 패턴(Engulfing의 강세형과 약세형 등)을 둘로 펼치면 수가 늘고, Kicking과 Kicking by Length를
> 하나로 묶으면 −1이 되어 60이 된다. Three Inside와 Three Outside를 Up과 Down으로 펼치면 +2다.

### 8.2 추세 요구 여부

**45종이 직전 추세를 요구하고 16종은 요구하지 않는다.** 요구하지 않는 16종은 성격이 셋으로
갈린다.

| 갈래 | 패턴 | 개수 |
|---|---|---|
| Morris가 캔들 **선**으로 다루어 머리말 필드가 없다 | Doji, Long-Legged Doji, Rickshaw Man, Dragonfly Doji, Gravestone Doji, Takuri, Spinning Top, High-Wave, Marubozu, Closing Marubozu, Long Line, Short Line | 12 |
| Morris가 `Trend Required: No`라고 **명시**했다 | Kicking, Kicking by Length | 2 |
| 원전이 일본식 캔들 체계 밖이라 추세를 조건으로 두지 않는다 | Hikkake, Modified Hikkake | 2 |

Morris의 89개 머리말 가운데 `Trend Required: No`는 Kicking 둘뿐이다.

### 8.3 `min_history` 분포

§6의 두 식에서 나온다. 추세를 요구하지 않으면 `k`, 요구하면 `k + 9`다.

| `min_history` | 개수 | 패턴 |
|---|---|---|
| 1 | 12 | 추세를 요구하지 않는 단일 봉 12종 |
| 2 | 2 | Kicking, Kicking by Length |
| 3 | 1 | Hikkake |
| 4 | 1 | Modified Hikkake |
| 10 | 4 | Hammer, Hanging Man, Inverted Hammer, Belt-hold |
| 11 | 14 | Shooting Star와 두 캔들 추세형 13종 |
| 12 | 21 | 세 캔들 추세형 21종 |
| 13 | 3 | Concealing Baby Swallow, Three-Line Strike, Rising/Falling Three Methods |
| 14 | 3 | Breakaway, Ladder Bottom, Mat Hold |
| **합계** | **61** | |

### 8.4 우리가 값을 정한 자리

결정 A에 따라 이 표준이 채운 값을 한자리에 모은다. **아래는 모두 원저자의 정의가 아니다.**

| # | 자리 | 값 | 근거의 성격 |
|---|---|---|---|
| 1 | 척도의 분모 | 그 봉의 고저 범위 | Morris가 허용한 세 방법 가운데 선택(§2 앞머리) |
| 2 | 긴 실체 | `> 0.50 · Range` | **【원전】** Morris가 되풀이한 값 |
| 3 | 짧은 실체 | `< (1/3) · Range` | **【우리 규약·유도】** Morris의 Spinning Top 규칙에서 유도(§2.2) |
| 4 | 도지 허용오차 | `≤ 0.03 · Range` | 형식은 원전, **값은 우리 규약**(Morris의 1~3퍼센트 가운데 상단) |
| 5 | 긴 그림자 | `≥ 2.0 · Body` | **【원전】** Nison과 Morris가 같은 값을 준다 |
| 6 | 매우 짧은 그림자 | `≤ 0.10 · Range` | 형식과 예시값은 원전, **채택은 우리 규약** |
| 7 | "같다" | `≤ 0.03 · Range` | **【원전 지시】** Morris 6장이 도지 개념을 쓰라고 지시 |
| 8 | "가깝다" | `≤ 0.10 · Range` | **【우리 규약】** 매우 짧은 그림자와 같은 값(§2.6) |
| 9 | "비슷한 크기" | 작은 쪽 ≥ 큰 쪽의 0.50배 | **【우리 규약】** 원전에 숫자가 없다 |
| 10 | 퇴화 봉 규칙 | §2.7의 둘 | **【우리 규약】** 어느 원전도 다루지 않는다 |
| 11 | 부등식 규약 | §4.2의 표 | Engulfing만 원전, 나머지는 **우리 규약** |
| 12 | 갭이 미구분인 다섯 | 실체 사이의 갭 | **【우리 규약】**(§2.8) |
| 13 | 별 계열 침투 깊이 | 첫 실체의 50퍼센트 초과 | **【우리 규약】** 이웃 패턴의 원전 값을 유추 적용 |
| 14 | 확인의 내용(일반) | 다음 봉 종가가 방향대로 | **【우리 규약】**(§5.5) |
| 15 | 확인의 기한(일반) | 1봉 | **【우리 규약】**(§5.5) |
| 16 | Harami Cross의 `range` | 실체 범위 | **【우리 규약】** 원문이 모호(§7.3.3) |
| 17 | Unique Three River의 "아래" | 실체 전체가 아래 | **【우리 규약】** 원문이 모호(§7.4.17) |
| 18 | Three Stars in the South의 `range` | 고저 범위 | **【우리 규약】** 원문이 모호(§7.4.14) |
| 19 | Three Methods의 작은 캔들 수 | 2 이상 5 이하, 최소 `n` 채택 | **【원전 범위】** Nison, 다만 "최소 `n`"은 우리 규약 |
| 20 | Three Methods의 "강한 날" | 긴 실체 | **【우리 규약】**(§7.5.5) |
| 21 | Kicking by Length의 "더 긴 쪽" | 실체 길이, 동률은 불성립 | **【우리 규약】**(§7.3.10) |
| 22 | High-Wave와 Spinning Top의 경계 | 그림자가 실체의 2배 이상인가 | **【우리 규약】**(§7.2.1) |
| 23 | In-Neck과 Thrusting의 경계 | `Equal`이면 In-Neck, 아니면 Thrusting | **【우리 규약】** 원전은 상대 표현만 준다(§7.3.15) |

**원전이 값을 준 자리는 위에서 2, 5, 7, 19와 §4.3의 중간점, §7의 개별 배수(Takuri 3배,
Shooting Star 3배), Hikkake의 3봉 기한, Hanging Man과 Inverted Hammer의 확인 내용이다.**
나머지는 모두 우리가 골랐고 각 자리에 근거를 적었다.

**원전이 값을 주었으나 채택하지 않은 자리가 하나 있다.** Morris가 Inverted Hammer의 위그림자에
적은 "usually no more than two times"라는 상한이며, §7.1.9가 그 근거를 적었다.

---

## §9. 출처 (1차 원전)

| 기호 | 서지 |
|---|---|
| `[N]` | Steve Nison, *Japanese Candlestick Charting Techniques*, **Second Edition**, New York Institute of Finance, 2001 |
| `[M]` | Gregory L. Morris (with Ryan Litchfield), *Candlestick Charting Explained: Timeless Techniques for Trading Stocks and Futures*, **Third Edition**, McGraw-Hill, 2006 |
| `[Ch]` | Daniel L. Chesler, "Trading False Moves with the Hikkake Pattern", *Active Trader*, 2004년 4월호, 42~46쪽 |

**판을 반드시 밝혀 둔다. 세 편 모두 초판이 아니다.** Nison의 초판은 1991년, Morris의 초판은
1992년이며 이 표준은 그 초판들을 대조하지 않았다. 인용을 다시 확인하려면 위에 적은 판의 해당
장을 열어야 한다.

Nison의 *Beyond Candlesticks*(1994)는 구하지 못했고 **근거로 삼은 항목이 하나도 없다.**

원전의 추출 텍스트는 저작물 전문이므로 저장소에 두지 않는다. 인용 위치를 줄 번호까지 담은
대조 기록은 `docs/candlestick-patterns/analysis-1-original-sources.md`에 있다.

**TA-Lib은 출처가 아니다.** 함수 목록과 이름을 가져왔고 값을 맞대어 보는 대조군으로 쓰지만,
판정 규칙과 임계값은 위 세 편과 이 표준이 소유한다.

---

## §10. 이 표준이 남긴 것

### 10.1 대상 범위와 남은 해석 선택

이 표준은 결정 A의 방식으로 모든 값을 채웠으므로 **비어 있어 구현할 수 없는 자리는 없다.**

**대상 범위는 사용자가 확정했다(2026-08-01). 61종 전부를 대상으로 삼는다.** 계보가 다른
Hikkake 두 종과 TA-Lib이 세운 `Kicking by Length`를 포함하며, 각 절이 원전과 계보를 밝혀
정보를 보존한다. 대조군 목록과 1:1로 맞아 검증이 단순해지는 것이 채택 근거다. 이 결정으로
§8.1의 61이라는 집계가 확정된다.

아래 둘은 원문이 두 가지로 읽히는 자리이며 **이 표준이 한쪽을 골랐다.** 각 절에 대안 읽기를
함께 적어 두었으므로 나중에 다른 읽기로 바꾸어도 다른 절이 영향을 받지 않는다.

- **원문 구조가 모호한 여섯 자리를 §8.4의 16, 17, 18, 19, 21, 22로 닫았다.** Harami Cross의
  `range`, Unique Three River의 "아래", Three Stars in the South의 `range`, Three Methods의
  작은 캔들 수와 "강한 날", Kicking by Length의 "더 긴 쪽"이다.
- **Rising/Falling Three Methods의 작은 캔들 수를 2 이상 5 이하로 두었다.** Nison이 준
  범위이며 상한 없는 읽기는 배제했다. 이 확정이 창 길이를 유한하게 만들어 상태 보관량과
  `min_history`를 정한다.

### 10.2 표준을 쓰다 드러난 것

- **Morris 3판의 Engulfing 규칙 2는 인쇄된 문장 자체가 오식이다.** 감싸는 쪽과 감싸이는
  쪽이 뒤바뀌어 있고 그대로 구현하면 Harami가 된다. §7.3.1이 같은 책의 다른 세 절과 Nison을
  근거로 방향을 바로잡았다.
- **Spinning Top과 High-Wave는 원전만으로는 구별되지 않는다.** 둘 다 "작은 실체와 긴
  그림자"이며, §7.2.1이 경계를 새로 세우지 않으면 두 패턴이 같은 것이 된다.
- **In-Neck과 Thrusting도 마찬가지다.** Nison이 "stronger than the in-neck pattern"이라는
  상대 표현만 주므로, 한쪽을 정의하지 않으면 다른 쪽의 경계가 서지 않는다.
- **강세형과 약세형이 대칭이 아닌 패턴이 넷 있다.** Belt-hold(종가 조건이 강세형에만),
  In-Neck(길이 요건이 강세형에만), Stick Sandwich(구조 자체가 다름), Three-Line
  Strike(넷째 날 기준이 시가와 고가로 갈림)다. **원전 그대로이며 이 표준이 만든 비대칭이
  아니다.** 구현이 대칭을 가정하면 값이 어긋난다.
- **`Kicking` 계열만 추세를 요구하지 않는 반전형이다.** Morris 89개 머리말 가운데 유일한
  예외이며, 이 때문에 `min_history`가 2로 다른 두 캔들 패턴(11)과 크게 다르다.

### 10.3 대조 방침

TA-Lib과 값을 맞대어 볼 때 **차이가 나는 것이 정상이다.** 이 표준은 TA-Lib의 임계표를
승계하지 않았고 추세 요건을 넣었으며(TA-Lib은 사실상 넣지 않는다) 확인을 별도 키로 낸다.
**값이 어긋나면 이 표준을 다시 읽어 원인을 밝히고, TA-Lib을 따라 구현이나 임계를 바꾸지
않는다.** 대조가 뜻을 갖는 자리는 봉의 모양 판정이 서로 겹치는 부분에 한한다.
