import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ErrorBlock, NavBar, Skeleton, Tag } from "antd-mobile";
import { api } from "../api";
import { Disclaimer, MerchantCard } from "../components";

export default function CasePage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [c, setC] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.caseDetail(id).then(setC).catch((e) => setErr(e.message));
  }, [id]);
  if (err) return <ErrorBlock title="加载失败" description={err} />;
  if (!c) return <Skeleton.Paragraph lineCount={8} />;
  return (
    <div className="page">
      <NavBar onBack={() => nav(-1)}>案例</NavBar>
      <div className="page-pad">
        <Tag color={c.type === "warning" ? "danger" : "success"}>{c.type === "warning" ? "负面警示" : c.type === "reversal" ? "争议反转" : "正面标杆"}</Tag>
        <h2 style={{ margin: "8px 0 4px" }}>{c.title}</h2>
        <div className="meta">{c.subtitle}</div>
        <div className="section-title">时间线</div>
        <ul className="timeline">
          {(c.timeline || []).map((t, i) => (
            <li key={i}>
              <div className="d">{t.date}</div>
              <div className="t">{t.text}</div>
            </li>
          ))}
        </ul>
        <div className="section-title">正文</div>
        <div className="body-text">{c.body}</div>
        <div className="section-title">关联商家</div>
        {(c.merchants || []).map((m) => (
          <MerchantCard key={m.id} item={m} />
        ))}
        <Disclaimer />
      </div>
    </div>
  );
}
