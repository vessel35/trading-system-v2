# 캔들스틱 패턴 계산 표준

이 문서는 `core_lib.patterns`가 제공하는 TA-Lib 기반 캔들스틱 패턴 61종의 계산
정책이다. **판정 규칙은 이 문서에 옮겨 적지 않는다.** TA-Lib v0.7.1의 C 소스가
원본이고, 어긋나면 우리 문서나 포트가 틀린 것이다.

## §0. 전제와 소유 범위

이 표준은 다음을 소유한다.

- TA-Lib v0.7.1을 계산 원본으로 쓰는 전제와 출처 고정값
- TA-Lib 기본 캔들 설정 11개와 범위·평균 계산 기반
- TA-Lib raw integer 계층과 우리 네 키 어댑터 계층의 출력 정책
- 공개 패턴 이름, 대응 `CDL` 함수, 워밍업, 사용하는 캔들 설정, raw 값 집합
- 포획값 기반 검증과 수제 입력 보완 방식
- 패턴 레지스트리 판 `2.0.0+talib.0.7.1`
- 런타임과 CI가 TA-Lib에 의존하지 않는다는 정책

이 표준은 다음을 소유하지 않는다.

- Nison, Morris, Chesler 원전에서 판정 규칙을 새로 유도하는 작업
- TA-Lib C 판정 규칙을 문장으로 재기술한 규칙집
- 지표 표준 `docs/references/technical_indicators_calc_spec.md` §11의 커버리지 집계
- 전략이 패턴 값을 어떻게 해석해 매매 결정을 내리는지

원전 조사 기록은 `docs/candlestick-patterns/analysis-1-original-sources.md`에 남아
있다. 그 문서는 계산의 기준이 아니라 TA-Lib 전환 전 조사 기록이다.

## §1. 출처 명세

TA-Lib 출처는 태그뿐 아니라 변경 불가능한 커밋으로 고정한다.

| 항목 | 값 |
|---|---|
| 저장소 | `https://github.com/TA-Lib/ta-lib` |
| 태그 | `v0.7.1` |
| 커밋 | `2247d599bddf37ed37e3a709371517e46efc66f6` |
| 캔들 설정 파일 | `src/ta_common/ta_global.c` |
| 범위·평균 매크로 파일 | `src/ta_func/ta_utility.h` |
| 판정 함수 파일 | `src/ta_func/ta_CDL*.c` |

위 계산 원본 63개는 원래 경로를 유지해 `third_party/ta-lib/`에 보존한다. 범위는
`src/ta_common/ta_global.c`, `src/ta_func/ta_utility.h`, `src/ta_func/ta_CDL*.c`
61개뿐이다. `third_party/ta-lib/SHA256SUMS`는 원본 저장소 주소, 태그, 커밋과 각
파일의 SHA-256을 고정하며, 기본 pytest 무결성 검사는 반입 파일 집합과 개수 및
해시를 네트워크 없이 대조한다. 원본 BSD 3-clause `LICENSE`도 함께 보존한다.

Hilbert 계열 C 소스 일곱 개는 같은 고정점에서 `third_party/ta-lib/`에 반입되어
범용 TA-Lib 무결성 검사와 원본 목록의 보호를 받지만, 아직 계산 코드로 이식하지
않았다. 계산 정책은 `docs/references/technical_indicators_calc_spec.md`가 소유하며
이 캔들스틱 표준의 소유 범위에는 포함되지 않는다.

## §2. 계산 기반

TA-Lib의 `TA_CDL*` 함수들은 공통 캔들 설정과 범위·평균 매크로를 사용한다. 포트의
기반 구현은 `services/core-lib/core_lib/patterns/talib_candles.py`에 있다.

### §2.1 캔들 설정 11개

| 설정 | 범위 | 평균 기간 | 계수 |
|---|---|---:|---:|
| BodyLong | RealBody | 10 | 1.0 |
| BodyVeryLong | RealBody | 10 | 3.0 |
| BodyShort | RealBody | 10 | 1.0 |
| BodyDoji | HighLow | 10 | 0.1 |
| ShadowLong | RealBody | 0 | 1.0 |
| ShadowVeryLong | RealBody | 0 | 2.0 |
| ShadowShort | Shadows | 10 | 1.0 |
| ShadowVeryShort | HighLow | 10 | 0.1 |
| Near | HighLow | 5 | 0.2 |
| Far | HighLow | 5 | 0.6 |
| Equal | HighLow | 5 | 0.05 |

