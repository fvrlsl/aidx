import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button, CapsuleTabs, ErrorBlock, NavBar, Popup, ProgressBar, Skeleton, TextArea, Toast } from "antd-mobile";
import { api } from "../api";
import { Disclaimer, EvidenceItem, LevelTag } from "../components";

const USER_LEVELS = [
  { v: 5, l: "很好" },
  { v: 4, l: "推荐" },
  { v: 3, l: "还行" },
  { v: 2, l: "不推荐" },
  { v: 1, l: "极差" },
];
const CLAIMS = [
  { v: "customer", l: "顾客" },
  { v: "current_staff", l: "现员工" },
  { v: "former_staff", l: "前员工" },
  { v: "hearsay", l: "听说的" },
];

export default function Merchant() {
  const { id } = useParams();
  const nav = useNavigate();
  const [m, setM] = useState(null);
  const [ev, setEv] = useState([]);
  const [sum, setSum] = useState(null);
  const [dim, setDim] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ level: 4, identity_claim: "customer", comment: "" });
  const [err, setErr] = useState("");

  const load = () => {
    Promise.all([api.merchant(id), api.evidence(id, { dimension: dim || undefined, page_size: 30 }), api.ratings(id)])
      .then(([a, b, c]) => {
        setM(a);
        setEv(b.items);
        setSum(c);
        if (c.mine) setForm((f) => ({ ...f, level: c.mine.level, identity_claim: c.mine.identity_claim, comment: c.mine.comment || "" }));
      })
      .catch((e) => setErr(e.message));
  };
  useEffect(load, [id, dim]);

  const submit = async () => {
    try {
      const res = await api.rate(id, form);
      Toast.show({ content: res.message });
      setOpen(false);
      load();
    } catch (e) {
      Toast.show({ content: e.message });
    }
  };

  if (err) return <ErrorBlock title="加载失败" description={err} />;
  if (!m) return <Skeleton.Paragraph lineCount={8} />;
  const rating = m.rating || {};

  return (
    <div className="page">
      <NavBar onBack={() => nav(-1)}>商家详情</NavBar>
      <div className="hero" style={{ paddingBottom: 20 }}>
        <h1>{m.name}</h1>
        <p>
          {[m.industry, m.region].filter(Boolean).join(" · ")}
          {rating.computed_at ? ` · 更新 ${String(rating.computed_at).slice(0, 10)}` : ""}
        </p>
        <div style={{ marginTop: 12 }}>
          <LevelTag level={m.overall_level} label={`平台评级 ${m.overall_label}`} />
        </div>
      </div>
      <div className="page-pad">
        <div className="dim-grid">
          {Object.entries(m.dimensions || {}).map(([k, label]) => (
            <div key={k} className="dim-card">
              <div className="k">{label}</div>
              <div className="v">{rating.dim_labels?.[k] || "—"}</div>
            </div>
          ))}
        </div>
        <div className="section-title">依据（公开信息）</div>
        <CapsuleTabs activeKey={dim || "all"} onChange={(k) => setDim(k === "all" ? "" : k)}>
          <CapsuleTabs.Tab title="全部" key="all" />
          {Object.entries(m.dimensions || {}).map(([k, label]) => (
            <CapsuleTabs.Tab title={label} key={k} />
          ))}
        </CapsuleTabs>
        {ev.map((e) => (
          <EvidenceItem key={e.id} ev={e} />
        ))}
        {!ev.length ? <div className="meta" style={{ padding: 12 }}>暂无该维度依据</div> : null}

        <div className="section-title">用户怎么看</div>
        <div className="merchant-card">
          <div className="meta" style={{ marginBottom: 8 }}>
            {sum?.disclaimer}
          </div>
          {sum?.distribution?.map((d) => (
            <div key={d.level} style={{ marginBottom: 8 }}>
              <div className="row">
                <span>{d.label}</span>
                <span className="meta">{d.percent}%</span>
              </div>
              <ProgressBar percent={d.percent} style={{ "--fill-color": "#1f8a4c" }} />
            </div>
          ))}
          <div className="meta" style={{ marginTop: 8 }}>
            {(sum?.identity || []).map((i) => `${i.label} ${i.count}人`).join(" · ")}
          </div>
        </div>
        {sum?.comments?.map((c, i) => (
          <div key={i} className="evidence-item">
            <div className="sum">{c.comment}</div>
            <div className="src">
              {c.nickname} · {c.level_label} · {c.identity_label}
            </div>
          </div>
        ))}

        <Button block color="primary" onClick={() => setOpen(true)} style={{ marginTop: 8 }}>
          {sum?.mine ? "修改我的评分" : "给这家打分"}
        </Button>
        <Button block fill="outline" style={{ marginTop: 8 }} onClick={() => nav(`/tip/${id}`)}>
          提供线索
        </Button>
        <Button block fill="outline" style={{ marginTop: 8 }} onClick={() => nav(`/feedback/${id}`)}>
          我是商家 / 信息纠错
        </Button>
        <Button
          block
          fill="none"
          style={{ marginTop: 4 }}
          onClick={() => nav("/rules")}
        >
          评级说明
        </Button>
        <Disclaimer />
      </div>

      <Popup visible={open} onMaskClick={() => setOpen(false)} bodyStyle={{ borderRadius: "16px 16px 0 0", padding: 16 }}>
        <div className="section-title" style={{ marginTop: 0 }}>
          你怎么看
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {USER_LEVELS.map((x) => (
            <Button key={x.v} size="small" color={form.level === x.v ? "primary" : "default"} onClick={() => setForm({ ...form, level: x.v })}>
              {x.l}
            </Button>
          ))}
        </div>
        <div className="meta" style={{ marginBottom: 8 }}>
          我是（不校验）
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {CLAIMS.map((x) => (
            <Button key={x.v} size="small" color={form.identity_claim === x.v ? "primary" : "default"} onClick={() => setForm({ ...form, identity_claim: x.v })}>
              {x.l}
            </Button>
          ))}
        </div>
        <TextArea rows={3} maxLength={200} showCount placeholder="可选：写一下事由，不要写具体人名" value={form.comment} onChange={(v) => setForm({ ...form, comment: v })} />
        <Button block color="primary" style={{ marginTop: 12 }} onClick={submit}>
          提交
        </Button>
      </Popup>
    </div>
  );
}
