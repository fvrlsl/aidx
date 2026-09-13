import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { List } from "antd-mobile";
import { api } from "../api";

export default function Me() {
  const nav = useNavigate();
  const [me, setMe] = useState(null);
  useEffect(() => {
    api.me().then(setMe).catch(() => setMe({ nickname: "未登录" }));
  }, []);
  return (
    <div className="page">
      <div className="hero">
        <h1>{me?.nickname || "本地体验用户"}</h1>
        <p>
          已评 {me?.rating_count ?? 0} 家 · 线索 {me?.tip_count ?? 0} 条
        </p>
      </div>
      <List>
        <List.Item onClick={() => nav("/rules")}>评级说明</List.Item>
        <List.Item onClick={() => nav("/tip")}>提交线索</List.Item>
        <List.Item extra="一期演示">用户协议 / 隐私政策</List.Item>
      </List>
      <div className="page-pad">
        <div className="disclaimer">一期演示环境：登录使用 mock 微信身份，无需真实微信授权。正式环境将走 wx.login。</div>
      </div>
    </div>
  );
}
