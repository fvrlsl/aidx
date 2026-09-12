import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { TabBar, Toast } from "antd-mobile";
import { AppOutline, ContentOutline, HistogramOutline, UserOutline } from "antd-mobile-icons";
import { ensureLogin } from "./api";
import Home from "./pages/Home";
import Search from "./pages/Search";
import Merchant from "./pages/Merchant";
import CasePage from "./pages/Case";
import Rankings from "./pages/Rankings";
import Me from "./pages/Me";
import Rules from "./pages/Rules";
import Feedback from "./pages/Feedback";
import Tip from "./pages/Tip";

const TABS = [
  { key: "/", title: "首页", icon: <AppOutline /> },
  { key: "/rankings", title: "榜单", icon: <HistogramOutline /> },
  { key: "/cases", title: "案例", icon: <ContentOutline /> },
  { key: "/me", title: "我的", icon: <UserOutline /> },
];

export default function App() {
  const loc = useLocation();
  const nav = useNavigate();

  useEffect(() => {
    ensureLogin().catch((e) => Toast.show({ content: e.message }));
  }, []);

  const hideTab = ["/search", "/merchant", "/case/", "/feedback", "/tip", "/rules"].some((p) => loc.pathname.startsWith(p) && loc.pathname !== "/cases");

  return (
    <div className="phone-shell">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/search" element={<Search />} />
        <Route path="/merchant/:id" element={<Merchant />} />
        <Route path="/cases" element={<Rankings asCases />} />
        <Route path="/case/:id" element={<CasePage />} />
        <Route path="/rankings" element={<Rankings />} />
        <Route path="/me" element={<Me />} />
        <Route path="/rules" element={<Rules />} />
        <Route path="/feedback/:id" element={<Feedback />} />
        <Route path="/tip/:id?" element={<Tip />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {hideTab ? null : (
        <TabBar activeKey={loc.pathname === "/cases" ? "/cases" : TABS.find((t) => t.key === loc.pathname)?.key || "/"} onChange={(k) => nav(k)} style={{ position: "sticky", bottom: 0, background: "#fff", borderTop: "1px solid #eee" }}>
          {TABS.map((t) => (
            <TabBar.Item key={t.key} icon={t.icon} title={t.title} />
          ))}
        </TabBar>
      )}
    </div>
  );
}
