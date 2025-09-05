import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import App from "./App";
import CompaniesPage from "./pages/Companies";
import FinancialsPage from "./pages/FinancialsPage";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Screener as the home route */}
        <Route path="/" element={<App />} />
        <Route path="/screener" element={<App />} />

        {/* Companies page (your existing page) */}
        <Route path="/companies" element={<CompaniesPage />} />

        {/* New: Financials page by numeric company id */}
        <Route path="/financials/:companyId" element={<FinancialsPage />} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
