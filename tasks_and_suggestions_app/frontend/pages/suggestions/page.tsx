"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useAuthStore } from "@/store/auth-store";
import {
  getSuggestions,
  createSuggestion,
  upvoteSuggestion,
  deleteSuggestion,
  Suggestion,
} from "@/services/suggestion-api";
import {
  Lightbulb,
  Plus,
  Filter,
  MessageSquare,
  ThumbsUp,
  User,
  HelpCircle,
  TrendingUp,
  Sparkles,
  Calendar,
  EyeOff,
  UserCheck,
  Trash2,
} from "lucide-react";
import SuggestionMetrics from "@/components/feedback/SuggestionMetrics";

const CATEGORIES = [
  { id: "", label: "All Topics" },
  { id: "suggestion", label: "Suggestions" },
  { id: "feature_request", label: "Feature Requests" },
  { id: "improvement", label: "Improvements" },
  { id: "feedback", label: "General Feedback" },
  { id: "bug_report", label: "Bug Reports" },
];

const STATUS_THEMES: Record<string, { bg: string; color: string; border: string }> = {
  pending: { bg: "rgba(100,116,139,0.1)", color: "#94a3b8", border: "rgba(100,116,139,0.3)" },
  under_review: { bg: "rgba(245,158,11,0.1)", color: "#f59e0b", border: "rgba(245,158,11,0.3)" },
  accepted: { bg: "rgba(59,130,246,0.1)", color: "#3b82f6", border: "rgba(59,130,246,0.3)" },
  rejected: { bg: "rgba(239,68,68,0.1)", color: "#ef4444", border: "rgba(239,68,68,0.3)" },
  implemented: { bg: "rgba(16,185,129,0.1)", color: "#10b981", border: "rgba(16,185,129,0.3)" },
};

