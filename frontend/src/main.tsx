import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/instrument-sans";
import "./index.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./lib/auth";
import { RuntimeProvider } from "./lib/runtime";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <RuntimeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </RuntimeProvider>
    </BrowserRouter>
  </StrictMode>,
);
