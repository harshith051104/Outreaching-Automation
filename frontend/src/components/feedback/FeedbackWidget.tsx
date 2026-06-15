"use client";

import { useState } from "react";
import { Lightbulb } from "lucide-react";
import FeedbackModal from "./FeedbackModal";

export default function FeedbackWidget() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <div 
        id="global-feedback-widget"
        className="fixed bottom-6 right-6 z-50 flex items-center justify-center pointer-events-auto"
      >
        <button
          onClick={() => setIsOpen(true)}
          title="Share Suggestion or Feedback"
          className="flex items-center gap-2 rounded-full px-4 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-extrabold shadow-2xl hover:shadow-indigo-500/35 hover:-translate-y-0.5 active:translate-y-0 hover:scale-105 active:scale-95 transition-all duration-300 border border-indigo-400/20 cursor-pointer group"
          style={{
            boxShadow: "0 10px 30px -5px rgba(99, 102, 241, 0.4)",
          }}
        >
          <span className="text-base leading-none group-hover:rotate-12 group-hover:scale-110 transition-transform duration-300 select-none">
            💡
          </span>
          <span className="text-[10px] font-black uppercase tracking-widest leading-none select-none">
            Feedback
          </span>
          
          {/* Subtle pulsate glow */}
          <span className="absolute -inset-0.5 rounded-full bg-indigo-500/10 blur opacity-40 group-hover:opacity-100 group-hover:-inset-1 transition-all duration-300 pointer-events-none" />
        </button>
      </div>

      <FeedbackModal isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
}
