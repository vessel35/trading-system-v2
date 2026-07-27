export interface StrategyParameterHelp {
  name: string;
  defaultAndRange: string;
  meaning: string;
  formulas: readonly string[];
  guidance: string;
}

export interface StrategyHelp {
  displayName: string;
  overview: string;
  parameters: readonly StrategyParameterHelp[];
  sizing: {
    description: string;
    formulas: readonly string[];
  };
  example: {
    input: string;
    steps: readonly string[];
  };
}

export const strategyParamHelpById: Readonly<Record<string, StrategyHelp>> = {
  "vessel-reference": {
    displayName: "Vessel Reference",
    overview:
      "EMA 레짐 추종 — EMA(9)가 EMA(21) 위면 롱, 아래면 숏 진입하며 교차 이탈 시 청산합니다. ATR(14) 기반 고정 손절·목표를 사용하고 트레일링은 없습니다.",
    parameters: [
      {
        name: "atr_stop_multiple",
        defaultAndRange: "기본 2.0 · 범위 0.1–10.0 · number",
        meaning: "손절 폭을 ATR의 몇 배로 둘지 정하는 변동성 기반 보호 폭입니다.",
        formulas: [
          "손절폭(stop_distance) = ATR(14) × atr_stop_multiple",
          "롱: 손절가 = 종가 − 손절폭",
          "숏: 손절가 = 종가 + 손절폭",
        ],
        guidance:
          "클수록 손절이 넓어져 흔들림에 덜 잘리지만 단위당 손실이 커지고, 위험예산 고정 시 수량은 줄어듭니다.",
      },
      {
        name: "reward_risk",
        defaultAndRange: "기본 2.0 · 범위 0.1–10.0 · number",
        meaning: "목표를 위험(손절폭)의 몇 배로 둘지 정하는 손익비입니다.",
        formulas: [
          "목표폭(reward_distance) = 손절폭 × reward_risk",
          "롱: 목표가 = 종가 + 목표폭",
          "숏: 목표가 = 종가 − 목표폭",
        ],
        guidance: "2.0이면 목표가 위험의 2배인 2:1 손익비입니다.",
      },
      {
        name: "leverage",
        defaultAndRange: "기본 1 · 범위 1–100 · integer",
        meaning:
          "필요 증거금과 청산가에 영향을 주는 레버리지입니다. 진입·청산 신호 로직에는 영향을 주지 않습니다.",
        formulas: [
          "롱 청산가 = 진입가 × (1 − 1/leverage + mmr)",
          "숏 청산가 = 진입가 × (1 + 1/leverage − mmr)",
        ],
        guidance: "높을수록 청산가가 진입가에 가까워져 위험이 커집니다.",
      },
    ],
    sizing: {
      description:
        "RunConfig의 risk_based 사이징 기준입니다. risk_per_trade는 (0, 0.01] 범위로 최대 1%입니다.",
      formulas: [
        "수량 = risk_per_trade × 자본 / 손절폭",
        "1R(초기 위험 금액) = |진입가 − 손절가| × 수량 = 손절폭 × 수량",
      ],
    },
    example: {
      input:
        "입력: 자본 10,000 · risk_per_trade 1%(0.01) · 진입 종가 42,000 · ATR(14) 500 · atr_stop_multiple 2.0 · reward_risk 2.0 · leverage 3 · mmr 0.5%(0.005)",
      steps: [
        "손절폭 = 500 × 2.0 = 1,000 → 롱 손절가 = 42,000 − 1,000 = 41,000",
        "목표폭 = 1,000 × 2.0 = 2,000 → 롱 목표가 = 42,000 + 2,000 = 44,000",
        "수량 = 0.01 × 10,000 / 1,000 = 0.1 → 1R = 1,000 × 0.1 = 100 (자본의 1% ✓)",
        "청산가 = 42,000 × (1 − 1/3 + 0.005) = 42,000 × 0.671667 ≈ 28,210",
      ],
    },
  },
};
