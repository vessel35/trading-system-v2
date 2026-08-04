# 캔들스틱 패턴의 원전 정의 조사 (T1, T4·T7 보강, T10 정합화)

이 문서는 TA-Lib이 제공하는 캔들스틱 패턴을 core-lib에 들여올 때 **무엇을 구현할 수 있고
그 정의가 어디서 오는가**에만 답한다. 구현 코드는 쓰지 않았고 저장소 파일도 고치지 않았다.
패턴을 core-lib 안에서 어떤 모양으로 구성할지는 다른 담당의 몫이므로 여기서 다루지 않는다.

## 이 판에서 고친 것 (T10 정합화)

3차 적대적 교차 검토가 문서 안의 자기모순을 짚었고, 조율자가 결정 C의 우선순위 하나를
정정했다. 이번 판은 새 조사가 아니라 **이미 확정된 결정과 이미 확인한 원문을 문서 전체에
일관되게 반영하는 정합화**다.

- **결정 C의 우선순위를 바로잡았다.** 결정 C는 두 층이고 구체적인 층이 먼저다. Morris
  안에서는 `Rules of Recognition`이 규범이고 `Pattern Flexibility`는 **넓히든 좁히든**
  주석이며, "조건이 더 많은 쪽"이라는 원칙은 **Nison과 Morris 사이에만** 적용된다. 앞 판이
  Ladder Bottom에서 유연성 절의 두 조건을 규범으로 올린 것을 되돌려 주석으로 내렸고,
  같은 종류의 잘못 적용이 더 없는지 전수로 확인했다.
- **방향이 뒤집힌 정의를 고쳤다.** Engulfing의 규칙 2를 "둘째 실체가 첫 실체에 감싸인다"로
  옮겨 두었는데, 그대로 구현하면 Harami가 된다. Morris의 인쇄된 문장 자체가 감싸는 쪽과
  감싸이는 쪽을 뒤바꾼 오식이며, 같은 책의 유연성 절과 시나리오 절, 그리고 Nison
  L1517~L1519가 모두 반대 방향을 못박는다. 포함 관계와 대소 관계를 문서 전체에서 전수로
  훑어 Modified Hikkake의 지시 대상 모호 하나를 더 찾아 고쳤다.
- **채택표와 실제 정의를 하나로 맞췄다.** 5.3절이 "채택했다"고 적은 것을 4장 정의가 반영하지
  않은 자리가 열한 곳 있었다. Gravestone Doji, Shooting Star, 별 계열 넷, Identical Three
  Crows, Gap Side-by-side White Lines, Dragonfly Doji, Dark Cloud Cover, Hammer가 그것이다.
  채택표의 스물여덟 행을 4장과 하나씩 대조해 모두 맞췄다.
- **Nison에만 있는 조건 셋을 새로 채택했다.** Inverted Hammer의 다음 날 강세 확인,
  Counterattack의 둘째 날 시가가 추세 방향으로 크게 벌어졌다가 전일 종가로 돌아오는 조건,
  Stalled Pattern의 마지막 봉이 작은 양봉이라는 조건이다. Nison과 Morris가 둘 다 걸린
  패턴을 전수로 다시 대조한 결과다.
- **결정 B를 45종 정의 안까지 밀어 넣었다.** 추세를 요구하는 45종 전부가 이제 실행 규칙에
  방향과 판정식을 갖는다. 비교에 쓰는 봉은 **패턴의 첫날**로 확정했고 선택으로 열어 두지
  않았다.
- **확인 계약을 결정으로 만들었다.** 결정 12를 새로 넣어 **확인이 무엇인지**와 **기한이
  언제까지인지**를 묻는다. 원전이 내용을 준 곳과 주지 않은 곳, 기한을 준 곳과 주지 않은
  곳을 갈라 적었다. 결정 11에서 **확인 정보를 아예 버리는 선택지는 제거했다.**
- **숫자와 결론의 자기모순을 고쳤다.** 결정 4와 결정 7의 척도 의존 개수를 표의 실제 값으로
  맞췄고, "61종 모두 구조가 확정되었다"는 서술을 **"구현에서 제외할 패턴이 없다"**와
  **"구조 선택이 여섯 자리 남았다"**로 갈라 적었다.

## 앞 판에서 고친 것 (T7 보강)

사용자가 2026년 8월 1일에 네 가지를 확정했고, 2차 적대적 교차 검토가 원문 대조로 사실
오류 열세 건을 짚었다. **오류는 모두 사실이었고 반박 없이 고쳤다.** 이 판이 한 일은 다음
다섯 가지다.

- **사실 오류 열세 건을 고쳤다.** 가장 무거운 것은 Tasuki Gap이었다. 앞 판은 두 캔들의
  크기를 견주는 요건이 원전에 없고 TA-Lib이 더했다고 적었으나, Nison은
  `nison_jcct.txt` L3773~3774와 L7130~7131에서 "The two candles of the tasuki should be
  about the same size."라고 **직접 적는다.** 그 서술을 철회하고 조건을 정의에 채택했다.
  Modified Hikkake의 줄 번호를 바로잡고 원문에 없던 근접 허용오차 주장을 지웠으며,
  Breakaway·Ladder Bottom·Three-Line Strike·Mat Hold·In-Neck·Belt-hold·Upside Gap Two
  Crows·Two Crows·Three Outside·Gap Three Methods에서 빠뜨린 원문 조건을 넣었다.
  Three Outside와 Gap Three Methods의 규칙을 찾지 못했다는 2장의 옛 서술도 지웠다.
- **세 갈래 분류를 버리고 두 열로 대체했다.** 결정 A가 확정되면서 "구현 가능한가"라는 물음
  자체가 사라졌기 때문이다. 표에서 갈래 열을 빼고 **필요한 척도**와 **우리가 정해야 하는
  것** 두 열을 두었다. 갈래 개수는 세지 않는다.
- **확정된 네 결정을 61종 정의에 실제로 반영했다.** 추세는 45종이 요구하고 16종이 요구하지
  않으며, 요구하는 45종에는 정의 첫 항에 10기간 지수이동평균 기준을 명시했다. 원전끼리
  또는 원전 안에서 충돌한 28종을 전수 조사해 좁은 쪽으로 정리하고 채택 결과를 5.3절에
  목록으로 남겼다. 갭은 패턴마다 실체 사이인지 꼬리를 포함한 고저 범위 사이인지 단순 시가
  갭인지 원문에서 확인해 표에 적었다.
- **결정 목록을 다시 만들었다.** 결정 B와 D와 분류 폐기로 닫힌 셋을 지우고, 원문이 갭을
  구분하지 않은 자리와 원문 구조가 모호한 자리를 새로 올려 **열다섯 건**으로 정리했다.
  미래 참조가 되는 선택지와 여러 갭을 하나로 뭉개는 선택지는 제거했다. 선택지가 사실은
  하나뿐인 항목은 하나라고 적었다(결정 8).
- **인용의 재현성을 마무리했다.** Chesler 두 항목의 틀린 줄 번호를 바로잡고, Nison 쪽에
  장만 적혀 있던 항목에 줄 번호를 채웠다.

## 앞 판에서 고친 것 (T4 보강)

적대적 교차 검토가 Blocking 다섯 건을 지적했고, 조율자가 그 가운데 셋을 원문으로 직접
확인했다. **지적은 모두 사실이었고 아래와 같이 고쳤다.**

- **61종 각각의 실행 가능한 정의를 4장으로 새로 썼다.** 앞 판의 표에는 이름과 필요한
  척도만 있어 봉 순서, 색, 갭, 포함 관계, 부등식의 엄격성을 구현할 수 없었다. 4장이 이제
  이 문서의 본체다.
- **갈래 기준을 원래 지시서대로 되돌리고 직전 추세를 분류에 포함해 다시 세었다.** 앞 판은
  기준을 넓히고 추세를 분류에서 뺐는데, 그 변경은 확인 없이 한 것이었다. 5장이 새 집계다.
  기준을 넓혀야 할 이유는 고르지 않고 결정 항목으로 올렸다.
- **Advance Block과 Kicking by Length 판정을 뒤집었다.** 앞 판은 Advance Block의 원전
  규칙을 찾지 못했다고 했으나 `morris_cce.txt` 3879~3883줄에 있고, Kicking의 "더 긴 쪽
  방향" 규칙이 TA-Lib 설명에만 있다고 단정했으나 같은 추출본 2608~2621줄에 Morris가
  일본 이론으로 소개한 문장이 있다. **두 단정 모두 틀렸고 철회한다.** 갈래 3은 이제 비었다.
- **사용자 결정을 열하나에서 열여섯으로 늘렸다.** 그림자 척도, 부등식 엄격성, 퇴화 봉,
  확인 등급과 시점, 등록 파라미터 조합이 빠져 있었다. 실행 불가능했던 기존 결정 6의
  선택지 하나도 실행 가능한 형태로 다시 썼다.
- **재현 경로를 패턴마다 추출본 줄 번호로 남겼다.** 앞 판은 장 번호만 있었고 파일 위치도
  부정확했다.

보강 과정에서 **Morris 3판이 패턴마다 머리말 필드를 두고 있다는 것을 새로 찾았다.**
`Pattern Name`, `Type`, `Japanese Name`, 그리고 결정적으로 **`Trend Required`(Yes 또는 No)**와
**`Confirmation`(Required, Suggested, No)**이다. 이 두 필드가 검토가 지적한 추세 요건과
확인 등급 문제에 원전 근거를 직접 준다. 89개 항목을 모두 뽑아 4장과 5장에 반영했다.

조사에 쓴 환경과 자료는 다음과 같다. TA-Lib은 일회용 가상환경에 새로 설치했고, 파이썬
래퍼는 0.7.1, 그 안에 묶인 C 라이브러리는 `0.7.1 (Jul 16 2026 18:35:07)`이다.

## 확인 강도 표기 규약

이 조사에서 가장 큰 실패는 확인하지 못한 것을 확인한 것처럼 적는 것이다. 그래서 모든
항목에 확인 강도를 붙였고, 뜻은 다음과 같다.

- **직접**: 해당 저작의 본문을 내가 직접 읽고 그 문장을 인용했다.
- **2차**: 본문을 읽지 못했고 그 저작을 인용한 다른 자료로만 확인했다. 자료를 밝힌다.
- **미확인**: 어느 쪽으로도 확인하지 못했다. 모른다고 적는다.

**직접 확인한 저작에는 판(edition) 단서가 있다.** 이 점을 먼저 밝힌다.

- Steve Nison, *Japanese Candlestick Charting Techniques*, **Second Edition (2001)**.
  Internet Archive에 공개된 스캔본의 전문(298쪽)을 내려받아 읽었다. 지시서가 지목한 것은
  1991년 초판인데, 내가 읽은 것은 2001년 2판이다. 두 판의 패턴 정의가 같은지는 확인하지
  못했으므로, 아래에서 "Nison"이라고 적은 것은 모두 **2판 기준**이다.
- Gregory L. Morris (with Ryan Litchfield), *Candlestick Charting Explained*,
  **Third Edition (2006)**, McGraw-Hill. 전문(552쪽)을 내려받아 읽었다. 이 역시 1992년
  초판이 아니라 2006년 3판이다.
- Daniel L. Chesler, "Trading False Moves with the Hikkake Pattern",
  *Active Trader Magazine*, **April 2004**, 42~46쪽. 저자 본인 사이트에 공개된 원문 PDF
  전문을 읽었다.
- Steve Nison, *Beyond Candlesticks* (1994)는 **구하지 못했다.** 이 문서에서 그 책을 근거로
  삼은 항목은 하나도 없다.

Nison 2판 본문은 스캔 OCR이다. 그래서 **어떤 낱말이 나온다는 것은 강한 증거지만, 나오지
않는다는 것은 약한 증거다.** 아래에서 "Nison에 없다"고 적은 것은 정확히는 "내가 읽은 2판
OCR 본문에서 찾지 못했다"는 뜻이며, 그렇게 읽어야 한다.

---

# 1. 목록을 실제로 세어라

## 1.1 개수는 61이 맞다

TA-Lib 0.7.1의 함수 그룹 가운데 `Pattern Recognition` 그룹에 속한 함수는 **정확히 61개**다.
직전 단계가 적어 둔 61이라는 숫자는 검증되었다. 덧붙여 확인한 것이 둘 있다. 전체 함수
목록에서 이름이 `CDL`로 시작하는 것도 61개로 같고, `Pattern Recognition` 그룹과 `CDL`
접두사 집합은 완전히 일치한다. 곧 어느 쪽으로 세어도 61이고 경계 사례가 없다.

## 1.2 요구하는 입력은 61종 모두 같다

61개 함수 전부가 시가·고가·저가·종가 **네 계열을 모두** 요구한다. 일부만 쓰는 함수는
하나도 없다. 이는 추상 API가 보고하는 입력 이름을 61개 전부에 대해 뽑아 확인한 결과이며,
서로 다른 입력 서명은 단 하나(`open`, `high`, `low`, `close`)뿐이었다.

한 가지 유의할 점이 있다. **입력을 요구하는 것과 실제로 값을 쓰는 것은 다르다.** 예를 들어
Hikkake는 원저자가 시가와 종가를 쓰지 않는다고 못박은 패턴인데도(아래 2장 참고) TA-Lib은
네 계열을 다 받는다. 인터페이스가 획일적일 뿐이다.

## 1.3 파라미터를 받는 함수는 7개다

61개 가운데 파라미터를 받는 것은 7개이고, 파라미터는 모두 `penetration` 하나뿐이다.
나머지 54개는 파라미터가 없다.

| 함수 | `penetration` 기본값 |
|---|---|
| `CDLABANDONEDBABY` | 0.3 |
| `CDLDARKCLOUDCOVER` | 0.5 |
| `CDLEVENINGDOJISTAR` | 0.3 |
| `CDLEVENINGSTAR` | 0.3 |
| `CDLMATHOLD` | 0.5 |
| `CDLMORNINGDOJISTAR` | 0.3 |
| `CDLMORNINGSTAR` | 0.3 |

이 값들의 출처 문제는 5장에서 따로 다룬다. 미리 요점만 적으면, Dark Cloud Cover의 0.5는
Nison이 본문에서 언급한 수치와 맞아떨어지지만 별(star) 계열의 0.3은 원전에서 근거를
찾지 못했다.

## 1.4 반환 값이 실제로 갖는 값

값의 범위는 문서를 믿지 않고 관찰로 확인했다. 서로 다른 난수 씨앗과 세 가지 변동성으로
만든 무작위 보행 가격 계열, 그리고 호가 단위를 흉내 내려고 소수점 둘째 자리에서 반올림한
계열까지 합쳐 함수마다 수백만 봉을 흘려보내고 나타난 값을 모았다. 관찰된 값의 합집합은
다음 일곱 가지다.

`-200, -100, -80, 0, 80, 100, 200`

값의 뜻은 이렇게 갈린다.

- **0** 은 "이 봉에서 패턴이 성립하지 않음"이다. 다만 뒤에서 다시 말하듯이, 파이썬 래퍼는
  워밍업 구간도 0으로 채우므로 **0만 보고는 "성립하지 않음"과 "아직 계산되지 않음"을
  구별할 수 없다.**
- **±100** 이 통상적인 성립 신호다. 부호는 강세를 양, 약세를 음으로 쓴다.
- **±80** 은 `CDLENGULFING`, `CDLHARAMI`, `CDLHARAMICROSS` 세 함수에서만 관찰되었다.
  Engulfing으로 확인한 결과, 두 번째 실체가 앞 실체를 **양끝 모두 엄격히 넘어서면 ±100**,
  **한쪽 끝이 정확히 같으면 ±80**, **양끝이 모두 같으면 0**이었다. 곧 80은 경계에 걸친
  약한 성립을 뜻한다.
- **±200** 은 `CDLHIKKAKE`, `CDLHIKKAKEMOD` 두 함수에서만 관찰되었다. 이 두 패턴은
  원저자 정의에 확인(verification) 단계가 따로 있고, 200은 그 확인까지 끝났음을 뜻한다.

방향이 한쪽으로만 나오는 패턴이 많다는 점도 관찰되었다. 강세 신호만 내는 것이 20종,
약세 신호만 내는 것이 14종이며, 나머지 27종이 양방향이다. 예를 들어 `CDLHAMMER`는
0과 +100만, `CDLHANGINGMAN`은 0과 -100만 낸다. `CDLDOJI`가 0과 +100만 내는 것은
특히 오해하기 쉬운데, 도지는 방향성이 없는 캔들이므로 여기서 +100의 부호는 방향이 아니라
그저 "성립함"을 뜻한다.

## 1.5 몇 봉의 이력을 요구하는가

TA-Lib이 스스로 보고하는 워밍업 길이(lookback)를 61개 전부에 대해 읽었다. 분포는 다음과
같다. 최소는 2봉, 최대는 14봉이다.

| lookback | 함수 수 | 함수 |
|---|---|---|
| 2 | 2 | `CDLENGULFING`, `CDLXSIDEGAP3METHODS` |
| 3 | 1 | `CDL3OUTSIDE` |
| 5 | 1 | `CDLHIKKAKE` |
| 6 | 1 | `CDLMATCHINGLOW` |
| 7 | 3 | `CDLGAPSIDESIDEWHITE`, `CDLSTICKSANDWICH`, `CDLTASUKIGAP` |
| 8 | 1 | `CDL3LINESTRIKE` |
| 10 | 14 | `CDLBELTHOLD`, `CDLCLOSINGMARUBOZU`, `CDLDOJI`, `CDLDRAGONFLYDOJI`, `CDLGRAVESTONEDOJI`, `CDLHIGHWAVE`, `CDLHIKKAKEMOD`, `CDLLONGLEGGEDDOJI`, `CDLLONGLINE`, `CDLMARUBOZU`, `CDLRICKSHAWMAN`, `CDLSHORTLINE`, `CDLSPINNINGTOP`, `CDLTAKURI` |
| 11 | 17 | `CDLCOUNTERATTACK`, `CDLDARKCLOUDCOVER`, `CDLDOJISTAR`, `CDLHAMMER`, `CDLHANGINGMAN`, `CDLHARAMI`, `CDLHARAMICROSS`, `CDLHOMINGPIGEON`, `CDLINNECK`, `CDLINVERTEDHAMMER`, `CDLKICKING`, `CDLKICKINGBYLENGTH`, `CDLONNECK`, `CDLPIERCING`, `CDLSEPARATINGLINES`, `CDLSHOOTINGSTAR`, `CDLTHRUSTING` |
| 12 | 15 | `CDL2CROWS`, `CDL3INSIDE`, `CDL3STARSINSOUTH`, `CDL3WHITESOLDIERS`, `CDLABANDONEDBABY`, `CDLADVANCEBLOCK`, `CDLEVENINGDOJISTAR`, `CDLEVENINGSTAR`, `CDLIDENTICAL3CROWS`, `CDLMORNINGDOJISTAR`, `CDLMORNINGSTAR`, `CDLSTALLEDPATTERN`, `CDLTRISTAR`, `CDLUNIQUE3RIVER`, `CDLUPSIDEGAP2CROWS` |
| 13 | 2 | `CDL3BLACKCROWS`, `CDLCONCEALBABYSWALL` |
| 14 | 4 | `CDLBREAKAWAY`, `CDLLADDERBOTTOM`, `CDLMATHOLD`, `CDLRISEFALL3METHODS` |

이 lookback은 **패턴 자체가 차지하는 봉 수와 다르다.** 그 둘을 갈라 재려고 다음 실험을
했다. TA-Lib의 내부 평균 창 길이를 모두 0으로 만든 뒤 lookback을 다시 읽으면, 남는 것은
패턴이 실제로 걸치는 봉 수뿐이다. 그렇게 얻은 결과가 아래이며, 곧 **대부분의 함수에서
lookback의 대부분은 패턴의 길이가 아니라 TA-Lib이 "길다·짧다"를 재려고 돌리는 평균
창에서 온다.**

예를 들어 `CDLDOJI`는 lookback이 10이지만 패턴 자체는 1봉짜리다. 10봉은 전부 "이 봉의
실체가 최근 고저 범위에 견주어 작은가"를 판단하려고 쓰는 평균 창이다. 반대로
`CDLHIKKAKE`는 lookback 5가 온전히 패턴 구조에서 나온다.

패턴이 걸치는 봉 수를 독립적으로 한 번 더 확인하려고, 신호가 난 봉에서 k봉 앞의 값을
크게 흔들었을 때 그 신호가 바뀌는지를 보는 교란 실험도 했다. 평균 창을 끈 상태에서도
신호를 내는 함수들에 대해서는 두 방법이 일치했다(예: `CDLENGULFING` 2봉,
`CDL3OUTSIDE` 3봉, `CDLHIKKAKE` 5봉, `CDLHIKKAKEMOD` 6봉, `CDLTASUKIGAP` 3봉,
`CDLXSIDEGAP3METHODS` 3봉). 다만 평균 창을 끄면 "긴 실체" 판정이 성립할 수 없어 아예
신호를 내지 않는 함수가 많았고, **그런 함수에 대해서는 교란 실험이 아무것도 말해 주지
못했다.** 그 경우의 봉 수는 위의 lookback 실험 값만 근거로 삼았다.

---

# 2. 패턴마다 원전을 특정한다

## 2.1 세 저작이 서로 다른 몫을 맡고 있다

61종을 원전 기준으로 갈라 보면 그림이 뚜렷하다.

- **Nison 2판 본문에서 이름을 찾은 것이 40종.** 여기에는 Hammer, Engulfing,
  Dark-Cloud Cover, Piercing, Morning/Evening Star, Harami, Doji 계열, Tasuki,
  Separating Lines, Three Black Crows, Three White Soldiers 등 고전적인 패턴이 들어간다.
- **Nison 2판 OCR 본문에서 이름을 전혀 찾지 못한 것이 21종.** 그 21종은 다시 셋으로
  갈린다. 18종은 Morris에 정의가 있고, 2종(Hikkake, Modified Hikkake)은 Morris에도 없으며,
  나머지 1종(`CDLKICKINGBYLENGTH`)은 Morris의 Kicking을 TA-Lib이 변형한 것이어서 어느
  원전에도 별개 패턴으로 존재하지 않는다.
- **Hikkake 두 종은 일본식 캔들 패턴이 아니다.** 원저자가 따로 있고 정의도 캔들 실체를
  쓰지 않는다. 아래 2.4에서 따로 다룬다.

Nison 2판 본문에서 찾지 못했고 Morris에서 찾은 18종은 다음과 같다.
Three Inside Up/Down, Three Outside Up/Down, Three-Line Strike, Three Stars in the South,
Identical Three Crows, Homing Pigeon, Matching Low, Kicking, Marubozu, Closing Marubozu,
Long Line, Short Line, Ladder Bottom, Concealing Baby Swallow, Stick Sandwich,
Unique Three River, Mat Hold, Upside/Downside Gap Three Methods.

이 18종 가운데 셋(Three Outside Up/Down, Short Line, Upside/Downside Gap Three Methods)은
**규칙이 실린 자리가 나머지와 다르다.** Three Outside는 제목이 `Rules of Recognition`이
아니라 `Pattern Recognition`이어서 `morris_cce.txt` L4471에 있다. Upside/Downside Gap Three
Methods는 정상적인 `Rules of Recognition`이 L6825에 있고, 그보다 앞선 L6817~6824의 해설이
규칙보다 더 구체적이다. Short Line(짧은 날)은 패턴이 아니라 **캔들 선**이어서 Morris 2장에
규칙 묶음 없이 서술되어 있고, 판정 방법은 6장의 짧은 날 정의가 맡는다.

**앞 판은 이 셋의 규칙을 찾지 못했다고 적었으나 그것은 내 검색이 제목 형식 하나만 본
탓이었다. 세 패턴 모두 원전에 규칙이 있으며 4장 49번, 59번, 17번에 옮겼다.**

**Marubozu는 특별히 짚어 둔다.** `marubozu`, `marubo`, `bozu` 어느 철자로 찾아도 Nison 2판
OCR 본문에서 단 한 번도 나오지 않았다. 대신 Nison은 같은 개념을 다른 이름으로 적는다.
3장에서 "위꼬리가 없는 캔들은 shaven head를 가졌다고 하고, 아래꼬리가 없는 캔들은
shaven bottom을 가졌다고 한다"고 쓴다. 곧 **개념은 Nison에 있고 Marubozu라는 이름과
그것을 하나의 패턴으로 세우는 방식은 Morris 쪽**이다.

## 2.2 Nison이 실제로 적은 정의 (직접 확인)

아래는 Nison 2판 본문에서 내가 직접 읽은 문장을 우리말로 옮긴 것이다. 요약이 아니라
판정에 쓸 수 있을 만큼 그대로 옮겼고, 수치가 있으면 그대로 남겼다.

**Hammer와 Hanging Man (4장).** Nison은 인식 기준 셋을 나란히 적는다. 첫째, 실체가 거래
범위의 위쪽 끝에 있고 실체의 색은 중요하지 않다. 둘째, 아래꼬리가 길어야 하며 **실체
높이의 최소 두 배**여야 한다. 셋째, 위꼬리는 없거나 매우 짧아야 한다. 두 패턴을 가르는
것은 모양이 아니라 위치다. Nison은 "해머는 하락 뒤에 와야 하고, 행잉맨은 상승 뒤에 와야
한다"고 쓰고, 나아가 "해머는 단기 하락 뒤에 와도 유효하지만 행잉맨은 길게 이어진 상승,
되도록이면 사상 최고가 뒤에 나와야 한다"고 덧붙인다. 확인 요건도 갈린다.
"행잉맨은 확인을 받아야 하고 해머는 그럴 필요가 없다."

**Engulfing (4장).** 기준 셋이다. 첫째, 시장이 **뚜렷하게 규정할 수 있는 추세** 안에
있어야 한다. 약세 장악형이면 상승 추세, 강세 장악형이면 하락 추세이고, 단기 추세여도
된다. 둘째, 두 번째 실체가 앞 실체를 감싸야 하며 **꼬리까지 감쌀 필요는 없다.** 셋째,
두 번째 실체는 첫 실체와 반대색이어야 한다.

**Dark-Cloud Cover (4장).** 상승 추세에서 긴 양봉 다음에 음봉이 오는데, 그 음봉은 앞
양봉의 고가(또는 종가) 위에서 시작해 앞 양봉 실체 안으로 깊이 파고들어 마감한다.
용어사전 항목은 "되도록 절반보다 더 깊이"라고 적고, 본문은 "일부 일본 기술적 분석가는
음봉 종가가 양봉 실체를 **50퍼센트 넘게** 파고들 것을 요구한다"고 쓴다.

**Piercing (4장).** 하락 추세에서 긴 음봉 다음 세션이 갭 하락으로 열리고, 그 세션이 강한
양봉으로 끝나면서 **앞 음봉 실체의 절반보다 더 깊이** 파고들어 마감한다. Nison은 이
패턴을 On-Neck, In-Neck, Thrusting과 견주라고 적는데, 그 셋은 파고드는 깊이만 다르다.

**Doji (3장·8장·용어사전).** "시가와 종가가 같은(또는 거의 같은) 세션"이다. **허용오차를
숫자로 주지 않는다.** 이 한 문장이 뒤에 나오는 수치 공백의 뿌리다.

**Dragonfly Doji (8장).** 아래꼬리가 길고 시가·고가·종가가 세션의 고가에 있는 도지.

**Gravestone Doji (8장).** 시가와 종가가 세션의 저가에 있는 도지.

**Long-Legged Doji와 Rickshaw Man (8장).** 꼬리가 매우 긴 도지가 Long-Legged Doji이고,
그 시가와 종가가 **세션 범위의 한가운데**에 있으면 Rickshaw Man이라 부른다.

**High-Wave (용어사전).** 위아래 꼬리가 매우 길고 실체가 작은 캔들.

**Harami (6장).** 작은 실체가 앞 세션의 **유난히 큰** 실체 안에 들어가는 두 캔들 패턴.
두 번째 실체의 색은 흰색이든 검은색이든 되지만 대개는 첫 실체와 반대색이다.

**Harami Cross (6장).** 두 번째 세션이 작은 실체가 아니라 도지인 하라미.

**Star (용어사전).** 앞의 큰 실체에서 **갭을 두고 떨어진** 작은 실체.

**Evening Star (5장).** 세 캔들로 이루어진 천정 반전형. 첫째는 키 큰 양봉, 둘째는 첫 실체
위로 갭을 두고 뜬 작은 실체(색 무관), 셋째는 첫 세션 양봉 실체 **안으로 깊이** 마감하는
음봉이다. 가운데가 팽이형이 아니라 도지이면 Evening Doji Star다.

**Morning Star (5장).** 첫째가 긴 음봉, 둘째가 아래로 갭을 두고 뜬 작은 실체, 셋째가 첫
세션 음봉 실체 안으로 깊이 마감하는 양봉이다.

**Abandoned Baby (용어사전).** 매우 드문 반전 신호. **꼬리까지 포함해** 앞뒤 세션의
캔들에서 완전히 떨어진 도지 스타로 이루어진다. 서양의 섬꼴 반전과 같되 섬에 해당하는
세션이 도지인 경우다.

**Tri-Star (8장).** 모닝스타 또는 이브닝스타와 같은 배열을 이루는 도지 셋. 극히 드물다.

**Inverted Hammer (5장).** 하락 추세 뒤에 나오는, 위꼬리가 길고 실체가 세션 아래쪽에 있는
작은 실체의 캔들. 아래꼬리는 없거나 매우 짧아야 한다. 모양은 슈팅스타와 같지만 하락
추세에서 나오면 강세 신호가 되며, **다음 세션의 확인을 받아야 한다.**

**Shooting Star (5장).** 위꼬리가 길고 아래꼬리가 없거나 매우 짧으며 실체가 세션 저가
가까이에 있는, 상승 추세 뒤에 나오는 약세 캔들.

**Separating Lines (7장).** 상승(하락) 추세에서 앞 세션의 반대색 캔들과 **같은 값에
시가가 열리고** 더 높게(낮게) 마감하는 캔들. 이 캔들 뒤에는 앞선 추세가 이어져야 한다.

**Side-by-Side White Lines (7장).** **같은 시가**를 갖고 실체 크기가 서로 **비슷한**
연속된 양봉 둘. 상승 추세에서 이 둘이 위로 갭을 두면 강세 지속형이다. 하락 추세에서는
양봉임에도 여전히 약세로 본다.

**Tasuki (7장·용어사전).** 상승 타스키 갭은 양봉이 만든 상승 갭 뒤에 음봉이 오는 것으로,
그 음봉은 **양봉 실체 안에서 열려 양봉 실체 아래에서 마감**한다.

**Advance Block (용어사전).** 삼백병(Three White Soldiers)의 변형인데, 마지막 두 병사가
**위로 미는 힘이 약해지는 모습**을 보인다. 그 약함은 **긴 위꼬리로 나타날 수도 있고
실체가 점점 작아지는 것으로 나타날 수도 있다.** Nison은 "could be"라고 쓸 뿐 둘 중
무엇으로 판정하라고 정하지 않는다.

**Window (용어사전).** 서양의 갭과 같다. 지속형이며, 위로 열리면 상승창으로 지지 역할을,
아래로 열리면 하락창으로 저항 역할을 한다. 갭을 쓰는 패턴이 여럿이므로 함께 적어 둔다.

## 2.3 Morris가 실제로 적은 정의 (직접 확인)

Morris 3판은 패턴마다 "Rules of Recognition"이라는 번호 매긴 규칙 묶음을 두고, 그 뒤에
"Pattern Flexibility"에서 어떤 부분을 느슨하게 볼 수 있는지 적는다. 그래서 **Morris는
Nison보다 판정에 훨씬 가깝다.** 전체 61종에 대한 개별 규칙은 4장의 절마다 실어 두고, 여기에는
Nison에 없어서 Morris가 사실상 유일한 원전인 것들만 옮긴다.

- **Three Inside Up/Down**: 먼저 앞서 정한 규칙으로 하라미를 찾고, 셋째 날이 Three Inside
  Up이면 더 높은 종가를, Three Inside Down이면 더 낮은 종가를 보이면 된다.
- **Three-Line Strike (강세)**: 삼백병처럼 보이는 사흘이 상승 추세를 잇고, 넷째 날이 더
  높이 열렸다가 **첫 양봉의 시가 아래로** 떨어져 마감한다. 약세는 좌우가 뒤집힌다.
- **Three Stars in the South**: 첫날은 아래꼬리가 긴 긴 음봉이고, 둘째 날은 같은 모양이되
  더 작으며 저가가 전날 저가보다 높고, 셋째 날은 전날 범위 안에서 열고 닫는 작은
  Black Marubozu다.
- **Identical Three Crows**: 긴 음봉 셋이 계단처럼 내려가는데, **각 날이 전날 종가에서
  시작한다.**
- **Homing Pigeon**: 하락 추세에서 긴 음봉이 나오고, 짧은 음봉이 전날 실체 안에 완전히
  들어간다.
- **Matching Low**: 긴 음봉이 나오고, 둘째 날도 음봉인데 **종가가 첫날 종가와 같다.**
- **Kicking**: 한 색의 Marubozu 다음에 반대색 Marubozu가 오고, 두 캔들 사이에 **갭이
  있어야 한다.**
