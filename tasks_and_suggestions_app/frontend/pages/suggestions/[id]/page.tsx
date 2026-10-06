"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/store/auth-store";
import {
  getSuggestion,
  updateSuggestionStatus,
  upvoteSuggestion,
  getSuggestionComments,
  addSuggestionComment,
  Suggestion,
  SuggestionComment,
} from "@/services/suggestion-api";
import {
  ArrowLeft,
  Calendar,
  MessageSquare,
  ThumbsUp,
  Send,
  EyeOff,
  UserCheck,
  AlertCircle,
  HelpCircle,
  Clock,
  Briefcase,
  Sparkles,
} from "lucide-react";

const CATEGORIES = [
  { id: "suggestion", label: "Suggestion" },
  { id: "feature_request", label: "Feature Request" },
  { id: "improvement", label: "Improvement" },
  { id: "feedback", label: "General Feedback" },
  { id: "bug_report", label: "Bug Report" },
];

const STATUSES = [
  { id: "pending", label: "Pending", bg: "rgba(100,116,139,0.1) text-slate-400 border-slate-700/50" },
  { id: "under_review", label: "Under Review", bg: "rgba(245,158,11,0.1) text-amber-400 border-amber-800/30" },
  { id: "accepted", label: "Accepted", bg: "rgba(59,130,246,0.1) text-blue-400 border-blue-800/30" },
  { id: "rejected", label: "Rejected", bg: "rgba(239,68,68,0.1) text-red-400 border-red-800/30" },
  { id: "implemented", label: "Implemented", bg: "rgba(16,185,129,0.1) text-emerald-400 border-emerald-800/30" },
];

