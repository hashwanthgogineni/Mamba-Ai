// src/components/ChatMessage.tsx
// Message rendering modelled on Biona's Reports Analysis chat:
// the user's turn is a filled bubble on the right, the AI's turn has no
// bubble at all — it reads as text on the page, left aligned, markdown
// rendered. Both fade up on mount.
import ReactMarkdown from "react-markdown";
import { Loader2 } from "lucide-react";

export interface ChatMessageProps {
  message: string;
  isUser: boolean;
  /** Renders the spinner instead of the message body. */
  isThinking?: boolean;
  id?: string;
}

const ChatMessage = ({ message, isUser, isThinking = false, id }: ChatMessageProps) => {
  return (
    <div
      id={id}
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4 animate-fadeIn`}
    >
      <div
        className={`max-w-[90%] sm:max-w-[85%] px-3 sm:px-4 py-2.5 rounded-lg transition-all duration-300 ${
          isUser ? "bg-zinc-800 text-white" : "text-foreground"
        }`}
      >
        {isThinking ? (
          <div className="flex items-center gap-2.5">
            <Loader2 className="w-5 h-5 animate-spin text-[#25D366]" />
            <span className="text-[15px] text-white font-semibold">{message}</span>
          </div>
        ) : isUser ? (
          <p className="text-sm sm:text-base text-white font-medium whitespace-pre-wrap leading-relaxed break-words">
            {message}
          </p>
        ) : (
          <div className="text-sm sm:text-base prose prose-invert prose-sm max-w-none leading-relaxed break-words">
            <ReactMarkdown
              components={{
                p: ({ children }) => (
                  <p
                    className="mb-2 last:mb-0 break-words"
                    style={{ color: "#ffffff", overflowWrap: "break-word" }}
                  >
                    {children}
                  </p>
                ),
                li: ({ children }) => (
                  <li className="break-words" style={{ color: "#ffffff", overflowWrap: "break-word" }}>
                    {children}
                  </li>
                ),
                strong: ({ children }) => (
                  <strong style={{ color: "#d4d4d8" }} className="font-bold">
                    {children}
                  </strong>
                ),
                code: ({ children }) => (
                  <code className="text-[#25D366] bg-[#0d0d0d] px-1 py-0.5 rounded text-[0.9em]">
                    {children}
                  </code>
                ),
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#25D366] hover:text-[#4ae389] hover:underline transition-colors"
                  >
                    {children}
                  </a>
                ),
                h1: ({ children }) => (
                  <h1 style={{ color: "#d4d4d8" }} className="text-lg font-bold mb-3 mt-5">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 style={{ color: "#d4d4d8" }} className="text-base font-bold mb-2 mt-4">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 style={{ color: "#d4d4d8" }} className="text-sm font-bold mb-2 mt-3">
                    {children}
                  </h3>
                ),
              }}
            >
              {message}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