- **Marubozu (2장)**: 시가 쪽이든 종가 쪽이든 또는 양쪽 모두에서 실체 밖으로 나온 꼬리가
  없는 캔들. Black Marubozu는 양끝에 꼬리가 없는 긴 음봉, White Marubozu는 양끝에 꼬리가
  없는 긴 양봉이다.
- **Closing Marubozu (2장)**: 종가 쪽 끝에 꼬리가 없는 캔들. 양봉이면 위꼬리가 없고
  음봉이면 아래꼬리가 없다.
- **Ladder Bottom**: 시가와 종가가 잇달아 낮아지는 긴 음봉 셋이 삼흑병처럼 나오고, 넷째
  날은 위꼬리가 있는 음봉이며, 마지막 날은 전날 실체 위에서 열리는 양봉이다.
- **Concealing Baby Swallow**: 처음 이틀은 Black Marubozu 둘이고, 셋째 날은 갭 하락으로
  열리되 전날 실체 안까지 올라와 긴 위꼬리를 만드는 음봉이며, 넷째 날 음봉이 셋째 날을
  **꼬리까지 포함해** 완전히 감싼다.
- **Stick Sandwich (강세)**: 하락 추세의 음봉 다음에 그 음봉 종가 위에서 거래된 양봉이
  오고, 셋째 날은 **첫날과 같은 종가**를 갖는 음봉이다.
- **Unique Three River**: 첫날은 긴 음봉, 둘째 날은 하라미이되 실체가 역시 음봉이고
  아래꼬리가 새 저점을 만들며, 셋째 날은 가운데 날보다 아래에 있는 짧은 양봉이다.
- **Mat Hold (강세)**: 상승 시장에서 긴 양봉이 만들어지고, 둘째 날은 갭 상승했다가 더 낮게
  마감해 거의 별처럼 보이며, 이어지는 이틀은 상승삼법과 비슷한 되돌림 날이고, 다섯째 날은
  새 종가 고점을 만드는 양봉이다.
- **Rising/Falling Three Methods**: 현재 추세를 나타내는 긴 캔들이 나오고, 이어 작은 실체
  캔들 무리가 따르며(반대색이면 더 좋다), 그 작은 캔들들은 추세와 반대로 움직이되 **첫날의
  고저 범위 안에 머문다.** 마지막 날은 강한 캔들로, 첫날 종가 바깥에서 원래 추세 방향으로
  마감한다.

Morris가 준 수치 가운데 개별 패턴에 붙은 것으로 내가 직접 읽은 것들도 적어 둔다.
Matching High 항목에서 그는 "두 날의 종가는 둘째 날 종가가 첫날 종가의 **1/1000** 안에
있으면 같다고 본다"고 적는다(첫날이 20이면 둘째 날은 19.98에서 20.02 사이). 여러 패턴의
"Pattern Flexibility"에서 되풀이되는 정의 둘도 그의 것이다. **긴 실체는 고저 범위의
50퍼센트를 넘게 차지하는 실체**이고, **긴 날은 고저 범위가 (1) 중간값의 1.5퍼센트를
넘거나 (2) 직전 5일 고저 범위 평균의 0.75배를 넘는 날**이다. 두 방법 가운데 무엇을 쓰는지에
따라 결과가 달라진다는 점을 그가 스스로 밝힌다.

## 2.4 Hikkake 두 종은 계보가 다르다 (직접 확인)

`CDLHIKKAKE`와 `CDLHIKKAKEMOD`는 **일본식 캔들 패턴이 아니다.** 원저자는
**Daniel L. Chesler**이고, 원전은 *Active Trader Magazine* 2004년 4월호 42~46쪽에 실린
"Trading False Moves with the Hikkake Pattern"이다. 나는 이 기사의 원문 PDF 전문을 읽었다.
후속 논문으로 *The Technical Analyst* 2004년 12월호의 "Quantifying Market Deception with
The Hikkake Pattern"이 있다고 저자 본인의 글 목록이 밝히고 있으나, **그 후속 논문 본문은
읽지 못했다.**

Chesler가 적은 정의는 다음과 같다.

기본 Hikkake는 **가격 봉 두 개**로 이루어진다. 첫 봉은 **인사이드 바**여야 하며, 인사이드
바란 앞 봉보다 고가가 낮고 저가가 높은 봉이다. 두 번째 봉은, **약세 설정**이면 인사이드
바보다 고가와 저가가 모두 높아야 하고, **강세 설정**이면 인사이드 바보다 저가와 고가가
모두 낮아야 한다. 여기서 극성이 뒤집혀 있다는 점을 놓치기 쉽다. 위로 뚫고 나가는 것이
약세 설정이다.

확인 규칙도 그가 직접 적었다. **강세 설정이면 가격이 인사이드 바의 고가 위로 올라서야
하고, 약세 설정이면 인사이드 바의 저가 아래로 내려가야 한다.** 그리고 "**확인은 Hikkake
패턴으로부터 세 봉 안에 일어나야 하며, 그렇지 않으면 그 패턴은 무시한다.**"

Chesler는 이 패턴이 **시가와 종가의 관계, 곧 캔들 용어로 실체를 쓰지 않는다**고 못박는다.
서양 용어로는 "inside day false breakout"이 옳은 이름이라고 그 스스로 적었다.

변형(Modified Hikkake)에 대해서는 인사이드 바 **바로 앞 봉**에 두 요건을 더한다.
첫째, 그 봉은 **약세형이면 자기 범위의 꼭대기에서, 강세형이면 자기 범위의 바닥에서**
마감해야 한다. 둘째, **그 봉의 범위가 그 앞 봉의 범위보다 작아야 한다.** 그는 이 변형이
기본형보다 훨씬 드물게 나타나며, 기본형이 반전과 지속 양쪽으로 쓰이는 데 비해 변형은
주로 추세 반전형이라고 적는다.

**여기에는 수치 공백이 없다.** Chesler는 "The bar **must** close at the top of its range"
라고 **단정**하므로 종가가 그 봉의 고가와 같아야 하고, 강세형이면 저가와 같아야 한다.
앞 판이 이 자리에 근접 허용오차가 필요하다고 적었던 것은 원문에 없는 완화였고 철회한다.
4장 61번이 최종 정의다.

## 2.5 확인 강도 집계

61종을 확인 강도로 세면 다음과 같다.

- **직접 확인 61종.** Nison 2판, Morris 3판, Chesler 원문 가운데 최소 한 곳에서 내가 본문을
  직접 읽고 판정 규칙을 옮긴 것이다. 4장이 61종 전부의 규칙과 그 위치를 담는다.
- **2차 자료 0종.** 앞 판에서 2차로 두었던 두 종을 이 판에서 직접으로 올렸다.
  `CDLKICKINGBYLENGTH`의 방향 규칙은 `morris_cce.txt` L2608~2621에 있고,
  `CDLHIKKAKEMOD`의 두 요건은 Chesler 원문 L204~L213에 있다. 앞 판은 앞의 것을 "원전에
  없다"고 잘못 적었고, 뒤의 것은 원문을 읽고도 2차로 낮춰 적었다. 둘 다 바로잡았다.
- **미확인 0종.** 다만 이는 "이름과 판정 규칙의 출처를 하나도 못 찾은 패턴은 없다"는 뜻이지,
  "모든 세부가 확정되었다"는 뜻이 아니다. 세부의 공백은 3장과 4장에 남김없이 적었다.

*Beyond Candlesticks*(1994)를 근거로 삼은 항목은 앞서 밝힌 대로 **하나도 없다.**

---

# 3. 수치 기준의 공백

## 3.1 공백은 낱낱의 패턴이 아니라 여섯 개의 척도에 몰려 있다

61종을 훑으면 정성적 표현이 흩어져 있는 것처럼 보이지만, 실제로는 **여섯 개의 척도**로
모인다. 척도 하나를 정하면 그 척도를 쓰는 패턴이 한꺼번에 정해진다. 그래서 공백을 패턴별로
나열하는 대신 척도별로 정리하고, 어느 패턴이 어느 척도를 쓰는지는 4장의 절마다 적었고 5.5절 표에 모았다.

**첫째 척도, "긴 실체".** 상대 비교의 기준을 무엇으로 잡느냐에 따라 결과가 달라진다.
Nison은 "긴", "유난히 큰"이라고만 쓰고 숫자를 주지 않는다. **Morris는 숫자를 주되 하나로
정하지 않고 세 가지 방법을 나란히 제시한다.** 그가 6장에서 적은 세 방법은 이렇다.
첫째는 실체를 **가격 수준**과 견주는 방법으로, 값을 5퍼센트로 두면 가격이 100일 때 시가와
종가의 차이가 5 이상인 날이 긴 날이다. 이 방법은 과거 자료를 전혀 쓰지 않는다.
둘째는 실체를 **그날의 고저 범위**와 견주는 방법이다. 셋째는 실체를 **직전 X일 실체
평균**과 견주는 방법으로, X는 5에서 10 사이가 좋고 값을 130으로 두면 평균보다 30퍼센트
큰 날이 긴 날이다. Morris는 셋 가운데 하나를 쓰거나 섞어 써도 된다고 적었고, 둘째 방법은
단독으로 쓰면 가장 좋지 않다고 덧붙였다. 별도로 여러 패턴의 "Pattern Flexibility"에서는
**긴 실체를 고저 범위의 50퍼센트 초과**로, **긴 날을 고저 범위가 중간값의 1.5퍼센트를
넘거나 직전 5일 고저 범위 평균의 0.75배를 넘는 날**로 적는다.

곧 "긴 몸통"을 정하려면 **기준을 가격 수준으로 삼을지, 그 봉의 고저 범위로 삼을지,
최근 N봉의 평균 실체로 삼을지**를 골라야 하고, 고른 뒤에는 그 배수나 퍼센트를 정해야 한다.
지시서가 예로 든 그대로, 이 셋은 서로 다른 결과를 낸다. 변동성이 커지는 국면에서 "최근
평균 대비" 방식은 판정을 보수적으로 만들고 "그 봉의 고저 범위 대비" 방식은 그렇지 않다.

**둘째 척도, "짧은 실체".** Morris는 짧은 날을 긴 날과 **똑같은 세 방법으로, 최소
퍼센트 대신 최대 퍼센트를 써서** 정한다고 적는다. 그러므로 첫째 척도에서 방법을 고르면
둘째 척도는 자동으로 따라온다. 다만 임계값은 따로 정해야 한다.

**셋째 척도, "도지".** Nison은 "시가와 종가가 같은(또는 거의 같은)"이라고만 쓴다. Morris는
형식을 준다. 그가 6장에서 적은 것은 **도지 실체를 그날의 고저 범위와 견주는 최대
퍼센트**이며, "**1에서 3퍼센트 정도가 꽤 잘 듣는다**"고 적었다. 2장에서는 다른 말도 한다.
"시가와 종가의 차이가 몇 틱(최소 호가 단위) 안이면 충분하고도 남는다." **두 기준은 서로
다른 것이며 Morris 자신도 하나로 못박지 않는다.** 호가 단위 기준은 종목마다 다르고,
고저 범위 대비 퍼센트는 변동성에 따라 달라진다.

**넷째 척도, "매우 짧은 그림자" 또는 "긴 그림자".** Nison은 Hammer에서만 숫자를 준다.
**아래꼬리는 실체 높이의 최소 두 배.** 반대쪽인 "위꼬리는 없거나 매우 짧아야 한다"에는
숫자가 없다. Morris는 형식을 준다. 우산형(Umbrella) 날에 대해 **실체 길이를 아래꼬리
길이의 퍼센트로** 다루고, 값을 50으로 두면 실체가 아래꼬리의 절반을 넘을 수 없으니
아래꼬리가 실체의 최소 두 배가 된다고 적는다. 이것은 Nison의 두 배와 맞아떨어진다.
위꼬리는 **그날의 고저 범위에 대한 퍼센트**로 다루며, 값을 10으로 두면 위꼬리가 고저
범위의 10퍼센트 이하라는 뜻이라고 적는다. 슈팅스타와 역해머는 이 설정을 뒤집어 쓴다고
덧붙인다. 그러므로 **아래꼬리 기준은 실체 대비, 위꼬리 기준은 고저 범위 대비**로 서로 다른
분모를 쓴다는 것이 Morris의 방식이며, 이 비대칭을 그대로 따를지가 결정 사항이다.

**다섯째 척도, "거의 같다".** Separating Lines는 시가가 같아야 하고, Meeting Lines
(Counterattack)와 Matching Low와 Stick Sandwich는 종가가 같아야 하며, Identical Three
Crows는 각 날이 전날 종가에서 열려야 한다. Morris는 6장에서 이 문제를 따로 다루며
**"도지 날을 정할 때 쓴 것과 같은 개념을 여기에도 쓸 수 있다"**고 적는다. 그리고 개별
패턴에서는 앞서 인용한 **1/1000** 같은 아주 좁은 허용오차를 쓰기도 한다. 곧 **넓은 기준과
좁은 기준이 같은 책 안에 함께 있고, 어느 쪽을 쓸지는 정해져 있지 않다.**

**여섯째 척도, "가깝다"와 "비슷하다".** Side-by-Side White Lines는 두 실체가 "비슷한
크기"여야 하고, Stalled Pattern은 셋째 날이 둘째 날 종가 "가까이"에서 열려야 하며,
Advance Block은 실체가 "점점 작아지는" 것을 봐야 한다. Rickshaw Man은 시가와 종가가
범위의 "한가운데"에 있어야 한다. **이 척도에는 Nison도 Morris도 숫자를 주지 않는다.**

## 3.2 여기에 더해 "직전 추세"가 있다

위 여섯 척도와 성격이 다른, 그러나 영향 범위는 가장 넓은 공백이 하나 더 있다.
**Nison은 반전형 패턴 거의 전부에 직전 추세를 요구한다.** Engulfing의 첫 기준이 "뚜렷하게
규정할 수 있는 추세"이고, Hammer와 Hanging Man은 모양이 같아서 **오로지 직전 추세로만
구별된다.** 그런데 Nison은 추세를 어떻게 재는지 정하지 않는다. "단기 추세여도 된다"고만
적는다.

**Morris는 여기에 숫자를 준다.** 그는 6장에서 "여러 시험을 거친 결과 자료의 단기 지수
평활이 단기 추세를 가장 잘 짚어냈다"고 적고, "**지수 기간 10일**이 어느 값 못지않게 잘
듣는 것으로 나타났다"고 밝힌다. 개별 패턴 설명에서는 이를 "**첫날 범위의 중간값이
10기간 이동평균 위에 있다. 이는 상승 추세가 자리잡고 있었다는 뜻이다**"처럼 쓴다.

곧 직전 추세에 대해서는 **원전이 숫자를 주는 경우와 주지 않는 경우가 갈린다.** Nison은
요구만 하고 재는 법을 주지 않으며, Morris는 10기간 지수이동평균과 그날 범위 중간값의
비교라는 구체적인 방법을 준다.

## 3.3 원전이 숫자를 주는 자리를 따로 모으면

지시서가 요구한 대로, 원전이 숫자를 준 곳과 주지 않은 곳을 갈라 적는다.

**원전이 숫자를 준 것.**

- Hammer와 Hanging Man의 아래꼬리는 실체의 **최소 두 배** (Nison, 4장).
- Dark-Cloud Cover의 침투 깊이는 앞 양봉 실체의 **50퍼센트 초과** (Nison, 4장. 다만
  Nison은 이를 "일부 일본 기술적 분석가가 요구한다"고 적어 자기 규정이 아니라 관행으로
  소개한다. 용어사전에서는 "되도록 절반보다 더"라고 완화한다).
- Piercing의 침투 깊이는 앞 음봉 실체의 **절반 초과** (Nison, 4장).
- Thrusting은 앞 실체 안으로 들어오되 **중간점을 넘지 않는다** (Morris).
- 긴 실체는 고저 범위의 **50퍼센트 초과** (Morris, 여러 패턴의 Pattern Flexibility).
- 긴 날은 고저 범위가 중간값의 **1.5퍼센트** 초과이거나 직전 5일 고저 범위 평균의
  **0.75배** 초과 (Morris).
- 긴 날을 최근 실체 평균으로 잴 때 평균 기간 **X는 5에서 10 사이**, 임계는 예로 **130퍼센트**
  (Morris, 6장).
- 도지 실체는 고저 범위의 **1~3퍼센트** 정도 (Morris, 6장).
- 우산형의 실체는 아래꼬리의 **50퍼센트** 이하, 위꼬리는 고저 범위의 **10퍼센트** 이하
  (Morris, 6장. 예시 값으로 제시).
- Matching High에서 두 종가가 같다고 볼 허용오차는 **1/1000** (Morris).
- 추세 판정은 **10기간 지수이동평균**과 그날 범위 중간값의 비교 (Morris, 6장).
- Hikkake의 확인은 **세 봉 안에** 일어나야 한다 (Chesler, 2004).

**원전이 숫자를 주지 않은 것.**

- Nison의 도지 허용오차. "거의 같은"이라고만 적는다.
- Nison의 "없거나 매우 짧은 위꼬리".
- 별(star) 계열에서 셋째 날이 첫 실체 안으로 "깊이" 마감한다고 할 때 그 깊이.
  **Morning Star와 Evening Star에 침투율을 주는 서술을 Nison 본문에서 찾지 못했다.**
  Dark-Cloud Cover에는 50퍼센트가 있으나 별 계열에는 대응하는 숫자가 없다.
- "비슷한 크기", "가까이", "점점 작아지는", "한가운데" 계열 전부.
- Advance Block에서 약해짐을 위꼬리로 볼지 실체 크기로 볼지의 선택. Nison은 둘 다
  "could be"로 적고 정하지 않는다.
- Chesler의 "자기 범위의 꼭대기(바닥)에서 마감"의 허용오차.
- Nison이 요구하는 직전 추세를 재는 방법. Morris는 주지만 Nison은 주지 않는다.

**Morris가 일부 패턴에 수치를 붙였다고 알려진 부분은 사실이었으나, 그 성격을 정확히
적어야 한다.** Morris가 준 것은 대체로 **고정 상수가 아니라 매개변수가 있는 형식과 권장
범위**다. 그는 6장에서 "엄격한 규칙은 없고 지침만 있다"고 명시적으로 적는다. 그러므로
"Morris를 따른다"는 말만으로는 구현이 확정되지 않으며, **형식은 Morris에서 가져오되 값은
우리가 골라야 한다.** 이 구별이 흐려지면 우리가 고른 값이 마치 원저자의 정의인 것처럼
문서에 남게 된다.

---

# 4. 61종 각각의 실행 가능한 정의

## 4.0 이 장을 읽는 법

패턴마다 다음을 적었다.

- **원전과 위치.** 책과 장, 그리고 추출본의 줄 번호다. 줄 번호는 아래 부록에 적은
  디렉터리의 `morris_cce.txt`, `nison_jcct.txt`, `chesler_hikkake_2004.txt` 기준이며
  `L####`로 표기한다. 이 번호로 곧바로 원문을 다시 열 수 있다.
- **Morris 머리말.** Morris 3판은 패턴마다 `Trend Required`와 `Confirmation` 필드를
  둔다. 확인 등급은 `Required`(필수), `Suggested`(권고), `No`(불필요) 셋 가운데 하나다.
  이 값은 내가 판단한 것이 아니라 **Morris가 적어 둔 것**이다.
- **판정 규칙.** 원문을 그대로 인용하고 번역을 덧붙였다. 봉의 개수와 순서, 색, 실체와
  그림자의 관계, 갭의 유무와 방향, 포함 관계를 담았다.
- **남는 정성 표현.** 3장에서 정리한 여섯 척도 가운데 무엇을 정해야 하는지 적었다.
- **부등식.** 원전이 엄격 부등식인지 등호를 허용하는지 밝힌 자리만 적었다. 밝히지 않은
  자리는 밝히지 않았다고 적었다.

**원전에 판정 규칙이 없는 패턴은 없다고 적었고 지어내지 않았다.** 그런 패턴은 4.6절에
따로 세었다.

**사용자가 확정한 네 결정을 이 장 전체에 적용했다.** 적용 방식은 다음과 같다.

- **결정 A(수치 척도의 출처).** 원전이 수치를 준 자리는 그 수치를 그대로 썼다. 원전이
  비워 둔 자리는 값을 지어내지 않고 **"우리가 정해야 하는 것"으로 표시**했다. 값 자체는
  표준 문서를 쓸 때 정하며, 그때 그것이 원저자의 정의가 아니라 우리가 고른 규약임을
  명시해야 한다. 값을 비워 두었다는 이유로 패턴을 보류한 곳은 없다.
- **결정 B(직전 추세).** 원전이 추세를 요구하는 패턴마다 정의의 첫 항에 추세 조건을 넣고
  **"10기간 지수이동평균 기준"**이라고 적었다. 판정 방법은 61종 전부에서 하나로 같다.
  Morris가 6장에서 "the exponential period of 10 days seemed to work as well as any"라고
  적고 개별 패턴에서 "the midpoint of the range of the first day is above a 10-period moving
  average"라고 쓰는 방식을 그대로 따른다. 곧 **해당 봉 범위의 중간값이 10기간 지수이동평균
  위이면 상승, 아래이면 하락**이다. 이 판정은 패턴이 직접 하며 전략에 넘기지 않는다.
  그러므로 Hammer와 Hanging Man처럼 모양이 같고 추세로만 갈리는 쌍은 **서로 다른 패턴으로
  남는다.**
- **결정 C(조건 충돌).** 좁고 엄격한 쪽을 규범으로 삼았다. Morris 안에서 규칙 절과 유연성
  절이 어긋나면 규칙 절이 규범이고 유연성 절은 주석으로만 남겼다. Nison과 Morris가 어긋나면
  조건이 더 많은 쪽을 규범으로 삼아 한쪽에만 있는 조건을 채택했다. 충돌이 있었던 패턴과
  채택 결과는 5.3절에 모았다.
- **결정 D(갭).** 원전 정의를 바꾸지 않았다. 패턴마다 그 갭이 **실체 사이인지, 꼬리를
  포함한 고저 범위 사이인지, 단순 시가 갭인지**를 원문에서 확인해 적었고, 원문이 구분하지
  않으면 구분하지 않는다고 적었다. 24시간 시장에서 발생 빈도가 낮아지는 것은 받아들이며,
  나중에 실제 자료로 빈도를 재어 보고한다.

절마다 마지막에 **필요한 척도**와 **우리가 정해야 하는 것**을 적었다. 이 두 가지가 5.4절
표의 두 열이 되고 그대로 표준 문서의 입력이 된다.

Morris의 규칙은 강세형과 약세형이 한 묶음으로 쓰여 있는 경우가 많다. 그럴 때는 한 번만
인용하고 반대 방향은 좌우를 뒤집어 읽으라고 적었다. 뒤집는 방식이 대칭이 아닌 경우에는
따로 적었다.

**모든 Morris 패턴은 `Trend Required: Yes`다. 딱 하나, Kicking만 `No`다.** 이 사실이
5장의 정리를 지배한다.

## 4.1 단일 캔들 가운데 도지 계열과 우산형 (11종)

### 1. `CDLDOJI` — Doji

원전은 Morris 3판 2장(`morris_cce.txt` L1662 부근의 DOJI 절)과 Nison 2판 3장·8장이다.
Nison 용어사전(`nison_jcct.txt` L7000 부근)은 "A session in which the open and close are
the same (or almost the same)"라고 적는다. 곧 시가와 종가가 같거나 거의 같은 세션이다.

Morris 2장의 서술을 그대로 옮기면 이렇다. "A Doji occurs when the open and close for that
day are the same, or certainly very close to being the same. The lengths of the shadows can
vary." 번역하면, 도지는 그날의 시가와 종가가 같거나 확실히 아주 가까울 때 성립하며 꼬리의
길이는 어떻든 상관없다.

판정 규칙은 하나뿐이다.

1. 시가와 종가의 차이가 허용오차 안에 있다.

남는 정성 표현은 "거의 같다"이며 **도지 척도**로 수치화해야 한다. Morris 6장은 형식과 권장
범위를 준다. 실체를 그날 고저 범위와 견주는 최대 퍼센트이고 "A value in the neighborhood
of 1 to 3% seems to work quite well"이라고 적는다. 2장에서는 다른 기준도 말한다.
"If the difference between the open and close prices is within a few ticks (minimum trading
increments), it is more than satisfactory." 두 기준은 서로 다르며 Morris가 하나로 정하지
않았다.

부등식은 원전이 밝히지 않았다. 확인 봉은 Morris가 도지를 단일 캔들 선으로 다루므로 머리말
필드가 없다. 다만 2장은 "In almost all cases, a Doji by itself would not be significant
enough to forecast a change in the trend of prices, only a warning of impending trend
change"라고 적어, 도지 하나만으로는 추세 전환을 예고하기에 충분하지 않고 임박한 전환의
경고일 뿐이라고 밝힌다.

### 2. `CDLLONGLEGGEDDOJI` — Long-Legged Doji

원전은 Morris 3판 2장(`morris_cce.txt` L1690 부근)과 Nison 2판 8장·용어사전이다.
Morris는 "The Long-Legged Doji has long upper and lower shadows in the middle of the day's
trading range"라고 적는다. 곧 위아래 꼬리가 길고 그날 거래 범위의 한가운데에 있다.
Nison 용어사전은 "A doji with very long shadows"라고 적는다.

1. 그 봉이 도지다.
2. 위꼬리와 아래꼬리가 모두 길다.

남는 정성 표현은 도지 허용오차(**도지 척도**)와 "긴 꼬리"(**그림자 척도**)다. 분모를
무엇으로 삼을지는 3장에서 적었듯 정해져 있지 않다. 부등식은 밝히지 않았다.

### 3. `CDLRICKSHAWMAN` — Rickshaw Man

원전은 Nison 2판 8장·용어사전(`nison_jcct.txt` L4430, L4440, L7042 부근)이다. **Morris
3판에는 `rickshaw`라는 낱말이 한 번도 나오지 않는다.** Nison은 용어사전에서
"Rickshaw man—The nickname for the long-legged doji"라고 적고, Long-legged doji 항목에서
"If the opening and closing of a long-legged doji session are in the middle of the session's
range, the line is called a rickshaw man"이라고 적는다.

1. 그 봉이 Long-Legged Doji다.
2. 시가와 종가가 세션 범위의 **한가운데**에 있다.

남는 정성 표현은 "한가운데"(**가까움 척도**)이며, 범위의 중점에서 얼마나 벗어나도 되는지
원전이 정하지 않았다. 도지 척도와 그림자 척도도 함께 정해야 한다. 부등식은 밝히지 않았다.

### 4. `CDLDRAGONFLYDOJI` — Dragonfly Doji

원전은 Morris 3판 2장(`morris_cce.txt` L1731 부근)과 Nison 2판 8장·용어사전이다.
Morris는 "The Dragonfly Doji, or Tonbo (pronounced Tombo), occurs when the open and close
are at the high of the day"라고 적는다. Nison 용어사전은 "A doji with a long lower shadow
and where the open, high, and close are at the session's high"라고 적어 시가와 고가와
종가가 모두 세션 고가에 있다고 말한다.

1. 그 봉이 도지다.
2. 시가와 종가가 그날의 고가에 있다. 곧 위꼬리가 없다.
3. 아래꼬리가 길다.

Nison은 고가까지 셋이 같다고 하고 Morris는 시가와 종가만 말한다. **결정 C에 따라 조건이
더 많은 Nison을 채택한다.** 곧 시가와 종가뿐 아니라 **고가까지 같아야 한다.** 이는 위꼬리가
없다는 것과 같은 말이므로 Morris의 서술과 충돌하지 않고 그것을 좁힌다.

**최종 정의는 이렇다.**

1. 그 봉이 도지다.
2. 시가와 종가와 **고가가 모두 같다.** 곧 위꼬리가 없다.
3. 아래꼬리가 길다.

갭은 쓰지 않는다. 필요한 척도는 **도지**와 **그림자**다. 우리가 정해야 하는 것은 도지
허용오차와 "긴 아래꼬리"의 임계 둘이다. 규칙 2는 등호이므로 부등식 문제가 없다.

### 5. `CDLGRAVESTONEDOJI` — Gravestone Doji

원전은 Morris 3판 2장(`morris_cce.txt` L1712 부근)과 Nison 2판 8장·용어사전이다.
Morris는 "It develops when the Doji is at, or very near, the low of the day"라고 적고,
"If the upper shadow is quite long, it means that the Gravestone Doji is much more bearish"
라고 덧붙인다. Nison 용어사전은 "A doji in which the opening and closing are at the low of
the session"이라고 적는다.

1. 그 봉이 도지다.
2. 시가와 종가가 그날의 저가에 있거나 아주 가깝다. 곧 아래꼬리가 없다.
3. 위꼬리가 길다.

**두 원전의 엄격성이 다르고 결정 C가 이를 닫는다.** Morris는 "at, or very near"라고 적어
근접을 허용하고, Nison 용어사전은 "the opening and closing are at the low of the session"
이라고 적어 **정확한 일치**를 요구한다. 조건이 더 좁은 쪽이 Nison이므로 **Nison을 채택한다.**
Morris의 근접 허용은 주석으로만 남긴다.

**최종 정의는 이렇다.**

1. 그 봉이 도지다.
2. 시가와 종가가 그날의 **저가와 같다.** 곧 아래꼬리가 없다.
3. 위꼬리가 길다.

갭은 쓰지 않는다. 필요한 척도는 **도지**와 **그림자**다. 규칙 2를 Nison대로 등호로 읽으므로
**가까움 척도는 필요 없다.** 우리가 정해야 하는 것은 도지 허용오차와 "긴 위꼬리"의 임계
둘이다.

### 6. `CDLTAKURI` — Takuri

원전은 Morris 3판 3장 Hammer 절의 해설(`morris_cce.txt` L1126~1129)이다. 여기에 **원전이
직접 준 수치**가 있다. "A Takuri line has a lower shadow at least three times the length of
the body, whereas the lower shadow of a Hammer is a minimum of only twice the length of the
body." 곧 Takuri 선은 아래꼬리가 실체 길이의 **최소 세 배**이고, Hammer는 최소 두 배다.
Morris 2장(L1740 부근)은 "A Tonbo line with a very long lower shadow (tail) (shitahigi) is
also called a Takuri line. A Takuri line at the end of a down trend is extremely bullish"
라고 적는다. Nison 2판에서 `takuri`는 `nison_jcct.txt` L1250에 한 번만 나온다.

1. 그 봉이 Dragonfly Doji(Tonbo)의 모양이다.
2. 아래꼬리가 실체 길이의 **세 배 이상**이다.

**이 패턴은 아래꼬리 배수를 원전이 숫자로 주었다.** 남는 정성 표현은 도지 척도와 실체가
0일 때의 처리다. 실체가 0이면 "세 배"가 정의되지 않으므로 **퇴화 봉 규칙**이 반드시
필요하다(결정 3). 부등식은 "at least"이므로 **등호를 허용한다.**

### 7. `CDLHAMMER` — Hammer

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L1108, 규칙 L1149)과 Nison 2판 4장
(`nison_jcct.txt` L1236 부근)이다. Morris 머리말은 **Trend Required = Yes,
Confirmation = Required**다. 곧 확인이 필수다.

Morris의 규칙을 그대로 옮기면 이렇다.

> 1. The small real body is at the upper end of the trading range.
> 2. The color of the body is not important.
> 3. The long lower shadow should be much longer than the length of the real body,
>    usually two or three times.
> 4. There should be no upper shadow, or if there is, it should be very small.

번역하면 다음과 같다.

1. 작은 실체가 거래 범위의 위쪽 끝에 있다.
2. 실체의 색은 중요하지 않다.
3. 긴 아래꼬리가 실체 길이보다 훨씬 길어야 하며 보통 두 배에서 세 배다.
4. 위꼬리가 없어야 하고, 있더라도 아주 작아야 한다.

Nison 4장은 아래꼬리에 대해 "at least twice the height of the real body"라고 적어 **최소
두 배**라는 숫자를 준다. 곧 이 자리는 원전이 숫자를 주었다. Hammer와 Hanging Man을 가르는
것은 모양이 아니라 직전 추세이며, Nison은 "A hammer must come after a decline. A hanging
man must come after a rally"라고 적는다.

**아래꼬리 배수는 원전이 확정한다.** 규칙 절은 "usually two or three times"라고 열어 두지만,
같은 장의 해설 `morris_cce.txt` L1126~L1129가 "the lower shadow of a Hammer is a minimum of
only twice the length of the body"라고 적어 **최소 두 배**로 못박는다. 같은 문장이 Takuri를
최소 세 배로 구별하므로 두 값이 서로 다른 패턴을 가르는 기준임이 분명하다. Nison 4장도
"at least twice the height of the real body"라고 적어 같다. **따라서 두 배를 채택하고
규칙 절의 "두 배에서 세 배"는 주석으로만 남긴다.** 앞 판이 "배수를 하나로 정해야 한다"고
적은 것은 이 해설을 놓친 탓이었고 철회한다.

