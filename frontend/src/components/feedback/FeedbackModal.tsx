"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { Sparkles, MessageSquare, X, Info, Lightbulb, EyeOff } from "lucide-react";
import ScreenshotCapture from "./ScreenshotCapture";
import { createSuggestion } from "@/services/suggestion-api";
import api from "@/services/api";

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const CATEGORIES = [
  { id: "suggestion", label: "Suggestion" },
  { id: "feature_request", label: "Feature Request" },
  { id: "improvement", label: "Improvement" },
  { id: "feedback", label: "General Feedback" },
  { id: "bug_report", label: "Bug Report" },
];

export default function FeedbackModal({ isOpen, onClose }: FeedbackModalProps) {
  const pathname = usePathname();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("suggestion");
  const [anonymous, setAnonymous] = useState(false);
  
  const [screenshotData, setScreenshotData] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Hidden state for capture hide-and-show
  const [isHiddenForCapture, setIsHiddenForCapture] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setTitle("");
      setDescription("");
      setCategory("suggestion");
      setAnonymous(false);
      setScreenshotData(null);
      setError(null);
      setSuccess(false);
      setIsHiddenForCapture(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Convert pathname to nice page label
  const getPageName = (path: string): string => {
    const mapping: Record<string, string> = {
      "/dashboard": "Dashboard",
      "/dashboard/campaigns": "Campaigns",
      "/dashboard/leads": "Leads",
      "/dashboard/linkedin": "LinkedIn Campaigns",
      "/dashboard/gmail": "Gmail Automation",
      "/dashboard/analytics": "Analytics",
      "/dashboard/tasks": "Task Tracker",
      "/dashboard/chatbot": "AI Copilot",
      "/dashboard/settings": "Settings",
      "/dashboard/suggestions": "Suggestions Box",
    };
    
    if (mapping[path]) return mapping[path];
    if (path.startsWith("/dashboard/suggestions/")) return "Suggestion Details";
    if (path.startsWith("/dashboard/campaigns/")) return "Campaign Details";

    const segments = path.split("/").filter(Boolean);
    if (segments.length > 0) {
      return segments.map(s => s.charAt(0).toUpperCase() + s.slice(1).replace(/-/g, ' ')).join(" > ");
    }
    return "AI Outreach Platform";
  };

  const currentUrl = typeof window !== "undefined" ? window.location.href : "";
  const pageName = getPageName(pathname);

  // Convert Base64 dataURL to Blob for file upload
  const dataURLtoBlob = (dataurl: string) => {
    const arr = dataurl.split(",");
    const mime = arr[0].match(/:(.*?);/)![1];
    const bstr = atob(arr[1]);
    let n = bstr.length;
    const u8arr = new Uint8Array(n);
    while (n--) {
      u8arr[n] = bstr.charCodeAt(n);
    }
    return new Blob([u8arr], { type: mime });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;

    try {
      setSubmitting(true);
      setError(null);

      let screenshotUrl = "";
      let hasScreenshot = false;

      // 1. Upload screenshot if available
      if (screenshotData) {
        try {
          const blob = dataURLtoBlob(screenshotData);
          const formData = new FormData();
          formData.append("file", blob, "feedback_screenshot.png");

          const fileResp = await api.post("/files/upload", formData, {
            headers: { "Content-Type": "multipart/form-data" },
          });
          
          if (fileResp.data && fileResp.data.download_url) {
            screenshotUrl = fileResp.data.download_url;
            hasScreenshot = true;
          }
        } catch (uploadErr) {
          console.error("Screenshot upload failed, continuing without screenshot", uploadErr);
        }
      }

      // 2. Submit Suggestion
      await createSuggestion({
        title: title.trim(),
        description: description.trim(),
        category,
        anonymous,
        submitted_from: "widget",
        page_name: pageName,
        page_url: pathname,
        screenshot_url: screenshotUrl || undefined,
        has_screenshot: hasScreenshot,
        browser_info: typeof navigator !== "undefined" ? navigator.userAgent : "Unknown Browser",
      });

      setSuccess(true);
      setTimeout(() => {
        onClose();
        // Fire custom event to refresh lists if Suggestions list page is open
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event("suggestion-submitted"));
        }
      }, 1500);

    } catch (err: any) {
      console.error("Failed to submit feedback suggestion:", err);
      setError(err?.response?.data?.detail || "An error occurred. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div 
      id="quick-suggestion-modal"
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-all duration-300 ${
        isHiddenForCapture ? "opacity-0 pointer-events-none" : "opacity-100"
      }`}
    >
      <div className="w-full max-w-lg rounded-2xl p-6 bg-slate-900 border border-slate-800 text-white shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
        <div className="absolute -right-20 -top-20 h-48 w-48 opacity-10 rounded-full blur-3xl pointer-events-none bg-indigo-500" />
        
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
          <h2 className="text-base font-extrabold tracking-tight flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-400" />
            Quick Suggestion & Feedback
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50 hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="h-4 w-4 text-slate-400 hover:text-white" />
          </button>
        </div>

        {success ? (
          <div className="py-12 flex flex-col items-center justify-center text-center space-y-3">
            <div className="h-12 w-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30 animate-bounce">
              <Sparkles className="h-6 w-6" />
            </div>
            <h3 className="font-extrabold text-base text-slate-100">Thank you!</h3>
            <p className="text-xs text-slate-400 max-w-xs">
              Your suggestion has been logged. AI is generating metrics and PM outline in the background.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto pr-1 py-4 space-y-4">
            {error && (
              <div className="p-3 text-xs bg-rose-950/40 border border-rose-500/30 text-rose-300 rounded-xl">
                {error}
              </div>
            )}

            {/* Auto Context Info Banner */}
            <div className="flex gap-2 p-3 bg-slate-800/40 rounded-xl border border-slate-800/80 text-[11px] text-slate-400 leading-normal">
              <Info className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
              <div>
                Auto-collecting context: <strong className="text-slate-300">{pageName}</strong> <span className="opacity-60">({pathname})</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5 text-slate-400">
                  Category
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full text-xs font-semibold bg-slate-800 border border-slate-700/60 rounded-xl px-3 py-2.5 text-slate-200 outline-none focus:ring-1 focus:ring-indigo-500 transition-all"
                >
                  {CATEGORIES.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5 text-slate-400">
                  Suggestion Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Campaign duplication clone button"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full text-xs bg-slate-800 border border-slate-700/60 rounded-xl px-3 py-2 text-slate-100 outline-none focus:ring-1 focus:ring-indigo-500 transition-all font-medium"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5 text-slate-400">
                Description & Business Impact *
              </label>
              <textarea
                required
                rows={3}
                placeholder="What pain point are you facing? Describe your solution idea and the benefit it brings."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full text-xs bg-slate-800 border border-slate-700/60 rounded-xl px-3 py-2 text-slate-100 outline-none focus:ring-1 focus:ring-indigo-500 transition-all resize-none font-medium"
              />
            </div>

            {/* Screenshot Capture Section */}
            <div className="space-y-2 border-t border-slate-800 pt-3.5">
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Attachment
              </label>
              <ScreenshotCapture
                onScreenshotConfirmed={setScreenshotData}
                onCaptureStart={() => setIsHiddenForCapture(true)}
                onCaptureEnd={() => setIsHiddenForCapture(false)}
              />
            </div>

            {/* Footer Form Controls */}
            <div className="flex items-center justify-between border-t border-slate-800 pt-4 mt-2 shrink-0">
              <label className="flex items-center gap-2 text-xs font-semibold cursor-pointer select-none text-slate-300 hover:text-white transition-colors">
                <input
                  type="checkbox"
                  checked={anonymous}
                  onChange={(e) => setAnonymous(e.target.checked)}
                  className="h-4 w-4 rounded"
                  style={{ accentColor: "var(--primary)" }}
                />
                <span className="flex items-center gap-1">
                  <EyeOff className="h-3.5 w-3.5 text-slate-400" />
                  Post anonymously
                </span>
              </label>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={submitting}
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-750 transition-colors border border-slate-700/60 cursor-pointer disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !title.trim() || !description.trim()}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 transition-all shadow-md hover:shadow-indigo-500/25 active:scale-95 disabled:opacity-50 cursor-pointer"
                >
                  {submitting ? "Submitting..." : "Submit Suggestion"}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
