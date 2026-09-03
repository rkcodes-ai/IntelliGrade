import { Suspense } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Provider as ReduxProvider } from "react-redux";
import { RouterProvider } from "react-router-dom";

import { queryClient } from "@/api/queryClient";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { LoadingScreen } from "@/components/common/LoadingScreen";
import { AuthProvider } from "@/context/AuthProvider";
import { ThemeProvider } from "@/context/ThemeProvider";
import { ToastProvider } from "@/context/ToastProvider";
import { router } from "@/routes";
import { store } from "@/store";

export function App() {
  return (
    <ErrorBoundary>
      <ReduxProvider store={store}>
        <ThemeProvider>
          <QueryClientProvider client={queryClient}>
            <ToastProvider>
              <AuthProvider>
                {/* Suspense boundary for future route-level code splitting (React Router `lazy`). */}
                <Suspense fallback={<LoadingScreen />}>
                  <RouterProvider router={router} />
                </Suspense>
              </AuthProvider>
            </ToastProvider>
          </QueryClientProvider>
        </ThemeProvider>
      </ReduxProvider>
    </ErrorBoundary>
  );
}