**최종 정의는 이렇다.**

1. 직전 추세가 **하락**이다.
2. 작은 실체가 그 봉 거래 범위의 **위쪽 끝**에 있다. 실체의 색은 중요하지 않다.
3. 아래꼬리가 실체 길이의 **두 배 이상**이다.
4. 위꼬리가 없거나 아주 작다.

갭은 쓰지 않는다. 필요한 척도는 **짧은실체**, **가까움**, **그림자**, **직전 추세**다.
부등식은 "at least"이므로 등호를 허용한다. 우리가 정해야 하는 것은 짧은실체 임계, "위쪽
끝"의 허용폭, 위꼬리 상한 셋이다. 실체가 0이면 두 배가 정의되지 않아 **퇴화 봉 규칙**이
필요하다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **하락**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 8. `CDLHANGINGMAN` — Hanging Man

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L1119, 규칙 L1149)과 Nison 2판 4장이다.
**규칙 본문은 Hammer와 같은 묶음이며 위 7번과 동일하다.** Morris 머리말은
**Trend Required = Yes, Confirmation = No**다.

여기서 원전 사이의 어긋남을 짚어야 한다. **Morris는 Hanging Man의 확인을 불필요로 적었고,
Nison은 정반대로 적었다.** Nison 4장은 "A hanging man should be confirmed, while a hammer
need not be"라고 쓴다. 곧 Nison은 행잉맨에 확인이 필요하고 해머는 필요 없다고 하는데,
Morris 머리말은 Hammer가 `Required`이고 Hanging Man이 `No`다. **두 원전이 반대로 말한다.**
어느 쪽을 따를지는 **결정 C가 정했다.** 조건이 더 많은 쪽이 규범이므로 확인을 요구하는 Nison을
채택한다. 5.3절에 기록했다.

**최종 정의는 이렇다.**

1. 직전 추세가 **상승**이다.
2. 작은 실체가 그 봉 거래 범위의 **위쪽 끝**에 있다. 실체의 색은 중요하지 않다.
3. 아래꼬리가 실체 길이의 **두 배 이상**이다.
4. 위꼬리가 없거나 아주 작다.
5. **다음 날 약세 확인을 받는다.** Nison L1419~L1422는 최소 요건을 다음 날 시가가 실체
   아래에서 열리는 것으로, 권장 요건을 다음 날 종가가 실체 아래에서 마감하는 것으로 적는다.
   둘 가운데 어느 쪽을 쓸지는 결정 12가 정한다.

곧 모양은 Hammer와 같고 직전 추세와 확인 요건만 다르다. 필요한 척도와 정해야 하는 것은
7번과 같으며, 여기에 확인의 정의가 더해진다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **상승**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 9. `CDLINVERTEDHAMMER` — Inverted Hammer

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L1749, 규칙 L1796)과 Nison 2판 5장이다.
Morris 머리말은 **Trend Required = Yes, Confirmation = No**다. Morris의 규칙 원문은
Shooting Star와 한 묶음으로 쓰여 있으며 Inverted Hammer 몫은 다음과 같다.

> 1. A small real body is formed near the lower part of the price range.
> 2. No gap down is required, as long as the pattern falls after a downtrend.
> 3. The upper shadow is usually no more than two times as long as the body.
> 4. The lower shadow is virtually nonexistent.

번역하면 이렇다.

1. 작은 실체가 가격 범위의 아래쪽 부분 가까이에 만들어진다.
2. 패턴이 하락 추세 뒤에 오기만 하면 **갭 하락은 요구되지 않는다.**
3. 위꼬리는 보통 실체 길이의 두 배를 넘지 않는다.
4. 아래꼬리는 사실상 없다.

**규칙 3은 상한이지 하한이 아니다.** 곧 Morris의 Inverted Hammer는 위꼬리가 실체의 두 배
이하여야 한다. 아래 10번 Shooting Star가 세 배 이상을 요구하는 것과 대비된다. 이 비대칭은
Morris 본문 그대로이며 내가 만든 것이 아니다.

**Nison이 확인 요건을 더한다.** Morris 머리말은 `Confirmation = No`이지만
`nison_jcct.txt` L2428~L2432는 이렇게 적는다.

> Just as a hanging man needs bearish confirmation, the inverted hammer needs bullish
> confirmation. This confirmation could be in the form of the next day opening above the
> inverted hammer's real body or especially a close the next day over the inverted hammer's
> real body.

번역하면, 행잉맨이 약세 확인을 받아야 하듯 역해머는 **강세 확인을 받아야 한다.** 그 확인은
**다음 날 시가가 역해머의 실체 위에서 열리는 것**이거나, 특히 **다음 날 종가가 역해머의
실체 위에서 마감하는 것**이다.

**결정 C에 따라 채택한다.** Nison에만 있는 조건이고 조건이 더 많은 쪽이 규범이다. 8번
Hanging Man에서 이미 같은 이유로 Nison의 확인 요구를 채택했으므로 처리도 일관된다.
**Nison은 확인 조건을 두 갈래로 적고 기한을 다음 날로 한정한다.** 두 갈래 가운데 어느
쪽을 쓸지는 결정 11이 정한다.

**최종 정의는 이렇다.**

1. 직전 추세가 **하락**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다. 이 패턴은 한 봉
   짜리이므로 첫날이 곧 그 봉이다.
2. 작은 실체가 가격 범위의 아래쪽 부분 가까이에 있다.
3. 위꼬리가 실체 길이의 **두 배 이하**다.
4. 아래꼬리는 사실상 없다.
5. **다음 날 강세 확인을 받는다.** 확인의 정의는 결정 11이 정한다.

갭은 쓰지 않는다. Morris 규칙 2가 갭 하락이 요구되지 않는다고 명시한다. 필요한 척도는
**짧은실체**, **가까움**, **그림자**, **직전 추세**다. 부등식은 "no more than"이므로 등호를
허용한다. 우리가 정해야 하는 것은 짧은실체 임계, "아래쪽 부분"의 허용폭, 아래꼬리 상한,
그리고 확인의 정의 넷이다.

### 10. `CDLSHOOTINGSTAR` — Shooting Star

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L1771, 규칙 L1796)과 Nison 2판 5장이다.
Morris 머리말은 **Trend Required = Yes, Confirmation = Required**다.

> 1. Prices gap open after an uptrend.
> 2. A small real body is formed near the lower part of the price range.
> 3. The upper shadow is at least three times as long as the body.
> 4. The lower shadow is virtually nonexistent.

번역하면 이렇다.

1. 상승 추세 뒤에 가격이 **갭을 두고 열린다.**
2. 작은 실체가 가격 범위의 아래쪽 부분 가까이에 만들어진다.
3. 위꼬리가 실체 길이의 **최소 세 배**다.
4. 아래꼬리는 사실상 없다.

**Morris의 Shooting Star는 갭을 요구하고 Inverted Hammer는 요구하지 않는다.** 이 차이가
두 패턴을 가른다. Nison 용어사전은 갭을 요구하지 않고 "a small real body near the lows of
the session that arises after an uptrend"라고만 적으므로 두 원전이 갭 요건에서 어긋난다.
**결정 C에 따라 조건이 더 많은 Morris를 채택한다.** 곧 **갭 상승 시가를 필수 조건으로
둔다.**

**최종 정의는 이렇다.**

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다. 이 패턴은 한 봉짜리
   이므로 첫날이 곧 그 봉이다.
2. 그 봉은 **갭을 두고 열린다.**
3. 작은 실체가 가격 범위의 아래쪽 부분 가까이에 있다.
4. 위꼬리가 실체 길이의 **세 배 이상**이다.
5. 아래꼬리는 사실상 없다.

갭은 **단순 시가 갭**이다. Morris 규칙 1이 "Prices gap open"이라고만 적고 실체 기준인지
고저 범위 기준인지 구분하지 않으므로, 앞 봉의 종가 대비 시가의 위치로만 읽는다. 필요한
척도는 **짧은실체**, **가까움**, **그림자**, **직전 추세**다. 부등식은 "at least"이므로
등호를 허용한다. 실체가 0이면 세 배가 정의되지 않아 **퇴화 봉 규칙**이 필요하다. 우리가
정해야 하는 것은 짧은실체 임계, "아래쪽 부분"의 허용폭, 아래꼬리 상한 셋이다.

### 11. `CDLSPINNINGTOP` — Spinning Top

원전은 Morris 3판 2장(`morris_cce.txt` L1645 부근)과 Nison 2판 3장이다. Morris는
"Spinning Tops are candlestick lines that have small real bodies with upper and lower
shadows that are of greater length than the body's length"라고 적고, "The color of the body
of a spinning top, along with the actual size of the shadows, is not important. The small
body relative to the shadows is what makes the spinning top"이라고 덧붙인다.

1. 실체가 작다.
2. 위꼬리와 아래꼬리가 **모두** 실체 길이보다 길다.
3. 실체의 색은 중요하지 않다.

**규칙 2는 순수한 대소 비교다.** 꼬리 길이를 실체 길이와 직접 견주므로 바깥 척도가 필요
없다. 남는 정성 표현은 규칙 1의 "작은 실체"(**짧은실체 척도**)뿐이다. 다만 Morris가
"The small body relative to the shadows is what makes the spinning top"이라고 적은 것을
규칙 2가 이미 담고 있다고 읽으면 규칙 1이 규칙 2에 흡수되며, 그 경우 이 패턴은 척도 없이
판정된다. **두 읽기가 갈리는 자리이므로 결정이 필요하다.** 부등식은 "greater than"이므로
엄격 부등식이다. 실체가 0이면 규칙 2가 항상 참이 되므로 퇴화 봉 규칙이 필요하다.

## 4.2 단일 캔들 가운데 몸통과 그림자의 형태 (6종)

### 12. `CDLHIGHWAVE` — High-Wave Candle

원전은 Nison 2판 용어사전(`nison_jcct.txt` L4438, L5277 부근)이다. "High-wave candle—A
candle with very long upper and lower shadows and a small real body. It shows that the
market is losing its direction." 곧 위아래 꼬리가 매우 길고 실체가 작은 캔들이며 시장이
방향을 잃고 있음을 보인다.

**Morris 3판에는 이 단일 캔들 항목이 없다.** `morris_cce.txt` L7691의 "HIGH WAVES
(TUKANE NOCHIAL)"는 Sakata 장에 있는 **여러 봉의 위꼬리가 만드는 형태**를 가리키는 다른
개념이므로 이 패턴의 원전으로 쓸 수 없다.

1. 실체가 작다.
2. 위꼬리와 아래꼬리가 **모두 매우 길다.**

남는 정성 표현은 "작은 실체"(**짧은실체 척도**)와 "매우 긴 꼬리"(**그림자 척도**)다.
Spinning Top과의 경계가 정도의 차이뿐이므로, **두 패턴이 동시에 성립할 때 어떻게 할지**
정해야 한다. 부등식은 밝히지 않았다.

### 13. `CDLMARUBOZU` — Marubozu

원전은 Morris 3판 2장(`morris_cce.txt` L1600 부근)이다. **Nison 2판에는 `marubozu`라는
낱말이 한 번도 나오지 않으며**, 같은 개념을 3장에서 shaven head와 shaven bottom으로
부른다. Morris는 "Marubozu means close-cropped or close-cut in Japanese... the meaning
reflects the fact that there is no shadow extending from the body at either the open or the
close, or at both"이라고 적고, 이어서 "A Black Marubozu is a long black body with no
shadows on either end", "A White Marubozu is a long white body with no shadow on either
end"이라고 적는다.

1. 실체가 길다.
2. 위꼬리와 아래꼬리가 **모두 없다.**

**규칙 2는 문자 그대로 읽으면 시가와 종가가 각각 저가와 고가에 정확히 일치해야 한다는
뜻이다.** 원전은 허용오차를 주지 않았다. 남는 정성 표현은 "긴 실체"(**긴실체 척도**)이고,
"꼬리가 없다"를 엄격한 등호로 볼지 허용오차를 둘지가 **부등식 엄격성 결정**(결정 2)에
걸린다.

### 14. `CDLCLOSINGMARUBOZU` — Closing Marubozu

원전은 Morris 3판 2장(`morris_cce.txt` L1618 부근)이다. "A Closing Marubozu has no shadow
extending from the close end of the body, whether the body is white or black. If the body is
white, there is no upper shadow because the close is at the top of the body. Likewise, if the
body is black, there is no lower shadow because the close is a the bottom of the body."

1. 실체가 길다.
2. 양봉이면 위꼬리가 없다. 곧 종가가 고가와 같다.
3. 음봉이면 아래꼬리가 없다. 곧 종가가 저가와 같다.
4. 반대쪽 꼬리는 있어도 된다.

Morris는 같은 절에서 Opening Marubozu도 정의하며 "The Opening Marubozu is not as strong as
the Closing Marubozu"라고 적는다. **TA-Lib은 Closing Marubozu만 함수로 두고 Opening
Marubozu는 두지 않는다.** 남는 정성 표현과 부등식 문제는 13번과 같다.

### 15. `CDLBELTHOLD` — Belt-hold

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L1257과 L1268, 규칙 L1296)과 Nison 2판
6장(`nison_jcct.txt` L2792 부근)이다. Morris 머리말은 강세형이 **Trend Required = Yes,
Confirmation = Suggested**이고 약세형이 **Trend Required = Yes, Confirmation = Required**다.
곧 **같은 패턴인데 방향에 따라 확인 등급이 다르다.**

> 1. The Belt Hold line is identified by the lack of a shadow on one end.
> 2. The bullish white Belt Hold opens on its low and has no lower shadows.
> 3. The bearish black Belt Hold opens on its high and has no upper shadows.

번역하면 이렇다.

1. Belt Hold 선은 한쪽 끝에 꼬리가 없는 것으로 알아본다.
2. 강세형 양봉 Belt Hold는 저가에서 열리며 아래꼬리가 없다.
3. 약세형 음봉 Belt Hold는 고가에서 열리며 위꼬리가 없다.

**Marubozu가 종가 쪽을 보는 데 비해 Belt-hold는 시가 쪽을 본다.** 곧 Opening Marubozu와
같은 모양이다.

**Nison이 조건과 허용오차를 함께 준다.** `nison_jcct.txt` L2793~L2805에 있다.

> The bullish belt-hold is a strong white candle that opens on the low of the session (or
> with a very small lower shadow) and closes at, or near, the session highs.
>
> The bearish belt-hold is a long black candle that opens on the high of the session (or
> within a few ticks of the high) and continues lower through the session.
>
> The longer the height of the belt-hold candle line, the more significant it becomes.

번역하면 이렇다. 강세형은 세션 저가에서 열리거나 **아주 작은 아래꼬리**만 두고 열리며,
**세션 고가에 또는 그 가까이에서** 마감하는 강한 양봉이다. 약세형은 세션 고가에서 열리거나
**고가에서 몇 틱 안**에서 열려 세션 내내 낮아지는 긴 음봉이다. 그리고 belt-hold 선은
**길수록 의미가 커진다.**

**결정 C에 따라 자리마다 좁은 쪽을 고른다.** 이 서술에는 넓히는 것과 좁히는 것이 섞여 있다.

- **시가 쪽 꼬리 허용오차.** Nison의 "아주 작은 아래꼬리"와 "고가에서 몇 틱 안"은 Morris의
  "꼬리가 없다"를 **넓힌다.** 따라서 **채택하지 않고 Morris의 무꼬리 요건을 규범으로
  삼는다.** Nison의 허용오차는 주석으로만 남긴다.
- **강세형의 종가 위치.** Nison은 "세션 고가에 또는 그 가까이에서 마감"을 **추가로**
  요구한다. Morris에는 없는 조건이고 좁히는 쪽이므로 **채택한다.**
- **실체 길이.** Nison은 강세형을 "strong white candle", 약세형을 "long black candle"이라
  하고 길수록 의미가 크다고 적는다. Morris 규칙에는 길이 요건이 없으므로 이는 **추가**이며
  좁히는 쪽이므로 **채택한다.**

최종 정의는 이렇다(강세형 기준).

1. 직전 추세가 **하락**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다. 이 패턴은 한 봉
   짜리이므로 첫날이 곧 그 봉이다. **약세형은 방향이 반대여서 직전 추세가 상승이고, 중간값이
   이동평균 위이면 상승으로 본다.**
2. **긴 양봉**이다.
3. **아래꼬리가 없다.** 곧 시가가 저가와 같다.
4. 종가가 세션 **고가에 또는 그 가까이** 있다.

약세형은 좌우를 뒤집되, 종가 위치 조건은 Nison이 약세형에 대해 "continues lower through
the session"이라고만 적어 대칭으로 명시하지 않았다. **그 비대칭은 원문 그대로 두고 약세형에
종가 조건을 넣지 않는다.**

갭은 쓰지 않는다. 필요한 척도는 **긴실체**, **그림자**(무꼬리 판정), **가까움**(강세형의
종가 위치), **직전 추세**다. 우리가 정해야 하는 것은 강세형 종가가 고가에서 얼마나 떨어져도
"가까이"인지 하나다.

### 16. `CDLLONGLINE` — Long Line Candle

원전은 Morris 3판 2장(`morris_cce.txt` L1571 부근)과 6장의 식별 방법 절이다. 이것은
패턴이 아니라 **캔들 선**이므로 Morris 머리말 필드가 없다. 2장은 "Long describes the
length of the candlestick body, the difference between the open price and the close price...
A long day represents a large price movement for the day"라고 적고, 곧바로 "How much must
the open and close price differ to qualify as a long day? Like most forms of analysis,
context must be considered. Long compared to what?"라고 되묻는다. 그리고 "Anywhere from the
previous 5 to 10 days should be more than adequate"라고 적는다.

1. 실체가 길다.

**이 패턴은 판정 규칙 전체가 곧 척도다.** 그러므로 3장 첫째 척도를 정하면 그대로 정의가
된다. Morris 6장이 세 방법을 주고 하나로 정하지 않았다는 점은 3장에 적었다. 부등식은
"greater than this minimum value"라고 적어 **엄격 부등식**이다.

TA-Lib은 이 함수에서 긴 실체와 짧은 꼬리를 함께 요구하지만, **Morris의 Long Days 서술에는
꼬리 요건이 없다.** 이것은 6장에 적은 대로 TA-Lib이 더한 조건이다.

### 17. `CDLSHORTLINE` — Short Line Candle

원전은 Morris 3판 2장(`morris_cce.txt` L1590 부근)과 6장이다. 2장은 "Short days may also
be based on the same methodology as long days, with comparable results. There are also
numerous days that do not fall into any of these two categories"라고 적는다. 6장은 "The
exact same concept for determining long days is used for short days with one exception;
instead of minimum percentages, maximum percentages are used in the three formulas"라고
적는다.

1. 실체가 짧다.

16번과 마찬가지로 판정 규칙 전체가 척도다. 방법은 긴 날과 같고 **최소 퍼센트 대신 최대
퍼센트를 쓴다.** 부등식은 최대 기준이므로 등호 처리를 정해야 한다. 여기서도 TA-Lib은
꼬리 요건을 더했으나 원전에는 없다.

## 4.3 두 캔들과 그에 준하는 패턴 (16종)

### 18. `CDLENGULFING` — Engulfing

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L1361과 L1384, 규칙 L1407)과 Nison 2판
4장(`nison_jcct.txt` L1504 부근)이다. Morris 머리말은 강세형이 **Trend Required = Yes,
Confirmation = Suggested**, 약세형이 **Trend Required = Yes, Confirmation = Required**다.

> 1. A definite trend must be underway.
> 2. The second day's body must be completely engulfed by the prior day's body. This does
>    not mean, however, that either the top or the bottom of the two bodies cannot be equal;
>    it just means the both tops and both bottoms cannot be equal.
> 3. The first day's color should reflect the trend: black for a downtrend and white for an
>    uptrend.
> 4. The second real body of the engulfing pattern should be the opposite color of the first
>    real body.

번역하면 이렇다.

1. **뚜렷한 추세가 진행 중이어야 한다.**
2. 두 번째 날의 실체가 앞날의 실체를 **완전히 감싸야 한다.** 다만 이것은 두 실체의 위쪽
   끝이나 아래쪽 끝 가운데 **어느 한쪽이 같아서는 안 된다는 뜻이 아니다.** 위쪽 끝과
   아래쪽 끝이 **둘 다** 같아서는 안 된다는 뜻일 뿐이다.
3. 첫날의 색은 추세를 반영해야 한다. 하락 추세면 음봉, 상승 추세면 양봉이다.
4. 두 번째 실체는 첫 실체와 반대색이어야 한다.

**여기서 원문의 오식 하나를 짚어야 한다.** Morris의 규칙 2는 인쇄된 문장 그대로 옮기면
"The second day's body must be completely engulfed by the prior day's body", 곧 **둘째 실체가
앞 실체에 감싸인다**가 된다. 그런데 그것은 감싸는 쪽과 감싸이는 쪽이 뒤바뀐 서술이며,
그대로 구현하면 Engulfing이 아니라 Harami가 된다. Morris 자신의 Harami 규칙 3이
"with its body completely inside the body range of the long day"라고 같은 관계를 적는 것이
그 증거다.

**Morris의 다른 두 절이 올바른 방향을 못박는다.** 유연성 절은 "Engulfing means that no part
of the first day's real body is equal to or outside of the second day's real body"라고 적어
**첫 실체가 둘째 실체 안에 있다**고 말하고, 약세형 시나리오는 둘째 날이 "closes below the
open of the previous day"라고 적어 둘째 실체가 첫 실체를 넘어선다고 말한다. Nison 4장
L1517~L1519도 "a white bullish real body wraps around, or engulfs, the prior period's black
real body"라고 적어 같은 방향이다.

**따라서 규칙 2를 "둘째 실체가 첫 실체를 감싼다"로 읽는다.** 이것은 원전을 바꾸는 것이
아니라 원문의 명백한 오식을 다른 두 절과 Nison으로 교정한 것이며, 앞 판이 인쇄된 문장을
그대로 옮겨 방향을 뒤집어 적었던 것을 바로잡는 것이다.

**등호 처리는 규칙 절이 규범이다.** 규칙 2는 한쪽 끝의 등호를 허용하고 양쪽 끝이 모두 같은
것만 배제한다. 유연성 절은 "no part ... is equal to or outside"라고 적어 등호를 아예
금지하지만, **결정 C에 따라 Morris 안에서는 규칙 절이 규범이고 유연성 절은 주석이므로**
한쪽 등호 허용을 채택한다. 유연성 절이 덧붙인 "첫 실체를 30퍼센트 이상 감싸면 더 강하다"와
"꼬리까지 감싸면 성공률이 훨씬 높다"도 같은 이유로 주석으로만 남긴다.

**최종 정의는 이렇다(강세형 기준).**

1. 직전 추세가 **하락**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
2. 첫날은 **음봉**이다.
3. 둘째 날은 **양봉**이며 그 실체가 첫 실체를 **감싼다.** 이를 한 식으로 쓰면 이렇다.
   둘째 시가가 첫 종가 **이하**이고 둘째 종가가 첫 시가 **이상**이며, **그 둘이 동시에
   같지는 않다.** 곧 두 비교를 모두 비엄격 부등식으로 두되 양 끝이 함께 일치하는 경우만
   배제한다. 이것이 Morris 규칙 2가 "either the top or the bottom ... cannot be equal;
   it just means the both tops and both bottoms cannot be equal"라고 적은 바를 그대로
   옮긴 것이다.
4. 꼬리는 감쌀 필요가 없다.

**약세형은 대칭식으로 쓴다.** 직전 추세가 상승이고, 첫날이 양봉이며, 둘째 날은 음봉으로서
둘째 시가가 첫 종가 **이상**이고 둘째 종가가 첫 시가 **이하**이며 **그 둘이 동시에 같지는
않다.** 꼬리는 마찬가지로 감쌀 필요가 없다.

앞 판은 규칙 3에서 두 관계를 모두 엄격 부등식으로 적어 놓고 바로 뒤에 한쪽 끝은 같아도
된다고 덧붙여 두 문장이 어긋났다. 위의 한 식이 그 어긋남을 없앤다. 갭은 쓰지 않는다. 필요한 척도는 **직전 추세**뿐이고 크기 척도가
필요 없다. 우리가 정해야 하는 것은 없다.

### 19. `CDLHARAMI` — Harami

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L1502와 L1525, 규칙 L1543)과 Nison 2판
6장이다. Morris 머리말은 강세형이 **Trend Required = Yes, Confirmation = No**, 약세형이
**Trend Required = Yes, Confirmation = Required**다.

> 1. A long day is preceded by a reasonable trend.
> 2. The color of the long first day is not as important, but it is best if it reflects the
>    trend of the market.
> 3. A short day follows the long day, with its body completely inside the body range of the
>    long day. Just like the Engulfing day, the tops or bottoms of the bodies can be equal,
>    but both tops and both bottoms cannot be equal.
> 4. The short day should be the opposite color of the long day.

번역하면 이렇다.

1. 긴 날 앞에 **어느 정도의 추세**가 있다.
2. 긴 첫날의 색은 그리 중요하지 않으나 시장의 추세를 반영하면 가장 좋다.
3. 긴 날 뒤에 짧은 날이 오고, 그 실체가 긴 날의 실체 범위 **안에 완전히** 들어간다.
   장악형과 마찬가지로 실체의 위쪽 끝이나 아래쪽 끝은 같을 수 있으나 **양쪽이 모두** 같을
   수는 없다.
4. 짧은 날은 긴 날과 반대색이어야 한다.

**규칙 3이 등호 처리를 명시한다.** 남는 정성 표현은 "긴 날"(**긴실체 척도**), "짧은 날"
(**짧은실체 척도**), **직전 추세**다. 규칙 2가 "not as important... but it is best if"라고
적어 색 요건이 필수가 아니라 권고임을 밝힌 점도 구현에 영향을 준다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 20. `CDLHARAMICROSS` — Harami Cross

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L1641과 L1663, 규칙 L1680)과 Nison 2판
6장이다. Morris 머리말은 강세형이 **Confirmation = No**, 약세형이 **Required**다.

> 1. A long day occurs within a trending market.
> 2. The second day is a Doji (open and close are equal).
> 3. The second-day Doji is within the range of the previous long day.

번역하면 이렇다.

1. **추세가 있는 시장 안에서** 긴 날이 나온다.
2. 두 번째 날이 도지다. 곧 시가와 종가가 같다.
3. 두 번째 날의 도지가 앞선 긴 날의 **범위 안에** 있다.

**규칙 3의 "범위"가 실체 범위인지 고저 범위인지 Morris가 밝히지 않았다.** Harami의 규칙
3은 "body range"라고 못박은 데 비해 여기서는 그냥 "range"다. Nison 용어사전은 하라미
크로스를 "A harami with a doji on the second session instead of a small real body"라고 적어
하라미의 포함 관계를 그대로 물려받는다고 읽게 한다. **두 읽기가 갈리므로 채택 결정이
필요하다.** 남는 정성 표현은 긴실체 척도, 도지 척도, 직전 추세다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 21. `CDLDOJISTAR` — Doji Star

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L2064와 L2075, 규칙 L2101)과 Nison 2판
5장·용어사전이다. Morris 머리말은 강세형이 **Confirmation = No**, 약세형이 **Suggested**다.

> 1. The first day is a long day.
> 2. The second day gaps in the direction of the previous trend.
> 3. The second day is a Doji.
> 4. The shadows on the Doji day should not be excessively long, especially in the bullish
>    case.

번역하면 이렇다.

1. 첫날이 긴 날이다.
2. 두 번째 날이 **앞선 추세 방향으로** 갭을 만든다.
3. 두 번째 날이 도지다.
4. 도지 날의 꼬리가 지나치게 길어서는 안 되며, 특히 강세형에서 그렇다.

**규칙 2의 갭이 실체 사이의 갭인지 고저 범위 사이의 갭인지 밝히지 않았다.** Nison
용어사전은 "A doji that gaps from a long white or black candle's real body"라고 적어
**실체 기준**임을 밝히므로, 이 자리는 Nison이 더 구체적이다. 규칙 4의 "지나치게 길다"는
수치가 없고 "especially in the bullish case"라는 비대칭까지 있어 그대로는 구현할 수 없다.
남는 정성 표현은 긴실체 척도, 도지 척도, **그림자 척도**, 직전 추세다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 22. `CDLPIERCING` — Piercing Line

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L1892, 규칙 L1912)과 Nison 2판 4장이다.
Morris 머리말은 **Trend Required = Yes, Confirmation = Suggested**다.

> 1. The first day is a long black body continuing the downtrend.
> 2. The second day is a white body which opens below the low of the previous day (that's
>    low, not close).
> 3. the second day closes within but above the midpoint of the previous day's body.

번역하면 이렇다.

1. 첫날은 하락 추세를 잇는 긴 음봉이다.
2. 두 번째 날은 양봉이며 **앞날의 저가 아래에서** 열린다. Morris는 종가가 아니라 저가임을
   괄호로 못박는다.
3. 두 번째 날은 앞날 실체의 **중간점 위이면서 실체 안에서** 마감한다.

**규칙 3이 침투 깊이를 중간점으로 못박았으므로 이 자리는 원전이 숫자를 준 것이다.**
Nison도 4장에서 "closes more than halfway into the prior black candlestick's real body"라고
적어 같다. 남는 정성 표현은 "긴 음봉"(**긴실체 척도**)과 **직전 추세**뿐이다. 부등식은
"above the midpoint"이므로 엄격 부등식으로 읽힌다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **하락**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 23. `CDLDARKCLOUDCOVER` — Dark Cloud Cover

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L1982, 규칙 L2005)과 Nison 2판 4장이다.
Morris 머리말은 **Trend Required = Yes, Confirmation = Required**다.

> 1. The first day is a long white body, which is continuing the uptrend.
> 2. The second day is a black body day with the open above the previous day's high (that's
>    the high, not the close).
> 3. The second (black) day closes within and below the midpoint of the previous white body.

번역하면 이렇다.

1. 첫날은 상승 추세를 잇는 긴 양봉이다.
2. 두 번째 날은 음봉이며 **앞날의 고가 위에서** 열린다. 종가가 아니라 고가임을 괄호로
   못박는다.
3. 두 번째 음봉은 앞 양봉 실체의 **중간점 아래이면서 실체 안에서** 마감한다.

Nison 4장은 시가 조건을 "opens above the prior session's high (or close)"라고 적어 **고가
또는 종가**로 느슨하게 두고, 침투에 대해서는 "Some Japanese technicians require more than a
50-percent penetration"이라고 소개한다. **Morris가 고가로 못박은 데 비해 Nison은 종가도
허용하므로 두 원전이 어긋난다.** **결정 C에 따라 조건이 더 좁은 Morris의 고가 기준을
채택한다.** Nison의 종가 허용은 주석으로만 남긴다. 침투 깊이는 두 원전이 모두 중간점
50퍼센트를 말하므로 그대로 쓴다.

**최종 정의는 이렇다.**

1. 직전 추세가 **상승**이다.
2. 첫날은 **긴 양봉**이다.
3. 둘째 날은 음봉이며 **첫날의 고가 위에서** 열린다.
4. 둘째 날의 종가가 첫 실체의 **중간점 아래이면서 첫 실체 안에서** 마감한다.

갭은 쓰지 않는다. 규칙 3은 시가의 위치 비교다. 필요한 척도는 **긴실체**와 **직전 추세**다.
우리가 정해야 하는 것은 긴실체 임계 하나다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **상승**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 24. `CDLCOUNTERATTACK` — Counterattack (Meeting Lines)

원전은 Morris 3판 3장의 Meeting Lines(머리말 `morris_cce.txt` L2182와 L2193, 규칙 L2223)와
Nison 2판 6장이다. Morris 머리말은 강세형이 **Confirmation = Suggested**, 약세형이
**Required**다.

> 1. The lines have bodies that extend the current trend.
> 2. The first body's color always reflects the trend: black for downtrend and white for
>    uptrend.
> 3. The second body is the opposite color.
> 4. The close of each day is the same.
> 5. Both days should be long days.

번역하면 이렇다.

1. 두 선의 실체가 현재 추세를 이어 간다.
2. 첫 실체의 색은 언제나 추세를 반영한다. 하락 추세면 음봉, 상승 추세면 양봉이다.
3. 두 번째 실체는 반대색이다.
4. **두 날의 종가가 같다.**
5. 두 날 모두 긴 날이어야 한다.

**규칙 4가 이 패턴의 핵심이고 "같음" 척도를 요구한다.** Morris 6장은 "Equal values occur
when prices are required to be equal... Meeting Lines require that the close price of each
day be equal"이라고 적고, 도지와 같은 개념으로 허용오차를 둘 수 있다고 덧붙인다.

**Nison이 둘째 날의 시가 조건을 더한다.** `nison_jcct.txt` L3244~L3248은 이렇게 적는다.

> An important consideration of counterattack lines is if that second session should open
> robustly higher (in the case of the bearish counterattack) or sharply lower (for the
> bullish counterattack). The idea is that on the opening of the second day of this pattern,
> the market has moved strongly in the direction of the original trend.

