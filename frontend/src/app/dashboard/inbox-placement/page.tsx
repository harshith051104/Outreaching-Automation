"use client";

import { useEffect, useState } from "react";
import api from "@/services/api";
import { getGmailAccounts } from "@/services/gmail-api";
import type { GmailAccount } from "@/types/gmail";
import {
  Mail,
  ShieldCheck,
  ShieldAlert,
  Loader2,
  Send,
  History,
  AlertCircle,
  CheckCircle,
  Inbox,
  ArrowRight
} from "lucide-react";

interface InboxTest {
  id: string;
  from_email: string;
  to_email: string;
  subject: string;
  body: string;
  result: "inbox" | "spam";
  spam_score: number;
  sent_real?: boolean;
  created_at: string;
}

export default function InboxPlacementPage() {
  const [gmailAccounts, setGmailAccounts] = useState<GmailAccount[]>([]);
  const [form, setForm] = useState({
    from_email: "",
    to_email: "",
    subject: "",
    body: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [history, setHistory] = useState<InboxTest[]>([]);
  const [lastResult, setLastResult] = useState<InboxTest | null>(null);

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const accounts = await getGmailAccounts();
        setGmailAccounts(accounts);
        if (accounts.length > 0) {
          setForm((prev) => ({ ...prev, from_email: accounts[0].email }));
        }
        await fetchHistory();
      } catch (err) {
        console.error("Failed to load initial data:", err);
      }
    };
    loadInitialData();
  }, []);

  const fetchHistory = async () => {
    try {
      const response = await api.get("/inbox-placement/history");
      if (response.data?.status === "success") {
        setHistory(response.data.history || []);
      }
    } catch (err) {
      console.error("Failed to fetch test history:", err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.from_email || !form.to_email || !form.subject || !form.body) {
      setError("Please fill in all fields.");
      return;
    }

    setLoading(true);
    setError("");
    setSuccess("");
    setLastResult(null);

    try {
      const response = await api.post("/inbox-placement/test", form);
      if (response.data?.status === "success") {
        const test = response.data.test;
        setLastResult(test);
        setHistory((prev) => [test, ...prev]);
        setSuccess(
          test.sent_real 
            ? "Test email sent and deliverability analyzed successfully!" 
            : "Deliverability analyzed successfully (mock delivery)!"
        );
        // Clear subject & body
        setForm((prev) => ({ ...prev, subject: "", body: "" }));
      } else {
        setError("Failed to process deliverability test.");
      }
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || "An error occurred during testing.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTest = (test: InboxTest) => {
    setForm({
      from_email: test.from_email,
      to_email: test.to_email,
      subject: test.subject,
      body: test.body,
    });
    setLastResult(test);
    setSuccess("");
    setError("");
  };

  const inboxRate = history.length > 0
    ? Math.round((history.filter((t) => t.result === "inbox").length / history.length) * 100)
    : 0;

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4">
      {/* Header Banner */}
      <div
        className="rounded-2xl p-8 border relative overflow-hidden shadow-xl"
        style={{
          background: "linear-gradient(135deg, var(--banner-bg-from) 0%, var(--banner-bg-to) 100%)",
          border: "1px solid var(--banner-border)",
        }}
      >
        <div className="absolute -right-16 -top-16 h-48 w-48 opacity-10 rounded-full blur-3xl pointer-events-none" style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)" }} />
        <div className="relative z-10 space-y-3">
          <span className="text-[10px] px-3 py-1 rounded-full font-black uppercase tracking-wider" style={{ background: "rgba(124,92,255,0.1)", color: "var(--primary)", border: "1px solid rgba(124,92,255,0.2)" }}>
            Deliverability Analyzer
          </span>
          <h1 className="text-3xl font-extrabold tracking-tight" style={{ color: "var(--banner-text)" }}>Inbox Placement Test</h1>
          <p className="max-w-2xl text-sm leading-relaxed" style={{ color: "var(--banner-desc)" }}>
            Send dynamic verification drafts to assess spam classifications. Computes realistic spam scores using pattern detection, keyword analysis, and message layout metadata.
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-4">
        {/* Left Form Panel */}
        <div className="lg:col-span-3 space-y-4">
          {error && (
            <div className="flex items-center gap-3 bg-red-50 text-red-700 px-4 py-3 rounded-xl border border-red-100 text-xs">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-center gap-3 bg-green-50 text-green-700 px-4 py-3 rounded-xl border border-green-100 text-xs">
              <CheckCircle className="h-4 w-4 shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {lastResult && (
            <div
              className={`rounded-2xl p-5 border shadow-sm transition-all animate-in fade-in duration-200 ${
                lastResult.result === "inbox" 
                  ? "bg-emerald-50/50 border-emerald-100 text-emerald-950" 
                  : "bg-rose-50/50 border-rose-100 text-rose-950"
              }`}
            >
              <div className="flex items-center gap-4">
                <div
                  className={`flex h-14 w-14 items-center justify-center rounded-2xl shadow-sm ${
                    lastResult.result === "inbox"
                      ? "bg-emerald-500 text-white"
                      : "bg-rose-500 text-white"
                  }`}
                >
                  {lastResult.result === "inbox" ? (
                    <ShieldCheck className="h-7 w-7" />
                  ) : (
                    <ShieldAlert className="h-7 w-7" />
                  )}
                </div>
                <div className="space-y-1">
                  <p className="text-lg font-bold">
                    {lastResult.result === "inbox" ? "High Deliverability: Inbox" : "Risk Detected: Spam Folder"}
                  </p>
                  <div className="flex gap-3 text-xs opacity-80">
                    <span>Spam Score: <strong className="font-bold">{lastResult.spam_score.toFixed(1)}/10</strong></span>
                    <span>•</span>
                    <span>Status: <strong className="font-bold uppercase">{lastResult.sent_real ? "Delivered via Gmail" : "Simulated Local"}</strong></span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div
            className="rounded-2xl p-6 border space-y-5"
            style={{
              background: "var(--card-bg)",
              border: "1px solid var(--card-border)",
              boxShadow: "var(--card-shadow)",
              backdropFilter: "blur(12px)",
            }}
          >
            <div className="flex items-center gap-2 pb-3" style={{ borderBottom: "1px solid var(--card-border)" }}>
              <Mail className="h-5 w-5" style={{ color: "var(--primary)" }} />
              <h2 className="font-bold text-sm" style={{ color: "var(--foreground-color)" }}>Send Placement Test Draft</h2>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--sidebar-text-muted)" }}>From Connected Gmail Account *</label>
                  <select
                    value={form.from_email}
                    onChange={(e) => setForm({ ...form, from_email: e.target.value })}
                    style={{ width: "100%", borderRadius: "8px", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none", fontWeight: 600 }}
                    required
                  >
                    <option value="">Select Gmail Account</option>
                    {gmailAccounts.map((account) => (
                      <option key={account.id} value={account.email}>
                        {account.email} {account.is_active ? "" : "(Inactive)"}
                      </option>
                    ))}
                  </select>
                  {gmailAccounts.length === 0 && (
                    <p className="mt-1 text-[10px] font-medium" style={{ color: "#f59e0b" }}>
                      No connected Gmail accounts. Delivering as Simulated Local.
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--sidebar-text-muted)" }}>To Destination Email *</label>
                  <input
                    type="email"
                    value={form.to_email}
                    onChange={(e) => setForm({ ...form, to_email: e.target.value })}
                    placeholder="test@yourdomain.com"
                    style={{ width: "100%", borderRadius: "8px", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none" }}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--sidebar-text-muted)" }}>Subject *</label>
                <input
                  type="text"
                  value={form.subject}
                  onChange={(e) => setForm({ ...form, subject: e.target.value })}
                  placeholder="e.g. Urgent review: campaign analytics reports"
                  style={{ width: "100%", borderRadius: "8px", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none" }}
                  required
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--sidebar-text-muted)" }}>Email Body *</label>
                <textarea
                  value={form.body}
                  onChange={(e) => setForm({ ...form, body: e.target.value })}
                  rows={6}
                  placeholder="Write your email body draft here..."
                  style={{ width: "100%", borderRadius: "8px", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none", resize: "none" }}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="flex items-center justify-center gap-2 rounded-lg py-2.5 px-6 text-xs font-bold text-white hover:opacity-90 transition-all shadow-md disabled:opacity-50"
                style={{ background: "var(--primary)" }}
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Verifying Deliverability...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" /> Run Placement Test
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Stats & Sidebar History */}
        <div className="lg:col-span-1 space-y-6">
          <div className="rounded-2xl p-5 space-y-4" style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)", boxShadow: "var(--card-shadow)" }}>
            <h3 className="font-bold uppercase tracking-wider text-[10px] flex items-center gap-1.5" style={{ color: "var(--sidebar-text-muted)" }}>
              Deliverability Scorecard
            </h3>
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between pb-2" style={{ borderBottom: "1px solid var(--card-border)" }}>
                <span className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>Total Tests Run</span>
                <span className="font-extrabold" style={{ color: "var(--foreground-color)" }}>{history.length}</span>
              </div>
              <div className="flex items-center justify-between pb-2" style={{ borderBottom: "1px solid var(--card-border)" }}>
                <span className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>Inbox Placement</span>
                <span className="font-extrabold" style={{ color: "#10b981" }}>
                  {history.filter((t) => t.result === "inbox").length}
                </span>
              </div>
              <div className="flex items-center justify-between pb-2" style={{ borderBottom: "1px solid var(--card-border)" }}>
                <span className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>Spam Folder</span>
                <span className="font-extrabold" style={{ color: "#ef4444" }}>
                  {history.filter((t) => t.result === "spam").length}
                </span>
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>Deliverability Rate</span>
                <span className="font-extrabold" style={{ color: "var(--foreground-color)" }}>{inboxRate}%</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl p-5 space-y-4" style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)", boxShadow: "var(--card-shadow)" }}>
            <h3 className="font-bold uppercase tracking-wider text-[10px] flex items-center gap-1.5" style={{ color: "var(--sidebar-text-muted)" }}>
              <History className="h-4 w-4" /> Recent Placements
            </h3>
            
            {history.length === 0 ? (
              <p className="text-xs italic py-4" style={{ color: "var(--sidebar-text-muted)" }}>No deliverability tests executed yet.</p>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                {history.map((test) => (
                  <button
                    key={test.id}
                    onClick={() => handleSelectTest(test)}
                    className="w-full text-left p-3 rounded-xl transition-all flex flex-col gap-1.5 hover:opacity-90"
                    style={{
                      background: lastResult?.id === test.id ? "rgba(124,92,255,0.1)" : "var(--sidebar-toggle-bg)",
                      border: lastResult?.id === test.id ? "1px solid rgba(124,92,255,0.3)" : "1px solid var(--card-border)",
                      color: "var(--foreground-color)",
                    }}
                  >
                    <div className="flex justify-between items-center w-full">
                      <span className="text-[10px] font-semibold truncate max-w-[100px]" style={{ color: "var(--sidebar-text-muted)" }}>
                        To: {test.to_email}
                      </span>
                      <span
                        className="rounded px-1.5 py-0.5 text-[8px] font-bold uppercase"
                        style={{
                          background: test.result === "inbox" ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)",
                          color: test.result === "inbox" ? "#10b981" : "#ef4444",
                          border: test.result === "inbox" ? "1px solid rgba(16,185,129,0.3)" : "1px solid rgba(239,68,68,0.3)",
                        }}
                      >
                        {test.result}
                      </span>
                    </div>
                    <p className="truncate text-xs font-bold w-full" style={{ color: "var(--foreground-color)" }}>{test.subject}</p>
                    <span className="text-[9px]" style={{ color: "var(--sidebar-text-muted)" }}>
                      {new Date(test.created_at).toLocaleDateString()}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
