import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import Showcase from "./Showcase";
import "./styles.css";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {(import.meta as ImportMeta & { env?: { VITE_SHOWCASE?: string } }).env
      ?.VITE_SHOWCASE === "1" ? (
      <Showcase />
    ) : (
      <App />
    )}
  </React.StrictMode>,
);
