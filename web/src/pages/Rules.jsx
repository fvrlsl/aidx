import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { NavBar } from "antd-mobile";
import { api } from "../api";

export default function Rules() {
  const nav = useNavigate();
  const [md, setMd] = useState("");
  useEffect(() => {
    api.rules().then((r) => setMd(r.markdown));
  }, []);
  return (
    <div className="page">
      <NavBar onBack={() => nav(-1)}>评级说明</NavBar>
      <div className="page-pad">
        <div className="body-text">{md}</div>
      </div>
    </div>
  );
}
