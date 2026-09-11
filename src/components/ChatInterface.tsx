import { useState, useEffect, useRef, memo } from "react";
import { Send, Paperclip, Copy, MoreHorizontal, LogOut } from "lucide-react";
import { motion } from "framer-motion";
import { useNavigate, useLocation } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";

// Centralized color theme for consistency
const COLORS = {
  green: "#25D366",
  darkGreen: "#128C7E",
  border: "#1a1a1a",
  bgDark: "#0d0d0d",
  bgBlack: "#000000",
  grayText: "#999999",
  white: "#FFFFFF",
};

// TypeScript interfaces
interface Message {
  role: "user" | "bot";
  text: string;
}

interface ChatBubbleProps {
  msg: Message;
  onCopy: (text: string) => Promise<void>;
}

interface ChatBoxProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
}

interface SidebarSectionProps {
  title: string;
  children: React.ReactNode;
}

interface SidebarItemProps {
  text: string;
  active?: boolean;
}

interface SidebarProps {
  showSignOut: boolean;
  setShowSignOut: (show: boolean) => void;
  onSignOut: () => void;
  dropdownRef: React.RefObject<HTMLDivElement>;
  user: any;
}


export default function GamoraClone() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [showSignOut, setShowSignOut] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, refreshUser } = useAuth();
  const { toast } = useToast();

  const sendMessage = () => {
    if (!input.trim()) return;
    const userMsg: Message = { role: "user", text: input.trim() };
    const botMsg: Message = {
      role: "bot",
      text: "Hey! 👋 Not much, just chillin' in the digital realm. What's up with you? Ready to chat, game, or dive into some random topic? 😄",
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setTimeout(() => setMessages((prev) => [...prev, botMsg]), 400);
  };

  // Check if user just signed in via Google OAuth and show toast
  useEffect(() => {
    const checkGoogleSignIn = async () => {
      // Check if URL has OAuth callback parameters
      const urlParams = new URLSearchParams(window.location.search);
      const hasOAuthParams = urlParams.has('code') || urlParams.has('access_token');
      
      // Also check session storage for Google sign-in flag
      const googleSignIn = sessionStorage.getItem('google_sign_in');
      
      if (hasOAuthParams || googleSignIn) {
        // Wait a bit for auth state to update
        setTimeout(async () => {
          const { data: { session } } = await supabase.auth.getSession();
          if (session) {
            toast({
              title: "Welcome!",
              description: "Successfully signed in with Google",
            });
            // Clear the flag
            sessionStorage.removeItem('google_sign_in');
            // Clean up URL params
            if (hasOAuthParams) {
              window.history.replaceState({}, '', location.pathname);
            }
          }
        }, 500);
      }
    };
    
    checkGoogleSignIn();
  }, [toast, location.pathname]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowSignOut(false);
      }
    };

    if (showSignOut) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showSignOut]);

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      console.error("Copy failed: ", err);
    }
  };

  const handleSignOut = async () => {
    try {
      // Close the dropdown first
      setShowSignOut(false);
      
      // Sign out from Supabase
      const { error } = await supabase.auth.signOut();
      
      if (error) {
        console.error("Error signing out:", error);
        alert("Failed to sign out. Please try again.");
        return;
      }
      
      // Refresh the user state to ensure it's updated
      await refreshUser();
      
      // Navigate to homepage
      navigate("/");
      
    } catch (error) {
      console.error("Error signing out:", error);
      alert("An unexpected error occurred. Please try again.");
    }
  };

  return (
    <div className="flex h-screen bg-black text-white font-sans overflow-hidden">
      <Sidebar 
        showSignOut={showSignOut}
        setShowSignOut={setShowSignOut}
        onSignOut={handleSignOut}
        dropdownRef={dropdownRef}
        user={user}
      />

      <main className="flex-1 flex flex-col min-h-0">
        {/* Chat area - only this section scrolls */}
        <section className="flex-1 overflow-y-auto px-6 py-6 min-h-0">
          {messages.length === 0 ? (
            <div className="flex flex-col justify-center items-center h-full">
              <h1 className="text-4xl font-light mb-4">Ready to build <span className="text-[#25D366]">your next game?</span></h1>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto w-full">
              {messages.map((msg, i) => (
                <ChatBubble key={i} msg={msg} onCopy={copyToClipboard} />
              ))}
              <div ref={chatEndRef} />
            </div>
          )}
        </section>

        {/* Fixed input at bottom */}
        <div className="bg-black border-t border-[#1a1a1a] p-4 flex-shrink-0">
          <ChatBox value={input} onChange={setInput} onSend={sendMessage} />
        </div>
      </main>
    </div>
  );
}