번역하면, 반격선에서 중요하게 볼 것은 **둘째 세션의 시가가 약세형이면 크게 높이, 강세형이면
크게 낮게 열리는가**이다. 그 뜻은 둘째 날 시가에서 시장이 **원래 추세 방향으로 강하게
움직였다가** 종가에서 전일 종가로 돌아온다는 것이다. Nison은 약세형에 대해 L3235~L3236에서
"should ideally open above the prior day's high"라고 덧붙인다.

**결정 C에 따라 채택한다.** Nison에만 있는 조건이고 조건이 더 많은 쪽이 규범이다.

**최종 정의는 이렇다(강세형 기준).**

1. 직전 추세가 **하락**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
2. 첫날은 **긴 음봉**이다.
3. 둘째 날은 **긴 양봉**이며 그 **시가가 첫날의 종가보다 크게 낮다.**
4. 둘째 날의 **종가가 첫날의 종가와 같다.**

약세형은 좌우를 뒤집으며, 둘째 날 시가는 **되도록 첫날의 고가 위**에서 열린다. 갭은
쓰지 않는다. 규칙 3은 시가의 위치 비교다. 필요한 척도는 **긴실체**, **같음**, **가까움**
(시가가 "크게" 벌어졌는지), **직전 추세**다. 우리가 정해야 하는 것은 긴실체 임계,
"같다"의 허용오차, 그리고 둘째 시가가 얼마나 벌어져야 "크게"인지 셋이다.

### 25. `CDLSEPARATINGLINES` — Separating Lines

원전은 Morris 3판 4장(머리말 `morris_cce.txt` L5745와 L5756, 규칙 L5775)과 Nison 2판
7장·용어사전이다. Morris 머리말은 강세형이 **Trend Required = Yes, Confirmation = No**,
약세형이 **Yes, Required**다. 유형은 **C**, 곧 지속형이다.

> 1. The first day is the opposite color of the current trend.
> 2. The second day is the opposite color of the first.
> 3. The two bodies meet in the middle, at the open price.

번역하면 이렇다.

1. 첫날은 현재 추세와 반대색이다.
2. 두 번째 날은 첫날과 반대색이다.
3. 두 실체가 **시가에서 만난다.** 곧 두 날의 시가가 같다.

Nison 용어사전은 "the market opens at the same opening as the previous session's opposite
color candlestick and then closes higher (lower). The prior trend should resume after this
line"이라고 적어 같은 내용에 더해 **추세가 이어져야 한다**는 점을 덧붙인다. 남는 정성
표현은 **같음 척도**와 직전 추세다. Morris의 규칙에는 길이 요건이 없다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 26. `CDLKICKING` — Kicking

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L2586과 L2597, 규칙 L2618, 해설 L2608~2621)
이다. **Nison 2판에는 `kicking`이 한 번도 나오지 않는다.** Morris 머리말은 강세형과
약세형 모두 **Trend Required = No, Confirmation = Required**다. **89개 항목 가운데 추세를
요구하지 않는 것은 이 둘뿐이다.**

> 1. A Marubozu of one color is followed by a Marubozu of the opposite color.
> 2. A gap must occur between the two lines.

번역하면 이렇다.

1. 한 색의 Marubozu 뒤에 반대색 Marubozu가 온다.
2. 두 선 사이에 **갭이 반드시 있어야 한다.**

해설은 이렇게 적는다. "The Kicking pattern is similar to the Separating Lines pattern,
except that instead of the open prices being equal, a gap occurs. The bullish Kicking pattern
is a Black Marubozu followed by a White Marubozu. The bearish Kicking pattern is a White
Marubozu followed by a Black Marubozu... The market direction is not as important with this
pattern as it is with most other candle patterns." 곧 시가가 같은 대신 갭이 생기는 점만
Separating Lines와 다르고, 시장 방향이 다른 패턴만큼 중요하지 않다.

남는 정성 표현은 Marubozu 판정에 필요한 **그림자 척도**와 **긴실체 척도**다. **직전 추세는
필요 없다.** 갭의 정의(실체 사이인지 고저 범위 사이인지)는 밝히지 않았다.

### 27. `CDLKICKINGBYLENGTH` — Kicking (더 긴 Marubozu로 방향 결정)

**앞 판에서 이 항목을 잘못 판정했고 여기서 바로잡는다.** 앞 판은 "더 긴 쪽 방향" 규칙이
TA-Lib 설명에만 있다고 단정했다. 그 단정은 틀렸다. `morris_cce.txt` L2608~2621의 Kicking
해설 안에 다음 문장이 있다.

> Some Japanese theory says that future movement will be in the direction of the longer side
> of the two candles, regardless of the price trend.

번역하면, 일부 일본 이론은 **가격 추세와 무관하게** 두 캔들 가운데 **더 긴 쪽의 방향으로**
앞으로의 움직임이 나온다고 말한다.

**여기서 서로 다른 두 진술을 갈라 적어야 한다.**

- **함수 이름이 원전에 없다는 것은 사실이다.** Morris도 Nison도 `Kicking by Length`라는
  이름의 별개 패턴을 세우지 않았다. TA-Lib이 Kicking의 방향 결정 방식을 달리한 변형을
  별도 함수로 만든 것이다.
- **방향 규칙이 원전에 없다는 것은 사실이 아니다.** 위 문장이 원전에 있다. 다만 Morris는
  이것을 자기 규칙으로 채택한 것이 아니라 "Some Japanese theory says"라고 **전언으로**
  소개한다.

판정 규칙은 26번과 같고 방향 결정만 다르다.

1. 26번의 규칙 1과 2를 만족한다.
2. 두 Marubozu 가운데 **실체가 더 긴 쪽의 색**을 방향으로 삼는다. 가격 추세는 보지 않는다.

남는 정성 표현은 26번과 같고, 여기에 **두 실체 길이가 정확히 같을 때** 어떻게 할지가
더해진다. 원전은 그 경우를 다루지 않는다. 확인 강도는 **직접**으로 올린다.

### 28. `CDLHOMINGPIGEON` — Homing Pigeon

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L2301, 규칙 L2315)이다. Nison 2판에는
`homing pigeon`이 나오지 않는다. Morris 머리말은 **Trend Required = Yes,
Confirmation = No**다.

> 1. A long black body occurs in a downtrend.
> 2. A short black body is completely inside the previous day's body.

번역하면 이렇다.

1. **하락 추세에서** 긴 음봉이 나온다.
2. 짧은 음봉이 앞날의 실체 **안에 완전히** 들어간다.

**하라미와 다른 점은 두 날의 색이 같다는 것뿐이다.** 남는 정성 표현은 긴실체 척도,
짧은실체 척도, 직전 추세다. 포함 관계의 등호 처리는 밝히지 않았다. 하라미가 등호를
명시한 것과 대비되므로 **하라미 규약을 여기에도 적용할지 정해야 한다.**

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **하락**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 29. `CDLMATCHINGLOW` — Matching Low

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L2413, 규칙 L2449)이다. Morris 머리말은
**Trend Required = Yes, Confirmation = No**다.

> 1. A long black day occurs.
> 2. The second day is also a black day with its close equal to the close of the first day.

번역하면 이렇다.

1. 긴 음봉이 나온다.
2. 두 번째 날도 음봉이며 **종가가 첫날의 종가와 같다.**

Morris는 짝이 되는 Matching High 항목(L2506, 규칙 L2522)에서 **같음의 허용오차를 숫자로
준다.** "One should consider the two days to have the same closing price as long as the
second day's closing price is within one one-thousandth (1/1000) of the first day's closing
price. So, for example, if the first day closes at 20, the second day is permitted to close
between 19.98 and 20.02." 곧 첫날 종가의 1/1000 안이면 같다고 본다.

**이 1/1000은 Matching High 항목에 적혀 있고 Matching Low 항목에는 없다.** 두 패턴이
대칭이므로 같이 적용할 수 있으나, 그것은 우리가 확장하는 것이므로 결정 항목이다. 남는
정성 표현은 긴실체 척도, 같음 척도, 직전 추세다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **하락**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 30. `CDLINNECK` — In-Neck Line

원전은 Morris 3판 4장(머리말 `morris_cce.txt` L5999와 L6020, 규칙 L6036)과 Nison 2판
4장이다. Morris 머리말은 약세형과 강세형 **모두 Confirmation = Required**이고 유형은
지속형이다.

> Bearish In Neck Line
> 1. A black line develops in a downtrend.
> 2. The second day is a white day with an opening below the first day's low.
> 3. The close of the second day is just barely into the body of the first day. For all
>    practical purposes, the closes are equal.
>
> Bullish In Neck Line
> 1. The first day is a long white day that occurs during an uptrend.
> 2. The second day is black. It opens above the high of the previous day and then closes
>    just barely into the body of the first day.

번역하면 약세형은 이렇다. 첫째, 하락 추세에서 음봉이 나온다. 둘째, 두 번째 날은 양봉이며
**첫날의 저가 아래에서** 열린다. 셋째, 두 번째 날의 종가가 첫날 실체 안으로 **아주 조금만**
들어간다. 실질적으로 두 종가는 같다.

강세형은 이렇다. 첫째, 상승 추세에서 긴 양봉이 나온다. 둘째, 두 번째 날은 음봉이며 앞날의
고가 위에서 열려 첫날 실체 안으로 아주 조금만 들어가 마감한다.

**"아주 조금만"과 "실질적으로 같다"가 이 패턴의 핵심이고 수치가 없다.** Morris는 약세형에
길이 요건을 두지 않고 강세형에만 "long white day"를 둔다는 점도 비대칭이다.

**Nison이 둘째 봉의 크기 조건을 더한다.** `nison_jcct.txt` L1897~L1901에 있다.

> The on-neck pattern's white candle (usually a small one) closes near the low of the
> previous session. The in-neck pattern's white candle closes slightly into the prior real
> body (it should also be a small white candle).

번역하면, On-Neck의 양봉은 (대개 작은 것으로) 앞 세션의 저가 가까이에서 마감하고,
In-Neck의 양봉은 앞 실체 안으로 조금 들어가 마감하며 **그것 역시 작은 양봉이어야 한다.**

**결정 C에 따라 채택한다.** Morris에 없는 조건이고 좁히는 쪽이다. In-Neck의 경우 Nison이
"should also be"라고 적어 권고가 아니라 요건에 가깝게 쓴 점도 채택 근거다.

최종 정의는 약세형 기준으로 이렇다.

1. 직전 추세가 **하락**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
2. 첫날은 음봉이다.
3. 둘째 날은 **작은 양봉**이며 첫날의 **저가 아래에서** 열린다.
4. 둘째 날의 종가가 첫 실체 안으로 **아주 조금만** 들어간다.

갭은 쓰지 않는다. 규칙 3의 "저가 아래에서 열린다"는 시가의 위치 비교다. 필요한 척도는
**같음**(아주 조금만 들어감), **짧은실체**(둘째 봉), 강세형의 **긴실체**, **직전 추세**다.
우리가 정해야 하는 것은 "아주 조금만"의 침투 상한 하나다.

### 31. `CDLONNECK` — On-Neck Line

원전은 Morris 3판 4장(머리말 `morris_cce.txt` L5852와 L5873, 규칙 L5887)과 Nison 2판
4장이다. Morris 머리말은 약세형이 **Confirmation = Required**, 강세형이 **No**다.

> Bearish On Neck Line
> 1. A long black line is formed in a downtrend.
> 2. The second day is white and opens below the low of the previous day. This day does not
>    need to be a long day or it might resemble the bullish Meeting Line.
> 3. The second day closes at the low of the first day.
>
> Bullish On Neck Line
> 1. The first day is a long white day that occurs during an uptrend.
> 2. The second day is black. It opens above the high of the previous day and then closes at
>    the high of the previous day.

번역하면 약세형은 이렇다. 첫째, 하락 추세에서 긴 음봉이 만들어진다. 둘째, 두 번째 날은
양봉이며 앞날의 저가 아래에서 열린다. **이 날은 긴 날일 필요가 없으며, 길면 강세형 Meeting
Line처럼 보일 수 있다.** 셋째, 두 번째 날은 **첫날의 저가에서** 마감한다.

강세형은 좌우가 뒤집혀, 두 번째 음봉이 앞날의 고가 위에서 열려 **앞날의 고가에서** 마감한다.

**In-Neck와 다른 점은 종가가 닿는 지점이다.** In-Neck는 앞 실체 안으로 조금 들어가고
On-Neck는 앞날의 저가(또는 고가)에 닿는다. 규칙 3은 등호를 요구하므로 **같음 척도**가
필요하다. 규칙 2가 "does not need to be a long day"라고 명시적으로 길이 요건을 **배제**한
점은 구현에서 놓치기 쉽다.

Nison은 `nison_jcct.txt` L1897~L1898에서 On-Neck의 양봉을 "(usually a small one)"이라고
적는다. **"usually"는 요건이 아니라 경향이므로 결정 C의 대상이 아니다.** 30번 In-Neck에서
Nison이 "it should also be"라고 적은 것과 강도가 다르며, 그 차이를 그대로 둔다. 곧
On-Neck의 둘째 봉에는 크기 요건을 넣지 않는다.

갭은 쓰지 않는다. 규칙 2의 "앞날 저가 아래에서 열린다"는 시가의 위치 비교다. 필요한 척도는
**긴실체**(첫날), **같음**(종가가 앞날 저가에 닿음), **직전 추세**다. 우리가 정해야 하는
것은 "같다"의 허용오차 하나이며 공통 같음 척도에서 온다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 32. `CDLTHRUSTING` — Thrusting Line

원전은 Morris 3판 4장(머리말 `morris_cce.txt` L6148과 L6169, 규칙 L6185)과 Nison 2판
4장이다. Morris 머리말은 약세형이 **Confirmation = Suggested**, 강세형이 **No**다.

> Bearish Thrusting
> 1. A black day is formed in a downtrend.
> 2. The second day is white and opens considerably lower than the low of the first day.
> 3. The second day closes well into the body of the first day, but not above the midpoint.
>
> Bullish Thrusting
> 1. The first day is a long white day that occurs during an uptrend.
> 2. The second day is black. It opens way above the high of the first day and then trades
>    down to close within the body of the first day, but does not close below the midpoint of
>    the first day's body.

번역하면 약세형은 이렇다. 첫째, 하락 추세에서 음봉이 만들어진다. 둘째, 두 번째 날은
양봉이며 첫날의 저가보다 **상당히 낮게** 열린다. 셋째, 두 번째 날은 첫날 실체 안으로 깊이
들어가 마감하되 **중간점을 넘지는 않는다.**

강세형은 좌우가 뒤집힌다.

**Piercing과 Thrusting은 중간점을 기준으로 갈린다.** 중간점을 넘으면 Piercing, 넘지 못하면
Thrusting이다. 그러므로 중간점 자체는 원전이 준 정확한 값이고 척도가 필요 없다.

Nison은 `nison_jcct.txt` L1901~L1904에서 둘째 봉의 크기를 규정한다.

> The thrusting pattern should be a longer white candle that is stronger than the in-neck
> pattern, but still does not close above the middle of the prior black real body.

번역하면, Thrusting의 양봉은 In-Neck보다 **더 긴** 양봉이어야 하고 더 강하되, 여전히 앞
음봉 실체의 중간 위로는 마감하지 않는다.

**결정 C에 따라 채택한다.** Morris에 없는 조건이고 좁히는 쪽이다. 다만 Nison이 말하는
"더 길다"는 In-Neck의 둘째 봉과 견준 상대적 표현이지 절대 기준이 아니다. 그러므로 이
조건은 **둘째 봉이 In-Neck의 작은 양봉보다 크다**는 뜻으로 옮기며, 그 경계값은 우리가
정해야 한다.

갭은 쓰지 않는다. 필요한 척도는 **긴실체**(강세형 첫날), **짧은실체**(둘째 봉이 In-Neck의
작은 양봉을 넘어서는지), "상당히 낮게"를 재는 **가까움**, **직전 추세**다. 우리가 정해야
하는 것은 둘이다. 첫째는 "considerably lower"의 최소 폭이고, 둘째는 In-Neck과 Thrusting을
가르는 둘째 봉 크기의 경계다. 중간점에 정확히 닿는 경우의 처리는 공통 부등식 규약(결정 2)에
속한다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 33. `CDLSTICKSANDWICH` — Stick Sandwich

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L4704와 L4727, 규칙 L4739)이다. Nison 2판에는
`stick sandwich`가 나오지 않는다. Morris 머리말은 강세형이 **Confirmation = No**, 약세형이
**Suggested**다.

> Bullish Stick Sandwich
> 1. A black body in a downtrend is followed by a white body that trades above the close of
>    the previous black body.
> 2. The third day is a black day with a close equal to the first day.
>
> Bearish Stick Sandwich
> 1. The pattern starts with a white day that occurs during an uptrend.
> 2. The second day has a black real body that opens below the previous day's close and
>    closes below the previous day's open.
> 3. The third day is a white real body that engulfs the second day's black real body.

번역하면 강세형은 이렇다. 첫째, 하락 추세의 음봉 다음에 앞 음봉의 종가 위에서 거래되는
양봉이 온다. 둘째, 셋째 날은 음봉이며 **종가가 첫날과 같다.**

약세형은 대칭이 아니다. 첫째, 상승 추세의 양봉으로 시작한다. 둘째, 두 번째 날은 앞날
종가 아래에서 열려 앞날 시가 아래에서 마감하는 음봉이다. 셋째, 셋째 날은 두 번째 날의
음봉 실체를 **감싸는** 양봉이다.

**약세형에는 "종가가 같다"는 조건이 없다.** 강세형과 약세형의 구조가 원전에서 서로 다르며,
이는 내가 만든 비대칭이 아니라 Morris 본문 그대로다. 이 패턴은 세 봉짜리이지만 두 캔들
묶음에 함께 두었다. 남는 정성 표현은 **같음 척도**(강세형)와 직전 추세다.

## 4.4 세 캔들 (18종)

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 34. `CDLMORNINGSTAR` — Morning Star

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L2849, 규칙 L2895)과 Nison 2판 5장이다.
Morris는 Morning Star와 Evening Star의 규칙을 한 묶음으로 적었고, 머리말은 Morning Star가
**Trend Required = Yes, Confirmation = Required**다.

> 1. The first day is always the color that was established by the ensuing trend. That is,
>    an uptrend will yield a long white day for the first day of the Evening Star and a
>    downtrend will yield a black first day of the Morning Star.
> 2. The second day, the star, is always gapped from the body of the first day. Its color is
>    not important.
> 3. The third day is always the opposite color of the first day.
> 4. The first day, and most likely the third day, are considered long days.

번역하면 이렇다.

1. 첫날의 색은 언제나 진행 중이던 추세가 정한다. 상승 추세면 Evening Star의 첫날이 긴
   양봉이고, 하락 추세면 Morning Star의 첫날이 음봉이다.
2. 두 번째 날인 별은 언제나 **첫날의 실체로부터 갭을 이룬다.** 색은 중요하지 않다.
3. 셋째 날은 언제나 첫날과 반대색이다.
4. 첫날은 긴 날로 보며, 셋째 날도 그럴 가능성이 높다.

**규칙 2가 갭의 기준을 "body of the first day"로 못박은 것이 중요하다.** 실체 기준이며
꼬리 기준이 아니다. Nison 5장·용어사전은 셋째 날에 대해 "closes well into the first
session's black real body"라고 적어 **첫 실체 안으로 깊이** 마감할 것을 요구하는데,
**Morris의 네 규칙에는 그 침투 요건이 아예 없다.** 곧 침투 깊이는 Nison 쪽 요건이고
수치가 없다. TA-Lib이 쓰는 `penetration` 기본값 0.3의 근거는 두 원전 어디에서도 찾지
못했다.

**결정 C에 따라 Nison의 침투 요건을 채택한다.** Nison에만 있는 조건이고 조건이 더 많은
쪽이 규범이므로, 셋째 날이 첫 실체 안으로 깊이 마감하는 것은 **선택이 아니라 필수**다.
깊이의 값은 결정 8이 정한다. 규칙 4의 "most likely"는 셋째 날의 길이가 경향임을 뜻하므로
그대로 옮겨 선택 요건으로 둔다.

**최종 정의는 이렇다.**

1. 직전 추세가 **하락**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
2. 첫날은 **긴 음봉**이다.
3. 둘째 날은 작은 실체이며 첫날의 **실체 아래로 갭**을 이룬다. 색은 중요하지 않다.
4. 셋째 날은 **양봉**이며 첫 실체 안으로 **깊이 마감한다.** 깊이는 결정 8이 정한 값을 쓴다.

갭은 **실체 사이의 갭**이다. 필요한 척도는 **긴실체**와 **직전 추세**다. 우리가 정해야
하는 것은 긴실체 임계와 **침투 깊이** 둘이다. TA-Lib이 쓰는 `penetration` 기본값 0.3은
두 원전 어디에서도 근거를 찾지 못했으므로 쓰지 않는다.

### 35. `CDLEVENINGSTAR` — Evening Star

원전과 규칙은 34번과 같은 묶음이다(머리말 `morris_cce.txt` L2860, 규칙 L2895). Morris
머리말은 **Trend Required = Yes, Confirmation = Required**다. **최종 정의는 34번의 좌우를
뒤집은 것이며, Nison의 침투 요건도 똑같이 필수로 채택한다.**

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
2. 첫날은 **긴 양봉**이다.
3. 둘째 날은 작은 실체이며 첫날의 **실체 위로 갭**을 이룬다. 색은 중요하지 않다.
4. 셋째 날은 **음봉**이며 첫 실체 안으로 **깊이 마감한다.** 깊이는 결정 8이 정한 값을 쓴다.

갭은 **실체 사이의 갭**이다. 필요한 척도와 정해야 하는 것은 34번과 같다.

### 36. `CDLMORNINGDOJISTAR` — Morning Doji Star

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L2986, 규칙 L3033)과 Nison 2판 5장이다.
Morris 머리말은 **Trend Required = Yes, Confirmation = Suggested**다. 규칙은 Evening Doji
Star와 한 묶음이다.

> 1. Like many reversal patterns, the first day's color should represent the trend of the
>    market.
> 2. The second day must be a Doji Star (a Doji that gaps).
> 3. The third day is the opposite color of the first day.

번역하면 이렇다.

1. 많은 반전형이 그렇듯 첫날의 색이 시장의 추세를 나타내야 한다.
2. 두 번째 날은 반드시 **Doji Star**여야 한다. 곧 갭을 이루는 도지다.
3. 셋째 날은 첫날과 반대색이다.

**이 규칙은 21번 Doji Star의 정의를 그대로 물려받는다.** 그러므로 긴 첫날, 실체 기준 갭,
도지 허용오차가 함께 따라온다. **침투 깊이는 34번과 마찬가지로 Morris 규칙에 없고 Nison에만
있으며, 결정 C에 따라 필수로 채택한다.**

**최종 정의는 이렇다.**

1. 직전 추세가 **하락**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
2. 첫날은 **긴 음봉**이다.
3. 둘째 날은 **도지**이며 첫날의 **실체 아래로 갭**을 이룬다. 도지의 꼬리는 지나치게 길지
   않아야 한다.
4. 셋째 날은 **양봉**이며 첫 실체 안으로 **깊이 마감한다.** 깊이는 결정 8이 정한 값을 쓴다.

갭은 **실체 사이의 갭**이다. 필요한 척도는 **긴실체**, **도지**, **그림자**, **직전
추세**다. 우리가 정해야 하는 것은 긴실체 임계, 도지 허용오차, 꼬리 상한, 침투 깊이 넷이다.

### 37. `CDLEVENINGDOJISTAR` — Evening Doji Star

원전과 규칙은 36번과 같은 묶음이다(머리말 `morris_cce.txt` L2997, 규칙 L3033). Morris
머리말은 **Trend Required = Yes, Confirmation = Required**다. **최종 정의는 36번의 좌우를
뒤집은 것이며, Nison의 침투 요건도 똑같이 필수로 채택한다.**

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
2. 첫날은 **긴 양봉**이다.
3. 둘째 날은 **도지**이며 첫날의 **실체 위로 갭**을 이룬다.
4. 셋째 날은 **음봉**이며 첫 실체 안으로 **깊이 마감한다.** 깊이는 결정 8이 정한 값을 쓴다.

갭은 **실체 사이의 갭**이다. 필요한 척도와 정해야 하는 것은 36번과 같다.

### 38. `CDLABANDONEDBABY` — Abandoned Baby

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L3104와 L3117, 규칙 L3140)과 Nison 2판
용어사전이다. Morris 머리말은 강세형이 **Confirmation = Suggested**, 약세형이 **Required**다.

> 1. The first day should reflect the prior trend.
> 2. The second day is a Doji whose shadow gaps above or below the previous day's upper or
>    lower shadow.
> 3. The third day is the opposite color of the first day.
> 4. The third day gaps in the opposite direction with no shadows overlapping.

번역하면 이렇다.

1. 첫날이 앞선 추세를 반영해야 한다.
2. 두 번째 날은 도지이며, 그 **꼬리가** 앞날의 위꼬리 또는 아래꼬리 **위나 아래로 갭을
   이룬다.**
3. 셋째 날은 첫날과 반대색이다.
4. 셋째 날이 반대 방향으로 갭을 이루며 **꼬리가 전혀 겹치지 않는다.**

**이 패턴의 갭은 실체가 아니라 꼬리 기준이다.** 규칙 2와 4가 그 점을 못박으며, 이는 별
계열의 다른 패턴이 실체 기준 갭을 쓰는 것과 다르다. Nison 용어사전도 "gaps away
(including shadows)"라고 적어 같다. **두 원전이 일치하는 드문 자리다.**

남는 정성 표현은 도지 척도와 직전 추세다. **갭 자체는 꼬리끼리의 대소 비교이므로 척도가
필요 없다.** TA-Lib이 이 함수에 `penetration` 0.3을 두는 근거는 원전에 없다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 39. `CDLTRISTAR` — Tri Star

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L3214와 L3238, 규칙 L3230)과 Nison 2판
8장·용어사전이다. Morris 머리말은 강세형이 **Confirmation = Suggested**, 약세형이
**Required**다.

> 1. All three days are Doji.
> 2. The second day gaps above or below the first and third day.

번역하면 이렇다.

1. 세 날이 **모두 도지**다.
2. 두 번째 날이 첫날과 셋째 날 **위나 아래로 갭을 이룬다.**

Nison 용어사전은 "Three doji that have the same formation as a morning or evening star
pattern. An extraordinarily rare pattern"이라고 적는다. 남는 정성 표현은 도지 척도와 갭의
기준(실체인지 꼬리인지 밝히지 않았다), 그리고 직전 추세다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 40. `CDL2CROWS` — Two Crows

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L4166, 규칙 L4187)과 Nison 2판 6장이다.
Morris 머리말은 **Trend Required = Yes, Confirmation = Required**다.

> 1. The trend continues with a long white day.
> 2. The second day is a gap up and a black day.
> 3. The third day is also a black day.
> 4. The third day opens inside the body of the second day and closes inside the body if the
>    first day.

번역하면 이렇다.

1. 추세가 긴 양봉으로 이어진다.
2. 두 번째 날은 **갭 상승한 음봉**이다.
3. 셋째 날도 음봉이다.
4. 셋째 날은 두 번째 날의 실체 **안에서 열려** 첫날의 실체 **안에서 마감한다.**

원문 규칙 4의 "if"는 "of"의 오식으로 보이며 뜻은 "첫날의 실체 안"이다.

**규칙 절 앞의 해설이 갭의 종류와 둘째 날의 종가 위치를 밝힌다.** `morris_cce.txt`
L4179~L4185에 있다.

> The next day gaps much higher, but closes near its low, which is still above the body of
> the first day. The next (third) day opens inside the body of the second black day, then
> sells off into the body of the first day. This has closed the gap...

번역하면, 둘째 날은 크게 갭 상승하지만 저가 가까이에서 마감하며 **그 종가가 여전히 첫날의
실체 위**에 있다. 셋째 날은 둘째 음봉의 실체 안에서 열려 첫날의 실체 안까지 밀려 내려가고,
**이로써 갭이 메워진다.**

**결정 C에 따라 이 해설을 채택한다.** 조건이 둘 더 붙는다. 첫째, 둘째 날의 **종가가 첫
실체 위에 남아야** 한다. 둘째, 셋째 날이 첫 실체 안에서 마감함으로써 **갭이 메워진다는
것이 이 패턴의 완성 조건**임이 분명해진다.

최종 정의는 이렇다.

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
2. 첫날은 **긴 양봉**이다.
3. 둘째 날은 음봉이며 첫 실체 위로 **실체 갭**을 이루고, 그 **종가가 첫 실체 위에 남는다.**
4. 셋째 날은 음봉이며 둘째 실체 **안에서 열려** 첫 실체 **안에서 마감한다.**

갭은 **실체 사이의 갭**이다. 해설이 "above the body of the first day"라고 실체를 기준으로
말한다. 필요한 척도는 **긴실체**와 **직전 추세**다. 우리가 정해야 하는 것은 포함 관계의
등호 처리 하나이며, 이는 공통 부등식 규약(결정 2)에서 온다.

### 41. `CDLUPSIDEGAP2CROWS` — Upside Gap Two Crows

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L3314, 규칙 L3336)과 Nison 2판 6장이다.
Morris 머리말은 **Trend Required = Yes, Confirmation = Required**다.

> 1. An uptrend continues with a long white day.
> 2. An upward gapping black day is formed after the white day.
> 3. A second black day opens above the first black day and closes below the body of the
>    first black day. Its body engulfs the first black day.
> 4. The close of the second black day is still above the close of the long white day.

번역하면 이렇다.

1. 상승 추세가 긴 양봉으로 이어진다.
2. 그 양봉 뒤에 **위로 갭을 이루는 음봉**이 만들어진다.
3. 두 번째 음봉이 첫 음봉 **위에서 열려** 첫 음봉의 실체 **아래에서 마감한다.** 곧 그
   실체가 첫 음봉을 감싼다.
4. 두 번째 음봉의 종가가 여전히 **긴 양봉의 종가보다 위에 있다.**

**규칙 4가 이 패턴을 Two Crows와 가른다.** Two Crows는 셋째 날이 첫날 실체 안에서
마감하고, 여기서는 첫 양봉의 종가 위에 머문다.

**Nison이 갭의 종류를 명시한다.** `nison_jcct.txt` L2850~L2852에 있다.

> The upside-gap refers to the gap between the real body of the small black real body and
> the real body preceding it.

번역하면, 여기서 말하는 상승 갭은 **작은 음봉의 실체와 그 앞 실체 사이의 갭**이다. 곧
**실체 사이의 갭**이며 꼬리를 포함한 고저 범위 사이의 갭이 아니다. Nison은 이어
L2856~L2858에서 "An ideal upside-gap two crows has the second black real body opening above
the first black real body's open. It then closes under the first black candle's close."라고
적어, 이상적인 형태에서는 **둘째 음봉의 실체가 첫 음봉의 시가 위에서 열려 첫 음봉의 종가
아래에서 마감**한다고 밝힌다. 이는 Morris 규칙 3의 감쌈을 시가와 종가로 풀어 쓴 것이다.

**결정 D에 따라 갭 정의를 실체 사이의 갭으로 확정해 정의에 넣는다.**

최종 정의는 이렇다.

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
2. 첫날은 **긴 양봉**이다.
3. 둘째 날은 음봉이며 첫 실체 위로 **실체 갭**을 이룬다.
4. 셋째 날은 음봉이며 둘째 음봉의 **시가 위에서 열려** 둘째 음봉의 **종가 아래에서
   마감한다.** 곧 그 실체가 둘째 음봉의 실체를 감싼다.
5. 셋째 날의 **종가가 첫 양봉의 종가보다 위에 남는다.**

필요한 척도는 **긴실체**와 **직전 추세**다. 우리가 정해야 하는 것은 없다. 규칙 3의 감쌈과
규칙 5는 모두 대소 비교로 끝난다.

### 42. `CDL3WHITESOLDIERS` — Three Advancing White Soldiers

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L3659, 규칙 L3676)과 Nison 2판 6장이다.
Morris 머리말은 **Trend Required = Yes, Confirmation = No**다.

> 1. Three consecutive long white lines occur, each with a higher close.
> 2. Each should open within the previous body.
> 3. Each should close at or near the high for the day.

번역하면 이렇다.

1. 연속된 **긴 양봉 셋**이 나오며 각각 종가가 더 높다.
2. 각 봉은 **앞 실체 안에서** 열려야 한다.
3. 각 봉은 그날의 **고가에 또는 고가 가까이에서** 마감해야 한다.

남는 정성 표현은 긴실체 척도, 규칙 3의 "고가 가까이"(**가까움 척도** 또는 **그림자 척도**),
직전 추세다. 규칙 3이 "at or near"이므로 **등호를 허용한다.**

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **하락**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 43. `CDL3BLACKCROWS` — Three Black Crows

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L3728, 규칙 L3749)과 Nison 2판 6장이다.
Morris 머리말은 **Trend Required = Yes, Confirmation = Required**다.

