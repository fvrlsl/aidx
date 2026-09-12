import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Dialog, Empty, Form, Input, NavBar, SearchBar, Toast } from "antd-mobile";
import { api } from "../api";
import { MerchantCard } from "../components";

export default function Search() {
  const nav = useNavigate();
  const timer = useRef();
  const [q, setQ] = useState("");
  const [items, setItems] = useState(null);
  const [suggest, setSuggest] = useState(false);

  const run = (value) => {
    setQ(value);
    clearTimeout(timer.current);
    if (!value.trim()) {
      setItems(null);
      setSuggest(false);
      return;
    }
    timer.current = setTimeout(async () => {
      try {
        const res = await api.search(value.trim());
        setItems(res.items);
        setSuggest(res.suggest_create);
      } catch (e) {
        Toast.show({ content: e.message });
      }
    }, 300);
  };

  const create = async () => {
    const name = q.trim();
    try {
      const res = await api.createMerchant({ name });
      if (res.action === "confirm_needed") {
        const first = res.candidates[0];
        const ok = await Dialog.confirm({ content: `你是指「${first.name}」吗？` });
        if (ok) {
          await api.createMerchant({ name, confirm_merchant_id: first.id });
          Toast.show({ content: "已挂到已有商家，待审核" });
          nav(`/merchant/${first.id}`);
        }
        return;
      }
      if (res.action === "alias_added") {
        nav(`/merchant/${res.merchant.id}`);
        return;
      }
      Toast.show({ content: "已提交，审核通过后公开" });
    } catch (e) {
      Toast.show({ content: e.message });
    }
  };

  return (
    <div className="page">
      <NavBar onBack={() => nav(-1)}>搜索商家</NavBar>
      <div className="page-pad">
        <SearchBar placeholder="蜜雪 / 胖东来 / 麦当劳" value={q} onChange={run} autoFocus />
        {items && !items.length ? <Empty description="没有找到这个商家" /> : null}
        {items?.map((m) => (
          <MerchantCard key={m.id} item={m} />
        ))}
        {suggest ? (
          <div style={{ marginTop: 16 }}>
            <Button block color="primary" onClick={create}>
              补充「{q}」这个商家
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
