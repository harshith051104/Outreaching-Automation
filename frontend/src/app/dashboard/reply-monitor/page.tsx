"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthStore } from "@/store/auth-store";
import { useWebSocket } from "@/hooks/use-websocket";
import {
  getPendingReplies,
  generateDraft,
  approveDraft,
  rejectDraft,
  getMonitorStats,
  updateDraft,
  deleteReply,
  Reply,
  MonitorStats,
} from "@/services/monitor-api";
import { getGmailAccounts } from "@/services/gmail-api";
import { Sparkles, Mail, Trash2, Send, X, CheckCircle, AlertCircle, ChevronDown } from "lucide-react";
import { getLLMStatus, toggleLLMStatus } from "@/services/linkedin-outreach-api";

export default function ReplyMonitorPage() {
  const user = useAuthStore((s) => s.user);
  const [replies, setReplies] = useState<Reply[]>([]);
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedReply, setSelectedReply] = useState<Reply | null>(null);
  const [generatingDraft, setGeneratingDraft] = useState<string | null>(null);
  const [sendingDraft, setSendingDraft] = useState<string | null>(null);
  const [notification, setNotification] = useState<string | null>(null);
  const [gmailAccounts, setGmailAccounts] = useState<any[]>([]);
  const [selectedGmailAccountId, setSelectedGmailAccountId] = useState("");
  const [editedSubject, setEditedSubject] = useState("");
  const [editedBody, setEditedBody] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [llmDisabled, setLlmDisabled] = useState<boolean>(false);

  useEffect(() => {
    const fetchLLMStatus = async () => {
      try {
        const res = await getLLMStatus("reply_monitor");
        setLlmDisabled(res.disabled);
      } catch (err) {
        console.error("Failed to load reply monitor LLM status:", err);
      }
    };
    fetchLLMStatus();
  }, []);

  const handleToggleLLM = async () => {
    const nextState = !llmDisabled;
    try {
      await toggleLLMStatus(nextState, "reply_monitor");
      setLlmDisabled(nextState);
    } catch (err) {
      console.error("Failed to toggle LLM status:", err);
    }
  };

  useEffect(() => {
    if (selectedReply) {
      setSelectedGmailAccountId(selectedReply.gmail_account_id || selectedReply.campaign?.gmail_account_id || "");
      if (selectedReply.draft_response) {
        setEditedSubject(selectedReply.draft_response.subject || "");
        setEditedBody(selectedReply.draft_response.body_text || "");
      } else {
        setEditedSubject("");
        setEditedBody("");
      }
    } else {
      setSelectedGmailAccountId("");
      setEditedSubject("");
      setEditedBody("");
    }
  }, [selectedReply]);

  const loadData = useCallback(async () => {
    try {
      const [repliesData, statsData, accountsData] = await Promise.all([
        getPendingReplies(),
        getMonitorStats(),
        getGmailAccounts().catch(() => []),
      ]);
      setReplies(repliesData);
      setStats(statsData);
      setGmailAccounts(accountsData);
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleWsMessage = useCallback(
    (message: { type: string; data: Record<string, unknown> }) => {
      if (message.type === "new_reply") {
        setNotification(`New reply from ${message.data.from_email || "unknown"}`);
        loadData();
        setTimeout(() => setNotification(null), 5000);
      } else if (message.type === "draft_ready") {
        setNotification("Draft response generated!");
        loadData();
        setTimeout(() => setNotification(null), 3000);
      } else if (message.type === "draft_sent") {
        setNotification("Response sent successfully!");
        loadData();
        setTimeout(() => setNotification(null), 3000);
      }
    },
    [loadData]
  );

  const { isConnected } = useWebSocket({
    userId: user?.id || "",
    onMessage: handleWsMessage,
    enabled: !!user?.id,
  });

  const handleGenerateDraft = async (replyId: string, gmailAccountId?: string) => {
    setGeneratingDraft(replyId);
    try {
      await generateDraft(replyId, gmailAccountId);
      await loadData();
      const updated = await (await import("@/services/monitor-api")).getReplyDetails(replyId);
      setSelectedReply(updated);
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to generate draft response";
      setNotification(`Error: ${msg}`);
      setTimeout(() => setNotification(null), 6000);
    } finally {
      setGeneratingDraft(null);
    }
  };

  const handleApproveDraft = async (replyId: string) => {
    setSendingDraft(replyId);
    setIsSaving(true);
    try {
      await updateDraft(replyId, editedSubject, editedBody, selectedGmailAccountId);
      await approveDraft(replyId);
      await loadData();
      setSelectedReply(null);
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to send email response";
      setNotification(`Error: ${msg}`);
      setTimeout(() => setNotification(null), 6000);
    } finally {
      setSendingDraft(null);
      setIsSaving(false);
    }
  };

  const handleRejectDraft = async (replyId: string) => {
    try {
      await rejectDraft(replyId, "Rejected by user");
      await loadData();
      const updated = await (await import("@/services/monitor-api")).getReplyDetails(replyId);
      setSelectedReply(updated);
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to reject draft";
      setNotification(`Error: ${msg}`);
      setTimeout(() => setNotification(null), 6000);
    }
  };

  const handleDeleteReply = async (replyId: string) => {
    if (!confirm("Are you sure you want to delete this reply entirely?")) return;
    try {
      await deleteReply(replyId);
      await loadData();
      if (selectedReply?.id === replyId) setSelectedReply(null);
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to delete reply";
      setNotification(`Error: ${msg}`);
      setTimeout(() => setNotification(null), 6000);
    }
  };

  // Detect if a reply is a bounce/delivery notification
  const isBounceEmail = (reply: Reply) => {
    const bounceSenders = ["mailer-daemon", "postmaster", "delivery-status", "mail delivery subsystem"];
    const bounceSubjects = ["delivery status notification", "undeliverable", "mail delivery failed", "failure notice"];
    const fromEmail = (reply.from_email || "").toLowerCase();
    const subject = (reply.subject || "").toLowerCase();
    return (
      bounceSenders.some(s => fromEmail.includes(s)) ||
      bounceSubjects.some(s => subject.includes(s))
    );
  };

  const getClassificationStyle = (classification: string | null, reply?: Reply) => {
    // Check if it's actually a bounce email
    if (reply && isBounceEmail(reply)) {
      return { background: "rgba(107,114,128,0.15)", color: "#9ca3af", border: "1px solid rgba(107,114,128,0.3)", label: "bounce" };
    }
    switch (classification) {
      case "interested":
        return { background: "rgba(16,185,129,0.15)", color: "#10b981", border: "1px solid rgba(16,185,129,0.3)" };
      case "meeting_requested":
      case "meeting_request":
        return { background: "rgba(59,130,246,0.15)", color: "#3b82f6", border: "1px solid rgba(59,130,246,0.3)" };
      case "not_interested":
        return { background: "rgba(239,68,68,0.15)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.3)" };
      case "follow_up_later":
        return { background: "rgba(245,158,11,0.15)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.3)" };
      case "referral":
        return { background: "rgba(99,102,241,0.15)", color: "#6366f1", border: "1px solid rgba(99,102,241,0.3)" };
      case "question":
        return { background: "rgba(124,92,255,0.15)", color: "var(--primary)", border: "1px solid rgba(124,92,255,0.3)" };
      case "spam":
      case "bounce":
        return { background: "rgba(107,114,128,0.15)", color: "#9ca3af", border: "1px solid rgba(107,114,128,0.3)" };
      default:
        return { background: "rgba(107,114,128,0.1)", color: "var(--sidebar-text-muted)", border: "1px solid var(--card-border)" };
    }
  };

  const cardStyle: React.CSSProperties = {
    background: "var(--card-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: "16px",
    boxShadow: "var(--card-shadow)",
    backdropFilter: "blur(12px)",
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-center space-y-3">
          <div className="h-8 w-8 border-4 border-t-transparent rounded-full animate-spin mx-auto" style={{ borderColor: "var(--primary)", borderTopColor: "transparent" }}></div>
          <p style={{ color: "var(--sidebar-text-muted)" }}>Loading reply monitor...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 max-w-7xl mx-auto">
      {/* Notification Toast */}
      {notification && (
        <div
          className="fixed top-4 right-4 z-50 rounded-xl px-4 py-3 text-white shadow-xl flex items-center gap-2"
          style={{
            background: notification.startsWith("Error:") ? "rgba(239,68,68,0.9)" : "rgba(16,185,129,0.9)",
            backdropFilter: "blur(12px)",
            border: notification.startsWith("Error:") ? "1px solid rgba(239,68,68,0.5)" : "1px solid rgba(16,185,129,0.5)",
          }}
        >
          {notification.startsWith("Error:") ? <AlertCircle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
          <span className="text-sm font-medium">{notification}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--foreground-color)" }}>Reply Monitor</h1>
          <p className="text-sm" style={{ color: "var(--sidebar-text-muted)" }}>
            Real-time email reply monitoring with AI-powered draft responses
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={handleToggleLLM}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold transition-all hover:opacity-80"
            style={{
              background: llmDisabled ? "rgba(245,158,11,0.1)" : "rgba(16,185,129,0.1)",
              color: llmDisabled ? "#f59e0b" : "#10b981",
              border: llmDisabled ? "1px solid rgba(245,158,11,0.3)" : "1px solid rgba(16,185,129,0.3)",
            }}
            title={llmDisabled ? "Resume actual LLM calls" : "Pause LLM calls (use mock responses)"}
          >
            <Sparkles className="h-3.5 w-3.5" style={{ opacity: llmDisabled ? 1 : undefined }} />
            {llmDisabled ? "LLM: Mock" : "LLM: Active"}
          </button>

          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ background: isConnected ? "#10b981" : "#ef4444" }} />
            <span className="text-sm" style={{ color: "var(--sidebar-text-muted)" }}>
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            { label: "Total Replies", value: stats.total_replies, color: "var(--primary)" },
            { label: "Pending Drafts", value: stats.pending_drafts, color: "#f59e0b" },
            { label: "Sent Responses", value: stats.sent_responses, color: "#10b981" },
          ].map((s) => (
            <div key={s.label} style={cardStyle} className="p-4">
              <div className="text-sm" style={{ color: "var(--sidebar-text-muted)" }}>{s.label}</div>
              <div className="mt-1 text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
            </div>
          ))}
          <div style={cardStyle} className="p-4">
            <div className="text-sm mb-2" style={{ color: "var(--sidebar-text-muted)" }}>Classifications</div>
            <div className="flex flex-wrap gap-1">
              {Object.entries(stats.classification_breakdown).map(([key, count]) => {
                const style = getClassificationStyle(key);
                return (
                  <span
                    key={key}
                    className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                    style={{ background: style.background, color: style.color, border: style.border }}
                  >
                    {key}: {count as number}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Replies List */}
        <div className="lg:col-span-2">
          <div style={cardStyle} className="overflow-hidden">
            <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: "1px solid var(--card-border)" }}>
              <h2 className="font-semibold" style={{ color: "var(--foreground-color)" }}>
                Incoming Replies ({replies.length})
              </h2>
              <Mail className="h-4 w-4" style={{ color: "var(--sidebar-text-muted)" }} />
            </div>
            <div className="max-h-[600px] overflow-y-auto">
              {replies.length === 0 ? (
                <div className="p-8 text-center" style={{ color: "var(--sidebar-text-muted)" }}>
                  No pending replies. New replies will appear here in real-time.
                </div>
              ) : (
                replies.map((reply) => {
                  const isBounce = isBounceEmail(reply);
                  const classStyle = getClassificationStyle(reply.classification, reply);
                  const displayLabel = isBounce ? "bounce" : reply.classification;
                  return (
                    <div
                      key={reply.id}
                      className="cursor-pointer p-4 transition-colors"
                      style={{
                        borderBottom: "1px solid var(--card-border)",
                        background: selectedReply?.id === reply.id ? "rgba(124,92,255,0.08)" : "transparent",
                      }}
                      onClick={() => setSelectedReply(reply)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium font-mono text-xs" style={{ color: "var(--foreground-color)" }}>
                              {reply.from_email}
                            </span>
                            {displayLabel && (
                              <span
                                className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                                style={{ background: classStyle.background, color: classStyle.color, border: classStyle.border }}
                              >
                                {displayLabel}
                              </span>
                            )}
                            {reply.draft_response?.status === "rejected" && (
                              <span className="rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: "rgba(239,68,68,0.15)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.3)" }}>
                                Rejected
                              </span>
                            )}
                            {reply.draft_response?.status === "pending" && (
                              <span className="rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: "rgba(245,158,11,0.15)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.3)" }}>
                                Pending Review
                              </span>
                            )}
                          </div>
                          <div className="mt-1 text-sm font-medium" style={{ color: "var(--foreground-color)" }}>{reply.subject}</div>
                          <div className="mt-0.5 text-xs line-clamp-2" style={{ color: "var(--sidebar-text-muted)" }}>{reply.snippet}</div>
                          {reply.campaign && (
                            <div className="mt-1 text-[10px]" style={{ color: "var(--sidebar-text-muted)" }}>
                              Campaign: {reply.campaign.name}
                            </div>
                          )}
                        </div>
                        <div className="ml-4 text-right flex flex-col items-end gap-2 shrink-0">
                          <div className="text-[10px]" style={{ color: "var(--sidebar-text-muted)" }}>
                            {new Date(reply.received_at).toLocaleDateString()}
                          </div>
                          <div className="flex items-center gap-2">
                            {!reply.draft_response && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleGenerateDraft(reply.id);
                                }}
                                disabled={generatingDraft === reply.id}
                                className="rounded-lg px-3 py-1 text-xs text-white font-bold disabled:opacity-50 transition-all hover:opacity-80"
                                style={{ background: "var(--primary)" }}
                              >
                                {generatingDraft === reply.id ? "Generating..." : "Generate Draft"}
                              </button>
                            )}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteReply(reply.id);
                              }}
                              className="p-1 rounded hover:opacity-80 transition-opacity"
                              style={{ color: "var(--sidebar-text-muted)" }}
                              title="Delete reply"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Reply Detail / Draft Panel */}
        <div className="lg:col-span-1">
          <div style={cardStyle} className="overflow-hidden">
            <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--card-border)" }}>
              <h2 className="font-semibold" style={{ color: "var(--foreground-color)" }}>
                {selectedReply ? "Reply Details" : "Select a Reply"}
              </h2>
            </div>
            {selectedReply ? (
              <div className="p-4 space-y-4">
                {/* Reply Info */}
                <div className="space-y-2">
                  {[
                    { label: "From", value: selectedReply.from_email },
                    { label: "Subject", value: selectedReply.subject },
                    { label: "Received", value: new Date(selectedReply.received_at).toLocaleString() },
                  ].map((item) => (
                    <div key={item.label}>
                      <span className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--sidebar-text-muted)" }}>{item.label}:</span>
                      <span className="ml-2 text-sm" style={{ color: "var(--foreground-color)" }}>{item.value}</span>
                    </div>
                  ))}

                  {/* Gmail Account Selector */}
                  <div className="flex items-center justify-between py-1">
                    <span className="text-xs font-bold uppercase tracking-wider shrink-0" style={{ color: "var(--sidebar-text-muted)" }}>Reply From:</span>
                    <select
                      value={selectedGmailAccountId}
                      onChange={async (e) => {
                        const newAccountId = e.target.value;
                        setSelectedGmailAccountId(newAccountId);
                        if (newAccountId) {
                          await handleGenerateDraft(selectedReply.id, newAccountId);
                        }
                      }}
                      style={{
                        marginLeft: "8px",
                        flex: 1,
                        maxWidth: "200px",
                        borderRadius: "8px",
                        padding: "4px 8px",
                        fontSize: "12px",
                        background: "var(--sidebar-toggle-bg)",
                        border: "1px solid var(--card-border)",
                        color: "var(--foreground-color)",
                        outline: "none",
                      }}
                    >
                      <option value="">Select Gmail Account</option>
                      {gmailAccounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.name || account.email}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Reply Content */}
                <div>
                  <div className="mb-1 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--sidebar-text-muted)" }}>Reply Content:</div>
                  <div className="rounded-xl p-3 text-sm" style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)" }}>
                    {selectedReply.snippet || selectedReply.body || "No content"}
                  </div>
                </div>

                {/* Classification */}
                {selectedReply.draft_response?.classification && (
                  <div>
                    <div className="mb-1 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--sidebar-text-muted)" }}>AI Classification:</div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                          style={(() => {
                            const s = getClassificationStyle(selectedReply.draft_response.classification?.classification);
                            return { background: s.background, color: s.color, border: s.border };
                          })()}
                        >
                          {selectedReply.draft_response.classification?.classification}
                        </span>
                        <span className="text-xs" style={{ color: "var(--sidebar-text-muted)" }}>
                          Confidence: {((selectedReply.draft_response.classification?.confidence_score || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="text-xs" style={{ color: "var(--sidebar-text-muted)" }}>
                        {selectedReply.draft_response.classification?.reasoning}
                      </div>
                    </div>
                  </div>
                )}

                {/* Draft Response */}
                {selectedReply.draft_response ? (
                  <div className="space-y-3">
                    <div className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--sidebar-text-muted)" }}>
                      AI Suggested Response (Editable):
                    </div>

                    <div className="space-y-2 rounded-xl p-3" style={{ background: "rgba(124,92,255,0.05)", border: "1px solid rgba(124,92,255,0.15)" }}>
                      <div>
                        <label className="block text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Subject</label>
                        <input
                          type="text"
                          value={editedSubject}
                          onChange={(e) => setEditedSubject(e.target.value)}
                          style={{ width: "100%", borderRadius: "8px", padding: "6px 10px", fontSize: "12px", background: "var(--card-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none" }}
                        />
                      </div>
                      <div>
                        <label className="block text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Body Text</label>
                        <textarea
                          value={editedBody}
                          onChange={(e) => setEditedBody(e.target.value)}
                          style={{ width: "100%", borderRadius: "8px", padding: "6px 10px", fontSize: "12px", background: "var(--card-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)", outline: "none", minHeight: "140px", resize: "vertical" }}
                        />
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApproveDraft(selectedReply.id)}
                        disabled={sendingDraft === selectedReply.id || isSaving}
                        className="flex-1 flex items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold text-white disabled:opacity-50 transition-all hover:opacity-90"
                        style={{ background: "#10b981" }}
                      >
                        <Send className="h-3 w-3" />
                        {sendingDraft === selectedReply.id ? "Sending..." : "Approve & Send"}
                      </button>
                      <button
                        onClick={() => handleRejectDraft(selectedReply.id)}
                        className="px-4 py-2 text-xs font-bold rounded-lg transition-all hover:opacity-80"
                        style={{ background: "var(--sidebar-toggle-bg)", color: "var(--foreground-color)", border: "1px solid var(--card-border)" }}
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => handleGenerateDraft(selectedReply.id)}
                    disabled={generatingDraft === selectedReply.id}
                    className="w-full rounded-lg px-4 py-2 text-sm text-white font-bold disabled:opacity-50 hover:opacity-90 transition-all"
                    style={{ background: "var(--primary)" }}
                  >
                    {generatingDraft === selectedReply.id ? "Generating Draft..." : "Generate AI Draft Response"}
                  </button>
                )}

                {/* Lead Info */}
                {selectedReply.lead && (
                  <div className="pt-4" style={{ borderTop: "1px solid var(--card-border)" }}>
                    <div className="mb-2 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--sidebar-text-muted)" }}>Lead Info:</div>
                    <div className="space-y-1 text-sm" style={{ color: "var(--foreground-color)" }}>
                      <div>Name: <span className="font-semibold">{selectedReply.lead.name}</span></div>
                      <div>Company: <span className="font-semibold">{selectedReply.lead.company}</span></div>
                      <div>Role: <span className="font-semibold">{selectedReply.lead.role}</span></div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 text-center" style={{ color: "var(--sidebar-text-muted)" }}>
                Select a reply from the list to view details and generate a draft response.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}