import { useRef } from "react";
import { ProTable } from "@ant-design/pro-components";
import { Button, Tag, message } from "antd";
import { adminApi } from "../api";

export default function Evidence() {
  const ref = useRef();
  const act = async (id, action) => {
    await adminApi.reviewEvidence(id, { action });
    message.success("已处理");
    ref.current.reload();
  };
  return (
    <ProTable
      actionRef={ref}
      rowKey="id"
      request={async (p) => {
        const res = await adminApi.evidence({ status: p.status || "draft", merchant_id: p.merchant_id, page: p.current, page_size: p.pageSize });
        return { data: res.items, total: res.total, success: true };
      }}
      columns={[
        { title: "ID", dataIndex: "id", width: 70, search: false },
        { title: "商家", dataIndex: "merchant_name", search: false },
        { title: "商家ID", dataIndex: "merchant_id", hideInTable: true },
        { title: "维度", dataIndex: "dimension_label", search: false },
        { title: "摘要", dataIndex: "summary", ellipsis: true, search: false },
        { title: "级别", dataIndex: "source_level", search: false, width: 70 },
        {
          title: "正负",
          dataIndex: "polarity",
          search: false,
          render: (v) => <Tag color={v > 0 ? "green" : "red"}>{v > 0 ? "正面" : "负面"}</Tag>,
        },
        {
          title: "状态",
          dataIndex: "status",
          valueType: "select",
          initialValue: "draft",
          valueEnum: { draft: "草稿", approved: "已发布", rejected: "拒绝", archived: "归档" },
        },
        {
          title: "操作",
          search: false,
          render: (_, r) =>
            r.status === "draft" ? (
              <>
                <Button size="small" type="link" onClick={() => act(r.id, "approve")}>
                  通过
                </Button>
                <Button size="small" type="link" danger onClick={() => act(r.id, "reject")}>
                  拒绝
                </Button>
              </>
            ) : (
              <Button size="small" type="link" onClick={() => act(r.id, "archive")}>
                归档
              </Button>
            ),
        },
      ]}
    />
  );
}
