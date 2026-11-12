import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import OperatorDashboard from "./OperatorDashboard";
import Showcase from "./Showcase";
import "./styles.css";

const isOperatorRoute = window.location.pathname.replace(/\/+$/, "") === "/operator";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {(import.meta as ImportMeta & { env?: { VITE_SHOWCASE?: string } }).env
      ?.VITE_SHOWCASE === "1" ? (
      <Showcase />
    ) : isOperatorRoute ? (
      <OperatorDashboard />
    ) : (
      <App />
    )}
  </React.StrictMode>,
);
