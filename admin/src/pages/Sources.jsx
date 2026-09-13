import { useRef } from "react";
import { ProTable } from "@ant-design/pro-components";
import { Button, Form, Input, Modal, Select, message } from "antd";
import { adminApi } from "../api";

export default function Sources() {
  const ref = useRef();
  const clip = () => {
    let form;
    Modal.confirm({
      title: "剪藏链接",
      content: (
        <Form ref={(f) => (form = f)} layout="vertical" initialValues={{ source_level: "B", process_now: true }}>
          <Form.Item name="url" label="链接" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="source_level" label="信源级别">
            <Select options={["A", "B", "C", "D"].map((x) => ({ label: x, value: x }))} />
          </Form.Item>
          <Form.Item name="title" label="标题（可空，自动抓）">
            <Input />
          </Form.Item>
          <Form.Item name="summary" label="摘要（可空）">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      ),
      onOk: async () => {
        const v = await form.validateFields();
        const res = await adminApi.clip({ ...v, process_now: true });
        message.success(`已入库，管道：${res.pipeline?.status || "queued"}`);
        ref.current.reload();
      },
    });
  };
  return (
    <ProTable
      actionRef={ref}
      rowKey="id"
      search={{ labelWidth: 80 }}
      toolBarRender={() => [
        <Button key="c" type="primary" onClick={clip}>
          剪藏链接
        </Button>,
      ]}
      request={async (params) => {
        const res = await adminApi.sources({
          q: params.title,
          status: params.status,
          level: params.source_level,
          page: params.current,
          page_size: params.pageSize,
        });
        return { data: res.items, total: res.total, success: true };
      }}
      columns={[
        { title: "ID", dataIndex: "id", width: 70, search: false },
        { title: "标题", dataIndex: "title", ellipsis: true },
        { title: "级别", dataIndex: "source_level", width: 70 },
        { title: "来源", dataIndex: "publisher", search: false },
        { title: "状态", dataIndex: "status", width: 90 },
        { title: "抽取", dataIndex: "extraction", search: false, render: (v) => (v ? `${v.dimension || ""} ${v.polarity || ""} ${v.summary || ""}` : "-") },
        {
          title: "操作",
          search: false,
          render: (_, r) => (
            <Button
              size="small"
              onClick={async () => {
                await adminApi.processSource(r.id);
                message.success("已重跑");
                ref.current.reload();
              }}
            >
              重跑管道
            </Button>
          ),
        },
      ]}
    />
  );
}