> 1. Three consecutive long black days occur.
> 2. Each day closes at a new low.
> 3. Each day opens within the body of the previous day.
> 4. Each day closes at or neat its lows.

번역하면 이렇다.

1. 연속된 **긴 음봉 셋**이 나온다.
2. 각 날이 **새 저점에서** 마감한다.
3. 각 날이 앞날의 실체 **안에서** 열린다.
4. 각 날이 저가에 또는 저가 가까이에서 마감한다.

원문 규칙 4의 "neat"는 "near"의 오식이다. 42번을 좌우로 뒤집은 것이되 **규칙 2가 더해져
있다.** 삼백병에는 "새 고점" 요건이 없는데 삼흑병에는 "새 저점" 요건이 있다. 이 비대칭은
Morris 본문 그대로다. 남는 정성 표현은 42번과 같다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **상승**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 44. `CDLIDENTICAL3CROWS` — Identical Three Crows

원전은 Morris 3판 3장이며 다른 항목과 머리말 형식이 다르다. `morris_cce.txt` L3800에
"IDENTICAL THREE CROWS (doji samba garasu)"라는 제목이 있고 바로 아래에 "Bearish reversal
pattern. **No confirmation is required.**"라고 적혀 있다. 규칙은 L3811 부근이다.

> 1. Three long black days are stair-stepping downward.
> 2. Each day starts at the previous day's close.

번역하면 이렇다.

1. 긴 음봉 셋이 **계단처럼 내려간다.**
2. 각 날이 **앞날의 종가에서 시작한다.**

해설은 "This is a special case of the Three Black Crows pattern... The difference is that the
second and third black days open at or near the previous day's close"라고 적어 삼흑병의
특수한 경우이며 차이는 둘째와 셋째 날이 앞날 종가에 **또는 그 가까이에서** 열리는 것이라고
밝힌다. **규칙 2는 등호를 말하는데 해설은 "at or near"로 근접을 허용하므로 같은 절 안에서
두 서술이 어긋난다.** 결정 C에 따라 **Morris 안에서는 규칙 절이 규범이므로 등호를 채택한다.**
해설의 근접 허용은 주석으로만 남긴다.

**최종 정의는 이렇다.**

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
2. **긴 음봉 셋**이 계단처럼 내려간다. 곧 각 날의 종가가 앞날보다 낮다.
3. 둘째 날과 셋째 날의 **시가가 각각 앞날의 종가와 같다.**

갭은 쓰지 않는다. 필요한 척도는 **긴실체**, **같음**, **직전 추세**다. 우리가 정해야 하는
것은 긴실체 임계와 "같다"의 허용오차 둘이다. 확인은 원전이 불필요라고 명시했다.

### 45. `CDLADVANCEBLOCK` — Advance Block

**앞 판에서 이 항목을 잘못 판정했고 여기서 바로잡는다.** 앞 판은 Morris의 규칙을 확실히
대응시키지 못했다며 "원전 정의가 확정되지 않은 패턴"으로 두었으나, `morris_cce.txt`
L3879에 규칙이 분명히 있다.
머리말은 L3853이고 **Trend Required = Yes, Confirmation = Required**다.

> 1. Three white days occur with consecutively higher closes.
> 2. Each day opens within the previous day's body.
> 3. A definite deterioration in the upward strength is evidenced by long upper shadows on
>    the second and third days.

번역하면 이렇다.

1. 잇달아 더 높게 마감하는 **양봉 셋**이 나온다.
2. 각 날이 **앞날의 실체 안에서** 열린다.
3. 위로 미는 힘이 뚜렷하게 약해졌음이 **둘째와 셋째 날의 긴 위꼬리**로 드러난다.

**규칙 3이 판정 구조를 확정한다.** 앞 판이 인용했던 Nison 용어사전의 "긴 위꼬리이거나
실체가 점점 작아지는 것"이라는 두 갈래 서술과 달리, **Morris는 긴 위꼬리 하나로 정한다.**
그러므로 규약을 새로 만들 필요가 없고, 원전 정의가 확정되지 않았다는 앞 판의 사유가
사라진다.

**유연성 절은 주석으로만 남긴다.** Morris의 유연성 절은 실체가 점점 작아지는 현상도 함께
설명하지만, 결정 C의 첫째 층에 따라 Morris 안에서는 규칙 절이 규범이므로 **긴 위꼬리 하나로
판정한다.**

**최종 정의는 이렇다.**

1. 직전 추세가 **상승**이다.
2. 잇달아 더 높게 마감하는 **양봉 셋**이 나온다.
3. 각 날이 **앞날의 실체 안에서** 열린다.
4. 둘째 날과 셋째 날에 **긴 위꼬리**가 있다.

갭은 쓰지 않는다. 삼백병과 달리 실체 길이 요건이 없다는 점도 규칙 그대로다. 필요한 척도는
**그림자**와 **직전 추세**다. 우리가 정해야 하는 것은 "긴 위꼬리"의 임계 하나다. 확인 강도는
**직접**이다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **상승**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 46. `CDLSTALLEDPATTERN` — Stalled Pattern (Deliberation)

원전은 Morris 3판 3장의 Deliberation(머리말 `morris_cce.txt` L4012와 L4023, 규칙 L4052)과
Nison 2판 6장이다. Morris 머리말은 강세형이 **Confirmation = No**, 약세형이 **Suggested**다.

> Bearish Deliberation
> 1. The first and second day have long white bodies.
> 2. The third day opens near the second day's close.
> 3. The third day is a Spinning Top and most probably a star.
>
> Bullish Deliberation
> 1. The first day of the pattern is a long black day that occurs in a downtrend.
> 2. The second day is also a long black day.
> 3. The third day is a Star or relatively small black day that may gap away from the prior
>    day's black real body.

번역하면 약세형은 이렇다. 첫째, 첫날과 두 번째 날이 긴 양봉 실체를 갖는다. 둘째, 셋째
날은 두 번째 날의 종가 **가까이에서** 열린다. 셋째, 셋째 날은 팽이형이며 아마도 별일
것이다.

강세형은 이렇다. 첫째, 하락 추세에서 긴 음봉으로 시작한다. 둘째, 두 번째 날도 긴 음봉이다.
셋째, 셋째 날은 별이거나 상대적으로 작은 음봉이며 앞날의 음봉 실체에서 갭을 이룰 **수도**
있다.

**두 방향의 서술 강도가 다르다.** 약세형은 팽이형을 요구하고 강세형은 "may gap"이라고
적어 갭을 선택으로 둔다.

**Nison이 약세형 셋째 봉의 색과 위치를 확정한다.** `nison_jcct.txt` L2980~L2988은 이렇게
적는다.

> If the last two candles are long white ones that make a new high followed by a small white
> candle, it is called a stalled pattern... This last small white candle can either gap away
> from the long white body (in which case it becomes a star) or it can be, as the Japanese
> express it, "riding on the shoulder" of the long white real body (that is, be at the upper
> end of the prior long white real body).

번역하면, **새 고점을 만드는 긴 양봉 둘 뒤에 작은 양봉**이 오면 그것이 정체형이다. 이
마지막 작은 양봉은 긴 양봉 실체에서 **갭을 이룰 수도 있고**(그 경우 별이 된다) 일본식
표현으로 긴 양봉 실체의 **"어깨에 올라탄"** 자리, 곧 앞 긴 양봉 실체의 **위쪽 끝**에 있을
수도 있다.

**결정 C에 따라 채택한다.** Morris 약세형 규칙은 셋째 봉을 팽이형이라고만 하고 색을
정하지 않는데, Nison은 **양봉**으로 못박는다. 조건이 더 많은 쪽이 규범이므로 색을 넣는다.
Nison은 또 둘째 날까지가 **새 고점을 만든다**는 조건을 더하므로 그것도 넣는다. 갭은 Nison도
"either ... or"로 선택으로 두므로 필수가 아니다.

**최종 정의는 이렇다(약세형 기준).**

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
2. 첫날과 둘째 날이 **긴 양봉**이며 둘째 날이 **새 고점**을 만든다.
3. 셋째 날은 **작은 양봉**이며 둘째 날의 종가 **가까이에서** 열린다. 앞 긴 양봉 실체의
   위쪽 끝에 있거나 그 실체에서 갭을 이루며, 둘 가운데 어느 쪽이든 된다.

강세형은 Morris 규칙 그대로 두되 좌우를 뒤집는다. Nison은 강세형을 따로 적지 않으므로
색 조건을 강세형에 대칭으로 넣지 않는다. 갭은 **선택적 실체 갭**이다. 필요한 척도는
**긴실체**, **짧은실체**, **가까움**, **직전 추세**다. 우리가 정해야 하는 것은 긴실체
임계, 짧은실체 임계, "가까이"의 허용폭 셋이다.

### 47. `CDL3STARSINSOUTH` — Three Stars in the South

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L4542, 규칙 L4562)이다. Nison 2판에는 이
이름이 나오지 않는다. Morris 머리말은 **Trend Required = Yes, Confirmation = Suggested**다.

> 1. The first day is a long black day with a long lower shadow (Hammer-like).
> 2. The second day has the same basic shape as the first day, only smaller. The low is above
>    the previous day's low.
> 3. The third day is a small Black Marubozu that opens and closes inside the previous day's
>    range.

번역하면 이렇다.

1. 첫날은 **아래꼬리가 긴 긴 음봉**이며 해머와 비슷한 모양이다.
2. 두 번째 날은 첫날과 기본 모양이 같되 **더 작다.** 저가는 앞날의 저가보다 **위**에 있다.
3. 셋째 날은 **작은 Black Marubozu**이며 앞날의 **범위 안에서** 열고 닫는다.

남는 정성 표현이 많다. 긴실체 척도, "긴 아래꼬리"(**그림자 척도**), "더 작다"의 기준,
Marubozu 판정의 그림자 척도, "작은"의 짧은실체 척도, 직전 추세다. **규칙 3의 "범위"가
고저 범위인지 실체 범위인지 밝히지 않았다.**

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **하락**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 48. `CDL3INSIDE` — Three Inside Up / Down

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L4340과 L4327, 규칙 L4363)이다. Morris
머리말은 Three Inside Up이 **Trend Required = Yes, Confirmation = No**, Three Inside Down이
**Yes, Required**다.

**Morris는 이 패턴이 자기가 만든 것임을 명시한다.** `morris_cce.txt` L4359~4362에
"The Three Inside Up and Three Inside Down patterns are not found in any Japanese literature.
We developed them to assist in improving the overall results of the Harami pattern, and they
have done quite well"이라고 적는다. 곧 일본 문헌에 없으며 하라미의 성적을 높이려고 자신이
개발했다는 것이다.

> 1. A Harami pattern is first identified using all previously set rules.
> 2. The third day shows a higher close for a Three Inside Up and a lower close for a Three
>    Inside Down.

번역하면 이렇다.

1. 먼저 **앞서 정한 모든 규칙으로 하라미를 찾는다.**
2. 셋째 날이 Three Inside Up이면 더 높은 종가를, Three Inside Down이면 더 낮은 종가를
   보인다.

**규칙 2의 "더 높은 종가"가 무엇에 대한 것인지 밝히지 않았다.** 두 번째 날 대비인지 첫날
대비인지 정해야 한다. 남는 정성 표현은 하라미가 요구하는 긴실체·짧은실체 척도와 직전
추세이며, 셋째 날 자체는 대소 비교만으로 끝난다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 49. `CDL3OUTSIDE` — Three Outside Up / Down

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L4435와 L4446)이다. **규칙 제목이 다른
항목과 달리 "Rules of Recognition"이 아니라 "Pattern Recognition"이며 L4471에 있다.**
Morris 머리말은 Three Outside Up이 **Trend Required = Yes, Confirmation = No**,
Three Outside Down이 **Yes, Required**다.

**이 패턴도 Morris가 만든 것이다.** L4467~4470에 "The Three Outside Up and Three Outside
Down patterns are not found in any Japanese literature. We developed them to assist in
improving the overall results of the Engulfing pattern, and they have done quite well"이라고
적는다.

> 1. An Engulfing pattern is formed using all of the previously set rules.
> 2. The third day has a higher close for the Threee Outside Up pattern and a lower for a
>    Three Outside Down pattern.

번역하면 이렇다.

1. **앞서 정한 모든 규칙으로 장악형을 만든다.**
2. 셋째 날이 Three Outside Up이면 더 높은 종가를, Three Outside Down이면 더 낮은 종가를
   갖는다.

원문 "Threee"는 오식이다. **규칙 1이 장악형의 규칙 전부를 물려받으므로 장악형이 요구하는
직전 추세가 그대로 따라온다.** 곧 이 패턴은 대소 비교만으로 끝나지 않는다.
Morris는 이어서 "Confirmation patterns do not have any more flexibility than the underlying
pattern"이라고 적어, 확인 패턴은 바탕 패턴보다 더 느슨해질 수 없다고 밝힌다.

**해설이 셋째 종가의 비교 대상을 준다.** `morris_cce.txt` L4462~L4465에 있다.

> Here, the Engulfing pattern is followed by either a higher or a lower close on the third
> day, depending on whether the pattern is up or down.

번역하면, 장악형 **다음에** 셋째 날의 더 높거나 더 낮은 종가가 따라온다. 곧 비교 대상은
장악형을 이루는 **둘째 날(장악하는 봉)의 종가**다. 같은 구조를 Morris는 Three Inside에서도
쓰며 L4356~L4358에 "A bullish Harami followed by a third day that closes higher"라고 적는다.

**결정 C에 따라 이 비교 대상을 정의에 넣는다.** 비교 대상을 명시하는 편이 명시하지 않는
것보다 좁다.

최종 정의는 이렇다(Three Outside Up 기준).

1. 18번 Engulfing의 규칙 전부를 만족한다. 곧 직전 추세가 하락이고, 둘째 실체가 첫 실체를
   감싸며, 두 실체의 색이 반대다.
2. 셋째 날의 **종가가 둘째 날의 종가보다 높다.**

Three Outside Down은 좌우를 뒤집는다. 갭은 쓰지 않는다. 필요한 척도는 **직전 추세**뿐이다.
우리가 정해야 하는 것은 없다. 셋째 날 조건은 대소 비교로 끝난다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 50. `CDLUNIQUE3RIVER` — Unique Three River Bottom

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L3491, 규칙 L3512)이다. Nison 2판에는 이
이름이 나오지 않는다. Morris 머리말은 **Trend Required = Yes, Confirmation = Required**다.

> 1. The first day is a long black day.
> 2. The second day is a Harami day, but the body is also black.
> 3. The second day has a lower shadow that sets a new low.
> 4. The third day is a short white day that is below the middle day.

번역하면 이렇다.

1. 첫날은 긴 음봉이다.
2. 두 번째 날은 하라미 날이되 **실체도 음봉**이다.
3. 두 번째 날은 **새 저점을 만드는 아래꼬리**를 갖는다.
4. 셋째 날은 **가운데 날보다 아래에 있는** 짧은 양봉이다.

**규칙 3이 규칙 2와 긴장 관계에 있다.** 하라미는 실체가 앞 실체 안에 들어가는 것인데 여기서는
꼬리가 새 저점을 만들어야 하므로, 포함 관계가 실체에만 적용됨을 분명히 해야 한다. 규칙 4의
"아래에 있다"가 실체 전체인지 종가인지 밝히지 않았다. 남는 정성 표현은 긴실체 척도,
짧은실체 척도, 직전 추세다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **하락**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 51. `CDLCONCEALBABYSWALL` — Concealing Baby Swallow

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L5133, 규칙 L5154)이다. Nison 2판에는 이
이름이 나오지 않는다. Morris 머리말은 **Trend Required = Yes, Confirmation = No**다.
네 봉짜리이지만 세 캔들 묶음에 함께 두었다.

> 1. Two Black Marubozu days make up the first two days of the pattern.
> 2. The third day is black with a down gap open. However, this day trades into the body of
>    the previous day, producing a long upper shadow.
> 3. The fourth black day completely engulfs the third day, including the shadow.

번역하면 이렇다.

1. **Black Marubozu 둘**이 이 패턴의 처음 두 날을 이룬다.
2. 셋째 날은 음봉이며 **갭 하락으로 열린다.** 다만 이 날은 앞날의 실체 안까지 거래되어
   **긴 위꼬리**를 만든다.
3. 넷째 날 음봉이 셋째 날을 **꼬리까지 포함해 완전히 감싼다.**

**규칙 3의 감쌈이 꼬리까지 포함한다는 점이 명시되어 있다.** 장악형이 실체만 감싸는 것과
대비되며, 이 자리는 원전이 분명하다. 남는 정성 표현은 Marubozu 판정의 그림자·긴실체 척도,
"긴 위꼬리"(**그림자 척도**), 직전 추세다.

## 4.5 네 봉 이상과 갭 지속형 (10종)

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세가 **하락**일 것을 요구한다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의
**10기간 지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 52. `CDL3LINESTRIKE` — Three-Line Strike

원전은 Morris 3판 4장(머리말 `morris_cce.txt` L7307과 L7327, 규칙 L7360)이다. Morris
머리말은 강세형이 **Trend Required = Yes, Confirmation = No**, 약세형이 **Yes, Suggested**다.
유형은 지속형이다.

> Bullish Three-Line Strike
> 1. Three days resembling Three White Soldiers are continuing an uptrend.
> 2. A higher open on the fourth day drops to close below the open of the first white day.
>
> Bearish Three-Line Strike
> 1. Three days resembling Three Black Crows are continuing a downtrend.
> 2. A lower open on the fourth day rallies to close above the open of the first black day.

번역하면 강세형은 이렇다. 첫째, **삼백병과 닮은 사흘**이 상승 추세를 이어 간다. 둘째,
넷째 날이 더 높게 열렸다가 떨어져 **첫 양봉의 시가 아래에서** 마감한다.

약세형은 좌우가 뒤집힌다.

**규칙 절 바로 앞의 해설이 훨씬 구체적이다.** `morris_cce.txt` L7344~L7357에 있다.

> Bullish Three-Line Strike
> Three white days with consecutively higher highs are followed by a long black day. This
> long black day opens at a new high and then plummets to a lower low than the first white
> day of the pattern.
>
> Bearish Three-Line Strike
> A downtrend is accentuated by three black days that each have consecutively lower lows.
> The fourth day opens at a new low, then rallies to close above the high of the first black
> day.

번역하면 강세형은 이렇다. **고가가 잇달아 높아지는** 양봉 셋 뒤에 **긴 음봉**이 온다. 그
긴 음봉은 **새 고점에서 열려** 첫 양봉보다 **더 낮은 저점까지** 떨어진다. 약세형은
**저가가 잇달아 낮아지는** 음봉 셋 뒤에 넷째 날이 **새 저점에서 열려 첫 음봉의 고가 위로**
올라 마감한다.

**결정 C에 따라 이 해설을 규범으로 채택한다.** 조건이 더 많은 쪽이 규범이며, 해설은 규칙
절이 "resembling"으로 남긴 자리를 세 가지로 메운다. 첫째, 앞 세 봉의 관계가 고가 또는
저가의 **연속 갱신**으로 확정된다. 둘째, 넷째 날이 **길어야** 한다는 요건이 생긴다. 셋째,
넷째 날의 종가 기준이 약세형에서 **첫날의 시가가 아니라 고가**로 좁아진다. 음봉의 고가는
시가보다 높거나 같으므로 이는 규칙 절보다 엄격하다.

최종 정의는 이렇다(강세형 기준).

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
2. 양봉 셋이 이어지며 **고가가 잇달아 높아진다.**
3. 넷째 날은 **긴 음봉**이며 **새 고점에서 열린다.**
4. 넷째 날의 **저가가 첫 양봉의 저가보다 낮고**, 종가가 첫 양봉의 **시가 아래**다.

**앞 판이 "resembling 때문에 판정이 서지 않는다"고 적은 결론은 철회한다.** 해설이 판정을
세운다. 갭은 쓰지 않는다. 필요한 척도는 **긴실체**와 **직전 추세**다. 우리가 정해야 하는
것은 넷째 날의 "긴" 실체 임계 하나이며, 이는 공통 긴실체 척도에서 온다.

### 53. `CDLBREAKAWAY` — Breakaway

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L4990과 L5001, 규칙 L5044)이다. Morris
머리말은 강세형과 약세형 모두 **Trend Required = Yes, Confirmation = Suggested**다.

> 1. The first day is a long day with color representing the current trend.
> 2. The second day is the same color and the body gaps in the direction of the trend.
> 3. The third and fourth days continue the trend direction, with closes consecutively
>    greater in the direction of trend. It is better if the third day is white for the
>    bullish case and black for the bearish case.
> 4. The fifth day is a long opposite-color day that closes inside the gap caused by the
>    first and second days.

번역하면 이렇다.

1. 첫날은 현재 추세를 나타내는 색의 긴 날이다.
2. 두 번째 날은 같은 색이며 **실체가 추세 방향으로 갭을 이룬다.**
3. 셋째 날과 넷째 날은 추세 방향을 이어 가며 종가가 잇달아 추세 방향으로 더 나아간다.
   강세형이면 셋째 날이 양봉인 편이, 약세형이면 음봉인 편이 낫다.
4. 다섯째 날은 **반대색의 긴 날**이며 첫날과 두 번째 날이 만든 **갭 안에서** 마감한다.

**규칙 2가 갭의 기준을 실체로 못박았다.** 규칙 3의 색 조건은 "It is better if"이므로 필수가
아니라 권고다.

**유연성 절이 봉 수를 열어 둔다.** `morris_cce.txt` L5065~L5070에 있다.

> There could be more than three days after the gap as long as the last day of the pattern
> closes inside the initial gap. It is also possible to have at least two days after the gap.

번역하면, 마지막 날이 처음의 갭 안에서 마감하기만 하면 갭 뒤의 날이 셋보다 많아도 되고
둘만 있어도 된다.

**결정 C에 따라 규칙 절의 고정 다섯 봉을 규범으로 삼는다.** 유연성 절은 봉 수를 넓히므로
좁은 쪽인 규칙 절이 이긴다. 유연성 절은 표준에 **주석으로만** 남긴다. 이 선택의 결과로
갭 뒤가 둘 또는 넷 이상인 변형은 잡히지 않으며, 그 대신 패턴의 봉 수가 다섯으로 고정되어
상태 크기와 워밍업이 확정된다.

**계보도 적어 둔다.** `morris_cce.txt` L5041~L5043은 이렇게 적는다.

> Japanese literature does not discuss a bearish version of the Breakaway pattern. I decided
> to test such a pattern and have found that it works quite well.

곧 **약세형 Breakaway는 일본 문헌에 없고 Morris가 시험 삼아 만든 것이다.** Three Inside와
Three Outside에 이어 Morris가 창안했다고 스스로 밝힌 세 번째 자리다.

갭은 **실체 사이의 갭**이다. 필요한 척도는 **긴실체**와 **직전 추세**다. 우리가 정해야
하는 것은 없다. 봉 수는 결정 C가 다섯으로 확정했다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 54. `CDLLADDERBOTTOM` — Ladder Bottom

원전은 Morris 3판 3장(머리말 `morris_cce.txt` L5213, 규칙 L5230)이다. Nison 2판에는 이
이름이 나오지 않는다. Morris 머리말은 **Trend Required = Yes, Confirmation = No**다.

> 1. Three long black days with consecutive lower opens and closes occur much like the Three
>    Black Crows pattern.
> 2. The fourth day is black with an upper shadow.
> 3. The last day is white with an open above the body of the previous day.

번역하면 이렇다.

1. **시가와 종가가 잇달아 낮아지는 긴 음봉 셋**이 삼흑병과 비슷하게 나온다.
2. 넷째 날은 **위꼬리가 있는** 음봉이다.
3. 마지막 날은 양봉이며 **앞날의 실체 위에서** 열린다.

**규칙 2는 위꼬리가 있기만 하면 되고 길이를 요구하지 않는다.** 이는 45번 Advance Block이
"긴 위꼬리"를 요구한 것과 다르며 Morris 본문 그대로다.

**유연성 절이 규칙 절과 세 자리에서 어긋난다.** `morris_cce.txt` L5250~L5254에 있다.

> The four black days of the Ladder Bottom pattern may or may not be long, but consecutively
> lower closes must occur. The last day must be white and may be either long or short, as
> long as the close is above the previous day's high.

번역하면, 네 음봉은 길어도 되고 길지 않아도 되지만 **종가가 잇달아 낮아져야 하며**,
마지막 날은 양봉이어야 하고 길든 짧든 상관없되 **종가가 앞날의 고가 위**여야 한다.

**결정 C는 두 층으로 되어 있고 구체적인 층이 먼저다.** Morris 안에서는 `Rules of
Recognition`이 규범이고 `Pattern Flexibility`는 주석이며, 이 규칙이 먼저 적용된다. "조건이
더 많은 쪽"이라는 일반 원칙은 **Nison과 Morris 사이에만** 적용된다. 따라서 유연성 절의
조건은 그것이 넓히는 것이든 좁히는 것이든 **실행 조건으로 올리지 않는다.**

**앞 판은 이 우선순위를 거꾸로 적용해 유연성 절의 두 조건을 규범으로 올렸다. 되돌린다.**
아래 셋은 모두 **주석으로만** 보존한다.

- 네 음봉이 길지 않아도 된다는 완화.
- 네 음봉 전체에 연속 하락 종가를 요구하는 추가.
- 마지막 양봉의 종가가 앞날 고가 위여야 한다는 추가.

**최종 정의는 규칙 절 그대로다.**

1. 직전 추세가 **하락**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **아래**이면 하락으로 본다.
2. **긴 음봉 셋**이 시가와 종가를 잇달아 낮추며 이어진다.
3. 넷째 날은 **위꼬리가 있는 음봉**이다.
4. 마지막 날은 **양봉**이며 **앞날의 실체 위에서 열린다.**

갭은 쓰지 않는다. 규칙 4의 "앞날의 실체 위에서 열린다"는 갭이 아니라 시가의 위치 비교다.
필요한 척도는 **긴실체**, **그림자**, **직전 추세**이며, 위꼬리가 존재한다는 판정은
**퇴화 봉 규칙**에 걸린다. 우리가 정해야 하는 것은 긴실체 임계와 위꼬리를 "있다"고 볼 최소
크기 둘이다.

### 55. `CDLMATHOLD` — Mat Hold

원전은 Morris 3판 4장(머리말 `morris_cce.txt` L7146과 L7159, 규칙 L7194)이다. Nison 2판에는
이 이름이 나오지 않는다. Morris 머리말은 강세형이 **Trend Required = Yes,
Confirmation = No**, 약세형이 **Yes, Suggested**다.

> Bullish Mat Hold
> 1. A long white day is formed in an uptrending market.
> 2. A gap up with a lower close on the second day forms almost a starlike day.
> 3. The following two days are reaction days similar to the Rising Three Methods.
> 4. The fifth day is a white day with a new closing high.
>
> Bearish Mat Hold
> 1. The pattern begins with a long black day that occurs during a downtrend.
> 2. The next day is a white day whose real body gaps away from the prior day's black real
>    body.
> 3. Two relatively short days follow, with each making a higher top and bottom than the
>    preceding day.
> 4. The fifth day is a long black day that opens below the close of the fourth day and then
>    closes below the open of the second day.

번역하면 강세형은 이렇다. 첫째, 상승 시장에서 긴 양봉이 만들어진다. 둘째, 두 번째 날은
갭 상승했다가 더 낮게 마감해 **거의 별 같은 날**을 이룬다. 셋째, 이어지는 이틀은 상승삼법과
비슷한 되돌림 날이다. 넷째, 다섯째 날은 **새 종가 고점**을 만드는 양봉이다.

약세형은 훨씬 구체적이다. 첫째, 하락 추세에서 긴 음봉으로 시작한다. 둘째, 다음 날은
양봉이며 그 실체가 앞 음봉 실체에서 갭을 이룬다. 셋째, 상대적으로 짧은 이틀이 이어지며
각각 앞날보다 고점과 저점이 더 높다. 넷째, 다섯째 날은 긴 음봉이며 넷째 날의 종가 아래에서
열려 **두 번째 날의 시가 아래에서** 마감한다.

**규칙 절의 강세형은 정성적이지만 해설이 그 자리를 메운다.** `morris_cce.txt`
L7172~L7180에 있다.

> The first three days start out like the Upside Gap Two Crows, with the exception that the
> second black body (third day) dips into the body of the first long white day. This is
> followed by another small black body that closes even lower, but still within the range of
> the first white body. The fifth day sees a large gap opening, with a strong rise to a close
> above the high of the highest of the three black days.

번역하면 이렇다. 처음 사흘은 Upside Gap Two Crows처럼 시작하되, **셋째 날의 두 번째 음봉이
첫 긴 양봉의 실체 안으로 파고든다**는 점이 다르다. 이어 **또 하나의 작은 음봉이 더 낮게
마감하되 여전히 첫 양봉의 범위 안**에 머문다. **다섯째 날은 큰 갭 상승으로 열려 세 음봉
가운데 가장 높은 고가 위로** 힘차게 올라 마감한다.

**결정 C에 따라 이 해설을 규범으로 채택한다.** 규칙 절보다 조건이 많고 좁다. 채택하면
강세형의 정의는 이렇게 선다.

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
2. 첫날은 **긴 양봉**이다.
3. 두 번째 날은 첫 실체 위로 **실체 갭**을 이루는 음봉이며 종가가 시가보다 낮다.
4. 셋째 날은 음봉이며 **첫 양봉의 실체 안으로 파고든다.**
5. 넷째 날은 **작은 음봉**이며 셋째 날보다 낮게 마감하되 **첫 양봉의 범위 안**에 머문다.
6. 다섯째 날은 양봉이며 **갭 상승으로 열려 세 음봉의 최고 고가 위에서** 마감한다.

**앞 판이 "강세형은 판정이 서지 않는다"고 적은 결론은 철회한다.** 해설이 판정을 세운다.
다만 해설이 규칙 절의 "새 종가 고점"을 "세 음봉의 최고 고가 위"로 바꾸므로, 어느 쪽을
쓰는지는 표준에 명시해야 한다. 결정 C에 따라 더 좁은 해설 쪽을 쓴다.

약세형은 규칙 절이 이미 구체적이므로 그대로 쓴다.

갭은 **실체 사이의 갭**이다. 규칙 절의 약세형이 "real body gaps away from the prior day's
black real body"라고 못박는다. 필요한 척도는 **긴실체**, **짧은실체**, **직전 추세**다.
우리가 정해야 하는 것은 없다. **TA-Lib의 `penetration` 0.5는 원전에 근거를 찾지 못했으므로
쓰지 않는다.**

### 56. `CDLRISEFALL3METHODS` — Rising / Falling Three Methods

원전은 Morris 3판 4장(머리말 `morris_cce.txt` L7003과 L7018, 규칙 L7055)과 Nison 2판
7장이다. Morris 머리말은 Rising이 **Trend Required = Yes, Confirmation = No**, Falling이
**Yes, Suggested**다.

> 1. A long candlestick is formed representing the current trend.
> 2. This candlestick is followed by a group of small real body candlesticks. It is best if
>    they are opposite in color.
> 3. The small candlesticks rise or fall opposite to the trend and remain within the high-low
>    range of the first day.
> 4. The final day should be a strong day, with a close outside of the first day's close and
>    in the direction of the original trend.

번역하면 이렇다.

1. 현재 추세를 나타내는 긴 캔들이 만들어진다.
2. 그 캔들 뒤에 **작은 실체 캔들 무리**가 따른다. 반대색이면 가장 좋다.
3. 그 작은 캔들들은 추세와 반대로 오르내리되 **첫날의 고저 범위 안에 머문다.**
4. 마지막 날은 강한 날이어야 하며 **첫날의 종가 바깥**에서 원래 추세 방향으로 마감한다.

**규칙 2의 "a group"이 몇 봉인지 Morris는 정하지 않았지만 Nison이 유한 범위를 준다.**
`nison_jcct.txt` L3994~L3996은 이렇게 적는다.

> The ideal number of small candles is three but two or more than three are also acceptable
> if they hold within the long white candle's high-low range.

그리고 L4025~L4027이 그 범위를 닫는다.

> Nonetheless, from my experience, two and up to five small real bodies work fine.

번역하면, 작은 캔들의 **이상적인 수는 셋**이지만 그것들이 긴 양봉의 고저 범위 안에 머물기만
하면 **둘이거나 셋보다 많아도** 된다. 그리고 Nison 자신의 경험으로는 **둘에서 다섯까지**
잘 작동한다.

**따라서 봉 수는 상한이 없는 것이 아니라 둘에서 다섯 사이로 닫힌다.** 앞 판이 개수를 미정으로
두고 상한 없는 범위를 열어 둔 것은 이 대목을 놓친 탓이었고 철회한다. 결정 10에 남는 선택지는
**고정 세 봉**과 **둘에서 다섯까지의 유한 범위** 둘뿐이며, 어느 쪽을 골라도 패턴의 창 길이는
유한하다.

**규칙 3이 고저 범위 기준임을 명시한 점은 분명하다.** 규칙 2의 색 조건은 "It is best if"이므로
권고다. 남는 정성 표현은 긴실체 척도, 짧은실체 척도, "강한 날"의 기준, 직전 추세다.