### §2.2 범위와 평균

범위 종류는 셋이다.

- `RealBody = abs(close - open)`
- `HighLow = high - low`
- `Shadows = upper_shadow + lower_shadow`

`upper_shadow = high - max(open, close)`이고
`lower_shadow = min(open, close) - low`다.

평균은 TA-Lib의 `TA_CANDLEAVERAGE` 형태를 따른다.

```text
average = period_total / avg_period  if avg_period != 0
average = candle_range(target)       if avg_period == 0
divisor = 2                          if range_type == Shadows
divisor = 1                          otherwise
candle_average = factor * average / divisor
```

`period_total`은 대상 봉 바로 앞 `avg_period`개 봉의 `candle_range` 합이다.
`avg_period`가 0이면 이동 합을 만들지 않고 대상 봉 자신의 range를 사용한다.

### §2.3 워밍업

TA-Lib `lookback`은 해당 패턴이 쓰는 설정들의 평균 기간 최댓값과 패턴 구조가 읽는
추가 과거 봉 수에서 온다. 우리 `min_history`는 `lookback + 1`이다. raw integer
계열에서 `lookback` 이전 prefix는 TA-Lib wrapper와 같이 0으로 정렬되지만, 네 키
어댑터 계열은 같은 구간을 모두 `NaN`으로 둔다.

## §5. 출력 정책

출력은 두 계층이다. raw integer는 TA-Lib 동등성의 기준이고, 네 키 출력은 기존
소비자가 읽는 어댑터 표현이다.

### §5.1 네 키 이름

패턴 이름이 `pat_hammer`이면 네 키는 아래 순서다.

| 키 | 뜻 |
|---|---|
| `pat_hammer` | 성립 여부 |
| `pat_hammer_dir` | 방향. `+1.0`은 양, `-1.0`은 음, `0.0`은 없음 |
| `pat_hammer_strength` | 성립 강도. `1.0`은 full, `0.5`는 boundary |
| `pat_hammer_confirm` | Hikkake류 확인 여부 |

모든 등록 패턴은 자기 이름에 같은 접미사를 붙여 네 키를 만든다.

### §5.2 raw integer 값

전체 허용 raw integer는 `0`, `±80`, `±100`, `±200`이다. 이것은 어댑터가
받아들이는 전체 도메인이고, 모든 패턴이 모든 비영 값을 낸다는 뜻이 아니다.

| raw integer | 뜻 |
|---:|---|
| `0` | 비성립 또는 raw warm-up prefix |
| `±80` | boundary match. 현재는 `CDLENGULFING`, `CDLHARAMI`, `CDLHARAMICROSS`에서만 소스상 가능 |
| `±100` | full match |
| `±200` | Hikkake류 confirmation |

부호는 TA-Lib raw 부호다. 모든 패턴에서 전략 방향을 뜻한다고 일반화하지 않는다.

### §5.3 네 키 어댑터 모양

허용되는 네 키 모양은 넷뿐이다.

| 상태 | 성립 키 | 방향 키 | 강도 키 | 확인 키 |
|---|---:|---:|---:|---:|
| warm-up | `NaN` | `NaN` | `NaN` | `NaN` |
| 비성립 raw `0` | `0.0` | `0.0` | `0.0` | `0.0` |
| match raw `±80` 또는 `±100` | `1.0` | `±1.0` | `0.5` 또는 `1.0` | `0.0` |
| raw `±200` | `0.0` | `±1.0` | `0.0` | `1.0` |

성립과 확인은 동시에 켜질 수 없다. 일부 키만 `NaN`인 출력도 허용하지 않는다.

## §6. 61종 대응표

이 표의 값 열은 세 뜻을 분리한다.

- **전체 허용 raw**: §5.2의 `0`, `±80`, `±100`, `±200`. 어댑터 전체 정책이다.
- **소스상 비영 raw**: 해당 `CDL` 함수가 TA-Lib 소스상 낼 수 있는 비영 값이다.
  모든 패턴은 성립하지 않을 때 raw `0`을 낼 수 있으므로 표에서는 0을 반복하지 않는다.
- **22000봉 관측 비영 raw**: 일곱 국면 22000봉 포획에서 실제 관측된 비영 값이다.
  표본 결과이며 정책이 아니다. `-`는 그 표본에서 관측되지 않았다는 뜻일 뿐이다.

