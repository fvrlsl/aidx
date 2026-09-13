import { useRef } from "react";
import { ProTable } from "@ant-design/pro-components";
import { Button, message } from "antd";
import { adminApi } from "../api";

export default function Tips() {
  const ref = useRef();
  return (
    <ProTable
      actionRef={ref}
      rowKey="id"
      request={async (p) => {
        const res = await adminApi.tips({ status: p.status || "new", page: p.current, page_size: p.pageSize });
        return { data: res.items, total: res.total, success: true };
      }}
      columns={[
        { title: "商家原文", dataIndex: "merchant_name_raw", search: false },
        { title: "链接", dataIndex: "url", search: false, ellipsis: true },
        { title: "说明", dataIndex: "text", search: false },
        { title: "状态", dataIndex: "status", valueEnum: { new: "新", accepted: "采纳", rejected: "拒绝" }, initialValue: "new" },
        {
          title: "操作",
          search: false,
          render: (_, r) => (
            <>
              <Button type="link" onClick={async () => { const res = await adminApi.handleTip(r.id, "accept"); message.success(`已采纳 ${res.pipeline?.status || ""}`); ref.current.reload(); }}>
                采纳并入池
              </Button>
              <Button type="link" danger onClick={async () => { await adminApi.handleTip(r.id, "reject"); ref.current.reload(); }}>
                拒绝
              </Button>
            </>
          ),
        },
      ]}
    />
  );
}
