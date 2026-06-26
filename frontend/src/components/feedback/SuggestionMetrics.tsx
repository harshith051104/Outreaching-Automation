"use client";

import { Suggestion } from "@/services/suggestion-api";
import { MessageSquare, Laptop, Clock, CheckCircle2, AlertTriangle, EyeOff } from "lucide-react";

interface SuggestionMetricsProps {
  suggestions: Suggestion[];
}

export default function SuggestionMetrics({ suggestions }: SuggestionMetricsProps) {
  const total = suggestions.length;
  const widget = suggestions.filter((s) => s.submitted_from === "widget").length;
  
  const pending = suggestions.filter((s) => s.status === "pending").length;
  const underReview = suggestions.filter((s) => s.status === "under_review").length;
  const implemented = suggestions.filter((s) => s.status === "implemented").length;
  const rejected = suggestions.filter((s) => s.status === "rejected").length;

  const cards = [
    {
      title: "Total Submissions",
      value: total,
      desc: `${widget} via Widget • ${total - widget} via Feed`,
      icon: MessageSquare,
      color: "from-blue-600 to-indigo-600",
      iconColor: "text-blue-400",
    },
    {
      title: "In Review Progress",
      value: pending + underReview,
      desc: `${pending} Pending • ${underReview} Under Review`,
      icon: Clock,
      color: "from-amber-600 to-orange-600",
      iconColor: "text-amber-400",
    },
    {
      title: "Implemented & Resolved",
      value: implemented,
      desc: `${rejected} Rejected or Archived`,
      icon: CheckCircle2,
      color: "from-emerald-600 to-teal-600",
      iconColor: "text-emerald-400",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((c, i) => {
        const Icon = c.icon;
        return (
          <div
            key={i}
            className="rounded-2xl p-5 border border-slate-800 bg-slate-900/60 shadow-lg relative overflow-hidden flex flex-col justify-between"
          >
            {/* Subtle background glow */}
            <div className={`absolute -right-8 -top-8 h-24 w-24 opacity-5 rounded-full blur-2xl pointer-events-none bg-gradient-to-br ${c.color}`} />
            
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                {c.title}
              </span>
              <Icon className={`h-5 w-5 ${c.iconColor}`} />
            </div>

            <div className="mt-3.5 space-y-0.5">
              <span className="text-2xl font-black tracking-tight text-white leading-none">
                {c.value}
              </span>
              <p className="text-[10px] text-slate-400 font-semibold leading-relaxed">
                {c.desc}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
