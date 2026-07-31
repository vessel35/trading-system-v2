export type SummaryHelpSectionId = "verdict" | "metrics" | "health" | "cost";

export interface SummaryHelpItem {
  /** Stable key shared with the tile that opens this entry. */
  id: string;
  /** The label printed on the tile, so the reader can match them by eye. */
  label: string;
  /** The standard term, expanded once in both English and Korean. */
  term: string;
  /** What the number is, in plain words. */
  meaning: string;
  /** How to read it: which direction is good, and what it does not tell you. */
  reading: string;
  /** The threshold this system applies, or a note that none is applied. */
  criterion: string;
}

export interface SummaryHelpSection {
  title: string;
  triggerAriaLabel: string;
  overview: string;
  concepts: readonly string[];
  items: readonly SummaryHelpItem[];
  note?: string;
  caution?: string;
}

export const summaryHelpBySection: Readonly<
  Record<SummaryHelpSectionId, SummaryHelpSection>
> = {
  verdict: {
    title: "판정 도움말",
    triggerAriaLabel: "판정 도움말",
    overview:
      "이 실행을 다음 단계로 올려도 되는지에 대한 저장된 판정입니다. 판정은 세 단계를 거칩니다. 먼저 데이터와 증거가 쓸 만한지 확인하고, 그다음 성적이 최소 기준을 넘는지 확인하며, 마지막으로 실행 전에 적어 둔 성공·실패 기준에 비추어 다음 행동을 정합니다.",
    concepts: [
      "판정은 실행이 끝난 시점에 계산되어 저장된 값입니다. 이 화면에서 다시 계산하지 않으므로, 기준이 바뀌면 새로 실행해야 판정도 바뀝니다.",
      "데이터 커버리지나 증거 무결성이 먼저 실패하면 성적은 아예 보지 않고 승격을 막습니다. 믿을 수 없는 데이터에서 나온 좋은 성적은 좋은 성적이 아니기 때문입니다.",
      "카드에 함께 표시되는 한 줄 설명은 왜 그 경로가 나왔는지에 대한 근거이며, 게이트를 통과하지 못한 경우에는 어떤 항목에서 걸렸는지를 알려 줍니다.",
    ],
    items: [
      {
        id: "gate",
        label: "GATE",
        term: "Hard Gate(하드 게이트)",
        meaning:
          "성적이 최소 기준을 모두 넘었는지에 대한 통과·미통과 판정입니다. pass는 통과, not_promotable은 기준 미달, established_regression은 이미 검증을 마친 전략이 원래의 기대 범위에서 벗어난 경우입니다.",
        reading:
          "하나라도 못 넘으면 나머지가 아무리 좋아도 통과하지 못합니다. 못 넘은 항목은 카드 아래의 '저장된 판정 상세 보기'에 이름으로 남으므로, 어디에서 걸렸는지 먼저 확인하십시오.",
        criterion:
          "PF 1.3 이상, Sortino 1.0 이상, Calmar 0.8 이상, SQN 1.6 이상, MDD 절댓값 30% 이하, 파산 확률 0.1% 미만, 기대값(expectancy R) 0 초과, 거래 30건 이상을 모두 만족",
      },
      {
        id: "route",
        label: "ROUTE",
        term: "Decision Route(후속 경로)",
        meaning:
          "실행 전에 등록한 주지표와 성공·실패 기준에 비추어 결정되는 다음 행동입니다. 결과를 보고 나서 기준을 바꾸는 사후 합리화를 막기 위해 기준을 미리 적어 둡니다.",
        reading:
          "promote는 성공 기준을 넘어 다음 단계로 올린다는 뜻이고, partial_keep은 성공과 실패 사이에 놓여 일부만 유지한다는 뜻입니다. retest는 실패 기준에 걸렸지만 우위가 남아 있어 다시 검증한다는 뜻이며, abandon은 실패 기준에 걸렸고 우위도 확인되지 않아 폐기한다는 뜻입니다.",
        criterion: "하드 게이트를 통과하지 못한 실행은 경로가 자동으로 retest가 됨",
      },
      {
        id: "envelope",
        label: "ENVELOPE",
        term: "Strategy Profile Envelope(전략 프로파일 기대 범위)",
        meaning:
          "이 전략이 원래 어떤 모습으로 움직여야 하는지 등록해 둔 승률과 페이오프의 기대 범위에, 이번 결과가 들어왔는지를 봅니다.",
        reading:
          "in_range는 기대한 모습대로 움직였다는 뜻이고, warning은 범위를 벗어났지만 아직 검증 중인 전략이라 경고만 남긴 것입니다. reject는 이미 검증을 마친 전략이 원래 모습에서 벗어난 경우여서 회귀로 보고 막습니다. 성적이 좋아도 범위를 벗어났다면 우연히 다른 국면에 맞아떨어진 것은 아닌지 확인하라는 신호입니다.",
        criterion: "검증을 마친(established) 전략만 범위 이탈이 미통과 사유가 됨",
      },
      {
        id: "oos-degradation",
        label: "OOS degradation",
        term: "Out-of-Sample Degradation(표본 밖 성적 열화)",
        meaning:
          "설정을 고를 때 사용한 구간의 성적에 비해, 고를 때 쓰지 않은 구간의 성적이 얼마나 떨어졌는지를 비율로 나타낸 값입니다.",
        reading:
          "0%면 처음 보는 구간에서도 성적이 유지됐다는 뜻이고, 값이 클수록 과거 데이터에만 맞춰진 설정이라는 뜻입니다. 스윕의 walk_forward와 is_oos에서 계산되어 대표 실행에만 저장되므로, 단일 실행에서는 비어 있는 것이 정상입니다.",
        criterion: "50% 미만(스윕 과최적화 게이트)",
      },
    ],
  },
  metrics: {
    title: "핵심 지표 도움말",
    triggerAriaLabel: "핵심 지표 도움말",
    overview:
      "실행이 끝난 뒤 저장된 성적 지표입니다. 손익은 모두 수수료·슬리피지·펀딩비·강제청산 비용을 뺀 순손익(net) 기준이며, 이 화면에서 다시 계산하지 않고 저장된 값을 그대로 보여 줍니다.",
    concepts: [
      "지표의 재료는 두 가지입니다. 하나는 거래 하나하나의 순손익이고(PF, 승률, SQN 등이 여기서 나옵니다), 다른 하나는 시간에 따라 자본이 어떻게 변했는지를 기록한 자본곡선(equity curve)입니다(MDD, Sharpe, Sortino 등이 여기서 나옵니다).",
      "자본곡선을 쓰는 지표는 하루의 마지막 값으로 일별 리샘플한 뒤 365의 제곱근을 곱해 연율화합니다. 암호화폐 시장은 휴장일이 없어 1년을 365일로 봅니다.",
      "R 배수(R-multiple)는 그 거래에서 처음 각오했던 손실 금액을 1로 놓고 결과를 나눈 값입니다. 진입가와 손절가의 차이에 수량을 곱한 금액이 1R이며, 결과가 2R이면 각오한 손실의 두 배를 벌었다는 뜻입니다.",
      "'통과 기준'은 이 시스템이 실제로 적용하는 하드 게이트 기준값입니다. 기준이 없다고 적힌 지표는 판정에 쓰이지 않고 해석을 돕는 참고 지표입니다.",
    ],
    items: [
      {
        id: "pf",
        label: "PF",
        term: "Profit Factor(수익 팩터)",
        meaning:
          "이익을 낸 거래들의 이익 합계를, 손실을 낸 거래들의 손실 합계(절댓값)로 나눈 값입니다.",
        reading:
          "1.0이면 번 만큼 잃어 본전이고, 2.0이면 손실 1을 낼 때 이익 2를 냈다는 뜻입니다. 클수록 좋습니다. 다만 거래 수가 적으면 우연히 큰 값이 나오기 쉬우므로 거래 수와 함께 보아야 합니다.",
        criterion: "1.3 이상",
      },
      {
        id: "sortino",
        label: "Sortino",
        term: "Sortino Ratio(소르티노 비율)",
        meaning:
          "일별 수익률의 평균을 하락 변동성으로 나눈 뒤 연율화한 값입니다. 하락 변동성은 마이너스 수익률만 모아 계산한 표준편차입니다.",
        reading:
          "위로 크게 튀는 변동은 위험으로 세지 않고 아래로 떨어지는 변동만 위험으로 봅니다. 그래서 같은 수익이라면 손실 구간이 얕고 드물수록 값이 높아집니다. 클수록 좋습니다.",
        criterion: "1.0 이상",
      },
      {
        id: "calmar",
        label: "Calmar / MAR",
        term: "Calmar Ratio(칼마 비율), 같은 계산을 장기 구간에 적용할 때 부르는 이름이 MAR",
        meaning:
          "연평균 복리 수익률(CAGR)을 최대낙폭의 절댓값으로 나눈 값입니다. 최근 3년 구간을 기준으로 계산하고, 실행 기간이 3년보다 짧으면 전체 기간을 씁니다.",
        reading:
          "가장 크게 물렸던 폭 1만큼을 감수하고 1년에 얼마를 벌었는지를 나타냅니다. 1.0이면 연수익과 최대낙폭이 같은 크기라는 뜻입니다. 클수록 좋습니다.",
        criterion: "0.8 이상",
      },
      {
        id: "sqn",
        label: "SQN",
        term: "SQN(System Quality Number, 시스템 품질 지수)",
        meaning:
          "R 배수의 평균을 R 배수의 표준편차로 나눈 뒤, 거래 수의 제곱근을 곱한 값입니다. 표본이 많다고 값이 끝없이 커지지 않도록 거래 수는 100건까지만 반영합니다.",
        reading:
          "결과가 들쭉날쭉하지 않고 일관될수록, 그리고 표본이 많을수록 높아집니다. 거래가 30건 미만이면 판단할 표본이 부족하다고 보고 계산하지 않아 빈 값으로 표시됩니다.",
        criterion: "1.6 이상(거래 30건 이상일 때만 산출)",
      },
      {
        id: "sharpe",
        label: "Sharpe",
        term: "Sharpe Ratio(샤프 비율)",
        meaning:
          "일별 수익률의 평균을 표준편차로 나눈 뒤 연율화한 값입니다. 무위험 수익률은 0으로 둡니다.",
        reading:
          "수익을 변동성으로 나눈, 가장 널리 쓰이는 위험조정 수익 지표입니다. 위로 튀는 변동도 위험으로 세기 때문에 대개 Sortino보다 낮게 나옵니다.",
        criterion: "게이트 기준 없음(참고 지표)",
      },
      {
        id: "psr",
        label: "PSR",
        term: "PSR(Probabilistic Sharpe Ratio, 확률적 샤프 비율)",
        meaning:
          "관측된 Sharpe가 0보다 실제로 크다고 볼 수 있는 확률입니다. 수익률 분포가 한쪽으로 치우친 정도(왜도)와 꼬리가 두꺼운 정도(첨도)를 보정하고, 스윕에서 시도한 조합 수만큼 다중검정 보정을 적용합니다.",
        reading:
          "0.95는 관측된 성적이 우연이 아닐 확률이 95%라는 뜻입니다. 조합을 많이 시도할수록 보정이 커져 값이 낮아지는데, 이것이 여러 번 던져 나온 우연을 걸러 내는 장치입니다. 스윕의 대표 실행에만 저장되므로 단일 실행에서는 비어 있습니다.",
        criterion: "0.95 이상(스윕 과최적화 게이트)",
      },
      {
        id: "mdd",
        label: "MDD",
        term: "MDD(Maximum Drawdown, 최대낙폭)",
        meaning:
          "자본곡선이 그때까지의 최고점 대비 가장 크게 떨어진 폭을 백분율로 나타낸 값입니다.",
        reading:
          "−12.3%는 고점 대비 자본이 12.3%까지 줄어든 적이 있다는 뜻입니다. 0에 가까울수록 좋습니다. 실제로 버텨야 하는 손실의 크기이므로, 감당할 수 없는 값이면 수익이 커도 쓸 수 없는 전략입니다.",
        criterion: "절댓값 30% 이하",
      },
      {
        id: "ror",
        label: "Risk of ruin",
        term: "Risk of Ruin(파산 확률)",
        meaning:
          "이 실행에서 나온 R 배수들을 무작위로 다시 뽑아 거래 순서를 10,000번 새로 만들어 보고, 그중 고점 대비 60% 손실에 도달한 경우의 비율입니다. 거래당 위험은 자본의 1%로 가정하며, 같은 입력이면 항상 같은 값이 나오도록 난수 시드를 고정합니다.",
        reading:
          "순서가 나쁘게 배열되어 손실이 몰렸을 때 계좌가 회복 불가능해질 확률의 추정치입니다. 0%에 가까울수록 좋습니다.",
        criterion: "0.1% 미만",
      },
      {
        id: "ulcer",
        label: "Ulcer",
        term: "Ulcer Index(얼서 지수)",
        meaning:
          "매 시점의 고점 대비 낙폭을 백분율로 바꾼 뒤 제곱평균제곱근을 낸 값입니다.",
        reading:
          "MDD가 가장 깊었던 한 번만 본다면, 얼서 지수는 얼마나 깊게 그리고 얼마나 오래 물려 있었는지를 함께 봅니다. 낮을수록 좋고, MDD가 비슷한 두 실행을 구분할 때 유용합니다.",
        criterion: "게이트 기준 없음(참고 지표)",
      },
      {
        id: "kelly",
        label: "Kelly",
        term: "Kelly Criterion(켈리 비율)",
        meaning:
          "승률과 페이오프(평균 이익을 평균 손실로 나눈 값)로 계산한 이론상 최적 베팅 비율입니다. 승률에서 (1 − 승률)을 페이오프로 나눈 값을 뺀 것입니다.",
        reading:
          "0.2는 이론상 자본의 20%를 걸 때 장기 성장률이 가장 커진다는 뜻이지만, 그대로 쓰면 변동이 지나치게 커서 실무에서는 그 일부만 씁니다. 음수이면 기대값이 마이너스라 걸지 말아야 한다는 신호입니다. 실제 진입 수량은 이 값이 아니라 자금 관리 정책이 정합니다.",
        criterion: "게이트 기준 없음(참고 지표)",
      },
      {
        id: "win-rate",
        label: "Win rate",
        term: "Win Rate(승률)",
        meaning: "종료된 거래 가운데 순손익이 0보다 큰 거래의 비율입니다.",
        reading:
          "승률만으로는 좋고 나쁨을 판단할 수 없습니다. 추세추종 전략은 승률이 35%여도 이익 거래가 크게 나서 돈을 벌고, 반대로 승률이 80%여도 한 번의 손실이 크면 잃습니다. 반드시 PF나 페이오프와 함께 보아야 합니다.",
        criterion: "게이트 기준 없음(전략 프로파일 기대 범위와 비교)",
      },
      {
        id: "trades",
        label: "Trades",
        term: "Trade Count(거래 수)",
        meaning:
          "진입해서 청산까지 끝난 거래의 수입니다. 아래 보조 표시는 이익 거래 수(W), 손실 거래 수(L), 그리고 R 배수 계산에서 제외된 거래 수(R 제외)입니다.",
        reading:
          "R 제외는 최초 위험이 없거나 0이어서 R 배수를 만들 수 없었던 거래입니다. SQN과 파산 확률은 R 배수가 있는 거래만 표본으로 쓰므로, R 제외가 많으면 두 지표의 표본이 표시된 거래 수보다 적습니다.",
        criterion: "30건 이상",
      },
    ],
    note: "PSR과 OOS 열화는 여러 실행을 묶어야 계산할 수 있는 과최적화 집계입니다. 스윕의 대표 실행에만 저장되므로 단일 실행에서 비어 있는 것은 오류가 아닙니다.",
    caution:
      "지표 하나만 보고 판단하지 마십시오. 거래가 몇 건뿐이면 PF는 얼마든지 커질 수 있고, 기간이 짧으면 MDD는 아직 나쁜 국면을 겪지 않은 것일 뿐일 수 있습니다. 이 시스템이 거래 30건과 여러 기준을 한꺼번에 요구하는 이유입니다.",
  },
  health: {
    title: "데이터 건강도 도움말",
    triggerAriaLabel: "데이터 건강도 도움말",
    overview:
      "성적이 좋은지가 아니라 이 성적을 믿어도 되는지를 보는 칸입니다. 사용한 시세 데이터에 빠진 구간이 얼마나 있었는지, 그리고 저장된 증거 파일이 자체 검사를 통과했는지를 나타냅니다.",
    concepts: [
      "백테스트는 정해진 간격의 캔들을 하나씩 따라가며 진행합니다. 거래소 점검이나 수집 누락으로 캔들이 비면 그 시간 동안 전략은 아무것도 보지 못하므로, 그 구간을 포함한 성적은 실제와 달라집니다.",
      "그래서 실행이 끝나면 캔들이 몇 개 있어야 했고 실제로 몇 개가 있었는지, 빠진 구간이 얼마나 길게 이어졌는지를 함께 저장합니다. 기준에 못 미치면 지표가 좋아도 판정은 not_promotable이 됩니다.",
      "무결성 검사는 저장된 증거 파일이 스스로 앞뒤가 맞는지 확인하는 여섯 가지 검사입니다. 현금과 포지션 평가액의 합이 총자본과 같은지, 기록의 시간 순서가 맞는지, 비용이 한 번만 반영됐는지, 순손익이 비용을 뺀 값인지, 같은 입력에서 같은 결과가 나오는지, 필수 기록이 빠지지 않았는지를 봅니다.",
    ],
    items: [
      {
        id: "coverage",
        label: "Coverage",
        term: "Data Coverage(데이터 커버리지)",
        meaning:
          "실행 구간에 있어야 할 캔들 수 대비 실제로 존재한 캔들 수의 비율입니다. 아래 보조 표시는 실제로 관측한 개수와 있어야 했던 개수입니다.",
        reading:
          "100%면 빠진 캔들이 하나도 없다는 뜻입니다. 값이 낮을수록 전략이 보지 못한 시간이 많았다는 뜻이므로 성적의 신뢰도가 떨어집니다.",
        criterion: "95% 이상",
      },
      {
        id: "integrity",
        label: "Integrity",
        term: "Evidence Integrity(증거 무결성)",
        meaning:
          "증거 파일의 여섯 가지 자체 검사 결과입니다. 모두 통과하면 passed, 하나라도 실패하면 diagnostic_only가 됩니다.",
        reading:
          "diagnostic_only는 참고로 볼 수는 있으나 판정 근거로는 쓸 수 없다는 뜻입니다. 어떤 검사가 왜 실패했는지는 이 카드 아래의 '무결성 실패 상세'와 '무결성·비용' 탭에서 확인할 수 있습니다.",
        criterion: "passed여야 승격 가능",
      },
      {
        id: "max-gap",
        label: "Max gap",
        term: "Max Consecutive Gap(최대 연속 결측)",
        meaning:
          "빠진 캔들이 끊기지 않고 이어진 가장 긴 구간이며, 봉 개수와 초 단위로 함께 표시합니다.",
        reading:
          "전체 커버리지가 높아도 한 곳이 길게 비어 있으면 그 기간의 거래는 믿기 어렵습니다. 예를 들어 1시간봉에서 24개면 하루가 통째로 비었다는 뜻입니다.",
        criterion: "86,400초(24시간) 이하",
      },
      {
        id: "gap-exits",
        label: "Gap exits",
        term: "Data Gap Exit(데이터 공백 청산)",
        meaning:
          "포지션을 들고 있는 동안 데이터가 끊겨 엔진이 강제로 청산 처리한 거래의 수입니다. 아래 보조 표시의 source absent는 해당 구간의 1분봉이 하나도 없어 원천 데이터 자체가 없었던 구간의 수입니다.",
        reading:
          "이 값이 0보다 크면 그만큼의 거래는 전략의 판단이 아니라 데이터 사정으로 끝났다는 뜻이므로, 성적을 해석할 때 감안해야 합니다. 해당 거래의 청산 사유는 거래 탭에서 DATA_GAP으로 표시됩니다.",
        criterion: "적을수록 좋음(별도 통과 기준 없음)",
      },
    ],
    note: "일부 1분봉만 있어 버린 구간의 수(partial bucket)와 펀딩 정산 시점을 관측하지 못한 횟수는 '무결성·비용' 탭에서 함께 볼 수 있습니다.",
  },
  cost: {
    title: "비용 분해 도움말",
    triggerAriaLabel: "비용 분해 도움말",
    overview:
      "매매 자체의 손익에서 어떤 비용이 얼마나 빠져나가 최종 손익이 되었는지를 보여 줍니다. 화면의 모든 성적 지표는 비용을 뺀 뒤의 순손익을 기준으로 계산합니다.",
    concepts: [
      "총손익에서 수수료와 슬리피지, 펀딩비, 강제청산 비용을 빼면 순손익이 됩니다. 백테스트에서 비용을 빼먹으면 실제로는 지는 전략도 이기는 것처럼 보이기 때문에, 이 시스템은 모든 판정을 순손익으로 합니다.",
      "표시되는 값은 저장된 문자열 그대로이며, 화면에서 다시 더하거나 반올림하지 않습니다. 금액은 소수점 아래 여덟 자리까지 정확히 보존됩니다.",
    ],
    items: [
      {
        id: "gross-pnl",
        label: "Gross PnL",
        term: "Gross Profit and Loss(총손익)",
        meaning:
          "진입가와 청산가의 차이에 수량을 곱해 모든 거래에 대해 더한, 비용을 빼기 전의 매매 손익입니다.",
        reading:
          "슬리피지를 두 번 세지 않도록 실제 체결가가 아니라 주문 기준가로 계산합니다. 슬리피지로 인한 손실은 아래의 Slippage 항목에서 따로 빠집니다.",
        criterion: "판정에 직접 쓰이지 않음(순손익의 출발점)",
      },
      {
        id: "fee",
        label: "Fee",
        term: "Trading Fee(거래 수수료)",
        meaning:
          "체결 금액에 거래소 수수료율을 곱한 금액이며, 진입과 청산 양쪽에서 발생한 합계입니다.",
        reading:
          "거래를 자주 할수록 커집니다. 짧은 시간에 많이 사고파는 전략이라면 이 항목만으로 총손익이 사라질 수 있으므로 반드시 확인해야 합니다. 적용된 요율은 실행 설정에 저장되어 있습니다.",
        criterion: "판정에 직접 쓰이지 않음(순손익에서 차감)",
      },
      {
        id: "slippage",
        label: "Slippage",
        term: "Slippage(슬리피지)",
        meaning:
          "주문하려던 기준가와 실제 체결가의 차이 때문에 생기는 비용입니다. 진입과 청산에 각각 설정된 비율을 적용합니다.",
        reading:
          "호가가 얇거나 변동이 심할 때 실제로 겪는 불리한 체결을 모형으로 반영한 값입니다. 값이 0이면 비용을 0으로 설정하고 돌린 것이므로, 실전 성적을 낙관적으로 보고 있다는 뜻입니다.",
        criterion: "판정에 직접 쓰이지 않음(순손익에서 차감)",
      },
      {
        id: "funding",
        label: "Funding",
        term: "Funding Cost(펀딩비)",
        meaning:
          "무기한 선물에서 8시간마다(협정 세계시 기준 0시·8시·16시) 롱과 숏 사이에 오가는 정산 금액의 합계입니다. 포지션 수량에 그때의 가격과 펀딩 비율을 곱해 계산합니다.",
        reading:
          "양수이면 낸 금액이고 음수이면 오히려 받은 금액입니다. 포지션을 오래 들고 있는 전략일수록 누적이 커지므로, 며칠씩 보유하는 추세추종 전략에서는 무시할 수 없는 항목입니다.",
        criterion: "판정에 직접 쓰이지 않음(순손익에서 차감)",
      },
      {
        id: "liquidation-penalty",
        label: "Liquidation penalty",
        term: "Liquidation Penalty(강제청산 비용)",
        meaning:
          "증거금이 부족해 거래소가 포지션을 강제로 청산했을 때 추가로 발생하는 비용입니다.",
        reading:
          "0이 아니라면 손절이 아니라 증거금 부족으로 끝난 거래가 있었다는 뜻이므로, 레버리지나 수량 산정을 다시 확인해야 합니다.",
        criterion: "판정에 직접 쓰이지 않음(순손익에서 차감)",
      },
      {
        id: "net-pnl",
        label: "Net PnL",
        term: "Net Profit and Loss(순손익)",
        meaning:
          "총손익에서 수수료·슬리피지·펀딩비·강제청산 비용을 모두 뺀 최종 손익입니다.",
        reading:
          "이 화면의 PF, 승률, MDD를 비롯한 모든 지표가 이 값을 씁니다. 종료 자본에서 시작 자본을 뺀 금액과 같아야 하며, 다르면 무결성 검사에서 걸립니다.",
        criterion: "모든 성적 지표의 기준값",
      },
      {
        id: "initial-capital",
        label: "Initial capital",
        term: "Initial Capital(시작 자본)",
        meaning: "실행을 시작할 때 주어진 자본입니다.",
        reading:
          "수량 산정의 기준이 되는 금액이므로, 같은 전략이라도 이 값이 다르면 거래 수량과 절대 손익이 달라집니다. 비율로 표시되는 지표(MDD, 승률 등)는 이 값에 좌우되지 않습니다.",
        criterion: "판정에 직접 쓰이지 않음(계산의 출발점)",
      },
      {
        id: "final-equity",
        label: "Final equity",
        term: "Final Equity(종료 자본)",
        meaning:
          "실행 마지막 시점의 자본이며, 남아 있던 포지션을 정리한 뒤의 값입니다.",
        reading:
          "시작 자본과의 차이가 순손익 합계와 일치해야 합니다. 두 값이 어긋나면 회계 항등식 검사가 실패하고 무결성이 diagnostic_only로 내려갑니다.",
        criterion: "판정에 직접 쓰이지 않음(회계 항등식으로 검증)",
      },
    ],
  },
};
