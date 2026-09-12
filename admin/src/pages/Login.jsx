import { LoginForm, ProFormText } from "@ant-design/pro-components";
import { message } from "antd";
import { useNavigate } from "react-router-dom";
import { adminApi } from "../api";

export default function Login() {
  const nav = useNavigate();
  return (
    <div style={{ paddingTop: 80 }}>
      <LoginForm
        title="良心商家"
        subTitle="运营后台"
        onFinish={async (v) => {
          try {
            const res = await adminApi.login(v.username, v.password);
            localStorage.setItem("gm_admin_token", res.token);
            message.success("登录成功");
            nav("/");
          } catch (e) {
            message.error(e.message);
          }
        }}
      >
        <ProFormText name="username" label="用户名" initialValue="admin" rules={[{ required: true }]} />
        <ProFormText.Password name="password" label="密码" initialValue="admin123" rules={[{ required: true }]} />
      </LoginForm>
    </div>
  );
}
