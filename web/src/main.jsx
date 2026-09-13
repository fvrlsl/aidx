import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider } from "antd-mobile";
import zhCN from "antd-mobile/es/locales/zh-CN";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <ConfigProvider locale={zhCN}>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </ConfigProvider>
);
