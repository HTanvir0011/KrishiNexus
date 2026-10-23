import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Self-hosted type, so the union kiosk renders correctly with no network.
import "@fontsource-variable/anek-bangla/wdth.css";
import "@fontsource/tiro-bangla/400.css";
import "@fontsource/tiro-bangla/400-italic.css";

import App from "./App";
import "./index.css";

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