export default function SuggestionDetailsPage() {
  const { id } = useParams() as { id: string };
  const { user } = useAuthStore();

  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [comments, setComments] = useState<SuggestionComment[]>([]);
  const [loading, setLoading] = useState(true);

  const [commentText, setCommentText] = useState("");
  const [sendingComment, setSendingComment] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);

  useEffect(() => {
    if (id) {
      loadSuggestionDetails();
    }
  }, [id]);

  const loadSuggestionDetails = async () => {
    try {
      setLoading(true);
      const [sugData, commentsData] = await Promise.all([
        getSuggestion(id),
        getSuggestionComments(id).catch(() => []),
      ]);
      setSuggestion(sugData);
      setComments(commentsData);
    } catch (err) {
      console.error("Failed to load suggestion detail data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleVote = async () => {
    if (!suggestion || !user) return;

    // Optimistic update
    const originalSuggestion = { ...suggestion };
    const hasVoted = suggestion.votes.includes(user.id);
    setSuggestion({
      ...suggestion,
      votes: hasVoted
        ? suggestion.votes.filter((uid) => uid !== user.id)
        : [...suggestion.votes, user.id],
    });

    try {
      const updated = await upvoteSuggestion(id);
      setSuggestion(updated);
    } catch (err) {
      console.error("Failed to upvote:", err);
      setSuggestion(originalSuggestion);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!suggestion) return;
    try {
      setUpdatingStatus(true);
      const updated = await updateSuggestionStatus(id, newStatus);
      setSuggestion(updated);
      
      // Reload comments to see automated system messages for status adjustments
      const freshComments = await getSuggestionComments(id).catch(() => []);
      setComments(freshComments);
    } catch (err) {
      console.error("Failed to update status:", err);
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;

    try {
      setSendingComment(true);
      const newComment = await addSuggestionComment(id, commentText);
      setComments([...comments, newComment]);
      setCommentText("");
    } catch (err) {
      console.error("Failed to post comment:", err);
    } finally {
      setSendingComment(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <div className="text-center space-y-4">
          <div className="h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-gray-500 font-medium">Retrieving suggestion details...</p>
        </div>
      </div>
    );
  }

  if (!suggestion) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center space-y-4">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto" />
        <h2 className="text-lg font-bold text-slate-900">Suggestion Not Found</h2>
        <p className="text-sm text-slate-500">
          The suggestion you are looking for does not exist or has been deleted.
        </p>
        <Link
          href="/dashboard/suggestions"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-xs font-bold text-white transition-all shadow-md"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Suggestions
        </Link>
      </div>
    );
  }

  const currentCategory = CATEGORIES.find((c) => c.id === suggestion.category) || CATEGORIES[0];
  const currentStatus = STATUSES.find((s) => s.id === suggestion.status) || STATUSES[0];
  const hasVoted = user ? suggestion.votes.includes(user.id) : false;

  return (
    <div className="max-w-6xl mx-auto space-y-6 p-4">
      {/* Back navigation */}
      <div>
        <Link
          href="/dashboard/suggestions"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Idea Box
        </Link>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Post details and comments */}
        <div className="lg:col-span-2 space-y-6">
          <div 
            className="rounded-2xl p-6 space-y-5"
            style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", boxShadow: "var(--card-shadow)" }}
          >
            <div className="flex items-start justify-between gap-4">
              <h1 className="text-xl font-extrabold tracking-tight leading-snug">
                {suggestion.title}
              </h1>
            </div>

            <div className="border-t pt-4" style={{ borderColor: "var(--card-border)" }}>
              <h3 className="text-xs font-bold uppercase tracking-wider mb-2.5" style={{ color: "var(--sidebar-text-muted)" }}>
                Suggestion Details
              </h3>
              <p className="text-xs whitespace-pre-wrap leading-relaxed">
                {suggestion.description}
              </p>
            </div>

            {/* Visual Screenshot Display */}
            {suggestion.has_screenshot && suggestion.screenshot_url && (
              <div className="border-t pt-4" style={{ borderColor: "var(--card-border)" }}>
                <h3 className="text-xs font-bold uppercase tracking-wider mb-2.5" style={{ color: "var(--sidebar-text-muted)" }}>
                  Attached Screenshot
                </h3>
                <div 
                  onClick={() => setIsLightboxOpen(true)}
                  className="relative max-w-md rounded-xl overflow-hidden border bg-slate-950/20 cursor-zoom-in hover:opacity-95 active:scale-[0.99] transition-all group"
                  style={{ borderColor: "var(--card-border)" }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={suggestion.screenshot_url}
                    alt="Attached screen capture"
                    className="max-h-[220px] w-full object-contain mx-auto"
                  />
                  <div className="absolute inset-0 bg-black/10 group-hover:bg-black/25 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="px-3 py-1.5 rounded-lg bg-slate-900/80 text-white text-[10px] font-bold uppercase tracking-wider border border-slate-800">
                      Expand Screenshot
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* AI Product Manager Analysis Summary */}
            {(suggestion.ai_summary || suggestion.ai_priority || suggestion.ai_business_impact || suggestion.ai_suggested_category) && (
              <div className="border-t pt-4 space-y-3" style={{ borderColor: "var(--card-border)" }}>
                <h3 className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5" style={{ color: "var(--primary)" }}>
                  <Sparkles className="h-4 w-4" /> AI Product Insights
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-indigo-950/10 border border-indigo-900/25 p-4 rounded-xl">
                  {suggestion.ai_summary && (
                    <div className="md:col-span-2 space-y-1">
                      <span className="block text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest leading-none">
                        AI Summary
                      </span>
                      <p className="text-xs font-bold text-slate-200">
                        {suggestion.ai_summary}
                      </p>
                    </div>
                  )}
                  
                  {suggestion.ai_priority && (
                    <div className="space-y-1">
                      <span className="block text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest leading-none">
                        Priority Assessment
                      </span>
                      <span className="inline-flex items-center gap-1 text-[10px] font-black text-rose-400 bg-rose-950/20 border border-rose-900/30 px-2 py-0.5 rounded uppercase tracking-wider">
                        🔥 {suggestion.ai_priority}
                      </span>
                    </div>
                  )}

                  {suggestion.ai_suggested_category && (
                    <div className="space-y-1">
                      <span className="block text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest leading-none">
                        Suggested Category
                      </span>
                      <span className="inline-flex text-[10px] font-black text-indigo-400 bg-indigo-950/30 border border-indigo-900/30 px-2 py-0.5 rounded uppercase tracking-wider">
                        {suggestion.ai_suggested_category.replace("_", " ")}
                      </span>
                    </div>
                  )}

                  {suggestion.ai_business_impact && (
                    <div className="md:col-span-2 space-y-1 mt-1 border-t border-indigo-950/30 pt-2.5">
                      <span className="block text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest leading-none">
                        Business Impact & Value
                      </span>
                      <p className="text-xs font-medium text-slate-300 italic">
                        "{suggestion.ai_business_impact}"
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Discussion comments section */}
          <div 
            className="rounded-2xl p-6 space-y-6"
            style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", boxShadow: "var(--card-shadow)" }}
          >
            <h2 className="font-extrabold text-sm border-b pb-3 flex items-center gap-2" style={{ borderColor: "var(--card-border)" }}>
              <MessageSquare className="h-4.5 w-4.5 text-indigo-500" />
              Community Discussion ({comments.length})
            </h2>

            {/* Comments List */}
            <div className="space-y-4 max-h-[380px] overflow-y-auto pr-1">
              {comments.length === 0 ? (
                <div className="py-8 text-center text-xs" style={{ color: "var(--sidebar-text-muted)" }}>
                  No comments yet. Share your thoughts below!
                </div>
              ) : (
                comments.map((comment) => (
                  <div key={comment.id} className="flex items-start gap-3 text-xs">
                    <div className="h-8 w-8 rounded-full flex items-center justify-center font-bold shrink-0 bg-slate-800 border border-slate-700 text-slate-350">
                      {comment.author_info?.name?.charAt(0)?.toUpperCase() || "U"}
                    </div>
                    <div 
                      className="flex-1 p-3 rounded-xl space-y-1"
                      style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}
                    >
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-slate-200">
                          {comment.author_info?.name || "System Announcement"}
                        </span>
                        <span className="text-[10px]" style={{ color: "var(--sidebar-text-muted)" }}>
                          {new Date(comment.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <p className="leading-relaxed whitespace-pre-wrap font-medium" style={{ color: "var(--foreground-color)" }}>
                        {comment.message}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Comment Form */}
            <form onSubmit={handleAddComment} className="flex gap-2 pt-2">
              <input
                type="text"
                placeholder="Share your feedback or suggestions..."
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)" }}
                className="flex-1 px-3.5 py-2 text-xs rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all font-semibold"
              />
              <button
                type="submit"
                disabled={sendingComment || !commentText.trim()}
                className="p-2 bg-indigo-650 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center justify-center shrink-0 cursor-pointer"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Information panel & upvotes */}
        <div className="space-y-6">
          {/* Main Info */}
          <div 
            className="rounded-2xl p-6 space-y-5"
            style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", boxShadow: "var(--card-shadow)" }}
          >
            {/* Upvote Widget */}
            <div className="flex items-center justify-between pb-4 border-b" style={{ borderColor: "var(--card-border)" }}>
              <div className="space-y-0.5">
                <span className="block text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--sidebar-text-muted)" }}>
                  Community Upvotes
                </span>
                <span className="text-lg font-black">{suggestion.votes.length}</span>
              </div>
              <button
                onClick={handleVote}
                className={`flex items-center gap-1.5 font-bold py-2 px-4 rounded-xl border text-xs transition-all cursor-pointer ${
                  hasVoted
                    ? "bg-indigo-950/40 border-indigo-500 text-indigo-400 shadow"
                    : "bg-slate-800/40 border-slate-700 text-slate-400 hover:text-slate-200"
                }`}
              >
                <ThumbsUp className={`h-4 w-4 ${hasVoted ? "fill-indigo-500" : ""}`} />
                <span>{hasVoted ? "Upvoted" : "Upvote"}</span>
              </button>
            </div>

            {/* Category */}
            <div className="space-y-1.5">
              <span className="block text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--sidebar-text-muted)" }}>
                Category
              </span>
              <span 
                className="inline-flex text-xs font-bold rounded px-2.5 py-0.5 uppercase tracking-wider"
                style={{ background: "var(--sidebar-toggle-bg)", color: "var(--foreground-color)", border: "1px solid var(--card-border)" }}
              >
                {currentCategory.label}
              </span>
            </div>

            {/* Status with progression controller */}
            <div className="space-y-2">
              <span className="block text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--sidebar-text-muted)" }}>
                Status Progression
              </span>
              <div className="flex flex-col gap-2">
                <span
                  className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold border self-start ${currentStatus.bg}`}
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
                  {currentStatus.label}
                </span>

                {/* Status selector */}
                <div className="border-t pt-2.5 mt-1" style={{ borderColor: "var(--card-border)" }}>
                  <label className="block text-[9px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--sidebar-text-muted)" }}>
                    Transition Status
                  </label>
                  <select
                    value={suggestion.status}
                    disabled={updatingStatus}
                    onChange={(e) => handleStatusChange(e.target.value)}
                    style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)" }}
                    className="w-full text-xs rounded-lg px-2.5 py-2 font-semibold focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
                  >
                    {STATUSES.map((s) => (
                      <option key={s.id} value={s.id} className="bg-slate-900 text-white">
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Author details */}
            <div className="border-t pt-4 space-y-3" style={{ borderColor: "var(--card-border)" }}>
              <div className="flex justify-between items-center text-xs">
                <span className="font-medium flex items-center gap-1" style={{ color: "var(--sidebar-text-muted)" }}>
                  <Briefcase className="h-3.5 w-3.5" /> Author
                </span>
                {suggestion.anonymous ? (
                  <span className="font-semibold italic flex items-center gap-1" style={{ color: "var(--sidebar-text-muted)" }}>
                    <EyeOff className="h-3.5 w-3.5 text-slate-400" /> Anonymous
                  </span>
                ) : (
                  <span className="font-bold flex items-center gap-1">
                    <UserCheck className="h-3.5 w-3.5 text-slate-400" />
                    {suggestion.author_info?.name || "System User"}
                  </span>
                )}
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="font-medium flex items-center gap-1" style={{ color: "var(--sidebar-text-muted)" }}>
                  <Clock className="h-3.5 w-3.5" /> Posted On
                </span>
                <span className="font-semibold text-slate-350">
                  {new Date(suggestion.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
              </div>
            </div>

            {/* Widget Context & Technical Details */}
            <div className="border-t pt-4 space-y-3" style={{ borderColor: "var(--card-border)" }}>
              <div className="flex justify-between items-center text-xs">
                <span className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>Submission Source</span>
                <span className="font-extrabold uppercase tracking-widest text-[9px] bg-slate-800 border border-slate-700/60 px-1.5 py-0.5 rounded text-indigo-400">
                  {suggestion.submitted_from}
                </span>
              </div>

              {suggestion.page_name && (
                <div className="flex justify-between items-center text-xs">
                  <span className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>Page Context</span>
                  <span className="font-bold text-slate-200 text-right max-w-[145px] truncate" title={suggestion.page_name}>
                    {suggestion.page_name}
                  </span>
                </div>
              )}

              {suggestion.page_url && (
                <div className="flex justify-between items-center text-xs">
                  <span className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>Page URL</span>
                  <code className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded font-mono truncate max-w-[145px]" title={suggestion.page_url}>
                    {suggestion.page_url}
                  </code>
                </div>
              )}

              {suggestion.browser_info && (
                <div className="flex flex-col gap-1 border-t pt-2 text-xs" style={{ borderColor: "var(--card-border)" }}>
                  <span className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>Browser Info</span>
                  <div className="bg-slate-950/30 text-[9px] p-2 rounded border border-slate-800 font-mono text-slate-400 break-all leading-normal">
                    {suggestion.browser_info}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Lightbox Dialog Overlay */}
      {isLightboxOpen && suggestion.screenshot_url && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md animate-fade-in"
          onClick={() => setIsLightboxOpen(false)}
        >
          <div className="relative max-w-5xl max-h-[90vh] w-full flex flex-col items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={suggestion.screenshot_url}
              alt="Zoomed Screenshot"
              className="max-h-[80vh] object-contain rounded-xl select-none"
            />
            <button
              onClick={() => setIsLightboxOpen(false)}
              className="absolute -top-12 right-0 px-3.5 py-2 text-white bg-slate-900 border border-slate-850 hover:bg-slate-800 rounded-xl hover:scale-105 active:scale-95 transition-all cursor-pointer font-bold uppercase tracking-widest text-[10px] shadow-lg"
            >
              Close Zoom
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
