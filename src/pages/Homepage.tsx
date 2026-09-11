// src/pages/Homepage.tsx
import React from "react";
import { useNavigate } from "react-router-dom";

const Homepage: React.FC = () => {
  const navigate = useNavigate();

  const handleGetStarted = () => {
    navigate("/chat-main");
  };

  return (
    <div className="bg-black text-white font-sans">
      {/* ✅ Header is already injected globally in App.tsx */}

      {/* Hero Section */}
      <section className="text-center py-20 px-6">
        {/* <span className="inline-block px-4 py-1 mb-6 border border-border/50 rounded-full text-sm text-gray-400 font-light">
          Vega One
        </span> */}
        <h1 className="text-4xl md:text-6xl font-light">
          Build games with{" "}
          <span className="text-green-500 font-light">natural language</span>
        </h1>
        <p className="mt-6 max-w-2xl mx-auto text-white font-light">
          Mamba transforms your ideas into game code instantly. No complex
          engines, no steep learning curves—just describe what you want to build.
        </p>
        <div className="flex justify-center gap-4 mt-8">
          <button
            onClick={handleGetStarted}
            className="
              bg-black text-green-500 border border-green-500 
              px-6 py-3 rounded-sm font-light
              transition-colors duration-300
              hover:bg-green-500 hover:text-black
            "
          >
            Get Started
          </button>
        </div>
      </section>

      {/* Features – top border matches header */}
      <section className="py-20 px-6 text-center border-t border-border/50">
        <h2 className="text-3xl md:text-4xl font-light mb-4">
          Everything you need to build
        </h2>
        <p className="text-white mb-12 font-light">
          Powerful features designed for game developers
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
          {/* Card 1 */}
          <div className="bg-black p-6 rounded-lg border border-border/50">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-8 h-8 mx-auto mb-3 text-green-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path d="M12 6v6l4 2" />
              <circle cx="12" cy="12" r="10" />
            </svg>
            <h3 className="text-xl md:text-2xl font-light mb-2">
              Instant code generation
            </h3>
            <p className="text-white text-sm font-light">
              Describe your game mechanics and watch as Mamba generates clean,
              production-ready code in real time.
            </p>
          </div>

          {/* Card 2 */}
          <div className="bg-black p-6 rounded-lg border border-border/50">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-8 h-8 mx-auto mb-3 text-green-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
            <h3 className="text-xl md:text-2xl font-light mb-2">
              Multiple game types
            </h3>
            <p className="text-white text-sm font-light">
              From platformers to puzzles, RPGs to racing games—Mamba
              understands and builds any genre you imagine.
            </p>
          </div>

          {/* Card 3 */}
          <div className="bg-black p-6 rounded-lg border border-border/50">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-8 h-8 mx-auto mb-3 text-green-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
            <h3 className="text-xl md:text-2xl font-light mb-2">
              Lightning fast iteration
            </h3>
            <p className="text-white text-sm font-light">
              Modify, refine, and enhance your game through conversation.
              Changes happen instantly as you chat.
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="text-center py-20 px-6 border-t border-border/50">
        <h2 className="text-4xl font-light mb-4">Ready to build your game?</h2>
        <p className="text-white max-w-2xl mx-auto mb-8 font-light">
          Join developers who are already creating games faster than ever. Start
          building today with no credit card required.
        </p>
        <button
          onClick={handleGetStarted}
          className="
            bg-black text-green-500 border border-green-500 
            px-8 py-4 rounded-sm font-light
            transition-colors duration-300
            hover:bg-green-500 hover:text-black
          "
        >
          Get started for free →
        </button>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-border/50 bg-black">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
          <div
            onClick={() => navigate("/")}
            className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity duration-200"
            title="Go to homepage"
          >
            <span
              className="text-green-500 text-lg md:text-xl"
              style={{ fontFamily: "'Pixelify Sans', sans-serif" }}
            >
              Mamba
            </span>
          </div>
          <p className="text-gray-400 text-sm font-light">
            © 2025 Mamba. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Homepage;
