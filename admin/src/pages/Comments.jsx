import { useRef } from "react";
import { ProTable } from "@ant-design/pro-components";
import { Button, message } from "antd";
import { adminApi } from "../api";

export default function Comments() {
  const ref = useRef();
  return (
    <ProTable
      actionRef={ref}
      rowKey="id"
      request={async (p) => {
        const res = await adminApi.userRatings({ comment_status: p.comment_status || "pending", page: p.current, page_size: p.pageSize });
        return { data: res.items, total: res.total, success: true };
      }}
      columns={[
        { title: "商家", dataIndex: "merchant_name", search: false },
        { title: "档位", dataIndex: "level", search: false },
        { title: "身份", dataIndex: "identity_claim", search: false },
        { title: "评论", dataIndex: "comment", search: false },
        { title: "状态", dataIndex: "comment_status", valueEnum: { pending: "待审", approved: "通过", hidden: "隐藏" }, initialValue: "pending" },
        {
          title: "操作",
          search: false,
          render: (_, r) => (
            <>
              <Button size="small" type="link" onClick={async () => { await adminApi.reviewUserRating(r.id, { comment_status: "approved" }); ref.current.reload(); }}>
                通过
              </Button>
              <Button size="small" type="link" danger onClick={async () => { await adminApi.reviewUserRating(r.id, { comment_status: "hidden" }); ref.current.reload(); }}>
                隐藏
              </Button>
            </>
          ),
        },
      ]}
    />
  );
}
