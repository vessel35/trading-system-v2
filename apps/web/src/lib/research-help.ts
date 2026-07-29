export type ResearchHelpId = "preregistration" | "sweep";

export interface ResearchHelpField {
  label: string;
  name: string;
  description: string;
}

export interface ResearchHelp {
  title: string;
  triggerAriaLabel: string;
  overview: string;
  concepts: readonly string[];
  fields: readonly ResearchHelpField[];
  example?: string;
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
      "grid는 모든 값의 조합을 격자로 실행하고, walk_forward는 시간 구간을 앞으로 밀며 검증하며, is_oos는 인샘플(IS)과 아웃오브샘플(OOS)로 나눠 검증합니다.",
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
    example:
      "예: reward_risk=[1.5, 2.0, 2.5], atr_stop_multiple=[1.5, 2.0]이면 3×2=6개 조합을 각각 백테스트합니다.",
    caution:
      '과거 데이터에 "가장 잘 맞는" 조합을 고르면 과적합(overfitting) 위험이 큽니다. 조합 수가 많을수록 우연히 좋아 보이는 결과가 나오기 쉬우며, 미래에도 좋다는 보장은 없습니다. 특히 grid는 집합 검증 증거가 없으므로 반드시 새 구간에서 OOS 재검증을 권장합니다.',
  },
};
