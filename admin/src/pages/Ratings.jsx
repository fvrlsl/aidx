import { useEffect, useState } from "react";
import { Button, Table, Tag, message } from "antd";
import { adminApi } from "../api";

export default function Ratings() {
  const [rows, setRows] = useState([]);
  const load = () => adminApi.pendingRatings().then((r) => setRows(r.items));
  useEffect(() => { load(); }, []);
  return (
    <Table
      rowKey="snapshot_id"
      dataSource={rows}
      columns={[
        { title: "商家", dataIndex: "merchant_name" },
        { title: "原档", dataIndex: "previous_label" },
        { title: "新档", dataIndex: "new_label", render: (v) => <Tag color="orange">{v}</Tag> },
        { title: "分数", dataIndex: "score" },
        { title: "计算时间", dataIndex: "computed_at" },
        {
          title: "操作",
          render: (_, r) => (
            <>
              <Button type="link" onClick={async () => { await adminApi.confirmRating(r.snapshot_id, true); message.success("已确认"); load(); }}>
                确认新档
              </Button>
              <Button type="link" danger onClick={async () => { await adminApi.confirmRating(r.snapshot_id, false); load(); }}>
                暂不生效
              </Button>
            </>
          ),
        },
      ]}
    />
  );
}
