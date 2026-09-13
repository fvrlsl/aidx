import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CapsuleTabs, ErrorBlock, Tag } from "antd-mobile";
import { api } from "../api";
import { MerchantCard } from "../components";

export default function Rankings({ asCases }) {
  const nav = useNavigate();
  const [type, setType] = useState(asCases ? "benchmark" : "benchmark");
  const [items, setItems] = useState([]);
  const [cases, setCases] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (asCases) {
      api.cases({ page_size: 20 }).then((r) => setCases(r.items)).catch((e) => setErr(e.message));
    } else {
      api.rankings({ type, limit: 20 }).then((r) => setItems(r.items)).catch((e) => setErr(e.message));
    }
  }, [type, asCases]);

  if (asCases) {
    return (
      <div className="page">
        <div className="hero">
          <h1>热点案例</h1>
          <p>标杆、争议反转与警示</p>
        </div>
        <div className="page-pad">
          {err ? <ErrorBlock description={err} /> : null}
          {cases.map((c) => (
            <div key={c.id} className="merchant-card" onClick={() => nav(`/case/${c.id}`)}>
              <div className="row">
                <div className="name">{c.title}</div>
                <Tag color={c.type === "warning" ? "danger" : c.type === "reversal" ? "warning" : "success"}>
                  {c.type === "warning" ? "警示" : c.type === "reversal" ? "反转" : "标杆"}
                </Tag>
              </div>
              <div className="meta">{c.subtitle}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="hero">
        <h1>榜单</h1>
        <p>基于公开信息的平台评级，非用户投票</p>
      </div>
      <div className="page-pad">
        <CapsuleTabs activeKey={type} onChange={setType}>
          <CapsuleTabs.Tab title="标杆榜" key="benchmark" />
          <CapsuleTabs.Tab title="争议榜" key="disputed" />
        </CapsuleTabs>
        {err ? <ErrorBlock description={err} /> : null}
        {items.map((m) => (
          <MerchantCard key={m.id} item={m} extra={<div className="meta">#{m.rank} · 分数 {m.score}</div>} />
        ))}
      </div>
    </div>
  );
}
