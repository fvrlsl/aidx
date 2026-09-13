import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorBlock, SearchBar, Skeleton, Tag } from "antd-mobile";
import { api } from "../api";
import { Disclaimer, LevelTag, MerchantCard } from "../components";

export default function Home() {
  const nav = useNavigate();
  const [cases, setCases] = useState([]);
  const [ranks, setRanks] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([api.cases({ page_size: 4 }), api.rankings({ type: "benchmark", limit: 5 })])
      .then(([c, r]) => {
        setCases(c.items);
        setRanks(r.items);
      })
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="page">
      <div className="hero">
        <h1>良心商家</h1>
        <p>查一查，这家店对员工怎么样</p>
      </div>
      <div className="search-wrap">
        <SearchBar placeholder="搜品牌 / 商家名" onFocus={() => nav("/search")} style={{ "--background": "#fff", "--border-radius": "22px", "--height": "44px" }} />
      </div>
      <div className="page-pad">
        {err ? <ErrorBlock status="default" title="加载失败" description={err} /> : null}
        <div className="section-title">本周热点案例</div>
        {!cases.length && !err ? <Skeleton.Paragraph lineCount={3} /> : null}
        {cases.map((c) => (
          <div key={c.id} className="merchant-card" onClick={() => nav(`/case/${c.id}`)}>
            <div className="row">
              <div className="name">{c.title}</div>
              <Tag color={c.type === "warning" ? "danger" : c.type === "reversal" ? "warning" : "success"}>{c.type === "warning" ? "警示" : c.type === "reversal" ? "反转" : "标杆"}</Tag>
            </div>
            <div className="meta">{c.subtitle}</div>
          </div>
        ))}
        <div className="section-title">标杆商家</div>
        {ranks.map((m) => (
          <MerchantCard key={m.id} item={m} extra={m.tags?.includes("disputed_signal") ? <div className="meta">存在争议信号</div> : null} />
        ))}
        <Disclaimer />
      </div>
    </div>
  );
}