판정 규칙은 각 `src/ta_func/ta_CDL*.c` 파일과 그 포트가 소유한다.

| 우리 이름 | TA-Lib 함수 | 워밍업 | 쓰는 설정 | 소스상 비영 raw | 22000봉 관측 비영 raw |
|---|---|---:|---|---|---|
| `pat_doji` | `CDLDOJI` | 11 | BodyDoji | +100 | +100 |
| `pat_long_legged_doji` | `CDLLONGLEGGEDDOJI` | 11 | BodyDoji, ShadowLong | +100 | +100 |
| `pat_rickshaw_man` | `CDLRICKSHAWMAN` | 11 | BodyDoji, Near, ShadowLong | +100 | +100 |
| `pat_dragonfly_doji` | `CDLDRAGONFLYDOJI` | 11 | BodyDoji, ShadowVeryShort | +100 | +100 |
| `pat_gravestone_doji` | `CDLGRAVESTONEDOJI` | 11 | BodyDoji, ShadowVeryShort | +100 | +100 |
| `pat_takuri` | `CDLTAKURI` | 11 | BodyDoji, ShadowVeryLong, ShadowVeryShort | +100 | +100 |
| `pat_hammer` | `CDLHAMMER` | 12 | BodyShort, Near, ShadowLong, ShadowVeryShort | +100 | +100 |
| `pat_hanging_man` | `CDLHANGINGMAN` | 12 | BodyShort, Near, ShadowLong, ShadowVeryShort | -100 | -100 |
| `pat_inverted_hammer` | `CDLINVERTEDHAMMER` | 12 | BodyShort, ShadowLong, ShadowVeryShort | +100 | +100 |
| `pat_shooting_star` | `CDLSHOOTINGSTAR` | 12 | BodyShort, ShadowLong, ShadowVeryShort | -100 | -100 |
| `pat_spinning_top` | `CDLSPINNINGTOP` | 11 | BodyShort | -100, +100 | -100, +100 |
| `pat_high_wave` | `CDLHIGHWAVE` | 11 | BodyShort, ShadowVeryLong | -100, +100 | -100, +100 |
| `pat_marubozu` | `CDLMARUBOZU` | 11 | BodyLong, ShadowVeryShort | -100, +100 | -100, +100 |
| `pat_closing_marubozu` | `CDLCLOSINGMARUBOZU` | 11 | BodyLong, ShadowVeryShort | -100, +100 | -100, +100 |
| `pat_belt_hold` | `CDLBELTHOLD` | 11 | BodyLong, ShadowVeryShort | -100, +100 | -100, +100 |
| `pat_long_line` | `CDLLONGLINE` | 11 | BodyLong, ShadowShort | -100, +100 | -100, +100 |
| `pat_short_line` | `CDLSHORTLINE` | 11 | BodyShort, ShadowShort | -100, +100 | -100, +100 |
| `pat_engulfing` | `CDLENGULFING` | 3 | - | -100, -80, +80, +100 | -100, -80, +80, +100 |
| `pat_harami` | `CDLHARAMI` | 12 | BodyLong, BodyShort | -100, -80, +80, +100 | -100, -80, +80, +100 |
| `pat_harami_cross` | `CDLHARAMICROSS` | 12 | BodyDoji, BodyLong | -100, -80, +80, +100 | -100, -80, +80, +100 |
| `pat_doji_star` | `CDLDOJISTAR` | 12 | BodyDoji, BodyLong | -100, +100 | -100, +100 |
| `pat_piercing` | `CDLPIERCING` | 12 | BodyLong | +100 | +100 |
| `pat_dark_cloud_cover` | `CDLDARKCLOUDCOVER` | 12 | BodyLong | -100 | -100 |
| `pat_counterattack` | `CDLCOUNTERATTACK` | 12 | BodyLong, Equal | -100, +100 | -100, +100 |
| `pat_separating_lines` | `CDLSEPARATINGLINES` | 12 | BodyLong, Equal, ShadowVeryShort | -100, +100 | -100, +100 |
| `pat_kicking` | `CDLKICKING` | 12 | BodyLong, ShadowVeryShort | -100, +100 | - |
| `pat_kicking_by_length` | `CDLKICKINGBYLENGTH` | 12 | BodyLong, ShadowVeryShort | -100, +100 | - |
| `pat_homing_pigeon` | `CDLHOMINGPIGEON` | 12 | BodyLong, BodyShort | +100 | +100 |
| `pat_matching_low` | `CDLMATCHINGLOW` | 7 | Equal | +100 | +100 |
| `pat_in_neck` | `CDLINNECK` | 12 | BodyLong, Equal | -100 | -100 |
| `pat_on_neck` | `CDLONNECK` | 12 | BodyLong, Equal | -100 | -100 |
| `pat_thrusting` | `CDLTHRUSTING` | 12 | BodyLong, Equal | -100 | -100 |
| `pat_two_crows` | `CDL2CROWS` | 13 | BodyLong | -100 | -100 |
| `pat_three_black_crows` | `CDL3BLACKCROWS` | 14 | ShadowVeryShort | -100 | - |
| `pat_three_inside` | `CDL3INSIDE` | 13 | BodyLong, BodyShort | -100, +100 | -100, +100 |
| `pat_three_outside` | `CDL3OUTSIDE` | 4 | - | -100, +100 | -100, +100 |
| `pat_three_stars_in_the_south` | `CDL3STARSINSOUTH` | 13 | BodyLong, BodyShort, ShadowLong, ShadowVeryShort | +100 | - |
| `pat_three_white_soldiers` | `CDL3WHITESOLDIERS` | 13 | BodyShort, Far, Near, ShadowVeryShort | +100 | - |
| `pat_abandoned_baby` | `CDLABANDONEDBABY` | 13 | BodyDoji, BodyLong, BodyShort | -100, +100 | +100 |
| `pat_advance_block` | `CDLADVANCEBLOCK` | 13 | BodyLong, Far, Near, ShadowLong, ShadowShort | -100 | -100 |
| `pat_evening_doji_star` | `CDLEVENINGDOJISTAR` | 13 | BodyDoji, BodyLong, BodyShort | -100 | -100 |
| `pat_evening_star` | `CDLEVENINGSTAR` | 13 | BodyLong, BodyShort | -100 | -100 |
| `pat_identical_three_crows` | `CDLIDENTICAL3CROWS` | 13 | Equal, ShadowVeryShort | -100 | -100 |
| `pat_morning_doji_star` | `CDLMORNINGDOJISTAR` | 13 | BodyDoji, BodyLong, BodyShort | +100 | +100 |
| `pat_morning_star` | `CDLMORNINGSTAR` | 13 | BodyLong, BodyShort | +100 | +100 |
| `pat_stalled_pattern` | `CDLSTALLEDPATTERN` | 13 | BodyLong, BodyShort, Near, ShadowVeryShort | -100 | -100 |
| `pat_tri_star` | `CDLTRISTAR` | 13 | BodyDoji | -100, +100 | -100, +100 |
| `pat_unique_three_river` | `CDLUNIQUE3RIVER` | 13 | BodyLong, BodyShort | +100 | +100 |
| `pat_upside_gap_two_crows` | `CDLUPSIDEGAP2CROWS` | 13 | BodyLong, BodyShort | -100 | -100 |
| `pat_three_line_strike` | `CDL3LINESTRIKE` | 9 | Near | -100, +100 | +100 |
| `pat_breakaway` | `CDLBREAKAWAY` | 15 | BodyLong | -100, +100 | -100, +100 |
| `pat_concealing_baby_swallow` | `CDLCONCEALBABYSWALL` | 14 | ShadowVeryShort | +100 | - |
| `pat_gap_side_by_side_white` | `CDLGAPSIDESIDEWHITE` | 8 | Equal, Near | -100, +100 | -100, +100 |
| `pat_ladder_bottom` | `CDLLADDERBOTTOM` | 15 | ShadowVeryShort | +100 | +100 |
| `pat_mat_hold` | `CDLMATHOLD` | 15 | BodyLong, BodyShort | +100 | - |
| `pat_rise_fall_three_methods` | `CDLRISEFALL3METHODS` | 15 | BodyLong, BodyShort | -100, +100 | -100, +100 |
| `pat_stick_sandwich` | `CDLSTICKSANDWICH` | 8 | Equal | +100 | +100 |
| `pat_tasuki_gap` | `CDLTASUKIGAP` | 8 | Near | -100, +100 | -100, +100 |
| `pat_gap_three_methods` | `CDLXSIDEGAP3METHODS` | 3 | - | -100, +100 | -100, +100 |
| `pat_hikkake` | `CDLHIKKAKE` | 6 | - | -200, -100, +100, +200 | -200, -100, +100, +200 |
| `pat_hikkake_modified` | `CDLHIKKAKEMOD` | 11 | Near | -200, -100, +100, +200 | -100, +100 |

