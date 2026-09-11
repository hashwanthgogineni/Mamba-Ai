// src/components/Footer.tsx
import React from "react";

const Footer: React.FC = () => {
  return (
    <footer className="bg-black">
      {/* wrapper with full border */}
      <div className="border-t border-white/10">
        {/* actual content container */}
        <div className="max-w-7xl mx-auto py-8 px-6 flex flex-col md:flex-row justify-between items-center gap-6">
          {/* Clickable Mamba logo */}
          <div
            onClick={() => (window.location.href = "/")}
            className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity duration-200"
            title="Go to homepage"
          >
            <span
              className="text-green-400 text-lg md:text-xl"
              style={{ fontFamily: "'Pixelify Sans', sans-serif" }}
            >
              Mamba
            </span>
          </div>
          <p className="text-gray-300 text-sm font-light">
            © 2025 Mamba. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
