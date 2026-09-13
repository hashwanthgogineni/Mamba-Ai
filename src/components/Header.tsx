// src/components/Header.tsx
import { Button } from "@/components/ui/button";
import { ArrowLeft, LogOut } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { supabase } from "@/lib/supabase";

// Once you are inside the app the call-to-action is noise: you are already
// doing the thing it invites you to do.
const APP_ROUTES = ["/", "/chat-main", "/chat-dashboard", "/chat", "/index"];

const Header = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, loading } = useAuth();
  const inApp = APP_ROUTES.includes(location.pathname);
  // Only the dashboard has somewhere to go back TO.
  const canGoBack = location.pathname === "/chat-dashboard";

  const handleGetStarted = () => {
    if (location.pathname === "/") {
      navigate("/chat-main");
    } else if (location.pathname === "/chat-main") {
      navigate("/signin");
    } else {
      navigate("/chat-main");
    }
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    navigate("/");
  };

  return (
    <>
      <header className="sticky top-0 z-50 w-full bg-black border-b border-border/50">
        <div className="container flex h-16 items-center justify-between px-6">
          <div className="flex items-center space-x-3">
            <h1
              onClick={() => navigate("/")}
              className="
                font-logo text-2xl font-light text-primary 
                cursor-pointer hover:opacity-80 
                transition-opacity duration-200
              "
              title="Go to homepage"
            >
              Mamba
            </h1>
          </div>

          {/* Right-side controls */}
          <div className="flex items-center space-x-2">
            {canGoBack && (
              <div
                onClick={() => navigate("/")}
                title="Back to prompt"
                aria-label="Back to prompt"
                className="
                  flex items-center justify-center
                  h-10 w-10 rounded-full cursor-pointer p-2
                  transition-colors
                  hover:border hover:border-white/70
                "
              >
                <ArrowLeft className="h-5 w-5 text-green-500" />
              </div>
            )}
            {!loading && user ? (
              <div className="flex items-center space-x-4">
                {/* Logout icon */}
                <div
                  onClick={handleSignOut}
                  title="Sign Out"
                  className="
                    flex items-center justify-center
                    h-10 w-10
                    rounded-full
                    cursor-pointer
                    transition-colors
                    p-2
                    hover:border hover:border-white/70
                  "
                >
                  <LogOut className="h-5 w-5 text-green-500" />
                </div>
              </div>
            ) : inApp ? null : (
              <Button
                variant="default"
                size="sm"
                onClick={handleGetStarted}
                className="
                  bg-black text-green-500 border border-green-500 
                  px-4 py-2 rounded-sm font-light
                  transition-colors duration-300
                  hover:bg-green-500 hover:text-black
                "
              >
                Get Started
              </Button>
            )}
          </div>
        </div>
      </header>
    </>
  );
};

export default Header;