## §7. 검증 방법

포획값은 일회용 환경에서 TA-Lib wrapper `0.7.1`과 underlying C library `0.7.1`로
생성했다. 포획 날짜는 `2026-08-03`이고, 생성 결과는
`services/core-lib/tests/pattern_reference/talib_signals.py`에 고정되어 있다.

대조 계열은 일곱 국면 22000봉이다.

| 국면 | 봉 수 |
|---|---:|
| `mixed_hourly` | 4000 |
| `strong_uptrend` | 3000 |
| `strong_downtrend` | 3000 |
| `choppy_reversals` | 3000 |
| `frequent_gaps` | 3000 |
| `quiet_small_bodies` | 3000 |
| `wide_swings` | 3000 |

포획은 `scripts/capture_talib_pattern_signals.py`가 수행한다. 이 스크립트는
throwaway 환경에서만 TA-Lib을 import하고, repository의 테스트 fixture에는 각 국면의
fingerprint, bar count, wrapper/C-library version, optional `penetration` 기본값, sparse
non-zero raw integer 신호만 남긴다.

대조가 단언하는 것은 제한적이고 구체적이다. **위 일곱 국면의 정확한 22000봉에 대해**
61개 `CDL` 함수와 포트가 같은 bar index에서 같은 raw integer를 낸다는 뜻이다.
이는 61종 × 7국면 = 427쌍, 61종 × 22000봉 = 1,342,000개 bar-level 비교다.
이 포획은 모든 가능한 OHLC 조합을 증명하지 않으며, 표본에서 관측되지 않은 값이
소스상 불가능하다는 뜻도 아니다.