**추세 조건(결정 B).** Morris 머리말이 `Trend Required = Yes`인 패턴이므로 직전 추세를 요구하며 방향은 형태에 따라 갈린다. 판정은 **패턴 첫날 범위의 중간값**을
그 시점의 **10기간 지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승, **아래**이면
하락으로 본다.
비교에 쓰는 봉은 **패턴의 첫날**로 확정한다. Morris가 개별 패턴 해설에서 "The midpoint of the range of the first day is above a 10-period moving average"라고
적은 방식을 그대로 따르며, 이 자리는 선택으로 열어 두지 않는다.
### 57. `CDLGAPSIDESIDEWHITE` — Up/Down-gap Side-by-side White Lines

원전은 Morris 3판 4장(머리말 `morris_cce.txt` L6452와 L6463, 규칙 L6505)과 Nison 2판
7장·용어사전이다. Morris 머리말은 강세형이 **Confirmation = Suggested**, 약세형이
**Required**다.

> 1. A gap is made in the direction of the trend.
> 2. The second day is a white candle line.
> 3. The third day is also a white candle line of about the same size and opens at about the
>    same price.

번역하면 이렇다.

1. **추세 방향으로 갭**이 만들어진다.
2. 두 번째 날은 양봉이다.
3. 셋째 날도 양봉이며 **크기가 대략 같고 대략 같은 가격에서 열린다.**

Nison 용어사전은 "Two consecutive white candlesticks that have the same open and whose real
bodies are about the same size"라고 적어 **시가가 같다**고 못박는 반면 Morris는 "about the
same price"라고 느슨하게 둔다. **결정 C에 따라 조건이 더 좁은 Nison의 같은 시가를
채택한다.** Morris의 "대략 같은 가격"은 주석으로만 남긴다. 실체 크기에 대해서는 두 원전이
모두 "about the same size"로 같으므로 그대로 둔다.

**최종 정의는 이렇다(상승 갭 기준).**

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
2. 첫날과 둘째 날 사이에 **추세 방향으로 갭**이 있다.
3. 둘째 날과 셋째 날이 모두 **양봉**이다.
4. 둘째 날과 셋째 날의 **시가가 같다.**
5. 둘째 날과 셋째 날의 **실체 크기가 서로 비슷하다.**

하락 갭 형은 좌우를 뒤집는다. 갭의 종류는 **원문이 구분하지 않는다.** Morris 규칙 1은
"A gap is made in the direction of the trend"라고만 적고 Nison 용어사전도 갭의 기준을
밝히지 않는다. 필요한 척도는 **같음**(같은 시가), **가까움**(비슷한 실체 크기), **직전
추세**다. 우리가 정해야 하는 것은 "같다"의 허용오차, "비슷한 크기"의 허용폭, 그리고 갭
기준 셋이다.

### 58. `CDLTASUKIGAP` — Tasuki Gap

원전은 Morris 3판 4장(머리말 `morris_cce.txt` L6322와 L6333, 규칙 L6364)과 Nison 2판
7장·용어사전이다. Morris 머리말은 Upside가 **Trend Required = Yes,
Confirmation = Suggested**, Downside가 **Yes, Required**다.

> 1. A trend is underway, with a gap between two candlesticks of the same color.
> 2. The color of the first two candlesticks represents the prevailing trend.
> 3. The third day, an opposite-color candlestick opens within the body of the second day.
> 4. The third day closes into the gap but does not fully close the gap.

번역하면 이렇다.

1. **추세가 진행 중이며** 같은 색 캔들 둘 사이에 갭이 있다.
2. 처음 두 캔들의 색이 우세한 추세를 나타낸다.
3. 셋째 날은 반대색 캔들이며 **두 번째 날의 실체 안에서** 열린다.
4. 셋째 날은 **갭 안으로 마감하되 갭을 완전히 메우지는 않는다.**

**Nison이 조건 둘을 더 준다.** `nison_jcct.txt` L3773~3774와 용어사전 L7130~7131에 같은
문장이 있다.

> The two candles of the tasuki should be about the same size.

곧 **타스키를 이루는 두 캔들은 크기가 서로 비슷해야 한다.** 또 L3768~3771은 이렇게 적는다.

> The close on the black candle day is the fight point. If the market closes under the bottom
> of the window, the bullish outlook of the upward gap tasuki is voided.

곧 음봉 날의 종가가 승부처이며, 시장이 **창(갭)의 아래쪽 밑으로** 마감하면 상승 타스키의
강세 전망은 무효가 된다. 이것은 Morris 규칙 4의 "갭을 완전히 메우지 않는다"를 어느 값으로
재는지 밝혀 주는 서술이다.

**결정 C에 따라 두 조건을 모두 채택한다.** 조건이 더 많은 쪽이 규범이므로 최종 정의는
Morris 네 규칙에 Nison의 비슷한 크기 요건과 무효화 기준을 더한 것이다.

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다. 이것이 상승 타스키
   갭이다. **하락 타스키 갭은 방향이 반대여서 직전 추세가 하락이고, 중간값이 이동평균
   아래이면 하락으로 본다.**
2. 같은 색 캔들 둘 사이에 **실체 갭**이 있고 그 색이 추세를 나타낸다.
3. 두 캔들의 **실체 크기가 서로 비슷하다.**
4. 셋째 날은 반대색이며 **두 번째 날의 실체 안에서** 열린다.
5. 셋째 날의 **종가**가 갭 안으로 들어오되 **갭의 반대쪽 끝을 넘지 않는다.** 상승 타스키에서
   종가가 창의 아래쪽 밑으로 내려가면 무효다.

**앞 판이 "비슷한 크기 요건은 원전에 없고 TA-Lib이 더했다"고 적은 것은 사실이 아니었고
철회한다.** 위 원문이 그 반대를 말한다.

갭의 종류는 **실체 사이의 갭**이다. Morris 규칙 3이 실체를 말하고 Nison도 창을 실체 기준으로
설명한다. 필요한 척도는 **직전 추세**와 "비슷한 크기"를 재는 **가까움 척도** 둘이다.
우리가 정해야 하는 것은 두 실체가 얼마나 비슷해야 "비슷한 크기"인지 하나다.

### 59. `CDLXSIDEGAP3METHODS` — Upside / Downside Gap Three Methods

원전은 Morris 3판 4장(머리말 `morris_cce.txt` L6794와 L6805, 규칙 L6825)이다. Nison 2판에는
이 이름이 나오지 않는다. Morris 머리말은 Upside가 **Trend Required = Yes,
Confirmation = No**, Downside가 **Yes, Required**다.

> 1. A trend continues, with two long days that have a gap between them.
> 2. The third day fills the gap and is the opposite color of the first two days.

번역하면 이렇다.

1. **추세가 이어지며** 그 사이에 갭이 있는 **긴 날 둘**이 있다.
2. 셋째 날이 **갭을 메우며** 처음 두 날과 반대색이다.

**규칙 1이 추세와 긴 날을 함께 요구한다.**

**규칙 절 앞의 해설이 셋째 날을 구체화한다.** `morris_cce.txt` L6818~L6824에 있다.

> A gap appears between two candlesticks of the sample color. This color should reflect the
> trend of the market. The third day opens within the body of the second candlestick and then
> closes within the body of the first candlestick (bridging the first and second candles),
> which would also make it the opposite color of the first two days. This would, in
> traditional terminology, close the gap.

원문의 "sample"은 "same"의 오식이다. 번역하면, 같은 색 캔들 둘 사이에 갭이 나타나고 그
색이 시장의 추세를 반영해야 한다. **셋째 날은 둘째 캔들의 실체 안에서 열려 첫 캔들의 실체
안에서 마감하며**, 그렇게 두 캔들을 잇는다. 그 결과 셋째 날은 처음 두 날과 반대색이 된다.
전통적인 용어로는 이것이 갭을 메우는 것이다.

**결정 C에 따라 이 해설을 규범으로 채택한다.** 규칙 절의 "갭을 메운다"가 무슨 뜻인지를
해설이 시가와 종가의 위치로 정확히 정해 준다. **앞 판이 "메운다의 정확한 뜻이 불명확하다"고
적은 것은 이 해설을 놓친 탓이었고 철회한다.**

최종 정의는 이렇다(Upside 기준).

1. 직전 추세가 **상승**이다. 판정은 **패턴 첫날 범위의 중간값**을 그 시점의 **10기간
   지수이동평균**과 견주어, 중간값이 이동평균 **위**이면 상승으로 본다.
2. 첫날과 둘째 날은 **긴 양봉**이며 그 사이에 **실체 갭**이 있다.
3. 셋째 날은 음봉이며 둘째 실체 **안에서 열려** 첫 실체 **안에서 마감한다.**

Downside는 좌우를 뒤집는다. 갭은 **실체 사이의 갭**이다. 필요한 척도는 **긴실체**와
**직전 추세**다. 우리가 정해야 하는 것은 없다.

### 60. `CDLHIKKAKE` — Hikkake

원전은 Chesler의 *Active Trader* 2004년 4월호 기사이며 추출본은 `chesler_hikkake_2004.txt`
**L15~L27(설정)과 L38~L47(확인)**이다. 앞 판이 L14~L37만 가리켜 확인 규칙을 인용 범위 밖에
두었던 것을 바로잡는다. **이 패턴은 일본식 캔들 패턴이 아니고 Nison에도 Morris에도 없다.**

> The basic hikkake pattern consists of two price bars... The first bar in the pattern is an
> inside bar, which is simply a bar with a lower high and higher low than the preceding bar.
> The second bar in the pattern must have a higher high and higher low than the previous
> (inside) bar for a bearish hikkake set up, or a lower low and a lower high than the
> previous (inside) bar for a bullish hikkake set up.

> With the hikkake pattern, a false move should not be anticipated unless price crosses above
> the high of the inside bar (for a bullish setup) or below the low of the inside bar (for a
> bearish setup). Verification must occur within three bars of the hikkake pattern, otherwise
> the pattern is ignored.

번역하면 이렇다.

1. 첫 봉은 **인사이드 바**다. 곧 앞 봉보다 고가가 낮고 저가가 높은 봉이다.
2. 두 번째 봉은, **약세 설정**이면 인사이드 바보다 고가와 저가가 모두 높고, **강세 설정**
   이면 인사이드 바보다 저가와 고가가 모두 낮다.
3. 확인은 강세 설정이면 가격이 **인사이드 바의 고가 위로** 올라설 때, 약세 설정이면
   **인사이드 바의 저가 아래로** 내려갈 때 일어난다.
4. **확인은 패턴으로부터 세 봉 안에 일어나야 하며, 그렇지 않으면 그 패턴은 무시한다.**

Chesler는 "the basic hikkake pattern ignores the open-to-close relationship, also known in
candlestick terminology as the 'real body' portion of the price bar"라고 적어 **시가와 종가를
쓰지 않음**을 못박는다.

**이 패턴에는 남는 정성 표현이 없다.** 판정이 고가와 저가의 대소 비교만으로 끝나고, 확인
기한마저 원전이 세 봉으로 못박았다. **직전 추세도 요구하지 않는다.** 기사는 이 패턴이
반전형과 지속형 양쪽으로 기능한다고 적는다. 부등식은 인사이드 바 정의가 "lower high and
higher low"이므로 엄격 부등식이다.

갭을 쓰지 않는다. 필요한 척도는 **없다.** 우리가 정해야 하는 것은 **확인 완료 신호를 어느
봉의 출력으로 낼지** 하나이며, 이는 패턴 고유의 문제가 아니라 출력 시점 규약(결정 11)에
속한다.

**입력으로 필요한 봉은 셋이다.** Chesler가 설정을 두 봉이라 부르지만 첫 봉이 인사이드
바인지 판단하려면 그 앞 봉이 있어야 한다. 확인까지 보면 최대 여섯 봉이 필요하다.

### 61. `CDLHIKKAKEMOD` — Modified Hikkake

원전은 같은 Chesler 기사이며 추출본은 `chesler_hikkake_2004.txt` **L204~L213**이다.
앞 판이 L146~L156이라고 적은 것은 틀렸고 바로잡는다.

> One variation of the basic pattern applies the following set of requirements to the bar
> immediately preceding the inside bar:
> 1. The bar must close at the top of its range (for bearish patterns) or the low of its
>    range (for bullish patterns).
> 2. The range must be less than the range of the previous bar.

번역하면 이렇다.

1. 60번의 규칙 전부를 만족한다.
2. **인사이드 바 바로 앞 봉**이 약세형이면 자기 범위의 **꼭대기에서**, 강세형이면 자기
   범위의 **바닥에서** 마감한다.
3. 그 **맥락 봉의 고저 범위**가 **그 바로 앞 봉의 고저 범위보다 작다.** 곧 인사이드 바에서
   두 봉 앞의 범위와 견준다.

Chesler는 이 변형이 기본형보다 훨씬 드물며 주로 추세 반전형으로 기능한다고 덧붙인다.

**원문은 단정이지 여지가 아니다.** Chesler는 "The bar **must** close at the top of its
range"라고 적는다. 곧 종가가 그 봉의 고가와 같아야 하고(약세형), 강세형이면 저가와 같아야
한다. **앞 판이 여기에 근접 허용오차가 필요하다고 적은 것은 원문에 없는 완화였고
철회한다.** 규칙 2는 등호이고 규칙 3은 엄격 부등식이다.

갭을 쓰지 않는다. 필요한 척도는 **없다.** 우리가 정해야 하는 것도 **없다.** 다만 종가와
고가가 정확히 같은 봉은 실제 자료에서 드물어 발생 빈도가 매우 낮아진다. Chesler 자신도
"This version occurs far less frequently in the data than the basic hikkake pattern"이라고
적어 그 점을 예고한다. 빈도가 낮다는 이유로 허용오차를 도입하는 것은 원전을 바꾸는 것이므로
하지 않는다.

## 4.6 원전에 판정 규칙이 없어 쓰지 못한 패턴

**없다. 61종 모두 원전에서 판정 규칙을 찾아 옮겼다.**

**다만 다음 두 진술을 갈라 읽어야 한다.** 앞 판은 이 둘을 뭉뚱그려 적어 결정 10과
모순되었다.

- **구현에서 제외할 패턴은 없다.** 원전에 판정 규칙이 아예 없어 손댈 수 없는 패턴은
  하나도 없다. 61종 전부가 구현 대상이다.
- **그렇다고 구조 선택이 하나도 남지 않은 것은 아니다.** 원문이 같은 자리를 두 가지로
  읽을 수 있게 적어 둔 패턴이 여섯 있다. `CDLHARAMICROSS`, `CDLUNIQUE3RIVER`,
  `CDL3STARSINSOUTH`, `CDLRISEFALL3METHODS`(둘), `CDLKICKINGBYLENGTH`이며 결정 10에
  모아 두었다. 이들은 값을 정하는 문제가 아니라 **어느 읽기를 규범으로 삼을지**를 정하는
  문제이므로 척도를 아무리 정해도 풀리지 않는다.

**앞 판이 여기에 적었던 셋을 철회한다.** 앞 판은 `CDLMATHOLD` 강세형과 `CDL3LINESTRIKE`와
`CDLLADDERBOTTOM`을 "규칙이 있으되 그대로는 구현되지 않는다"고 적었다. 그것은 규칙 절만
읽고 **바로 옆의 해설과 유연성 절을 놓친 탓**이었다.

- `CDLMATHOLD` 강세형의 "almost a starlike day"는 `morris_cce.txt` L7172~L7180의 해설이
  셋째·넷째 봉의 위치와 다섯째 봉의 종가로 풀어 준다. 55번에 옮겼다.
- `CDL3LINESTRIKE`의 "resembling"은 L7344~L7357의 해설이 연속 고점·저점과 넷째 날의 긴
  반대색으로 풀어 준다. 52번에 옮겼다.
- `CDLLADDERBOTTOM`의 "much like"는 L5250~L5254의 유연성 절이 연속 하락 종가와 마지막
  양봉의 종가 조건으로 풀어 준다. 54번에 옮겼다.

**남는 것은 하나뿐이다.** `CDLKICKINGBYLENGTH`에서 두 Marubozu의 길이가 정확히 같은 경우를
원전이 다루지 않는다. 이는 정의가 서지 않는 것이 아니라 **동률 처리 규약 하나가 비어
있는 것**이므로 "우리가 정해야 하는 것"으로 표시했다.

## 4.7 확인 등급을 원전에서 옮긴 목록

검토가 지적한 대로 확인이 필요한 패턴은 Hikkake와 Hanging Man과 Inverted Hammer만이 아니다.
**Morris는 89개 항목 전부에 확인 등급을 적어 두었다.** 분포는 `Required` 36건,
`Suggested` 25건, `No` 28건이다.

`Required`로 적힌 것을 TA-Lib 함수로 옮기면 다음과 같다. Hammer, Belt-hold(약세형만),
Engulfing(약세형만), Harami(약세형만), Harami Cross(약세형만), Shooting Star, Dark Cloud
Cover, Counterattack(약세형만), Kicking(양쪽), Morning Star, Evening Star, Evening Doji
Star, Abandoned Baby(약세형만), Tri Star(약세형만), Upside Gap Two Crows, Unique Three
River, Three Black Crows, Advance Block, Two Crows, Three Inside(하락형만), Three
Outside(하락형만), In-Neck(양쪽), On-Neck(약세형만), Separating Lines(약세형만),
Side-by-side White Lines(약세형만), Downside Gap Three Methods, Downside Tasuki Gap.

**여기서 두 가지를 짚어야 한다.** 첫째, **같은 패턴인데 방향에 따라 등급이 다른 경우가
많다.** 대체로 약세형이 `Required`이고 강세형이 `Suggested` 또는 `No`다. 둘째,
**Hanging Man과 Inverted Hammer는 Morris가 `No`로 적었는데 Nison은 둘 다 확인을 받아야
한다고 적어 두 원전이 반대다.** Nison L2428~L2429는 "Just as a hanging man needs bearish
confirmation, the inverted hammer needs bullish confirmation"이라고 한 문장에서 둘을 함께
묶는다. **결정 C에 따라 두 패턴 모두 Nison의 확인 요구를 채택했고**, 4장 8번과 9번에
반영했다. 따라서 아래 `No` 목록에서 이 둘을 뺀다.

`Suggested`로 적힌 것에는 Belt-hold(강세형), Engulfing(강세형), Piercing, Doji Star(약세형),
Counterattack(강세형), Morning Doji Star, Abandoned Baby(강세형), Tri Star(강세형),
Three Stars in the South, Stalled Pattern(약세형), Stick Sandwich(약세형), Breakaway(양쪽),
Ladder Top, Thrusting(약세형), Upside Tasuki Gap, Side-by-side White Lines(강세형),
Falling Three Methods, Mat Hold(약세형), Three-Line Strike(약세형)가 있다.

`No`로 적힌 것에는 Matching Low, Harami(강세형), Harami Cross(강세형), Doji Star(강세형), Homing Pigeon, Matching High, Three White Soldiers,
Identical Three Crows, Deliberation(강세형), Three Inside Up, Three Outside Up, Stick
Sandwich(강세형), Concealing Baby Swallow, Ladder Bottom, Separating Lines(강세형),
On-Neck(강세형), Thrusting(강세형), Upside Gap Three Methods, Rising Three Methods,
Mat Hold(강세형), Three-Line Strike(강세형)가 있다.

Chesler의 Hikkake는 Morris 체계 밖이지만 **확인을 필수로 정하고 기한까지 세 봉으로
못박았다.** 곧 61종 가운데 확인 규정이 가장 엄격한 것이 Hikkake다.

---

# 5. 척도와 미정 항목으로 정리한다

## 5.1 세 갈래 분류를 버린다

앞 판은 61종을 갈래 1과 갈래 2와 갈래 3으로 나누고 어디에도 들지 않는 52종을 "갈래 밖"으로
남겼다. **그 분류를 버린다.** 이유는 둘이다.

첫째, **분류 체계가 대상에 맞지 않았다.** 갈래 2가 "정해야 할 기준이 하나뿐인 패턴"으로
정의되어 있는데 61종 가운데 52종이 둘 이상을 요구했다. 분류가 대상의 85퍼센트를 담지 못하면
그것은 분류가 아니다. 갈래 3도 "원전 정의가 확정되지 않은 패턴"으로 정의되었으나, 원전을
끝까지 읽고 나니 원전에 판정 규칙이 아예 없는 패턴은 하나도 없었다. 다만 4.6절에 적었듯
**원문이 두 가지로 읽히는 구조 선택이 여섯 자리 남아 있으며**(결정 10), 그것은 갈래 3이
말하던 "원전 정의가 확정되지 않음"과는 다르다. 남은 것의 대부분은 구조의 미확정이
아니라 **값의 미정**이었고, 그 둘은 다른 문제다.

둘째, **결정 A가 확정되면서 분류가 답하려던 물음 자체가 사라졌다.** 세 갈래는 "이 패턴을
구현할 수 있는가"를 묻는 도구였다. 그런데 결정 A는 원전이 값을 주지 않는 자리에서도 우리가
값을 정해 구현한다고 확정했다. 따라서 구현 가능성은 더 이상 패턴을 가르는 축이 아니다.
**모든 패턴이 구현 대상이며, 남는 물음은 "무엇을 정해야 하는가"뿐이다.**

그래서 표에서 갈래 열을 빼고 다음 두 열을 둔다. 갈래 개수는 세지 않는다.

- **필요한 척도.** 그 패턴이 어느 척도를 요구하는가. 없으면 없다고 적는다.
- **우리가 정해야 하는 것.** 그 패턴에서 원전이 비워 둔 자리가 무엇인가. 없으면 없다고 적는다.

이 두 열이 표준 문서를 쓸 때 그대로 입력이 된다. 왼쪽 열은 어느 공통 척도를 먼저 정하면
어느 패턴이 함께 풀리는지 보여 주고, 오른쪽 열은 패턴 고유로 남는 자리를 보여 준다.

## 5.2 직전 추세를 요구하는 패턴과 요구하지 않는 패턴

**결정 B에 따라 추세는 패턴이 직접 판정한다.** 판정 방법은 61종 전부에서 하나로 같다.
해당 봉 범위의 중간값이 **10기간 지수이동평균** 위이면 상승, 아래이면 하락으로 본다.
근거는 Morris 6장이다. 그는 "the exponential period of 10 days seemed to work as well as
any"라고 적고, 개별 패턴에서 "The midpoint of the range of the first day is above a
10-period moving average. This means that an uptrend has been in place."처럼 쓴다.

**추세를 요구하는 패턴은 45종이고 요구하지 않는 패턴은 16종이다.**

요구하지 않는 16종은 성격이 셋으로 갈린다.

- **Morris가 캔들 선으로 다루어 패턴 머리말이 없는 12종.** `CDLDOJI`,
  `CDLLONGLEGGEDDOJI`, `CDLRICKSHAWMAN`, `CDLDRAGONFLYDOJI`, `CDLGRAVESTONEDOJI`,
  `CDLTAKURI`, `CDLSPINNINGTOP`, `CDLHIGHWAVE`, `CDLMARUBOZU`, `CDLCLOSINGMARUBOZU`,
  `CDLLONGLINE`, `CDLSHORTLINE`이다. 이들은 Morris 2장의 캔들 선 절에 있고
  `Trend Required` 필드 자체가 없다. 한 봉의 모양만으로 정의되므로 추세를 묻지 않는다.
- **Morris가 패턴으로 다루면서 `Trend Required: No`라고 명시한 2종.** `CDLKICKING`과
  `CDLKICKINGBYLENGTH`다. Morris는 해설에서 "The market direction is not as important with
  this pattern as it is with most other candle patterns"라고 적고, 더 긴 쪽 방향 전언에서도
  "regardless of the price trend"라고 못박는다. **89개 머리말 가운데 `No`는 이 둘뿐이다.**
- **원전이 일본식 캔들 체계 밖이라 추세를 조건으로 두지 않는 2종.** `CDLHIKKAKE`와
  `CDLHIKKAKEMOD`다. Chesler는 이 패턴이 반전형과 지속형 양쪽으로 기능한다고 적을 뿐
  직전 추세를 판정 조건으로 요구하지 않는다.

나머지 45종은 모두 Morris 머리말이 `Trend Required: Yes`이며, 4장의 각 절에서 정의의 첫
항에 추세 조건을 넣었다.

**이 결정의 직접적인 결과가 하나 있다.** 모양이 같고 추세로만 갈리는 쌍이 **서로 다른
패턴으로 남는다.** `CDLHAMMER`와 `CDLHANGINGMAN`이 그렇고, `CDLINVERTEDHAMMER`와
`CDLSHOOTINGSTAR`가 그렇다. 추세를 전략에 넘겼다면 각 쌍을 하나로 합쳐야 했겠지만, 결정 B가
패턴 안에서 판정하기로 했으므로 넷이 그대로 유지된다.

## 5.3 원전 충돌 전수 조사와 채택 결과

**결정 C는 두 층으로 되어 있고 구체적인 층이 먼저 적용된다.**

- **첫째 층(먼저 적용).** Morris 안에서는 `Rules of Recognition`이 규범이고
  `Pattern Flexibility`는 주석이다. **유연성 절의 조건은 그것이 넓히는 것이든 좁히는
  것이든 실행 조건으로 올리지 않는다.**
- **둘째 층.** "조건이 더 많은 쪽"이라는 일반 원칙은 **Nison과 Morris 사이에만** 적용된다.

앞 판은 Ladder Bottom에서 이 우선순위를 거꾸로 적용해 유연성 절의 두 조건을 규범으로
올렸다. 이 판에서 되돌렸고 4장 54번과 아래 표에 반영했다. **규칙 절과 해설(Commentary)
사이의 관계는 다르다.** 해설은 유연성 절이 아니라 같은 규칙을 더 자세히 푼 서술이므로,
규칙 절이 비워 둔 자리를 해설이 채우는 경우에는 해설을 규범으로 채택한다.

61종을 전수 조사한 결과 충돌이 있었던 패턴은 **28종**이다. 충돌은 세 종류로 갈린다.

**종류 하나. Morris의 규칙 절과 그 주변 서술이 어긋난 경우 (10종).** Morris는 패턴마다
`Rules of Recognition`을 두는데, 바로 앞의 해설이나 뒤의 `Pattern Flexibility`가 규칙 절과
다른 말을 하는 자리가 있다.

| 패턴 | 충돌 내용 | 채택 |
|---|---|---|
| `CDL2CROWS` | 해설(L4179~4185)이 둘째 날 종가가 첫 실체 위에 남는다고 추가 | **해설 채택**(조건 추가) |
| `CDL3OUTSIDE` | 해설(L4462~4465)이 셋째 종가의 비교 대상을 줌 | **해설 채택**(조건 구체화) |
| `CDL3LINESTRIKE` | 해설(L7344~7357)이 연속 고저와 넷째 날의 긴 반대색을 추가 | **해설 채택**(조건 추가) |
| `CDLXSIDEGAP3METHODS` | 해설(L6818~6824)이 셋째 날의 시가·종가 위치를 구체화 | **해설 채택**(조건 구체화) |
| `CDLMATHOLD` | 해설(L7172~7180)이 셋째·넷째 봉 위치와 다섯째 종가를 구체화 | **해설 채택**(조건 추가) |
| `CDLIDENTICAL3CROWS` | 규칙은 전일 종가와 같음(등호), 해설은 "at or near"로 완화 | **규칙 절 채택**(해설이 넓힘) |
| `CDLADVANCEBLOCK` | 규칙은 긴 위꼬리 하나, 유연성 절은 실체 축소도 언급 | **규칙 절 채택**(유연성이 넓힘) |
| `CDLBREAKAWAY` | 유연성 절(L5065~5070)이 갭 뒤 봉 수를 둘 이상으로 열어 둠 | **규칙 절 채택**(고정 다섯 봉) |
| `CDLLADDERBOTTOM` | 유연성 절(L5250~5254)이 길이 요건을 완화하되 조건 둘을 추가 | **규칙 절 채택.** 유연성 절은 완화와 추가를 가리지 않고 모두 주석 |
| `CDLHAMMER` | 규칙은 "two or three times", 해설(L1126~1129)은 최소 두 배로 확정 | **해설 채택**(수치 확정) |

**종류 둘. Nison에만 있는 조건을 Morris가 적지 않은 경우 (14종).** 결정 C가 "조건이 더
많은 쪽"을 규범으로 정했으므로 모두 채택했다.

| 패턴 | Nison이 더 주는 조건 | 위치 |
|---|---|---|
| `CDLTASUKIGAP` | 두 캔들의 크기가 비슷해야 함, 무효화 기준 | L3773~3774, L3768~3771 |
| `CDLINNECK` | 둘째 양봉도 작아야 함 | L1893~1897 |
| `CDLTHRUSTING` | 둘째 양봉이 In-Neck보다 길어야 함 | L1898~1901 |
| `CDLBELTHOLD` | 강세형 종가가 세션 고가 가까이, 실체가 길수록 유의미 | L2793~2805 |
| `CDLUPSIDEGAP2CROWS` | 갭이 실체 사이의 갭임을 명시, 셋째 날 시가·종가 위치 | L2850~2852, L2856~2858 |
| `CDLMORNINGSTAR` | 셋째 날이 첫 실체 안으로 깊이 마감해야 함 | 5장·용어사전 |
| `CDLEVENINGSTAR` | 같음 | 5장·용어사전 |
| `CDLMORNINGDOJISTAR` | 같음 | 5장 |
| `CDLEVENINGDOJISTAR` | 같음 | 5장 |
| `CDLDRAGONFLYDOJI` | 시가·고가·종가가 모두 세션 고가에 있음 | 8장·용어사전 |
| `CDLGRAVESTONEDOJI` | 시가·종가가 세션 저가에 있음(Morris는 "at or very near") | 8장·용어사전 |
| `CDLINVERTEDHAMMER` | 다음 날 강세 확인을 받아야 함(Morris 머리말은 `No`) | L2428~2432 |
| `CDLCOUNTERATTACK` | 둘째 날 시가가 추세 방향으로 크게 벌어졌다가 전일 종가로 돌아옴 | L3235~3236, L3244~3248 |
| `CDLSTALLEDPATTERN` | 셋째 봉이 **작은 양봉**이고 둘째 날까지가 새 고점을 만듦 | L2980~2988 |

**종류 셋. Nison과 Morris가 같은 자리를 다르게 정한 경우 (4종).** 좁은 쪽을 골랐다.

| 패턴 | 충돌 | 채택 |
|---|---|---|
| `CDLDARKCLOUDCOVER` | Morris는 시가가 앞날 **고가** 위, Nison은 **고가 또는 종가** 위 | **Morris**(고가가 좁음) |
| `CDLGAPSIDESIDEWHITE` | Nison은 시가가 **같음**, Morris는 **대략 같은 가격** | **Nison**(같음이 좁음) |
| `CDLHANGINGMAN` | Morris는 확인 `No`, Nison은 확인을 받아야 한다고 적음 | **Nison**(확인 요구가 좁음) |
| `CDLSHOOTINGSTAR` | Morris 규칙 1은 갭 상승 시가를 요구, Nison 용어사전은 갭을 요구하지 않음 | **Morris**(조건 추가) |

