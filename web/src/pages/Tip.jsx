import { useNavigate, useParams } from "react-router-dom";
import { Button, Form, Input, NavBar, TextArea, Toast } from "antd-mobile";
import { api } from "../api";

export default function Tip() {
  const { id } = useParams();
  const nav = useNavigate();
  const onFinish = async (v) => {
    try {
      await api.tip({ merchant_id: id ? Number(id) : undefined, ...v });
      Toast.show({ content: "线索已提交" });
      nav(-1);
    } catch (e) {
      Toast.show({ content: e.message });
    }
  };
  return (
    <div className="page">
      <NavBar onBack={() => nav(-1)}>提供线索</NavBar>
      <Form onFinish={onFinish} footer={<Button block type="submit" color="primary">提交</Button>}>
        <Form.Item name="merchant_name_raw" label="商家名">
          <Input placeholder="选填，若未关联商家" />
        </Form.Item>
        <Form.Item name="url" label="链接">
          <Input placeholder="新闻 / 公告链接" />
        </Form.Item>
        <Form.Item name="text" label="说明">
          <TextArea rows={4} maxLength={1000} showCount placeholder="简要说明事件，不要写具体人名" />
        </Form.Item>
      </Form>
    </div>
  );
}
