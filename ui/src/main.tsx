import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./pages/AppShell";
//import  from "./App";                      // your screener-with-data
import Screener from "./pages/Screener";
import CompaniesPage from "./pages/Companies";
import FinancialsPage from "./pages/FinancialsPage";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Layout that shows header + ThemeToggle for every page */}
        <Route path="/" element={<AppShell />}>

          {/* Home: Screener (fetches data) */}
          <Route index element={<Screener />} />

          {/* Other pages (relative paths, no leading slash) */}
          <Route path="companies" element={<CompaniesPage />} />
          <Route path="financials/:companyId" element={<FinancialsPage />} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
