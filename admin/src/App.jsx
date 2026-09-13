import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ProLayout } from "@ant-design/pro-components";
import {
  AuditOutlined,
  CommentOutlined,
  DashboardOutlined,
  FileSearchOutlined,
  FormOutlined,
  FundOutlined,
  MergeCellsOutlined,
  NotificationOutlined,
  ShopOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Merchants from "./pages/Merchants";
import Sources from "./pages/Sources";
import Evidence from "./pages/Evidence";
import Cases from "./pages/Cases";
import Ratings from "./pages/Ratings";
import Comments from "./pages/Comments";
import Feedback from "./pages/Feedback";
import Tips from "./pages/Tips";
import Watchlist from "./pages/Watchlist";

const menus = [
  { path: "/", name: "看板", icon: <DashboardOutlined /> },
  { path: "/sources", name: "素材池", icon: <FileSearchOutlined /> },
  { path: "/evidence", name: "依据审核", icon: <AuditOutlined /> },
  { path: "/merchants", name: "实体管理", icon: <ShopOutlined /> },
  { path: "/ratings", name: "评级确认", icon: <FundOutlined /> },
  { path: "/cases", name: "案例", icon: <NotificationOutlined /> },
  { path: "/comments", name: "用户评价", icon: <CommentOutlined /> },
  { path: "/feedback", name: "商家工单", icon: <FormOutlined /> },
  { path: "/tips", name: "用户线索", icon: <ThunderboltOutlined /> },
  { path: "/watchlist", name: "热点监控", icon: <MergeCellsOutlined /> },
];

function Shell() {
  const loc = useLocation();
  const nav = useNavigate();
  if (!localStorage.getItem("gm_admin_token")) return <Navigate to="/login" replace />;
  return (
    <ProLayout
      title="良心商家"
      logo={false}
      location={loc}
      route={{ path: "/", routes: menus }}
      menuItemRender={(item, dom) => <a onClick={() => nav(item.path || "/")}>{dom}</a>}
      avatarProps={{ title: "admin", size: "small" }}
      actionsRender={() => [
        <a
          key="out"
          onClick={() => {
            localStorage.removeItem("gm_admin_token");
            nav("/login");
          }}
        >
          退出
        </a>,
      ]}
      layout="mix"
      fixSiderbar
    >
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/sources" element={<Sources />} />
        <Route path="/evidence" element={<Evidence />} />
        <Route path="/merchants" element={<Merchants />} />
        <Route path="/ratings" element={<Ratings />} />
        <Route path="/cases" element={<Cases />} />
        <Route path="/comments" element={<Comments />} />
        <Route path="/feedback" element={<Feedback />} />
        <Route path="/tips" element={<Tips />} />
        <Route path="/watchlist" element={<Watchlist />} />
      </Routes>
    </ProLayout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<Shell />} />
    </Routes>
  );
}
