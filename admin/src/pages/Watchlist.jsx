import { useRef } from "react";
import { ModalForm, ProFormSelect, ProFormText, ProTable } from "@ant-design/pro-components";
import { Button, Space, message } from "antd";
import { adminApi } from "../api";

export default function Watchlist() {
  const ref = useRef();
  return (
    <ProTable
      actionRef={ref}
      rowKey="id"
      search={false}
      toolBarRender={() => [
        <Button key="p0" onClick={async () => { const r = await adminApi.runWatch("P0"); message.success(`P0 新增 ${r.new_sources} 条`); ref.current.reload(); }}>
          立即跑 P0
        </Button>,
        <ModalForm
          key="n"
          title="新增监控"
          trigger={<Button type="primary">新增</Button>}
          onFinish={async (v) => {
            await adminApi.createWatch({ merchant_id: Number(v.merchant_id), keywords: v.keywords.split(/[,，]/).filter(Boolean), priority: v.priority, rss_urls: [] });
            ref.current.reload();
            return true;
          }}
        >
          <ProFormText name="merchant_id" label="商家 ID" rules={[{ required: true }]} />
          <ProFormText name="keywords" label="关键词（逗号）" />
          <ProFormSelect name="priority" label="优先级" options={["P0", "P1", "P2"].map((x) => ({ label: x, value: x }))} />
        </ModalForm>,
      ]}
      request={async () => {
        const res = await adminApi.watchlist();
        return { data: res.items, success: true };
      }}
      columns={[
        { title: "商家", dataIndex: "merchant_name" },
        { title: "关键词", dataIndex: "keywords", render: (v) => (v || []).join("、") },
        { title: "优先级", dataIndex: "priority" },
        { title: "启用", dataIndex: "enabled", render: (v) => (v ? "是" : "否") },
        { title: "最近命中", dataIndex: "last_hit_at" },
        {
          title: "操作",
          render: (_, r) => (
            <Space>
              <Button type="link" danger onClick={async () => { await adminApi.deleteWatch(r.id); ref.current.reload(); }}>
                删除
              </Button>
            </Space>
          ),
        },
      ]}
    />
  );
}
