import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { BusyProvider } from "./busy";
import { I18nProvider } from "./i18n";
import { ThemeProvider } from "./theme";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <I18nProvider>
        <BusyProvider>
          <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <App />
          </BrowserRouter>
        </BusyProvider>
      </I18nProvider>
    </ThemeProvider>
  </React.StrictMode>
);
