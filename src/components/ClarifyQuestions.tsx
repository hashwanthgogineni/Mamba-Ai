// src/components/ClarifyQuestions.tsx
// Shown between "you typed a prompt" and "the build starts".
// Nothing is generated while this is on screen — no project, no tokens.
import { motion } from "framer-motion";
import { Check } from "lucide-react";
import type { ClarifyQuestion } from "@/lib/api";

interface ClarifyQuestionsProps {
  questions: ClarifyQuestion[];
  answers: Record<string, string>;
  onAnswer: (questionId: string, value: string) => void;
  onSubmit: () => void;
  onSkip: () => void;
  summary?: string;
}

export default function ClarifyQuestions({
  questions,
  answers,
  onAnswer,
  onSubmit,
  onSkip,
  summary,
}: ClarifyQuestionsProps) {
  const answeredCount = questions.filter((q) => answers[q.id]).length;
  const allAnswered = answeredCount === questions.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="w-full space-y-4"
    >
      <div className="flex items-baseline gap-2">
        <span className="text-[#25D366] text-[10px] font-medium uppercase tracking-[0.16em]">
          Before I build
        </span>
        <span className="ml-auto text-gray-300 text-[10px] tabular-nums tracking-wider">
          {answeredCount} / {questions.length}
        </span>
      </div>

      {summary && (
        <p className="text-white text-[15px] font-normal leading-relaxed">{summary}</p>
      )}

      {questions.map((q) => (
        <div key={q.id} className="border border-[#1f1f1f] bg-black px-4 py-4">
          <p className="text-white text-base font-semibold mb-1">{q.question}</p>
          {q.why && <p className="text-gray-300 text-xs font-normal mb-3">{q.why}</p>}

          <div className="flex flex-col gap-2 mt-3">
            {q.options.map((opt) => {
              const selected = answers[q.id] === opt.value;
              return (
                <button
                  key={opt.value}
                  onClick={() => onAnswer(q.id, opt.value)}
                  className={`text-left px-3 py-2.5 border transition-colors duration-150 ${
                    selected
                      ? "border-[#25D366] bg-[#25D366]/10"
                      : "border-[#242424] hover:border-[#3a3a3a]"
                  }`}
                >
                  <span className="flex items-start gap-2">
                    <span
                      className={`mt-0.5 w-3.5 h-3.5 shrink-0 border flex items-center justify-center ${
                        selected ? "border-[#25D366] bg-[#25D366]" : "border-[#3a3a3a]"
                      }`}
                    >
                      {selected && <Check size={10} className="text-black" strokeWidth={3} />}
                    </span>
                    <span>
                      <span
                        className={`block text-[15px] font-medium ${
                          selected ? "text-white" : "text-gray-100"
                        }`}
                      >
                        {opt.label}
                      </span>
                      {opt.detail && (
                        <span className="block text-gray-300 text-xs font-normal mt-0.5">
                          {opt.detail}
                        </span>
                      )}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}

      <div className="flex items-center gap-3 pt-1">
        <motion.button
          onClick={onSubmit}
          disabled={!allAnswered}
          whileHover={allAnswered ? { scale: 1.03 } : undefined}
          whileTap={allAnswered ? { scale: 0.97 } : undefined}
          transition={{ type: "spring", stiffness: 500, damping: 14 }}
          className="px-5 py-2.5 bg-[#25D366] text-black text-sm font-medium rounded-sm
            border-none outline-none hover:bg-[#4ae389]
            disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-[#25D366]"
        >
          Build my game
        </motion.button>
        <button
          onClick={onSkip}
          className="text-gray-200 hover:text-white text-sm font-medium transition-colors border-none outline-none bg-transparent"
        >
          Skip, just build it
        </button>
      </div>
    </motion.div>
  );
}
