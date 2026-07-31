import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { InstitutionProvider } from "./auth/InstitutionContext";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Los datos de una guardia envejecen rápido, pero no tanto como para
      // recargar en cada montaje: 30 s de frescura y refresco al volver a la
      // pestaña (el operador deja la app abierta y vuelve).
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      retry: (intentos, error) => {
        // 401/403/404 no se reintentan: no se arreglan solos.
        if (error?.status >= 400 && error?.status < 500) return false;
        return intentos < 2;
      },
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <InstitutionProvider>
            <App />
          </InstitutionProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