/** Sidebar Component **/
const Sidebar = memo(({ showSignOut, setShowSignOut, onSignOut, dropdownRef, user }: SidebarProps) => (
  <aside className="w-64 bg-black border-r border-[#1a1a1a] flex flex-col h-screen overflow-hidden">
    <div className="flex-1 overflow-y-auto min-h-0">
      {/* Mamba Logo - Centered */}
      <div className="flex justify-center pt-6 pb-4">
        <span className="text-[#25D366] text-3xl font-logo font-light">
          Mamba
        </span>
      </div>

      {/* New Chat Button */}
      <div className="px-4 pb-4">
        <button className="w-full h-10 rounded-full bg-[#121212] hover:bg-[#1c1c1c] border border-[#1f1f1f] text-sm text-gray-200 font-light flex items-center justify-center transition-colors">
          <span className="text-base">＋</span>
          <span className="ml-2">New chat</span>
        </button>
      </div>

      <SidebarSection title="Chats">
        <SidebarItem text="Casual Greeting and Friendly Inquiry" active />
        <SidebarItem text="Casual Greeting and Friendly Inquiry" />
        <SidebarItem text="User Inquires About AI Algorithms" />
      </SidebarSection>
    </div>

    {/* Footer with Email and Sign Out - Fixed at bottom */}
    <div className="border-t border-[#1a1a1a] px-4 py-3 text-sm text-gray-300 flex-shrink-0 relative">
      <div className="flex items-center justify-between">
        <span className="truncate text-gray-300 text-[13px] font-light">
          {user?.email || "hashwanth.gogineni@ippon.tech"}
        </span>
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setShowSignOut(!showSignOut)}
            className="p-1 hover:bg-gray-800 rounded transition-colors border-none focus:outline-none"
          >
            <MoreHorizontal className="w-4 h-4 text-gray-500" />
          </button>
          
          {/* Sign Out Dropdown */}
          {showSignOut && (
            <div className="absolute bottom-full right-0 mb-2 bg-[#1a1a1a] border border-[#1a1a1a] rounded-lg shadow-lg z-50 w-fit min-w-[120px]">
              <button
                onClick={onSignOut}
                className="w-full px-3 py-2 text-left text-sm text-gray-200 hover:bg-[#2a2a2a] flex items-center gap-2 rounded-lg transition-colors border border-gray-700 font-light"
              >
                <LogOut className="w-4 h-4" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  </aside>
));

/** Sidebar Section Header **/
const SidebarSection = memo(({ title, children }: SidebarSectionProps) => (
  <div className="mb-3">
    <h3 className="px-4 py-2 text-xs uppercase text-gray-300 tracking-wider font-medium">{title}</h3>
    <div className="px-3 space-y-1">{children}</div>
  </div>
));

/** Sidebar Item **/
const SidebarItem = memo(({ text, active }: SidebarItemProps) => (
  <div
    className={`group flex justify-between items-center px-3 py-2 rounded-lg text-sm cursor-pointer transition border font-light ${
      active
        ? "bg-[#1c1c1c] border-[#2a2a2a] text-gray-100"
        : "hover:bg-[#111] border-transparent text-gray-400"
    }`}
  >
    <span className="truncate">{text}</span>
    <MoreHorizontal className="w-4 h-4 text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
  </div>
));

/** Chat Input Box **/
const ChatBox = memo(({ value, onChange, onSend }: ChatBoxProps) => (
  <div className="w-full max-w-4xl mx-auto">
    <div className="bg-[#0d0d0d] rounded-2xl p-4">
      <input
        type="text"
        placeholder="Ask Mamba"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onSend()}
        className="w-full bg-transparent text-gray-200 placeholder-gray-400 text-[16px] focus:outline-none border-none font-light"
      />
      <div className="flex items-center justify-end mt-3 text-sm text-gray-400">
        <div className="flex items-center gap-3">
          <Paperclip className="w-4 h-4 text-gray-500 hover:text-gray-300 cursor-pointer" />
          <button
            onClick={onSend}
            aria-label="Send message"
            className="bg-[#25D366] hover:bg-[#128C7E] rounded-full p-2.5 transition-colors border-none"
          >
            <Send className="w-4 h-4 text-black" />
          </button>
        </div>
                </div>
              </div>
          </div>
));

/** Chat Bubbles **/
const ChatBubble = memo(({ msg, onCopy }: ChatBubbleProps) => {
  const isUser = msg.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`mb-4 ${isUser ? "flex justify-end" : ""}`}
    >
      {isUser ? (
        <div className="bg-[#111] border border-[#1f1f1f] rounded-2xl px-4 py-2 text-sm text-gray-100 shadow font-light">
          {msg.text}
        </div>
      ) : (
        <div>
          <div className="text-[15px] leading-7 text-gray-100 whitespace-pre-line font-light">
            {msg.text}
          </div>
          <div className="mt-2 flex gap-3 text-gray-500 text-sm">
            <Copy
              className="w-4 h-4 cursor-pointer hover:text-white"
              onClick={() => onCopy(msg.text)}
            />
          </div>
        </div>
      )}
    </motion.div>
  );
});