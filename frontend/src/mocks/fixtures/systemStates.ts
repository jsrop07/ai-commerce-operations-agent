import type { SystemStateKind } from "../../components/SystemStates";

export interface SystemStateFixture {
  state: SystemStateKind;
  title: string;
  description: string;
}

export const systemStateFixtures: Record<
  SystemStateKind,
  SystemStateFixture
> = {
  loading: {
    state: "loading",
    title: "데이터를 불러오는 중입니다",
    description: "최신 운영 데이터를 확인하고 있습니다.",
  },

  empty: {
    state: "empty",
    title: "표시할 데이터가 없습니다",
    description: "현재 조건에 해당하는 운영 데이터가 없습니다.",
  },

  stale: {
    state: "stale",
    title: "정보가 오래되었습니다",
    description:
      "최신 정보가 아닐 수 있습니다. 기준 시각을 확인한 뒤 직접 검토하세요.",
  },

  denied: {
    state: "denied",
    title: "안전 정책으로 실행할 수 없습니다",
    description:
      "현재 환경에서는 외부 시스템 변경이 차단되어 있습니다. 내부 확인 업무 또는 제안만 사용할 수 있습니다.",
  },
};