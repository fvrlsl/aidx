import { useRef } from "react";
import { ModalForm, ProFormSelect, ProFormText, ProFormTextArea, ProTable } from "@ant-design/pro-components";
import { Button, Modal, Space, Tag, message } from "antd";
import { adminApi } from "../api";

export default function Merchants() {
  const ref = useRef();
  return (
    <ProTable
      actionRef={ref}
      rowKey="id"
      toolBarRender={() => [
        <ModalForm
          key="n"
          title="新建商家"
          trigger={<Button type="primary">新建</Button>}
          onFinish={async (v) => {
            await adminApi.createMerchant({ ...v, aliases: (v.aliases || "").split(/[,，]/).filter(Boolean) });
            message.success("已创建");
            ref.current.reload();
            return true;
          }}
        >
          <ProFormText name="canonical_name" label="标准名" rules={[{ required: true }]} />
          <ProFormText name="industry" label="行业" />
          <ProFormText name="region" label="地区" />
          <ProFormText name="aliases" label="别名（逗号分隔）" />
          <ProFormTextArea name="intro" label="简介" />
        </ModalForm>,
      ]}
      request={async (p) => {
        const res = await adminApi.merchants({ q: p.name, status: p.status, page: p.current, page_size: p.pageSize });
        return { data: res.items, total: res.total, success: true };
      }}
      columns={[
        { title: "ID", dataIndex: "id", width: 70, search: false },
        { title: "名称", dataIndex: "name" },
        { title: "行业", dataIndex: "industry", search: false },
        { title: "评级", dataIndex: "overall_label", search: false },
        { title: "状态", dataIndex: "status", valueEnum: { published: "已发布", pending: "待审", draft: "草稿", merged: "已合并" } },
        {
          title: "别名",
          search: false,
          render: (_, r) => (r.aliases || []).map((a) => <Tag key={a.id}>{a.alias}{a.status === "pending" ? "(待审)" : ""}</Tag>),
        },
        {
          title: "操作",
          search: false,
          render: (_, r) => (
            <Space>
              {r.status === "pending" ? (
                <Button size="small" type="link" onClick={async () => { await adminApi.merchantAction(r.id, "publish"); ref.current.reload(); }}>
                  发布
                </Button>
              ) : null}
              <Button size="small" type="link" onClick={async () => { await adminApi.merchantAction(r.id, "recompute"); message.success("已重算"); ref.current.reload(); }}>
                重算
              </Button>
              <Button
                size="small"
                type="link"
                onClick={() => {
                  let to;
                  Modal.confirm({
                    title: `把「${r.name}」合并到`,
                    content: <input placeholder="目标商家 ID" onChange={(e) => (to = e.target.value)} style={{ width: "100%" }} />,
                    onOk: async () => {
                      await adminApi.merge({ from_id: r.id, to_id: Number(to), reason: "运营合并" });
                      message.success("已合并");
                      ref.current.reload();
                    },
                  });
                }}
              >
                合并
              </Button>
            </Space>
          ),
        },
      ]}
    />
  );
}
