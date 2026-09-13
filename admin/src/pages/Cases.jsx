import { useRef } from "react";
import { ModalForm, ProFormSelect, ProFormText, ProFormTextArea, ProTable } from "@ant-design/pro-components";
import { Button, message } from "antd";
import { adminApi } from "../api";

export default function Cases() {
  const ref = useRef();
  return (
    <ProTable
      actionRef={ref}
      rowKey="id"
      search={false}
      toolBarRender={() => [
        <ModalForm
          key="n"
          title="新建案例"
          trigger={<Button type="primary">新建</Button>}
          onFinish={async (v) => {
            await adminApi.createCase({
              ...v,
              merchant_ids: (v.merchant_ids || "").split(/[,，]/).map(Number).filter(Boolean),
              timeline: [],
            });
            message.success("已创建");
            ref.current.reload();
            return true;
          }}
        >
          <ProFormText name="title" label="标题" rules={[{ required: true }]} />
          <ProFormText name="subtitle" label="副标题" />
          <ProFormSelect name="type" label="类型" options={[
            { label: "正面标杆", value: "benchmark" },
            { label: "争议反转", value: "reversal" },
            { label: "负面警示", value: "warning" },
          ]} />
          <ProFormSelect name="status" label="状态" options={[{ label: "草稿", value: "draft" }, { label: "发布", value: "published" }]} />
          <ProFormText name="merchant_ids" label="关联商家 ID（逗号）" />
          <ProFormTextArea name="body" label="正文" />
        </ModalForm>,
      ]}
      request={async (p) => {
        const res = await adminApi.cases({ page: p.current, page_size: p.pageSize });
        return { data: res.items, total: res.total, success: true };
      }}
      columns={[
        { title: "ID", dataIndex: "id", width: 70 },
        { title: "标题", dataIndex: "title" },
        { title: "类型", dataIndex: "type" },
        { title: "状态", dataIndex: "status" },
        { title: "浏览", dataIndex: "view_count" },
      ]}
    />
  );
}
