export type ResearchHelpId = "preregistration" | "sweep";

export interface ResearchHelpField {
  label: string;
  name: string;
  description: string;
}

export interface ResearchHelpExample {
  label: string;
  body: string;
}

export interface ResearchHelp {
  title: string;
  triggerAriaLabel: string;
  overview: string;
  concepts: readonly string[];
  fields: readonly ResearchHelpField[];
  example?: string;
  /** One worked example per choice, for settings where the choice is the hard part. */
  examples?: readonly ResearchHelpExample[];
  note?: string;
  caution?: string;
}

export const researchHelpById: Readonly<
  Record<ResearchHelpId, ResearchHelp>
> = {
  preregistration: {
    title: "연구 가설(사전등록) 도움말",
    triggerAriaLabel: "연구 가설 도움말",
    overview:
      "백테스트를 돌리기 전에 이 실행으로 무엇을 기대하는지와 어떤 결과를 성공 또는 실패로 볼지 미리 적어 두는 절차입니다.",
    concepts: [
      "결과를 본 뒤 유리한 쪽으로 해석을 바꾸는 사후 합리화를 막고, 처음 정한 기준으로 정직하게 판정할 수 있습니다.",
      "우연히 좋아 보이는 결과를 진짜 전략 우위로 착각하는 실수를 줄이는 데 도움이 됩니다.",
    ],
    fields: [
      {
        label: "가설",
        name: "hypothesis",
        description:
          '이 실행으로 확인하려는 주장입니다. 예: "레인지 저신뢰 진입을 막으면 큰 손실(tail)이 줄어든다."',
      },
      {
        label: "주지표",
        name: "primary_metric",
        description:
          "성공을 판단할 대표 지표 하나입니다. 폼에서 pf, sortino, calmar_or_mar, mdd 등을 선택할 수 있습니다.",
      },
      {
        label: "방향",
        name: "higher_is_better",
        description:
          "주지표가 높을수록 좋은지를 정합니다. 수익·위험조정수익 지표는 대부분 체크하고, MDD처럼 낮을수록 좋은 지표는 체크를 풉니다.",
      },
      {
        label: "성공·실패 기준",
        name: "success_threshold · failure_threshold",
        description:
          "주지표가 방향에 맞게 성공 임계를 넘으면 성공, 실패 임계에 못 미치면 실패로 판정할 기준값입니다.",
      },
      {
        label: "선언자",
        name: "declared_by",
        description:
          "가설과 기준을 미리 적은 사람이나 팀을 남기는 선택 입력입니다.",
      },
    ],
    note:
      '현재 사전등록의 "잠금(수정 불가로 고정)"은 미구현·유보(3차) 상태입니다. 지금은 실행 제출 메타데이터로 함께 저장됩니다.',
  },
  sweep: {
    title: "스윕 설정 도움말",
    triggerAriaLabel: "스윕 설정 도움말",
    overview:
      "여러 파라미터 조합을 한 번에 자동으로 돌려 성적을 비교하는 기능입니다.",
    concepts: [
      "grid는 파라미터 값을 바꿔 가며 비교하고, walk_forward와 is_oos는 값을 바꾸지 않고 기간을 나눠 같은 설정이 다른 시기에도 통하는지 확인합니다.",
      "그래서 순서를 두면 자연스럽습니다. grid로 후보를 좁히고, walk_forward나 is_oos로 그 후보가 처음 보는 구간에서도 버티는지 확인합니다.",
    ],
    fields: [
      {
        label: "유형",
        name: "type",
        description:
          "grid는 모든 조합을 비교합니다. walk_forward는 folds(2–20)개 시간 구간을 차례로 검증하고, is_oos는 split(0–1) 지점으로 학습 구간과 새 검증 구간을 나눕니다.",
      },
      {
        label: "축",
        name: "axis",
        description:
          "grid에서 바꿔 볼 파라미터와 값 2~20개를 한 축으로 둡니다. 두 축을 사용하면 각 축 값의 모든 조합을 실행합니다.",
      },
      {
        label: "결과",
        name: "runs · oos_degradation · psr",
        description:
          "조합별 성적을 히트맵이나 표로 비교합니다. 대표 run에는 검증 방식에서 계산된 과최적화 집계인 oos_degradation과 PSR이 함께 표시됩니다.",
      },
    ],
    examples: [
      {
        label: "grid — 어떤 값이 좋은지 비교한다",
        body:
          "reward_risk를 [1.5, 2.0, 2.5], atr_stop_multiple을 [1.5, 2.0]으로 두면 " +
          "3×2=6가지 조합이 만들어지고, 같은 기간을 6번 각각 백테스트해 성적을 나란히 " +
          "비교합니다. 조합 수는 100개까지만 실행되며, 같은 파라미터를 두 축에 넣을 수 " +
          "없습니다.",
      },
      {
        label: "walk_forward — 시간을 밀며 반복 검증한다",
        body:
          "2025년 1월부터 6월까지를 folds=3으로 두면 구간을 셋으로 나눠 앞에서부터 " +
          "차례로 검증합니다. 1~2월로 확인하고, 3~4월로 다시 확인하고, 5~6월로 또 " +
          "확인하는 식입니다. 한 시기에만 잘 맞는 설정인지, 시기가 바뀌어도 견디는지를 " +
          "봅니다. 파라미터 조합을 만들지 않고 기준 설정 하나를 여러 구간에 적용합니다.",
      },
      {
        label: "is_oos — 배운 구간과 처음 보는 구간을 가른다",
        body:
          "같은 기간을 split=0.7로 두면 앞 70%(1월 중순까지)를 인샘플, 뒤 30%를 " +
          "아웃오브샘플로 나눕니다. 앞 구간에서 좋아 보이던 설정이 뒤 구간에서도 " +
          "유지되는지 확인합니다. 뒤 구간은 설정을 고를 때 쓰지 않은 데이터라, " +
          "성적이 크게 떨어지면 과적합 신호입니다.",
      },
    ],
    caution:
      '과거 데이터에 "가장 잘 맞는" 조합을 고르면 과적합(overfitting) 위험이 큽니다. 조합 수가 많을수록 우연히 좋아 보이는 결과가 나오기 쉬우며, 미래에도 좋다는 보장은 없습니다. 특히 grid는 집합 검증 증거가 없으므로 반드시 새 구간에서 OOS 재검증을 권장합니다.',
  },
};
