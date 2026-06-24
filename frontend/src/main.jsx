import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { InstitutionProvider } from "./auth/InstitutionContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <InstitutionProvider>
          <App />
        </InstitutionProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