**채택하지 않은 자리도 적어 둔다.** 두 가지다. 첫째, `CDLONNECK`에서 Nison이 둘째 양봉을
"(usually a small one)"이라고 적은 것은 **"usually"라는 경향 표현이라 요건이 아니므로
채택하지 않았다.** 같은 문단에서 In-Neck에는 "it should also be"라고 적어 강도를 달리한
점이 근거다. 둘째, `CDLBELTHOLD`에서 Nison이 시가 쪽 꼬리에 준 허용오차("아주 작은
아래꼬리", "고가에서 몇 틱 안")는 Morris의 무꼬리 요건을 **넓히므로** 채택하지 않았다.
두 자리 모두 주석으로만 남긴다.

## 5.4 61종 표

원전 열의 `M`은 Morris 3판, `N`은 Nison 2판, `C`는 Chesler 2004년 기사이며 줄 번호는 각
추출본 기준이다. 추세와 확인은 Morris가 적어 둔 값이고, 방향에 따라 다르면 강세형과 약세형을
함께 적었다. 갭 열은 **결정 D**에 따라 원문에서 확인한 갭의 종류다.

| # | TA-Lib 함수 | 원전과 줄 번호 | 추세 | 확인 | 갭 종류 | 필요한 척도 | 우리가 정해야 하는 것 |
|---|---|---|---|---|---|---|---|
| 1 | `CDLDOJI` | M 2장 L1662, N 3·8장 L4390 | 없음 | 없음 | 없음 | 도지 | 도지 허용오차 |
| 2 | `CDLLONGLEGGEDDOJI` | M 2장 L1690, N 8장 L4439 | 없음 | 없음 | 없음 | 도지, 그림자 | 도지 허용오차, 긴 꼬리 임계 |
| 3 | `CDLRICKSHAWMAN` | N 8장 L4430·L7042 | 없음 | 없음 | 없음 | 도지, 그림자, 가까움 | 도지 허용오차, 긴 꼬리 임계, "한가운데"의 허용폭 |
| 4 | `CDLDRAGONFLYDOJI` | M 2장 L1731, N 8장 L4432 | 없음 | 없음 | 없음 | 도지, 그림자 | 도지 허용오차, 긴 아래꼬리 임계 |
| 5 | `CDLGRAVESTONEDOJI` | M 2장 L1712, N 8장 L4431 | 없음 | 없음 | 없음 | 도지, 그림자 | 도지 허용오차, 긴 위꼬리 임계 (Nison의 저가 등호 채택으로 가까움 척도는 빠짐) |
| 6 | `CDLTAKURI` | M 3장 L1126~1129, N L1250 | 없음 | 없음 | 없음 | 도지, 그림자 | 도지 허용오차, 실체가 0일 때의 처리 |
| 7 | `CDLHAMMER` | M 3장 L1108·L1149, N 4장 L1236 | Yes | Required | 없음 | 짧은실체, 가까움, 그림자 | 짧은실체 임계, "위쪽 끝"의 허용폭, 위꼬리 상한 |
| 8 | `CDLHANGINGMAN` | M 3장 L1119·L1149, N 4장 L1236 | Yes | **Nison 채택: 필요** | 없음 | 짧은실체, 가까움, 그림자 | 7번과 같음 |
| 9 | `CDLINVERTEDHAMMER` | M 3장 L1749·L1796, N 5장 L2364·L2428~2432 | Yes | **Nison 채택: 필요**(다음 날) | 없음(원문이 갭 불요를 명시) | 짧은실체, 가까움, 그림자 | 짧은실체 임계, "아래쪽 부분"의 허용폭, 아래꼬리 상한, 확인의 정의 |
| 10 | `CDLSHOOTINGSTAR` | M 3장 L1771·L1796, N 5장 L2338 | Yes | Required | **단순 시가 갭**(Morris 규칙 1 채택) | 짧은실체, 가까움, 그림자 | 짧은실체 임계, "아래쪽 부분"의 허용폭, 아래꼬리 상한 |
| 11 | `CDLSPINNINGTOP` | M 2장 L1645, N 3장 L1063 | 없음 | 없음 | 없음 | 짧은실체 | 짧은실체 임계, 실체가 0일 때의 처리 |
| 12 | `CDLHIGHWAVE` | N 용어사전 L4438·L5277 | 없음 | 없음 | 없음 | 짧은실체, 그림자 | 짧은실체 임계, "매우 긴" 꼬리 임계, Spinning Top과의 경계 |
| 13 | `CDLMARUBOZU` | M 2장 L1600 | 없음 | 없음 | 없음 | 긴실체, 그림자 | 긴실체 임계, "꼬리 없음"의 등호 처리 |
| 14 | `CDLCLOSINGMARUBOZU` | M 2장 L1618 | 없음 | 없음 | 없음 | 긴실체, 그림자 | 13번과 같음 |
| 15 | `CDLBELTHOLD` | M 3장 L1257·L1296, N 6장 L2793~2805 | Yes | Suggested / Required | 없음 | 긴실체, 그림자, 가까움 | 긴실체 임계, "꼬리 없음"의 등호 처리, 강세형 종가의 "가까이" |
| 16 | `CDLLONGLINE` | M 2장 L1571, 6장 L7690 | 없음 | 없음 | 없음 | 긴실체 | 긴실체 임계 |
| 17 | `CDLSHORTLINE` | M 2장 L1590, 6장 L7700 | 없음 | 없음 | 없음 | 짧은실체 | 짧은실체 임계 |
| 18 | `CDLENGULFING` | M 3장 L1361·L1407, N 4장 L1504 | Yes | Suggested / Required | 없음 | 없음(추세 외) | **없음.** 등호 처리를 원전이 명시함 |
| 19 | `CDLHARAMI` | M 3장 L1502·L1543, N 6장 L2486 | Yes | No / Required | 없음 | 긴실체, 짧은실체 | 긴실체 임계, 짧은실체 임계 |
| 20 | `CDLHARAMICROSS` | M 3장 L1641·L1680, N 6장 L2532 | Yes | No / Required | 없음 | 긴실체, 도지 | 긴실체 임계, 도지 허용오차, **규칙 3의 "range"가 실체 범위인지 고저 범위인지** |
| 21 | `CDLDOJISTAR` | M 3장 L2064·L2101, N 5장 L2225 | Yes | No / Suggested | **실체 갭**(N 용어사전이 명시) | 긴실체, 도지, 그림자 | 긴실체 임계, 도지 허용오차, "지나치게 길지 않은" 꼬리 상한 |
| 22 | `CDLPIERCING` | M 3장 L1892·L1912, N 4장 L1848 | Yes | Suggested | 없음(시가 위치 비교) | 긴실체 | 긴실체 임계 |
| 23 | `CDLDARKCLOUDCOVER` | M 3장 L1982·L2005, N 4장 L1689 | Yes | Required | 없음(시가 위치 비교) | 긴실체 | 긴실체 임계 |
| 24 | `CDLCOUNTERATTACK` | M 3장 L2182·L2223, N 6장 L3235~3248 | Yes | Suggested / Required | 없음(시가 위치 비교) | 긴실체, 같음, 가까움 | 긴실체 임계, "같다"의 허용오차, 둘째 시가가 얼마나 벌어져야 "크게"인지 |
| 25 | `CDLSEPARATINGLINES` | M 4장 L5745·L5775, N 7장 L4162 | Yes | No / Required | 없음 | 같음 | "같다"의 허용오차 |
| 26 | `CDLKICKING` | M 3장 L2586·L2618 | **No** | Required | 원문이 구분하지 않음 | 긴실체, 그림자 | 긴실체 임계, "꼬리 없음"의 등호 처리, 갭 기준 |
| 27 | `CDLKICKINGBYLENGTH` | M 3장 L2608~2621 | **No** | Required | 원문이 구분하지 않음 | 긴실체, 그림자 | 26번에 더해 **"더 긴 쪽"이 실체 길이인지 전체 길이인지**, 동률 처리 |
| 28 | `CDLHOMINGPIGEON` | M 3장 L2301·L2315 | Yes | No | 없음 | 긴실체, 짧은실체 | 긴실체 임계, 짧은실체 임계, 포함 관계의 등호 처리 |
| 29 | `CDLMATCHINGLOW` | M 3장 L2413·L2449 | Yes | No | 없음 | 긴실체, 같음 | 긴실체 임계, "같다"의 허용오차(Matching High의 1/1000을 확장할지) |
| 30 | `CDLINNECK` | M 4장 L5999·L6036, N 4장 L1897~1901 | Yes | Required | 없음(시가 위치 비교) | 같음, 짧은실체, 긴실체 | "아주 조금만"의 침투 상한, 짧은실체 임계, 긴실체 임계 |
| 31 | `CDLONNECK` | M 4장 L5852·L5887, N 4장 L1897 | Yes | Required / No | 없음(시가 위치 비교) | 긴실체, 같음 | 긴실체 임계, "같다"의 허용오차 |
| 32 | `CDLTHRUSTING` | M 4장 L6148·L6185, N 4장 L1901~1904 | Yes | Suggested / No | 없음 | 긴실체, 짧은실체, 가까움 | "considerably lower"의 최소 폭, In-Neck과 가르는 둘째 봉 경계, 긴실체 임계 |
| 33 | `CDLSTICKSANDWICH` | M 3장 L4704·L4739 | Yes | No / Suggested | 없음 | 같음 | "같다"의 허용오차 |
| 34 | `CDLMORNINGSTAR` | M 3장 L2849·L2895, N 5장 L2033 | Yes | Required | **실체 갭**(M 규칙 2가 명시) | 긴실체 | 긴실체 임계, **침투 깊이**(Nison 조건을 필수로 채택) |
| 35 | `CDLEVENINGSTAR` | M 3장 L2860·L2895, N 5장 L2034 | Yes | Required | **실체 갭** | 긴실체 | 34번과 같음 |
| 36 | `CDLMORNINGDOJISTAR` | M 3장 L2986·L3033, N 5장 L2037 | Yes | Suggested | **실체 갭** | 긴실체, 도지, 그림자 | 긴실체 임계, 도지 허용오차, 꼬리 상한, 침투 깊이 |
| 37 | `CDLEVENINGDOJISTAR` | M 3장 L2997·L3033, N 5장 L2096 | Yes | Required | **실체 갭** | 긴실체, 도지, 그림자 | 36번과 같음 |
| 38 | `CDLABANDONEDBABY` | M 3장 L3104·L3140, N 용어사전 L6849 | Yes | Suggested / Required | **꼬리 포함 갭**(양 원전이 명시) | 도지 | 도지 허용오차 |
| 39 | `CDLTRISTAR` | M 3장 L3214·L3230, N 8장 L4674 | Yes | Suggested / Required | 원문이 구분하지 않음 | 도지 | 도지 허용오차, 갭 기준 |
| 40 | `CDL2CROWS` | M 3장 L4166·L4179~4187, N 6장 L2862 | Yes | Required | **실체 갭**(해설이 명시) | 긴실체 | 긴실체 임계, 포함 관계의 등호 처리 |
| 41 | `CDLUPSIDEGAP2CROWS` | M 3장 L3314·L3336, N 6장 L2850~2858 | Yes | Required | **실체 갭**(N이 명시) | 긴실체 | 긴실체 임계 |
| 42 | `CDL3WHITESOLDIERS` | M 3장 L3659·L3676, N 6장 L2958 | Yes | No | 없음 | 긴실체, 가까움 | 긴실체 임계, "고가에 또는 가까이"의 허용폭 |
| 43 | `CDL3BLACKCROWS` | M 3장 L3728·L3749, N 6장 L2894 | Yes | Required | 없음 | 긴실체, 가까움 | 긴실체 임계, "저가에 또는 가까이"의 허용폭 |
| 44 | `CDLIDENTICAL3CROWS` | M 3장 L3800·L3811 | Yes | **No**(본문 명시) | 없음 | 긴실체, 같음 | 긴실체 임계, "같다"의 허용오차 (규칙 절의 등호 채택, 해설의 근접은 주석) |
| 45 | `CDLADVANCEBLOCK` | M 3장 L3853·L3879, N 용어사전 L6854 | Yes | Required | 없음 | 그림자 | "긴 위꼬리"의 임계 |
| 46 | `CDLSTALLEDPATTERN` | M 3장 L4012·L4052, N 6장 L2980~2988 | Yes | No / Suggested | **선택적 실체 갭**(양 원전이 선택으로 둠) | 긴실체, 짧은실체, 가까움 | 긴실체 임계, 짧은실체 임계, "가까이"의 허용폭 |
| 47 | `CDL3STARSINSOUTH` | M 3장 L4542·L4562 | Yes | Suggested | 없음 | 긴실체, 짧은실체, 그림자 | 긴실체·짧은실체 임계, 긴 아래꼬리 임계, "더 작다"의 기준, **규칙 3의 "범위" 해석** |
| 48 | `CDL3INSIDE` | M 3장 L4340·L4363 (**Morris 창안**, L4359~4362) | Yes | No / Required | 없음 | 긴실체, 짧은실체 | 긴실체 임계, 짧은실체 임계 |
| 49 | `CDL3OUTSIDE` | M 3장 L4435·L4462~4471 (**Morris 창안**, L4467~4470) | Yes | No / Required | 없음 | 없음(추세 외) | **없음** |
| 50 | `CDLUNIQUE3RIVER` | M 3장 L3491·L3512 | Yes | Required | 없음 | 긴실체, 짧은실체 | 긴실체·짧은실체 임계, **셋째 날이 "가운데 날보다 아래"인 비교 대상** |
| 51 | `CDLCONCEALBABYSWALL` | M 3장 L5133·L5154 | Yes | No | 원문이 구분하지 않음 | 긴실체, 그림자 | 긴실체 임계, "꼬리 없음"의 등호 처리, "긴 위꼬리" 임계, 갭 기준 |
| 52 | `CDL3LINESTRIKE` | M 4장 L7307·L7344~7360 | Yes | No / Suggested | 없음 | 긴실체 | 긴실체 임계 |
| 53 | `CDLBREAKAWAY` | M 3장 L4990·L5044, 유연성 L5065~5070 | Yes | Suggested | **실체 갭**(M 규칙 2가 명시) | 긴실체 | 긴실체 임계 |
| 54 | `CDLLADDERBOTTOM` | M 3장 L5213·L5230(유연성 L5250~5254는 주석) | Yes | No | 없음(시가 위치 비교) | 긴실체, 그림자 | 긴실체 임계, 위꼬리를 "있다"고 볼 최소 크기 |
| 55 | `CDLMATHOLD` | M 4장 L7146·L7172~7194 | Yes | No / Suggested | **실체 갭**(M 약세형 규칙 2가 명시) | 긴실체, 짧은실체 | 긴실체 임계, 짧은실체 임계 |
| 56 | `CDLRISEFALL3METHODS` | M 4장 L7003·L7055, N 7장 L3984 | Yes | No / Suggested | 없음 | 긴실체, 짧은실체 | 긴실체·짧은실체 임계, **"a group"의 봉 수**, "강한 날"의 기준 |
| 57 | `CDLGAPSIDESIDEWHITE` | M 4장 L6452·L6505, N 7장 L3883·L7104 | Yes | Suggested / Required | 원문이 구분하지 않음 | 가까움, 같음 | "같다"의 허용오차(Nison의 같은 시가 채택), "비슷한 크기"의 허용폭, 갭 기준 |
| 58 | `CDLTASUKIGAP` | M 4장 L6322·L6364, N 7장 L3768~3774·L7130 | Yes | Suggested / Required | **실체 갭** | 가까움 | "비슷한 크기"의 허용폭 |
| 59 | `CDLXSIDEGAP3METHODS` | M 4장 L6794·L6818~6825 | Yes | No / Required | **실체 갭** | 긴실체 | 긴실체 임계 |
| 60 | `CDLHIKKAKE` | C L15~27·L38~47 | **없음** | 필수(3봉 기한) | 없음 | **없음** | **없음** |
| 61 | `CDLHIKKAKEMOD` | C L204~213 | **없음** | 필수(3봉 기한) | 없음 | **없음** | **없음** |

## 5.5 우리가 정해야 하는 값의 집계

**패턴별로 표의 오른쪽 열에 적힌 자리를 세면 모두 116개다.** 그러나 그 대부분은 같은 공통
값을 여러 패턴이 함께 쓰는 것이므로, 실제로 정해야 하는 **서로 다른 값은 23개**다. 표준
문서를 쓸 때 이 23개를 정하면 61종이 모두 확정된다.

**공통 척도에서 오는 값 일곱.** 이 일곱만 정하면 표 오른쪽 열의 대부분이 한꺼번에 풀린다.
쓰는 패턴 수는 5.4절 표의 "필요한 척도" 열을 세어 얻었다.

1. **긴실체 임계.** 분모와 값을 함께 정한다. **37종**이 쓴다.
2. **짧은실체 임계.** 분모와 값. **17종**이 쓴다.
3. **도지 허용오차.** **12종**이 쓴다.
4. **긴 그림자 임계.** 분모와 값.
5. **없거나 매우 짧은 그림자 임계.**
6. **"같다"의 허용오차.** **8종**이 쓴다.
7. **"가깝다·비슷하다"의 허용오차.** **13종**이 쓴다.

넷째와 다섯째는 표에서 **그림자 척도 하나로 묶여 22종**이 쓴다. 한 패턴이 긴 그림자와 짧은
그림자를 함께 요구하는 경우가 많아(예: Hammer는 긴 아래꼬리와 짧은 위꼬리를 함께 요구한다)
둘을 갈라 세면 중복이 생기므로, 표에서는 묶어 두고 값만 둘로 나누어 정한다.

**공통 규약에서 오는 값 셋.** 특정 패턴이 아니라 판정 전반에 걸린다.

8. **부등식의 엄격성과 등호 처리.** 원전이 명시하지 않은 경계 전부에 걸린다.
9. **퇴화 봉 규칙.** 실체가 0이거나 고저 범위가 0인 봉의 처리다.
10. **갭의 기준을 원문이 구분하지 않은 패턴에서 무엇으로 볼지.** `CDLKICKING`,
    `CDLKICKINGBYLENGTH`, `CDLTRISTAR`, `CDLCONCEALBABYSWALL`, `CDLGAPSIDESIDEWHITE`
    다섯 종이 해당한다. **결정 D는 원전이 정한 갭을 바꾸지 않는다고 했을 뿐, 원전이 아예
    구분하지 않은 자리까지 정해 주지는 않는다.**

**패턴 고유로 남는 값 열하나.** 공통 척도로 풀리지 않는다.

11. 별 계열 넷(`CDLMORNINGSTAR`, `CDLEVENINGSTAR`, `CDLMORNINGDOJISTAR`,
    `CDLEVENINGDOJISTAR`)의 **침투 깊이.**
12. `CDLINNECK`의 **"아주 조금만"의 침투 상한.**
13. `CDLTHRUSTING`의 **"considerably lower"의 최소 폭.**
14. `CDLTHRUSTING`과 `CDLINNECK`을 가르는 **둘째 봉 크기의 경계.**
15. `CDLRISEFALL3METHODS`의 **"a group"이 몇 봉인지.**
16. `CDLRISEFALL3METHODS` 마지막 날의 **"강한 날" 기준.**
17. `CDLKICKINGBYLENGTH`의 **"더 긴 쪽"이 실체 길이인지 전체 길이인지**와 **동률 처리.**
18. `CDLHARAMICROSS` 규칙 3의 **"range"가 실체 범위인지 고저 범위인지.**
19. `CDLUNIQUE3RIVER` 셋째 날이 **"가운데 날보다 아래"일 때의 비교 대상.**
20. `CDL3STARSINSOUTH` 규칙 3의 **"범위"가 실체 범위인지 고저 범위인지.**
21. `CDLHIGHWAVE`와 `CDLSPINNINGTOP`의 **경계.**
22. **확인의 내용.** Morris가 `Required`나 `Suggested`로 표시한 패턴에서 무엇을 확인으로
    볼 것인가. 원전이 내용을 준 것은 Hikkake 둘과 Nison이 다룬 Hanging Man과 Inverted
    Hammer뿐이다. 결정 12가 다룬다.
23. **확인의 기한.** 확인이 며칠 안에 일어나야 하는가. **원전이 기한을 준 것은 Hikkake의
    세 봉뿐이고 나머지는 아무것도 주지 않는다.** 결정 12가 다룬다.

**값을 하나도 정할 필요가 없는 패턴이 넷이다.** `CDLENGULFING`, `CDL3OUTSIDE`,
`CDLHIKKAKE`, `CDLHIKKAKEMOD`다. 앞의 둘은 원전이 등호 처리까지 명시했고 추세 판정만
있으면 되며, 뒤의 둘은 고가와 저가의 대소 비교와 등호로만 판정이 끝난다.

**갭의 종류를 표에서 세면 이렇다.** 갭을 쓰지 않는 패턴이 42종, **실체 사이의 갭**이 12종,
**꼬리를 포함한 갭**이 1종(`CDLABANDONEDBABY`), **단순 시가 갭**이 1종
(`CDLSHOOTINGSTAR`), **원문이 구분하지 않는 것**이 5종이다. 결정 D에 따라 앞의 넷은 원전
그대로 두고, 마지막 다섯만 결정 9로 올린다.

**결정 A에 따라, 위 21개 값은 표준 문서를 쓸 때 우리가 정한다.** 그때 각 값에 대해
**원저자의 정의가 아니라 우리가 고른 규약임을 명시하고 왜 그 값인지 근거를 남긴다.**
값을 비워 두고 패턴을 보류하지 않으며, TA-Lib의 설정표를 그대로 승계하지도 않는다.

# 6. TA-Lib이 스스로 정한 것

이 장은 **대조군이 무엇을 하는지**를 적는다. 여기 적힌 것은 어느 것도 원저자의 정의가
아니며, 우리 표준의 출처로 삼을 수 없다. 앞 장들과 이 장을 섞어 읽지 않도록, 이 장에는
원전 이야기를 넣지 않았다.

**여기 적은 내용은 TA-Lib의 판정 소스 코드를 읽어서 얻은 것이 아니다.** 설치된 라이브러리를
바깥에서 관찰해 알아낸 것이다. 방법을 함께 적었으므로 재현할 수 있다.

## 6.1 TA-Lib은 "길다·짧다·가깝다"를 재는 자기만의 설정표를 가지고 있다

TA-Lib에는 캔들 판정 전용 설정이 **열한 개** 있다. 이름은 `BodyLong`, `BodyVeryLong`,
`BodyShort`, `BodyDoji`, `ShadowLong`, `ShadowVeryLong`, `ShadowShort`, `ShadowVeryShort`,
`Near`, `Far`, `Equal`이다. 설정 하나는 세 값을 갖는다. 무엇을 분모로 삼을지를 정하는
범위 종류(실체, 고저 범위, 꼬리 합), 평균을 낼 기간, 그리고 곱할 계수다.

**이 설정들의 기본값을 관찰로 복원했다.** 방법은 둘이다. 평균 기간은 lookback이 평균
기간에만 의존한다는 성질을 이용했다. 설정 하나만 남기고 나머지 평균 기간을 0으로 만든 뒤
lookback의 변화를 읽으면 그 설정의 기본 평균 기간이 그대로 나온다. 계수와 범위 종류는
전수 대조로 찾았다. 큰 무작위 자료 세 벌에 대해 기본 설정으로 얻은 출력을 기준으로 두고,
범위 종류 세 가지와 계수 0부터 5까지를 0.005 간격으로 훑으면서 **출력이 한 값도 다르지
않게 재현되는 조합**을 찾았다. 모든 설정에서 범위 종류는 하나만 일치했고, 계수가 일치하는
구간은 격자 한 칸 너비였다.

| 설정 | 범위 종류 | 평균 기간 | 계수 | 쓰는 함수 수 |
|---|---|---|---|---|
| `BodyLong` | 실체 | 10 | 1.0 | 32 |
| `BodyVeryLong` | (관찰 불가) | (관찰 불가) | (관찰 불가) | **0** |
| `BodyShort` | 실체 | 10 | 1.0 | 22 |
| `BodyDoji` | 고저 범위 | 10 | 0.1 | 12 |
| `ShadowLong` | 실체 | **0** | 1.0 | 8 |
| `ShadowVeryLong` | 실체 | **0** | 2.0 | 2 |
| `ShadowShort` | 꼬리 합 | 10 | 1.0 | 3 |
| `ShadowVeryShort` | 고저 범위 | 10 | 0.1 | 20 |
| `Near` | 고저 범위 | 5 | 0.2 | 9 |
| `Far` | 고저 범위 | 5 | 0.6 | 2 |
| `Equal` | 고저 범위 | 5 | 0.05 | 9 |

읽는 법을 예로 들면 이렇다. `BodyLong`은 "이 봉의 실체가 **직전 10봉 실체 평균의 1.0배**를
넘으면 길다"는 뜻이고, `BodyDoji`는 "이 봉의 실체가 **직전 10봉 고저 범위 평균의 0.1배**
이하이면 도지"라는 뜻이다. `ShadowLong`의 평균 기간이 0인 것은 평균을 쓰지 않는다는
뜻이며, 곧 "긴 꼬리"는 **그 봉 자신의 실체**와 견주어 판정된다. `ShadowVeryLong`의 계수가
2.0이므로 "매우 긴 꼬리"는 자기 실체의 두 배를 넘는 꼬리다.

**표에서 두 가지를 짚어 둔다.**

첫째, `BodyVeryLong`은 **어떤 패턴 함수도 쓰지 않는다.** 이 설정의 계수를 극단으로 바꿔도
61개 함수의 출력이 한 값도 달라지지 않았다. 평균 기간을 복원할 수 없었던 것도 이 때문이다.
설정은 존재하나 패턴 판정에서는 죽은 값이다.

둘째, **평균은 현재 봉을 넣지 않고 직전 봉들만으로 낸다.** 이를 따로 확인했다. 고저
범위가 1.0으로 일정한 봉 서른 개를 앞에 두고 시험 봉을 붙였을 때, `CDLDOJI`는 실체가
0.10이면 성립하고 0.11이면 성립하지 않았다. 그리고 시험 봉 자신의 고저 범위를 1.0에서
5.0으로 키워도 결과가 바뀌지 않았다. 만약 평균이 현재 봉을 포함했다면 결과가 뒤집혔을
것이다. 이 실험은 `BodyDoji`가 고저 범위 기준에 계수 0.1이라는 위 표의 값을 독립적으로
다시 확인해 주기도 한다.

**여기서 반드시 갈라 읽어야 할 것.** 이 표의 숫자들은 3장에서 정리한 여섯 척도에 대한
**TA-Lib의 답**이다. Morris가 제시한 형식과 겹치는 것도 있으나(예: 최근 N봉 실체 평균과
견주는 방식) **값이 같지는 않다.** 예를 들어 Morris는 최근 실체 평균 대비 임계를 130퍼센트
같은 값으로 예시했는데 TA-Lib은 1.0배를 쓴다. 도지도 Morris는 그날 고저 범위의 1~3퍼센트를
권했는데 TA-Lib은 직전 10봉 고저 범위 평균의 10퍼센트를 쓴다. **분모도 다르고 값도 다르다.**
나중에 우리가 TA-Lib과 같은 숫자를 고르는 일이 있더라도 그것은 우리가 이유를 대고 고른
규약이지 원저자의 정의가 아니다.

## 6.2 직전 추세를 TA-Lib은 요구하지 않는다

지시서가 특별히 확인하라고 한 항목이다. 결론부터 적으면 **TA-Lib은 원전이 요구하는
직전 추세를 사실상 요구하지 않는다.** 두 가지로 확인했다.

**첫째, 추세를 강하게 넣어도 발생 빈도가 거의 변하지 않는다.** 상승 방향으로 계속 끌리는
자료, 방향이 없는 자료, 하락 방향으로 계속 끌리는 자료를 각각 20만 봉씩 만들어 같은
함수를 돌렸다. `CDLENGULFING`의 발생 수는 상승에서 8324, 무방향에서 8410, 하락에서
8437로 사실상 같았다. 원전대로라면 강세 장악형은 하락 뒤에만, 약세 장악형은 상승 뒤에만
나와야 하므로 이런 결과가 나올 수 없다. `CDLMORNINGSTAR`는 357/306/259, `CDLEVENINGSTAR`는
251/281/345로 방향에 따라 기울기는 하지만 그 크기가 추세 조건이라 부를 만한 수준이 아니다.

**둘째, TA-Lib은 추세 대신 바로 앞 봉과의 위치 관계라는 국소 대용물을 쓴다.** 같은 모양의
해머 캔들을 놓고 **바로 앞 봉만** 바꿔 가며 시험했다. 앞 봉이 강한 음봉이면 `CDLHAMMER`가
+100을 내고 `CDLHANGINGMAN`은 0을 냈다. 앞 봉이 강한 양봉이면 반대로 `CDLHANGINGMAN`이
-100을 내고 `CDLHAMMER`는 0을 냈다. 나아가 해머 실체가 앞 봉 종가보다 아래에 놓이면
해머로, 위에 놓이면 행잉맨으로 갈렸다. 곧 판정 근거는 추세가 아니라 **직전 한 봉에 대한
가격 위치**다.

**이 대용물은 느슨해서 서로 배타적이지도 않다.** 30만 봉짜리 자료에서 `CDLHAMMER`는
8074번, `CDLHANGINGMAN`은 6497번 신호를 냈는데, 그 가운데 **131번은 같은 봉에서 둘 다**
신호를 냈다. 원전에서 이 둘은 하락 뒤인가 상승 뒤인가로만 갈리는, 정의상 동시에 성립할 수
없는 한 쌍이다. (덧붙여 `CDLINVERTEDHAMMER`와 `CDLSHOOTINGSTAR` 쌍에서는 동시 성립이
한 번도 없었다. 대용물이 함수마다 다르게 짜여 있다는 뜻이다.)

## 6.3 반환 값의 부호와 크기가 뜻하는 것

1.4절에서 관찰한 값을 TA-Lib의 규약으로 다시 정리하면 이렇다. 부호는 방향을 뜻해서 양이
강세, 음이 약세다. 크기는 세 단계다. 100이 통상 성립, 80이 경계에 걸친 약한 성립(장악형과
하라미 계열에서 한쪽 끝이 정확히 같은 경우), 200이 확인까지 끝난 성립(Hikkake 두 종)이다.
0은 성립하지 않음이다.

**부호가 방향을 뜻하지 않는 경우가 있다는 점이 함정이다.** 도지, 팽이형, 하이웨이브,
마루보즈, 긴 캔들, 짧은 캔들처럼 방향성이 없는 단일 캔들 패턴에서는 부호가 그 캔들의
색을 나타낼 뿐이다. 그러면서도 `CDLDOJI`는 색과 무관하게 언제나 +100만 낸다. 곧 **같은
±100 표기가 함수에 따라 방향을 뜻하기도 하고 색을 뜻하기도 하고 아무것도 뜻하지 않기도
한다.** 이 표기를 그대로 물려받으면 이 모호함까지 함께 물려받는다.

## 6.4 값이 안정되기까지 몇 봉이 필요한지 TA-Lib이 밝히는 방식

TA-Lib은 함수마다 lookback을 보고하며 그 값은 1.5절 표와 같다. 다만 실무에서 걸리는
문제가 둘 있다.

첫째, **파이썬 래퍼는 lookback 구간을 0으로 채운다.** 정수 출력이라 결측을 표시할 값이
없기 때문이다. 그래서 출력만 보고는 "패턴 없음"과 "아직 계산 안 됨"을 구별할 수 없다.
구별하려면 lookback 값을 따로 알고 앞부분을 잘라내야 한다.

둘째, **lookback은 패턴 길이가 아니라 대부분 평균 창 길이다.** 1.5절에서 보였듯이
`CDLDOJI`의 10봉은 전부 평균 창이다. 그러므로 lookback을 "이 패턴을 보려면 봉이 이만큼
필요하다"로 읽으면 맞지만, "이 패턴은 이만큼의 봉으로 이루어져 있다"로 읽으면 틀린다.

## 6.5 TA-Lib이 원전에 없이 더하거나 뺀 것

지금까지의 관찰을 종합해 **원전과 어긋나는 자리**를 모으면 다음과 같다.

- **추세 요건을 뺐다.** 6.2절 그대로다. 원전 정의의 첫 기준을 빼고 직전 한 봉과의 위치
  비교로 갈음했다.
- **원전에 없는 임계값을 넣었다.** 6.1절의 열한 개 설정 전체가 여기 해당한다. 특히
  `Near`, `Far`, `Equal`처럼 "가깝다·멀다·같다"를 직전 5봉 고저 범위 평균의 0.2배, 0.6배,
  0.05배로 못박은 것은 어느 원전에서도 근거를 찾지 못했다.
- **원전이 요구하지 않은 조건을 더했다.** 앞 판은 Tasuki Gap을 그 예로 들었으나 **그것은
  사실이 아니었고 철회한다.** Nison은 `nison_jcct.txt` L3773~3774와 L7130~7131에서
  "The two candles of the tasuki should be about the same size."라고 **직접 적는다.** 곧
  비슷한 크기 요건은 원전에 있으며 TA-Lib이 더한 것이 아니다. 이 자리에 남는 사례는
  `Far` 설정처럼 어느 원전에서도 대응 서술을 찾지 못한 임계값들이다.
- **원전의 단정을 그대로 옮긴 자리도 있다.** Modified Hikkake가 그 예다. Chesler는
  "The bar **must** close at the top of its range"라고 **단정하지 허용오차를 열어 두지
  않는다.** TA-Lib이 이 함수에서 임계값 설정을 하나도 쓰지 않는 것은 원전을 문자 그대로
  옮긴 결과이므로, 이 자리는 TA-Lib이 스스로 정한 것이 아니다. **앞 판이 여기에 근접
  허용오차가 필요하다고 적은 것은 원문에 없는 완화였고 철회한다.**
- **원전에 없는 패턴을 만들었다.** `CDLKICKINGBYLENGTH`가 그렇다. 5.4절에 적었다.
- **근거를 찾지 못한 기본값을 두었다.** 별 계열의 `penetration` 0.3이다. Dark Cloud
  Cover의 0.5는 Nison이 언급한 50퍼센트와 맞아떨어지지만, Morning Star와 Evening Star에
  대해 30퍼센트라는 수치를 준 원전 서술을 찾지 못했다. Mat Hold의 0.5도 마찬가지다.
- **판정에 쓰지 않는 설정을 남겨 두었다.** `BodyVeryLong`이다. 라이브러리를 읽고 설정을
  옮겨 적으면 쓰이지 않는 값까지 따라온다.

---

# 7. 아직 열려 있는 결정

## 7.0 결정 A와 B와 C와 D로 닫힌 것

사용자가 2026년 8월 1일에 네 가지를 확정했고 이 판이 그것을 반영했다. 그 결과 앞 판의
열여섯 결정 가운데 셋이 닫혔다.

- **앞 판 결정 2(직전 추세를 요구할 것인가, 어떻게 잴 것인가)는 닫혔다.** 결정 B가
  패턴이 직접 판정하고 Morris의 10기간 지수이동평균을 쓴다고 확정했다. 5.2절에 적용
  결과를 적었다.
- **앞 판 결정 8(갭에 기대는 패턴을 24시간 시장에서 어떻게 할 것인가)은 닫혔다.**
  결정 D가 원전 정의를 바꾸지 않고 발생 빈도가 낮아지는 것을 받아들인다고 확정했다.
  검토가 지적한 대로 여러 종류의 갭을 하나의 임계로 뭉개는 선택지는 실제로 여러 선택을
  하나인 척 숨기는 것이었으므로, 그 선택지도 함께 사라졌다.
- **앞 판 결정 16(갈래 체계의 빈칸을 어떻게 메울 것인가)은 닫혔다.** 5.1절에 적었듯
  세 갈래 분류를 버리고 척도와 미정 항목이라는 두 열로 대체했다.

**결정 C는 새 결정을 만들지 않고 스물여덟 자리의 충돌을 닫았다.** 5.3절이 그 목록이다.
따라서 검토가 요구한 "Morris와 Nison이 서로 다른 조건을 줄 때 패턴별 출처 우선순위"는
별도 결정으로 올리지 않는다. 결정 C가 일반 규칙으로 이미 답했기 때문이다.

**결정 A는 값을 정하는 일을 표준 문서로 넘겼다.** 그러므로 아래 결정 가운데 값에 관한
것들은 "정할 것인가"가 아니라 "무엇으로 정할 것인가"를 묻는다.

아래는 **실제로 아직 열려 있는 열여섯 건**이다. 3차 검토가 확인의 내용과 기한을 정하는
항목이 빠졌다고 지적해 결정 12로 새로 넣었고, 그만큼 번호가 하나씩 밀렸다.

## 결정 1. 원전으로 삼을 판을 확정한다

내가 읽은 것은 Nison **2판(2001)**과 Morris **3판(2006)**이고, 지시서가 지목한 것은
1991년과 1992년의 초판이다. *Beyond Candlesticks*(1994)는 구하지 못했다.

- **선택지 가.** 내가 읽은 2판과 3판을 원전으로 확정한다. 곧바로 표준 작성으로 갈 수 있고
  이 문서의 인용이 그대로 근거가 된다. 초판과 정의가 다른 부분이 있다면 모른 채 진행한다.
- **선택지 나.** 초판을 구해 대조한 뒤 진행한다. 정확하지만 입수에 시간이 든다.
- **선택지 다.** 2판과 3판으로 진행하되, 5.3절이 충돌로 기록한 스물여덟 종만 나중에 초판과
  대조한다. 위험이 집중된 곳만 확인하는 절충이다.

## 결정 2. 부등식의 엄격성과 등호 처리를 정한다

원전이 이 문제를 명시한 자리는 드물다. **Morris의 Engulfing 규칙 2와 Harami 규칙 3만
분명하다.** 두 실체의 위쪽 끝이나 아래쪽 끝 가운데 한쪽이 같은 것은 허용하고 양쪽이 모두
같은 것만 배제한다. 그 밖의 자리는 밝히지 않았다.

- **선택지 가.** 원전이 밝힌 자리만 그대로 따르고 나머지는 **엄격 부등식**으로 통일한다.
  규칙이 단순하다. Marubozu와 Separating Lines처럼 정확한 일치를 요구하는 패턴이 실질적으로
  성립하지 않게 된다.
- **선택지 나.** 나머지를 모두 **등호 허용**으로 통일한다. 신호가 실제로 나온다. "감싼다"
  같은 관계가 느슨해져 원전의 뜻에서 멀어질 수 있다.
- **선택지 다.** 자리의 성격에 따라 나눈다. 포함과 감쌈에는 Engulfing 규칙을 확장 적용하고,
  "같다"에는 결정 7의 허용오차를 쓰며, "꼬리 없음"에는 결정 6의 임계를 쓴다. 가장 정확하지만
  정할 것이 많다.

## 결정 3. 퇴화 봉을 어떻게 판정할지 정한다

실체가 0인 봉과 고저 범위가 0인 봉이 있다. **어느 원전도 이 경우를 다루지 않는다.**
그림자를 실체의 배수로 재는 규칙은 실체가 0이면 정의되지 않고, 고저 범위를 분모로 쓰는
비율은 고저 범위가 0이면 정의되지 않는다. Spinning Top의 "꼬리가 실체보다 길다"는 실체가
0이면 언제나 참이 된다.

- **선택지 가.** 퇴화 봉에서는 해당 패턴을 성립하지 않음으로 처리한다. 안전하고 규칙이
  하나다. 실체가 0인 봉은 도지이므로 도지를 요구하는 패턴까지 막으면 원전과 어긋난다.
- **선택지 나.** 분모가 0이 되는 비교만 거짓으로 처리하고 나머지 조건은 그대로 본다.
  도지 계열이 정상 동작한다. 예외 처리가 흩어져 검증이 어려워진다.
- **선택지 다.** 분모가 0일 때 쓸 대체 분모를 정한다. 판정이 끊기지 않는다. 원전에 없는
  규약이 하나 더 들어오고 그 선택이 결과를 바꾼다.

## 결정 4. 긴실체와 짧은실체를 재는 방법과 임계를 정한다

**37종이 긴실체 척도를, 17종이 짧은실체 척도를 쓴다.** 가장 넓게 영향을 미치는 값이다.
숫자는 5.4절 표의 "필요한 척도" 열을 기계적으로 세어 얻었으며 5.5절의 집계와 같다.
Morris는 6장에서 세 방법을 나란히 주고 하나로 정하지 않았다. 짧은 날은 같은 세 방법에
최소 퍼센트 대신 최대 퍼센트를 쓴다고 적는다.

- **선택지 가.** 가격 수준 대비 퍼센트. 과거 자료가 필요 없어 워밍업이 0이 된다. 종목마다
  값을 달리 잡아야 하고 변동성 국면 변화에 대응하지 못한다.
- **선택지 나.** 그 봉의 고저 범위 대비 퍼센트. 워밍업이 없고 종목에 무관하다. Morris가
  단독 사용은 가장 좋지 않다고 적은 방법이며, 꼬리가 긴 봉이 자동으로 짧은 실체가 된다.
- **선택지 다.** 최근 N봉 실체 평균 대비 배수. Morris가 캔들의 단기 지향과 가장 잘 맞는다고
  적었다. 워밍업이 N봉 생기고 N과 배수를 둘 다 정해야 한다.
- **선택지 라.** 둘 이상을 함께 요구한다. Morris가 허용한 방식이다. 오탐이 줄지만 신호가
  크게 드물어진다.

Morris가 여러 패턴의 유연성 절에서 되풀이한 **"긴 실체는 고저 범위의 50퍼센트 초과"**와
**"긴 날은 고저 범위가 중간값의 1.5퍼센트 초과이거나 직전 5일 고저 범위 평균의 0.75배
초과"**는 선택지 나와 다를 참고 값이다.

## 결정 5. 도지 허용오차를 정한다

**12종이 쓴다.** Nison은 숫자를 주지 않았고, Morris는 두 가지를 말했다. 6장은 그날 고저
범위 대비 최대 퍼센트라는 형식을 주며 "1에서 3퍼센트 정도가 꽤 잘 듣는다"고 적고, 2장은
"시가와 종가의 차이가 몇 틱 안이면 충분하고도 남는다"고 적는다.

- **선택지 가.** Morris 6장의 1~3퍼센트를 그 봉의 고저 범위에 적용한다. 원전에 근거가 있고
  워밍업이 없다.
- **선택지 나.** Morris 2장의 호가 단위 기준을 쓴다. 암호화폐처럼 호가 단위가 뚜렷한 시장에
  잘 맞는다. 종목마다 호가 단위를 알아야 하고 심볼별로 결과가 달라진다.
- **선택지 다.** 최근 N봉 고저 범위 평균 대비 퍼센트를 쓴다. 변동성 국면에 자동으로
  맞춰진다. **원전 근거가 없으므로 결정 A에 따라 우리가 고른 규약임을 명시해야 한다.**

## 결정 6. 긴 그림자와 짧은 그림자의 분모와 임계를 정한다

**긴 그림자를 9종이, 없거나 매우 짧은 그림자를 8종이 쓴다.** 원전 상황이 비대칭이다.
아래꼬리에는 숫자가 있고 위꼬리의 "없음"에는 없다. Nison과 Morris 모두 Hammer의 아래꼬리를
실체의 **최소 두 배**로 적고, Morris는 Takuri를 **최소 세 배**로 적어 둘을 구별한다.
Morris는 Inverted Hammer의 위꼬리를 실체의 **두 배 이하**로, Shooting Star의 위꼬리를
**세 배 이상**으로 적는다. 반면 "없거나 매우 짧은 그림자"에는 어느 원전도 숫자를 주지
않는다. Morris 6장은 형식만 준다. 우산형의 실체를 아래꼬리 길이의 퍼센트로 다루고, 위꼬리는
그날 고저 범위의 퍼센트로 다루며 값 10을 예로 든다.

- **선택지 가.** Morris의 비대칭을 그대로 따른다. 긴 그림자는 **실체를 분모로** 배수로 재고,
  짧은 그림자는 **그날 고저 범위를 분모로** 퍼센트로 잰다. 원전에 가장 충실하다. 분모가
  둘이라 설명이 복잡하고, 실체가 0인 봉에서 앞쪽 분모가 무너진다.
- **선택지 나.** 둘 다 그날 고저 범위를 분모로 삼는다. 분모가 하나로 통일되어 퇴화 봉 문제가
  줄어든다. 원전이 준 두 배와 세 배를 그대로 쓸 수 없어 환산해야 하며 그 환산값은 우리가
  정하는 것이 된다.
- **선택지 다.** 둘 다 실체를 분모로 삼는다. 원전의 배수를 그대로 쓸 수 있다. 실체가 0이거나
  아주 작은 봉에서 배수가 발산하므로 결정 3에 크게 기댄다.

## 결정 7. "같다"와 "가깝다"의 허용오차를 정한다

**"같다"를 8종이, "가깝다·비슷하다"를 13종이 쓴다.** 숫자는 5.4절 표를 기계적으로 세어
얻었으며 5.5절의 집계와 같다. Morris 안에 넓은 기준과 좁은 기준이
함께 있다. 6장은 "도지 날을 정할 때 쓴 것과 같은 개념을 여기에도 쓸 수 있다"고 적고,
Matching High 항목에서는 **첫날 종가의 1/1000** 안이면 같다고 본다.

- **선택지 가.** 좁은 기준(1/1000 수준)을 모든 "같다"에 쓴다. 원전의 문자 그대로에 가깝다.
  Separating Lines, Matching Low, Stick Sandwich, Identical Three Crows가 거의 나오지 않는다.
- **선택지 나.** 넓은 기준(고저 범위 대비 퍼센트)을 쓴다. 신호가 실제로 나온다. "같다"의
  뜻이 원전보다 느슨해진다.
- **선택지 다.** "같다"에는 좁은 기준을, "가깝다·비슷하다"에는 넓은 기준을 쓴다. 두 표현이
  원전에서 실제로 다른 낱말이라는 점을 반영한다. 정할 값이 둘로 늘어난다.

## 결정 8. 별 계열의 침투 깊이를 정한다 (선택지가 사실상 하나다)

**이 항목은 선택지가 여럿인 척하지 않고 하나라고 적는다.** 결정 C가 Nison의 침투 요건을
채택하도록 이미 정했으므로 "넣을 것인가"는 닫혔고, 남은 것은 값 하나다. 그런데 값을 고를
근거가 원전 안에 하나뿐이다.

Nison은 Piercing과 Dark Cloud Cover에 **50퍼센트**라는 숫자를 준다. 별 계열에는 "well
into"라고만 적고 숫자를 주지 않는다. 따라서 원전 안에서 끌어올 수 있는 값은 이웃 패턴의
50퍼센트뿐이다. TA-Lib의 0.3은 결정 A가 승계를 금지했고 출처도 찾지 못했다.

- **유일한 선택지.** 별 계열 넷의 침투 깊이를 **첫 실체의 50퍼센트 초과**로 정하고, 그것이
  Nison이 이웃 패턴에 준 값을 유추 적용한 **우리 규약**임을 표준에 명시한다.

다른 값을 고르려면 원전 밖의 근거가 필요한데 그런 근거를 찾지 못했다. 사용자가 다른 값을
원하면 그 근거를 함께 정해 주어야 한다.

## 결정 9. 원문이 갭을 구분하지 않은 다섯 패턴의 갭 기준을 정한다

**결정 D는 원전이 정한 갭을 바꾸지 않는다고 했을 뿐, 원전이 아예 구분하지 않은 자리까지
정해 주지는 않는다.** 5.4절 표에서 갭 열이 "원문이 구분하지 않음"인 패턴은 다섯이다.
`CDLKICKING`, `CDLKICKINGBYLENGTH`, `CDLTRISTAR`, `CDLCONCEALBABYSWALL`,
`CDLGAPSIDESIDEWHITE`다.

- **선택지 가.** 다섯 모두 **실체 사이의 갭**으로 읽는다. 원전이 명시한 나머지 패턴 대부분이
  실체 기준이므로 일관된다. Kicking은 두 봉이 Marubozu여서 실체와 고저 범위가 같으므로
  실질적 차이가 없고, 나머지 넷에서만 차이가 난다.
- **선택지 나.** 다섯 모두 **꼬리를 포함한 고저 범위 사이의 갭**으로 읽는다. 갭의 통상적인
  뜻에 가깝고 Abandoned Baby가 실제로 그렇게 정의된다. 조건이 엄격해져 발생이 크게 줄고,
  실체 기준을 쓰는 이웃 패턴과 뜻이 갈린다.
- **선택지 다.** 패턴마다 이웃 패턴의 기준을 따라간다. 예컨대 `CDLTRISTAR`는 별 계열이므로
  실체 기준으로, `CDLCONCEALBABYSWALL`은 Marubozu가 앞에 있으므로 실체 기준으로 읽는 식이다.
  가장 정교하지만 자리마다 근거를 따로 남겨야 한다.

## 결정 10. 원문 구조가 모호한 여섯 자리의 해석을 정한다

값이 아니라 **구조**가 모호한 자리다. 척도를 아무리 정해도 풀리지 않는다.

- **`CDLHARAMICROSS` 규칙 3의 "range".** Harami는 "body range"라고 못박았는데 Harami Cross는
  그냥 "range"다. **실체 범위로 읽을 것인가 고저 범위로 읽을 것인가.** 실체 범위로 읽으면
  Harami와 일관되고, 고저 범위로 읽으면 원문의 낱말 차이를 존중한다.
- **`CDLUNIQUE3RIVER` 규칙 4의 "below the middle day".** 셋째 날이 가운데 날보다 아래여야
  한다는데 **무엇이 무엇보다 아래인지**를 정하지 않았다. 셋째 날의 실체 전체가 가운데 날의
  실체 아래인지, 종가가 가운데 날의 종가 아래인지, 저가끼리 비교하는지 세 읽기가 있다.
- **`CDL3STARSINSOUTH` 규칙 3의 "previous day's range".** 셋째 날이 앞날의 범위 안에서 열고
  닫는다는데 그 범위가 **실체 범위인지 고저 범위인지** 밝히지 않았다.
- **`CDLRISEFALL3METHODS` 규칙 2의 "a group of small real body candlesticks".** Morris는
  개수를 못박지 않았으나 **Nison이 유한 범위를 준다.** `nison_jcct.txt` L3994~L3996은
  이상적인 수를 셋으로 두고 둘이거나 셋보다 많아도 된다고 하며, L4025~L4027은 경험상
  **둘에서 다섯까지** 잘 작동한다고 적는다. 따라서 선택지는 **고정 세 봉**과 **둘에서
  다섯까지의 유한 범위** 둘이다. **상한이 없는 선택지는 원전 근거가 없으므로 제거한다.**
  어느 쪽을 골라도 창 길이는 유한하므로 상태 크기와 워밍업의 상한이 정해진다.
- **`CDLRISEFALL3METHODS` 규칙 4의 "a strong day".** 마지막 날이 강해야 한다는데 강함의
  기준이 없다. 긴 날로 읽을 것인가, 종가 조건만으로 충분하다고 볼 것인가.
- **`CDLKICKINGBYLENGTH`의 "the longer side of the two candles".** 원문은 "더 긴 쪽"이라고만
  하고 **실체 길이인지 고저 범위 길이인지** 밝히지 않는다. 엄격한 Marubozu라면 둘이 같지만,
  결정 2에서 꼬리에 허용오차를 두면 달라진다. **두 길이가 정확히 같을 때의 처리**도 없다.

여섯 자리 모두 **선택지가 둘 이상이고 어느 쪽도 원전이 배제하지 않는다.** 결정 C의 "좁은
쪽" 규칙으로도 갈리지 않는다. 좁고 넓음이 아니라 서로 다른 읽기이기 때문이다.

## 결정 11. 확인 등급과 출력 시점을 정한다

**Morris는 89개 항목 전부에 확인 등급을 적어 두었다.** 분포는 `Required` 36건,
`Suggested` 25건, `No` 28건이며, 같은 패턴이라도 방향에 따라 등급이 다른 경우가 많다.
Chesler의 Hikkake는 확인을 필수로 두고 기한까지 세 봉으로 못박았다. 곧 신호가 성립한 봉보다
늦게야 확정되는 패턴이 소수가 아니다.

먼저 **등급을 어떻게 다룰지** 정해야 한다.

- **선택지 가.** 확인을 패턴 정의 안에 넣어 `Required`인 것만 확인 뒤에 신호를 낸다.
  원전에 충실하다. 같은 모양이 방향에 따라 다른 시점에 신호를 내게 된다.
- **선택지 나.** 확인을 패턴 밖의 소비자 필터로 두고 패턴은 등급을 메타데이터로만 싣되,
  **모든 소비자가 `Required` 등급의 확인을 반드시 적용한다는 계약을 함께 둔다.** 패턴이
  순수해지고 `Suggested`는 전략이 고를 수 있다. **이 계약이 없으면 소비자가 필터를 쓰지
  않는 것만으로 `Required`가 사실상 버려지므로, 계약을 붙이지 못하면 이 선택지는 성립하지
  않는다.** 계약을 두면 그것을 강제하는 검증을 어디에 둘지도 함께 정해야 한다.
**앞 판의 선택지 가운데 "등급을 쓰지 않고 확인 정보를 버린다"는 것은 제거한다.**
결정 C로 채택한 더 엄격한 원전 조건을 다시 버리는 선택지이기 때문이다. `Required`로 적힌
패턴에서 확인을 무시하면 Morris가 요구한 조건과 Nison이 요구한 조건을 함께 버리게 되므로
승인 가능한 선택지가 아니다. 남는 선택지는 위의 둘이다.

이어서 **시점 정렬**을 정해야 한다. **앞 판의 선택지 가운데 "패턴이 시작된 봉에 신호를
낸다"는 것은 제거한다.** 나중 봉을 보아야 정해지는 값을 과거 봉에 기록하는 것이므로 저장소의
확정 캔들 계약과 미래 참조 금지 불변식을 깬다. 승인 가능한 선택지가 아니다.

- **선택지 가.** 확인이 끝난 봉에 신호를 낸다. 미래를 참조하지 않는다. 패턴이 시작된 봉과
  신호가 나오는 봉이 달라지므로 그 대응을 문서에 남겨야 한다.
- **선택지 나.** 확인 전 성립과 확인 후 성립을 다른 값으로 낸다. 정보가 보존된다. 소비자가
  둘을 구별해 쓰도록 계약을 정해야 하고, 출력 표현이 결정 13과 묶인다.

## 결정 12. 확인의 내용과 기한을 정한다

결정 11이 확인 등급을 **어디에 둘지**를 묻는다면, 이 결정은 **확인이 무엇인지**와 **언제까지
일어나야 하는지**를 묻는다. 둘은 다른 문제이고 앞 판에는 뒤의 것이 없었다.

**원전이 준 것을 먼저 정리한다.**

- **Chesler의 Hikkake만 완결되어 있다.** 확인은 강세 설정이면 가격이 인사이드 바의 고가
  위로 올라서는 것, 약세 설정이면 저가 아래로 내려가는 것이고, **기한은 세 봉**이다.
  61종 가운데 내용과 기한을 모두 원전이 준 유일한 패턴이다.
- **Nison은 두 패턴에 내용을 주고 기한을 다음 날로 한정한다.** Hanging Man에 대해
  `nison_jcct.txt` L1419~L1422는 "At a minimum this would be a lower opening under the real
  body of the hanging man. But I usually recommend a close beneath the hanging man."라고
  적는다. 곧 **최소 요건은 다음 날 시가가 실체 아래에서 열리는 것이고, 권장 요건은 다음 날
  종가가 실체 아래에서 마감하는 것**이다. Inverted Hammer에 대해서도 L2428~L2432가 방향만
  뒤집어 같은 두 단계를 적는다.
- **Morris는 등급만 주고 내용은 거의 주지 않는다.** 머리말 `Confirmation:` 필드는 89개
  항목 전부에 있지만, 확인이 무엇인지는 시나리오 절의 흩어진 문장에만 나오고 그 문장들도
  서로 형식이 다르다. Hammer에 대해서는 L1195~L1200이 "This confirmation may merely be the
  action on the open of the next day. Many times, though, it is best to wait for a confirming
  close on the following day."라고 적고, Harami에 대해서는 L1572~L1573이 "Confirmation on
  the third day would be a lower close."라고 적으며, Meeting Lines에 대해서는 L2237이
  "If the third day opens higher, confirmation has been given."이라고 적는다. **기한을 적은
  자리는 한 곳도 없다.**

곧 **확인의 내용과 기한이 원전에서 모두 확정되는 항목이 네 자리 있다.** `CDLHIKKAKE`와
`CDLHIKKAKEMOD`는 Chesler가 내용과 세 봉 기한을 함께 주고, `CDLHANGINGMAN`과
`CDLINVERTEDHAMMER`는 Nison이 내용과 함께 **기한을 다음 날로 한정**한다. 이 네 자리는
결정 대상이 아니라 이미 확정된 것이다.

**앞 판은 이 자리를 두 번 잘못 적었다.** 확인의 내용을 확정할 수 있는 것이 네 자리뿐이라고
줄여 적었고(Hanging Man과 Inverted Hammer는 4장 8번과 9번에서 이미 원전 문장으로 확정했다),
"Hikkake를 빼면 원전은 기한을 주지 않는다"고 **사실과 반대로** 단언했다. Nison L1419~L1422와
L2428~L2432는 두 패턴 모두 **다음 날**을 기한으로 명시한다. 둘 다 바로잡는다.

**따라서 결정 대상은 원전이 실제로 아무것도 주지 않은 나머지 항목뿐이다.**

**먼저 확인의 내용을 정해야 한다.**

- **선택지 가.** 원전이 내용을 준 네 자리는 원전대로 쓰고, 나머지는 **패턴 방향에 대한
  다음 봉의 종가 조건** 하나로 통일한다. 곧 강세 패턴이면 다음 봉 종가가 패턴 마지막 봉의
  종가보다 높고, 약세 패턴이면 낮으면 확인으로 본다. 규칙이 하나여서 구현과 검증이 단순하다.
  Nison이 최소 요건으로 인정한 시가 조건을 쓰지 못한다.
- **선택지 나.** Nison의 두 단계를 전체에 확장한다. 곧 **최소 요건은 다음 봉 시가**,
  **권장 요건은 다음 봉 종가**로 두고 어느 쪽을 쓸지는 파라미터로 연다. 원전의 서술 구조를
  가장 잘 보존한다. 값이 하나 늘고 등급과 곱해져 조합이 많아진다.
- **선택지 다.** 패턴마다 원전 시나리오 문장을 그대로 옮겨 서로 다른 확인 조건을 둔다.
  가장 충실하다. Morris의 시나리오 문장이 형식이 제각각이고 대부분의 패턴에는 아예 없으므로,
  없는 자리를 결국 우리가 채워야 하며 그 결과 규칙이 61개로 흩어진다.

**이어서 기한을 정해야 한다. 다만 네 자리는 결정 대상에서 뺀다.** `CDLHIKKAKE`와
`CDLHIKKAKEMOD`는 **세 봉**, `CDLHANGINGMAN`과 `CDLINVERTEDHAMMER`는 **다음 한 봉**으로
원전이 이미 정했다. **이 넷은 사용자가 고를 자리가 아니며 어떤 선택지도 이 값을 바꾸지
않는다.** 남은 것은 Morris가 등급만 매기고 기한을 적지 않은 나머지 항목이다.

- **선택지 가.** 나머지를 **다음 한 봉**으로 통일한다. Morris의 시나리오 문장이 "다음 날"
  또는 "셋째 날"을 가리키므로 원전의 어투에 가장 가깝고, 원전이 기한을 준 두 패턴
  (Hanging Man과 Inverted Hammer)의 값과도 같아진다. 확인이 한 봉 늦게 오면 놓친다.
- **선택지 나.** 나머지를 **세 봉**으로 둔다. Chesler가 Hikkake에 준 값을 유추 적용하는
  것이다. 확인을 놓칠 여지가 줄지만, 유추의 근거가 약하고 대기 중인 패턴을 더 오래 들고
  있어야 하므로 상태가 커진다.
- **선택지 다.** 나머지를 **패턴의 봉 수에 비례**해 둔다. 예컨대 한 봉 패턴은 다음 한 봉,
  여러 봉 패턴은 그보다 길게 둔다. 패턴의 성격을 반영하지만 비례 규칙 자체를 새로 만들어야
  하고 원전에 근거가 없다.

**어느 선택지도 위의 네 자리에는 적용되지 않는다.**

**어느 쪽을 고르든, 원전이 기한을 주지 않았다는 사실과 우리가 고른 값이 우리 규약이라는
것을 표준에 명시해야 한다.** 결정 A가 요구하는 바다.

## 결정 13. 반환 값의 표현을 정한다

TA-Lib은 ±100과 ±80과 ±200을 쓰고, 부호가 방향을 뜻하기도 하고 캔들의 색을 뜻하기도 한다.
6.3절에 적었듯 같은 ±100 표기가 함수에 따라 다른 것을 뜻한다.

- **선택지 가.** 성립 여부와 방향을 갈라 표현한다. 뜻이 분명해진다. 대조할 때 변환이 필요하고
  경계값을 어떻게 옮길지 따로 정해야 한다.
- **선택지 나.** 단일 수치로 내되 부호를 방향으로 고정하고, 방향이 없는 패턴은 양수만 낸다.
  단순하고 기존 지표 계약과 잘 맞는다. 확인 전후를 구별할 자리가 없다.
- **선택지 다.** 확인 전후와 방향을 모두 담는 다단계 수치를 쓴다. 정보가 가장 잘 보존된다.
  소비자가 해석 규칙을 알아야 한다.

**결정 11의 시점 정렬과 함께 정해야 한다.** 둘은 독립이 아니다.

## 결정 14. 등록할 파라미터 조합과 기본값을 정한다

5.5절의 값 가운데 무엇을 파라미터로 열고 무엇을 표준이 고정할지 정해야 한다. 결정 12의
확인 내용과 기한도 파라미터로 열 수 있는 값에 들어간다.

- **선택지 가.** 아무것도 열지 않고 표준이 정한 값 하나로 고정한다. 등록 목록이 단순해지고
  재현이 쉽다. 시장이나 주기에 맞지 않을 때 대응할 수 없다.
- **선택지 나.** 척도 일곱만 하나의 설정 묶음으로 열고 나머지는 고정한다. 실제로 조정이
  필요한 것을 열면서 등록 수가 폭발하지 않는다. 설정 묶음이 지표의 파라미터와 다른 모양이
  되므로 레지스트리 계약을 손봐야 한다.
- **선택지 다.** 패턴마다 보수적 조합과 느슨한 조합 둘을 등록한다. 민감도를 바로 견줄 수
  있다. 등록 수와 검증 부담이 두 배가 된다.

## 결정 15. `CDLKICKINGBYLENGTH`를 별개 패턴으로 둘 것인가

방향 규칙은 원전에 있으나 Morris는 그것을 자기 규칙으로 채택하지 않고 "Some Japanese theory
says"라고 전언으로 소개했고, 별개 패턴으로 세운 것은 TA-Lib이다.

- **선택지 가.** 별개로 두지 않고 `CDLKICKING` 하나만 구현한다. 원전의 패턴 목록과 일치한다.
  더 긴 쪽 방향이라는 정보를 버린다.
- **선택지 나.** `CDLKICKING` 하나만 두되 방향 결정 방식을 파라미터로 연다. 정보가 보존되고
  패턴 수도 늘지 않는다. 파라미터가 하나 늘어난다.
- **선택지 다.** TA-Lib처럼 별개 패턴 둘로 둔다. 대조가 가장 쉽다. 원전에 없는 패턴 이름이
  표준에 들어오므로 그것이 우리 선택임을 명시해야 한다.

## 결정 16. 61종 전부를 대상으로 삼을 것인가

원전 지지의 성격이 고르지 않다. Hikkake 두 종은 일본식 캔들 패턴이 아니고, Three Inside와
Three Outside는 Morris가 일본 문헌에 없고 자신이 만들었다고 본문에 적었으며, Breakaway
약세형도 Morris가 시험 삼아 만든 것이라고 밝혔다.

- **선택지 가.** 61종 전부를 대상으로 삼는다. 대조군과 목록이 일치해 검증이 단순하다.
  계보가 다른 패턴이 한 묶음에 섞인다.
- **선택지 나.** Nison과 Morris에 정의가 있는 것만 삼는다(59종). Hikkake 두 종을 빼면
  TA-Lib 대조 목록과 어긋난다.
- **선택지 다.** 일본 문헌에 뿌리를 둔 것만 삼는다(57종). Hikkake 둘에 더해 Morris가 창안한
  Three Inside와 Three Outside까지 뺀다. 계보가 가장 순수해지지만 넷 모두 실무에서 널리
  쓰이므로 손실이 크다.
- **선택지 라.** 전부 구현하되 계보를 메타데이터로 드러낸다. 정보가 가장 잘 보존된다.
  메타데이터 항목이 하나 늘고, 그 구성은 다른 담당의 소관과 겹친다.

# 부록. 재현에 필요한 것

**스크립트와 추출본이 있는 실제 디렉터리는 다음 하나다.**

```
/private/tmp/claude-501/-Users-vincent-workspaces-CoinTrading-trading-system-v2/
  0eeb4e04-411b-4f42-88a5-f4df7af1906b/scratchpad/
```

앞 판이 "같은 디렉터리"라고만 적어 산출물 디렉터리에서 찾을 수 없었던 문제를 바로잡는다.
이 문서가 놓인 산출물 디렉터리(`d75ae237-...`)와 자료가 놓인 디렉터리는 서로 다르다.

그 디렉터리의 파일은 이렇다.

- 원전 추출본 세 편. `nison_jcct.txt`(Nison 2판, 419,066자), `morris_cce.txt`(Morris 3판,
  603,681바이트), `chesler_hikkake_2004.txt`(Chesler 2004년 기사, 11,865바이트). **4장과
  5장의 `L####` 줄 번호는 모두 이 세 파일 기준이다.**
- Morris 머리말 색인. `morris_index.py`가 89개 항목의 `Pattern Name`, `Type`,
  `Japanese Name`, `Trend Required`, `Confirmation`과 규칙 블록의 줄 번호를 뽑아
  `morris_index.json`에 저장한다. `morris_pairs.py`는 강세형과 약세형을 묶어
  `morris_pairs.txt`로 낸다. 4.7절의 확인 등급 집계가 이 산출물에서 나왔다.
- 관찰 스크립트. 함수 목록과 입력·파라미터·lookback 수집(`enum1.py`, `enum2.py`), 출력 값
  관찰(`enum4.py`), 캔들 설정의 평균 기간과 의존 관계 복원(`probe_avg.py`), 계수와 범위
  종류 전수 대조(`probe_factor.py`), 경계값 80의 성격 확인(`probe80.py`), 추세 요건 확인
  (`probe_trend.py`, `probe_trend2.py`, `probe_hammer.py`), 패턴 봉 수 교란 실험
  (`probe_span.py`)이 있다.
- 가상환경 `talibenv`. `TA-Lib==0.7.1`, `numpy` 2.4.6, `pypdf`, Python 3.11.9 (macOS arm64
  휠). C 라이브러리는 `0.7.1 (Jul 16 2026 18:35:07)`이다.

원전 세 편의 내려받은 원본 PDF는 다음 디렉터리에 남아 있다.

```
/Users/vincent/.claude/projects/-Users-vincent-workspaces-CoinTrading-trading-system-v2/
  0eeb4e04-411b-4f42-88a5-f4df7af1906b/tool-results/
```

관찰로 얻은 수치는 모두 재현할 수 있으나, **원전 인용은 재현이 아니라 확인의 문제다.**
줄 번호로 해당 추출본을 열면 이 문서의 인용을 그대로 대조할 수 있고, 인용에 의심이 가는
자리가 있으면 해당 저작의 해당 장을 직접 열어 확인해야 한다.
