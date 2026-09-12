import { useEffect, useState } from "react";
import { ProCard, StatisticCard } from "@ant-design/pro-components";
import { adminApi } from "../api";

export default function Dashboard() {
  const [d, setD] = useState({});
  useEffect(() => {
    adminApi.dashboard().then(setD);
  }, []);
  const items = [
    ["已发布商家", d.merchants],
    ["待审商家", d.merchants_pending],
    ["待处理素材", d.sources_new],
    ["依据草稿", d.evidence_draft],
    ["跨档待确认", d.ratings_need_confirm],
    ["待审评论", d.comments_pending],
    ["未关工单", d.feedback_open],
    ["新线索", d.tips_new],
  ];
  return (
    <>
      <StatisticCard.Group>
        {items.map(([t, v]) => (
          <StatisticCard key={t} statistic={{ title: t, value: v ?? "-" }} />
        ))}
      </StatisticCard.Group>
      <ProCard title="评级分布" style={{ marginTop: 16 }}>
        {Object.entries(d.level_distribution || {}).map(([k, v]) => (
          <span key={k} style={{ marginRight: 16 }}>
            {k}：{v}
          </span>
        ))}
      </ProCard>
    </>
  );
}
