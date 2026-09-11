// src/App.tsx
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Routes,
  Route,
  useLocation,
} from "react-router-dom";

import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import ChatInterface from "@/components/ChatInterface";
import GamoraAIMain from "@/components/GamoraAIMain";
import GamoraAIDashboard from "@/components/GamoraAIDashboard";
import SignInPage from "./pages/SignInPage";
import ProtectedRoute from "@/components/ProtectedRoute";
import Header from "@/components/Header"; // header
import { AuthProvider } from "@/hooks/useAuth"; // auth provider

const queryClient = new QueryClient();

/** Inner component to allow useLocation */
const AppContent = () => {
  const location = useLocation();

  // hide header on sign in page and chat pages
  // Pages that render their own <Header /> must not also get the global one.
  const hideHeader = ["/", "/signin", "/chat", "/chat-main", "/chat-dashboard"].includes(
    location.pathname
  );

  return (
    <>
      {!hideHeader && <Header />}
      <Routes>
        {/* Public pages */}
        {/* Homepage disabled for now — "/" boots straight into the builder.
            The component is kept so it can be re-enabled by restoring this route. */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <GamoraAIMain />
            </ProtectedRoute>
          }
        />
        <Route 
          path="/index" 
          element={
            <ProtectedRoute>
              <Index />
            </ProtectedRoute>
          } 
        />

        {/* Chat interfaces - all protected */}
        <Route 
          path="/chat" 
          element={
            <ProtectedRoute>
              <ChatInterface />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/chat-main" 
          element={
            <ProtectedRoute>
              <GamoraAIMain />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/chat-dashboard" 
          element={
            <ProtectedRoute>
              <GamoraAIDashboard />
            </ProtectedRoute>
          } 
        />

        {/* Auth page */}
        <Route path="/signin" element={<SignInPage />} />


        {/* Example protected page later */}
        {/* 
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        /> 
        */}

        {/* Fallback */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </>
  );
};

const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <AuthProvider>
          <BrowserRouter>
            <AppContent />
          </BrowserRouter>
        </AuthProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
