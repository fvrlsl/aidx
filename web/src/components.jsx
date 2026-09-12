import { Tag } from "antd-mobile";
import { useNavigate } from "react-router-dom";

export function LevelTag({ level, label }) {
  return <span className={`level-tag level-${level || "insufficient"}`}>{label || "信息不足"}</span>;
}

export function MerchantCard({ item, extra }) {
  const nav = useNavigate();
  return (
    <div className="merchant-card" onClick={() => nav(`/merchant/${item.id}`)}>
      <div className="row">
        <div>
          <div className="name">{item.name}</div>
          <div className="meta">
            {[item.industry, item.region].filter(Boolean).join(" · ")}
            {item.matched_alias && item.matched_alias !== item.name ? ` · 匹配「${item.matched_alias}」` : ""}
          </div>
        </div>
        <LevelTag level={item.overall_level} label={item.overall_label} />
      </div>
      {extra}
    </div>
  );
}

export function EvidenceItem({ ev }) {
  return (
    <div className="evidence-item">
      <div className="sum">
        <span className={ev.polarity > 0 ? "polarity-plus" : "polarity-minus"}>{ev.polarity > 0 ? "正面 · " : "负面 · "}</span>
        {ev.summary}
      </div>
      <div className="src">
        <Tag color="default" fill="outline" style={{ marginRight: 6 }}>
          {ev.dimension_label}
        </Tag>
        {ev.source_level}级 · {ev.source_name || "公开来源"}
        {ev.event_date ? ` · ${ev.event_date}` : ""}
        {ev.is_historical ? " · 历史事件" : ""}
        {ev.source_url ? (
          <>
            {" · "}
            <a href={ev.source_url} target="_blank" rel="noreferrer">
              原文
            </a>
          </>
        ) : null}
      </div>
      {ev.merchant_reply ? <div className="src">商家回应：{ev.merchant_reply}</div> : null}
    </div>
  );
}

export function Disclaimer() {
  return (
    <div className="disclaimer">
      平台评级依据来自公开渠道整理，用户评价未经核实。如有异议请通过「我是商家 / 信息纠错」反馈。本页信息不构成投资或消费建议。
    </div>
  );
}