포획이 덮지 못한 자리는 수제 입력으로 보완했다. Kicking 두 종, Three Black Crows,
Three Stars in the South, Three White Soldiers, Abandoned Baby의 반대 방향, Concealing
Baby Swallow, Mat Hold, Hikkake Modified confirmation처럼 rare branch나 포획 침묵이
있는 경로는 테스트가 손으로 만든 OHLC 입력을 넣어 TA-Lib C 0.7.1과 확인한 raw 값을
고정한다. 이 수제 입력은 포획 국면을 특정 패턴에 맞춰 조정하지 않기 위한 보완 장치다.

문서 표도 검증 대상이다. 테스트는 이 문서의 캔들 설정 표와 61종 대응표를 파싱해
`DEFAULT_CANDLE_SETTINGS`, `TALIB_FUNCTIONS`, 포트의 `min_history`, 포트가 사용하는
캔들 설정, 포트 판정 함수의 소스상 비영 raw 값, 그리고 고정 포획 fixture의 관측 비영
raw 값과 비교한다.

## §8. 레지스트리 판

TA-Lib 전환 뒤 패턴 레지스트리 판은 `2.0.0+talib.0.7.1`이다.

- `2.0.0`: 수작업 원전 기반 규칙을 걷어내고 TA-Lib 동등성으로 공개 계산 정책을
  바꾼 major cutover다.
- `+talib.0.7.1`: SemVer build metadata로 기준 원본의 TA-Lib 판을 박는다. 런타임
  비교와 Evidence에서 어떤 외부 원본에 맞춘 포트인지 드러내기 위한 표기다.

모든 등록 패턴은 파라미터가 없고 `DEFAULT_PATTERN_REGISTRY`에만 들어간다.
기존 지표 `DEFAULT_REGISTRY`와 이름 집합은 서로소여야 한다.

## §9. 런타임과 CI 정책

런타임과 CI는 TA-Lib에 의존하지 않는다.

- 프로덕션 계산은 `core_lib.patterns.talib_*`의 포트 코드만 사용한다.
- 테스트 대조는 저장소에 고정된 `talib_signals.py` 포획값을 사용한다.
- TA-Lib wrapper와 C library는 포획값을 새로 뜨는 일회용 환경에서만 필요하다.
- 포획값을 새로 뜰 때는 wrapper/C-library version, 국면 fingerprint, bar count가 함께
  바뀌어야 하며, 현재 계열과 fingerprint가 다르면 테스트가 실패해야 한다.

따라서 CI가 TA-Lib을 설치하지 못해도 패턴 계산과 대조 테스트는 돌아야 한다. TA-Lib은
runtime dependency가 아니라 원본과 capture generation dependency다.
