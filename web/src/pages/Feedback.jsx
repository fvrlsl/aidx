import { useNavigate, useParams } from "react-router-dom";
import { Button, Form, Input, TextArea, Toast, NavBar, Selector } from "antd-mobile";
import { api } from "../api";

const TYPES = [
  { label: "信息错误", value: "info_error" },
  { label: "申诉评级", value: "appeal_rating" },
  { label: "补充正面材料", value: "add_positive" },
  { label: "要求删除", value: "request_remove" },
  { label: "其他", value: "other" },
];

export default function Feedback() {
  const { id } = useParams();
  const nav = useNavigate();
  const [form] = Form.useForm();

  const onFinish = async (v) => {
    try {
      const res = await api.feedback({
        merchant_id: Number(id),
        type: v.type[0],
        contact_name: v.contact_name,
        contact_phone: v.contact_phone,
        company_name: v.company_name,
        content: v.content,
      });
      Toast.show({ content: `已提交，工单号 ${res.ticket_no}` });
      nav(-1);
    } catch (e) {
      Toast.show({ content: e.message });
    }
  };

  return (
    <div className="page">
      <NavBar onBack={() => nav(-1)}>商家反馈</NavBar>
      <Form form={form} onFinish={onFinish} footer={<Button block type="submit" color="primary">提交</Button>} initialValues={{ type: ["info_error"] }}>
        <Form.Item name="type" label="反馈类型" rules={[{ required: true }]}>
          <Selector options={TYPES} />
        </Form.Item>
        <Form.Item name="contact_name" label="联系人" rules={[{ required: true }]}>
          <Input placeholder="姓名" />
        </Form.Item>
        <Form.Item name="contact_phone" label="电话" rules={[{ required: true }]}>
          <Input placeholder="仅运营可见" type="tel" />
        </Form.Item>
        <Form.Item name="company_name" label="企业名称">
          <Input placeholder="选填" />
        </Form.Item>
        <Form.Item name="content" label="说明" rules={[{ required: true }]}>
          <TextArea rows={4} maxLength={1000} showCount placeholder="请说明需要更正的内容和依据" />
        </Form.Item>
      </Form>
    </div>
  );
}