export default function SuggestionsPage() {
  const { user } = useAuthStore();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [activeCategory, setActiveCategory] = useState("");
  const [activeStatus, setActiveStatus] = useState("");
  const [activeSubmittedFrom, setActiveSubmittedFrom] = useState("");
  const [activeAnonymous, setActiveAnonymous] = useState<boolean | undefined>(undefined);

  // Submit Feedback Form State
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("suggestion");
  const [anonymous, setAnonymous] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [isSubmitOpen, setIsSubmitOpen] = useState(false);

  useEffect(() => {
    fetchSuggestionsList();
  }, [activeCategory, activeStatus, activeSubmittedFrom, activeAnonymous]);

  // Handle custom suggestion submission event for auto-refresh
  useEffect(() => {
    const handleRefresh = () => {
      fetchSuggestionsList();
    };
    if (typeof window !== "undefined") {
      window.addEventListener("suggestion-submitted", handleRefresh);
    }
    return () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("suggestion-submitted", handleRefresh);
      }
    };
  }, []);

  const fetchSuggestionsList = async () => {
    try {
      setLoading(true);
      const data = await getSuggestions({
        category: activeCategory || undefined,
        status: activeStatus || undefined,
        submitted_from: activeSubmittedFrom || undefined,
        anonymous: activeAnonymous,
      });
      setSuggestions(data);
    } catch (err) {
      console.error("Failed to load suggestions:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;

    try {
      setSubmitting(true);
      await createSuggestion({
        title,
        description,
        category,
        anonymous,
      });

      // Clear Form
      setTitle("");
      setDescription("");
      setCategory("suggestion");
      setAnonymous(false);
      setIsSubmitOpen(false);

      // Refresh list
      fetchSuggestionsList();
    } catch (err) {
      console.error("Failed to submit feedback:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleVote = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!user) return;

    // Optimistically update vote UI
    const originalSuggestions = [...suggestions];
    setSuggestions(
      suggestions.map((s) => {
        if (s.id === id) {
          const hasVoted = s.votes.includes(user.id);
          return {
            ...s,
            votes: hasVoted
              ? s.votes.filter((uid) => uid !== user.id)
              : [...s.votes, user.id],
          };
        }
        return s;
      })
    );

    try {
      const updated = await upvoteSuggestion(id);
      setSuggestions(
        suggestions.map((s) => (s.id === id ? updated : s))
      );
    } catch (err) {
      console.error("Failed to cast vote:", err);
      setSuggestions(originalSuggestions); // rollback
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm("Delete this suggestion? This cannot be undone.")) return;

    try {
      await deleteSuggestion(id);
      setSuggestions(suggestions.filter((s) => s.id !== id));
    } catch (err) {
      console.error("Failed to delete suggestion:", err);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4">
      {/* Header Banner */}
      <div
        className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl shadow-xl relative overflow-hidden"
        style={{
          background: "linear-gradient(135deg, var(--banner-bg-from) 0%, var(--banner-bg-to) 100%)",
          border: "1px solid var(--banner-border)",
        }}
      >
        <div className="absolute -right-16 -top-16 h-48 w-48 opacity-10 rounded-full blur-3xl pointer-events-none" style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)" }} />
        <div className="relative z-10 space-y-1">
          <h1 className="text-2xl font-extrabold tracking-tight flex items-center gap-2" style={{ color: "var(--banner-text)" }}>
            <Lightbulb className="h-6 w-6" style={{ color: "#fbbf24" }} />
            Ideation & Suggestion Box
          </h1>
          <p className="text-sm max-w-xl" style={{ color: "var(--banner-desc)" }}>
            Propose features, voting polls, general complaints, and platform optimization requests.
          </p>
        </div>
        <div className="relative z-10">
          <button
            onClick={() => setIsSubmitOpen(!isSubmitOpen)}
            className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold transition-all shadow-md hover:opacity-90"
            style={{ background: "var(--primary)", color: "#fff" }}
          >
            <Plus className="h-4 w-4" /> Share Idea
          </button>
        </div>
      </div>

      {/* Suggestion Form Panel */}
      {isSubmitOpen && (
        <div className="rounded-2xl p-6 space-y-4 animate-in slide-in-from-top-4 duration-200" style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)", boxShadow: "var(--card-shadow)" }}>
          <h2 className="font-bold text-sm pb-2 flex items-center gap-1.5" style={{ color: "var(--foreground-color)", borderBottom: "1px solid var(--card-border)" }}>
            <Sparkles className="h-4 w-4" style={{ color: "var(--primary)" }} /> Submit New Suggestion
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Add dark theme support or LinkedIn automation tags"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", borderRadius: "8px", color: "var(--foreground-color)", outline: "none" }}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", borderRadius: "8px", color: "var(--foreground-color)", outline: "none" }}
                >
                  <option value="suggestion">Suggestion</option>
                  <option value="feature_request">Feature Request</option>
                  <option value="improvement">Improvement</option>
                  <option value="feedback">General Feedback</option>
                  <option value="bug_report">Bug Report</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Description & Business Case *</label>
              <textarea
                required
                rows={4}
                placeholder="Explain the problem you are solving, the proposed feature, and the expected benefits..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{ width: "100%", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", borderRadius: "8px", color: "var(--foreground-color)", outline: "none", resize: "none" }}
              />
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-xs font-medium cursor-pointer select-none" style={{ color: "var(--foreground-color)" }}>
                <input
                  type="checkbox"
                  checked={anonymous}
                  onChange={(e) => setAnonymous(e.target.checked)}
                  className="h-4 w-4 rounded"
                  style={{ accentColor: "var(--primary)" }}
                />
                <span className="flex items-center gap-1">
                  <EyeOff className="h-3.5 w-3.5" style={{ color: "var(--sidebar-text-muted)" }} />
                  Post anonymously
                </span>
              </label>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsSubmitOpen(false)}
                  className="px-4 py-2 rounded-lg text-xs font-bold transition-all hover:opacity-80"
                  style={{ color: "var(--sidebar-text-muted)", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !title.trim() || !description.trim()}
                  className="px-4 py-2 rounded-lg text-white text-xs font-bold transition-all shadow-md disabled:opacity-50 hover:opacity-90"
                  style={{ background: "var(--primary)" }}
                >
                  {submitting ? "Sharing..." : "Post Idea"}
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* Suggestion Metrics Dashboard */}
      <SuggestionMetrics suggestions={suggestions} />

      {/* Categories Tabs & Filters */}
      <div className="space-y-4 border-b border-slate-800 pb-4">
        <div className="flex flex-col lg:flex-row gap-4 items-start lg:items-center justify-between">
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className="px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 cursor-pointer"
                style={{
                  background: activeCategory === cat.id ? "var(--primary)" : "var(--sidebar-toggle-bg)",
                  color: activeCategory === cat.id ? "#fff" : "var(--foreground-color)",
                  border: activeCategory === cat.id ? "1px solid var(--primary)" : "1px solid var(--card-border)",
                }}
              >
                {cat.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 shrink-0 text-xs">
            <span className="font-bold uppercase tracking-wider flex items-center gap-1" style={{ color: "var(--sidebar-text-muted)" }}>
              <Filter className="h-3.5 w-3.5" /> Status
            </span>
            <select
              value={activeStatus}
              onChange={(e) => setActiveStatus(e.target.value)}
              style={{ padding: "6px 12px", fontSize: "12px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", borderRadius: "8px", color: "var(--foreground-color)", outline: "none" }}
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="under_review">Under Review</option>
              <option value="accepted">Accepted</option>
              <option value="rejected">Rejected</option>
              <option value="implemented">Implemented</option>
            </select>
          </div>
        </div>

        {/* Quick Filters Row */}
        <div className="flex flex-wrap gap-2.5 items-center text-xs">
          <span className="font-bold uppercase tracking-widest text-[10px]" style={{ color: "var(--sidebar-text-muted)" }}>Quick Filters:</span>
          <button
            onClick={() => setActiveSubmittedFrom(activeSubmittedFrom === "widget" ? "" : "widget")}
            className="px-3 py-1 rounded-full border transition-all cursor-pointer font-bold uppercase tracking-wider text-[9px] hover:opacity-90"
            style={{
              background: activeSubmittedFrom === "widget" ? "var(--primary)" : "var(--sidebar-toggle-bg)",
              color: activeSubmittedFrom === "widget" ? "#fff" : "var(--sidebar-text-muted)",
              borderColor: activeSubmittedFrom === "widget" ? "var(--primary)" : "var(--card-border)",
            }}
          >
            Widget Submissions
          </button>
          <button
            onClick={() => setActiveAnonymous(activeAnonymous === true ? undefined : true)}
            className="px-3 py-1 rounded-full border transition-all cursor-pointer font-bold uppercase tracking-wider text-[9px] hover:opacity-90"
            style={{
              background: activeAnonymous === true ? "var(--primary)" : "var(--sidebar-toggle-bg)",
              color: activeAnonymous === true ? "#fff" : "var(--sidebar-text-muted)",
              borderColor: activeAnonymous === true ? "var(--primary)" : "var(--card-border)",
            }}
          >
            Anonymous Only
          </button>
        </div>
      </div>

      {/* Suggestions List Grid */}
      {loading ? (
        <div className="flex h-[40vh] items-center justify-center">
          <div className="text-center space-y-4">
            <div className="h-10 w-10 border-4 border-t-transparent rounded-full animate-spin mx-auto" style={{ borderColor: "var(--primary)", borderTopColor: "transparent" }}></div>
            <p className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>Syncing suggestions...</p>
          </div>
        </div>
      ) : suggestions.length === 0 ? (
        <div className="rounded-2xl py-16 text-center space-y-3" style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)" }}>
          <HelpCircle className="h-10 w-10 mx-auto" style={{ color: "var(--card-border)" }} />
          <h3 className="font-semibold text-sm" style={{ color: "var(--foreground-color)" }}>No ideas posted yet</h3>
          <p className="text-xs max-w-xs mx-auto" style={{ color: "var(--sidebar-text-muted)" }}>
            Be the first to submit a suggestion, feature request, or general feedback.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {suggestions.map((sug) => {
            const hasVoted = user ? sug.votes.includes(user.id) : false;
            const statusTheme = STATUS_THEMES[sug.status] || STATUS_THEMES.pending;
            const categoryLabel = CATEGORIES.find((c) => c.id === sug.category)?.label || sug.category;

            return (
              <div
                key={sug.id}
                className="rounded-2xl p-5 flex flex-col justify-between gap-4 hover:-translate-y-0.5 transition-all"
                style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)", boxShadow: "var(--card-shadow)" }}
              >
                <div className="space-y-3">
                  {/* Category and Status Badge */}
                  <div className="flex items-center justify-between">
                    <span
                      className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider"
                      style={{ background: "var(--sidebar-toggle-bg)", color: "var(--sidebar-text-muted)", border: "1px solid var(--card-border)" }}
                    >
                      {categoryLabel}
                    </span>
                    <span
                      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold"
                      style={{ background: statusTheme.bg, color: statusTheme.color, border: `1px solid ${statusTheme.border}` }}
                    >
                      <span className="h-1 w-1 rounded-full" style={{ background: statusTheme.color }} />
                      {sug.status.replace("_", " ")}
                    </span>
                  </div>

                  {/* Context Tags */}
                  {(sug.submitted_from === "widget" || sug.ai_priority === "high" || sug.ai_priority === "critical") && (
                    <div className="flex flex-wrap gap-1.5 pt-0.5 animate-in fade-in duration-200">
                      {sug.submitted_from === "widget" && (
                        <span className="text-[9px] font-extrabold px-1.5 py-0.5 rounded bg-indigo-950/40 text-indigo-400 border border-indigo-500/20 uppercase tracking-widest">
                          Widget
                        </span>
                      )}
                      {(sug.ai_priority === "high" || sug.ai_priority === "critical") && (
                        <span className="text-[9px] font-extrabold px-1.5 py-0.5 rounded bg-rose-950/40 text-rose-400 border border-rose-500/20 uppercase tracking-widest animate-pulse">
                          🔥 {sug.ai_priority}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Title & Desc */}
                  <Link href={`/dashboard/suggestions/${sug.id}`} className="block group space-y-1.5">
                    <h3 className="font-extrabold text-xs leading-snug group-hover:opacity-80 transition-opacity line-clamp-1" style={{ color: "var(--foreground-color)" }}>
                      {sug.title}
                    </h3>
                    <p className="text-[11px] line-clamp-3 leading-relaxed whitespace-pre-wrap" style={{ color: "var(--sidebar-text-muted)" }}>
                      {sug.description}
                    </p>
                  </Link>
                </div>

                {/* Footer card metrics */}
                <div className="flex items-center justify-between pt-3 mt-1 text-[10px]" style={{ borderTop: "1px solid var(--card-border)", color: "var(--sidebar-text-muted)" }}>
                  <div className="flex items-center gap-1">
                    {sug.anonymous ? (
                      <div className="flex items-center gap-1 italic font-light">
                        <EyeOff className="h-3 w-3 shrink-0" />
                        <span>Anonymous</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1 font-semibold">
                        <UserCheck className="h-3 w-3 shrink-0" />
                        <span>{sug.author_info?.name || "System Admin"}</span>
                      </div>
                    )}
                    <span className="mx-1">•</span>
                    <span className="flex items-center gap-0.5 font-light">
                      <Calendar className="h-3 w-3 shrink-0" />
                      {new Date(sug.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      onClick={(e) => handleVote(sug.id, e)}
                      className="flex items-center gap-1 font-bold py-1 px-2.5 rounded-lg transition-all hover:opacity-80"
                      style={{
                        background: hasVoted ? "rgba(124,92,255,0.1)" : "var(--sidebar-toggle-bg)",
                        color: hasVoted ? "var(--primary)" : "var(--sidebar-text-muted)",
                        border: hasVoted ? "1px solid rgba(124,92,255,0.3)" : "1px solid var(--card-border)",
                      }}
                    >
                      <ThumbsUp className="h-3 w-3" style={{ fill: hasVoted ? "var(--primary)" : "transparent" }} />
                      <span>{sug.votes.length}</span>
                    </button>

                    <Link
                      href={`/dashboard/suggestions/${sug.id}`}
                      className="flex items-center gap-1 font-bold py-1 px-2.5 rounded-lg transition-all hover:opacity-80"
                      style={{ background: "var(--sidebar-toggle-bg)", color: "var(--sidebar-text-muted)", border: "1px solid var(--card-border)" }}
                    >
                      <MessageSquare className="h-3 w-3" />
                      <span>Discussion</span>
                    </Link>

                    {user && (sug.user_id === user.id || (user as any).is_admin) && (
                      <button
                        onClick={(e) => handleDelete(sug.id, e)}
                        className="flex items-center gap-1 font-bold py-1 px-2.5 rounded-lg transition-all hover:opacity-80"
                        style={{ background: "rgba(239,68,68,0.08)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.2)" }}
                      >
                        <Trash2 className="h-3 w-3" />
                        <span>Delete</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
