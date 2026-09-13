import { useRef } from "react";
import { ProTable } from "@ant-design/pro-components";
import { Button, Input, Modal, message } from "antd";
import { adminApi } from "../api";

export default function Feedback() {
  const ref = useRef();
  const reply = (r) => {
    let text = "";
    Modal.confirm({
      title: `回复 ${r.ticket_no}`,
      content: <Input.TextArea rows={4} onChange={(e) => (text = e.target.value)} />,
      onOk: async () => {
        await adminApi.handleFeedback(r.id, { status: "replied", action: "reject", reply: text });
        message.success("已回复");
        ref.current.reload();
      },
    });
  };
  return (
    <ProTable
      actionRef={ref}
      rowKey="id"
      request={async (p) => {
        const res = await adminApi.feedback({ status: p.status, page: p.current, page_size: p.pageSize });
        return { data: res.items, total: res.total, success: true };
      }}
      columns={[
        { title: "工单号", dataIndex: "ticket_no", search: false },
        { title: "商家", dataIndex: "merchant_name", search: false },
        { title: "类型", dataIndex: "type_label", search: false },
        { title: "联系人", dataIndex: "contact_name", search: false },
        { title: "电话", dataIndex: "contact_phone", search: false },
        { title: "内容", dataIndex: "content", ellipsis: true, search: false },
        { title: "状态", dataIndex: "status", valueEnum: { new: "新", reviewing: "处理中", replied: "已回复", closed: "关闭" } },
        { title: "操作", search: false, render: (_, r) => <Button type="link" onClick={() => reply(r)}>回复</Button> },
      ]}
    />
  );
}
