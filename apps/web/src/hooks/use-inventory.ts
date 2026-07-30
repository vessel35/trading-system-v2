import { useQuery } from "@tanstack/react-query";

import { apiClient, requestErrorMessage } from "../api/client";

export function useInventory(dataSource: string) {
  return useQuery({
    queryKey: ["inventory", dataSource],
    enabled: Boolean(dataSource),
    queryFn: async () => {
      const { data, error } = await apiClient.GET(
        "/api/v1/data-sources/{data_source}/inventory",
        {
          params: { path: { data_source: dataSource } },
        },
      );
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("데이터 인벤토리 응답이 비어 있습니다.");
      return data;
    },
  });
}
