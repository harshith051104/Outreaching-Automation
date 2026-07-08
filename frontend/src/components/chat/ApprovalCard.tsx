"use client";

import { useState, useEffect } from "react";
import api from "@/services/api";

export interface ApprovalAction {
  action_id: string;
  action_type: "linkedin_connections" | "email_send" | "campaign_launch" | "followup_send" | string;
  description: string;
  count?: number;
  items?: string[];
  status: "pending" | "approved" | "rejected" | "executing" | "completed" | "failed";
}

interface Props {
  action: ApprovalAction;
  onDecision: (actionId: string, decision: "approve" | "reject", resultData?: any) => void;
}

const ACTION_ICONS: Record<string, string> = {
  linkedin_connections: "💼",
  email_send: "📧",
  campaign_launch: "🚀",
  followup_send: "🔄",
};

const ACTION_COLORS: Record<string, { border: string; bg: string; badge: string }> = {
  linkedin_connections: {
    border: "rgba(10,102,194,0.3)",
    bg: "rgba(10,102,194,0.08)",
    badge: "rgba(10,102,194,0.2)",
  },
  email_send: {
    border: "rgba(124,92,255,0.3)",
    bg: "rgba(124,92,255,0.08)",
    badge: "rgba(124,92,255,0.2)",
  },
  campaign_launch: {
    border: "rgba(16,185,129,0.3)",
    bg: "rgba(16,185,129,0.08)",
    badge: "rgba(16,185,129,0.2)",
  },
  followup_send: {
    border: "rgba(245,158,11,0.3)",
    bg: "rgba(245,158,11,0.08)",
    badge: "rgba(245,158,11,0.2)",
  },
};

export default function ApprovalCard({ action: initialAction, onDecision }: Props) {
  const [action, setAction] = useState<ApprovalAction>(initialAction);
  const [loading, setLoading] = useState<"approve" | "reject" | "regenerate" | null>(null);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(() => {
    if (initialAction.status && initialAction.status !== "pending") {
      const ok = initialAction.status === "completed" || initialAction.status === "approved" || initialAction.status === "executing";
      const message = initialAction.status === "completed" || initialAction.status === "approved"
        ? "✅ Action executed."
        : initialAction.status === "rejected"
        ? "❌ Action rejected."
        : initialAction.status === "executing"
        ? "⏳ Action is executing..."
        : `⚠️ Action status: ${initialAction.status}`;
      return { ok, message };
    }
    return null;
  });

  // Keep state synchronized with props when they change (e.g. during switching sessions)
  useEffect(() => {
    setAction(initialAction);
    if (initialAction.status !== "pending") {
      const ok = initialAction.status === "completed" || initialAction.status === "approved" || initialAction.status === "executing";
      const message = initialAction.status === "completed" || initialAction.status === "approved"
        ? "✅ Action executed."
        : initialAction.status === "rejected"
        ? "❌ Action rejected."
        : initialAction.status === "executing"
        ? "⏳ Action is executing..."
        : `⚠️ Action status: ${initialAction.status}`;
      setResult({ ok, message });
    } else {
      setResult(null);
    }
  }, [initialAction]);

  const colors = ACTION_COLORS[action.action_type] || {
    border: "rgba(124,92,255,0.3)",
    bg: "rgba(124,92,255,0.08)",
    badge: "rgba(124,92,255,0.2)",
  };

  const icon = ACTION_ICONS[action.action_type] || "⚡";

  const handleDecision = async (decision: "approve" | "reject" | "regenerate") => {
    setLoading(decision);
    try {
      const res = await api.post("/chatbot/approvals/respond", {
        action_id: action.action_id,
        decision,
      });
      if (decision === "regenerate") {
        if (res.data && res.data.action_id) {
          setAction(res.data);
        }
      } else {
        setResult({
          ok: true,
          message:
            decision === "approve"
              ? `✅ Approved! ${res.data?.result?.executed ?? ""} actions executed.`
              : "❌ Action rejected.",
        });
        onDecision(action.action_id, decision, res.data);
      }
    } catch (err: any) {
      setResult({
        ok: false,
        message: err.response?.data?.detail || "Something went wrong.",
      });
    } finally {
      setLoading(null);
    }
  };

  if (result) {
    return (
      <div
        style={{
          borderRadius: "12px",
          border: `1px solid ${result.ok ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)"}`,
          background: result.ok ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
          padding: "14px 16px",
          marginTop: "8px",
          fontSize: "13px",
          color: result.ok ? "#34d399" : "#f87171",
          fontFamily: "inherit",
        }}
      >
        {result.message}
      </div>
    );
  }

  return (
    <div
      style={{
        borderRadius: "14px",
        border: `1px solid ${colors.border}`,
        background: colors.bg,
        padding: "16px",
        marginTop: "10px",
        fontFamily: "Inter, -apple-system, sans-serif",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
        <span style={{ fontSize: "22px" }}>{icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: "13px", fontWeight: "700", color: "#f5f3ff", lineHeight: 1.3 }}>
            Action Required
          </div>
          <div style={{ fontSize: "11px", color: "rgba(167,139,250,0.6)", marginTop: "2px" }}>
            Elly wants to execute a bulk action
          </div>
        </div>
        <span
          style={{
            fontSize: "10px",
            fontWeight: "700",
            padding: "3px 8px",
            borderRadius: "20px",
            background: colors.badge,
            color: "rgba(245,245,245,0.85)",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
          }}
        >
          {action.action_type.replace(/_/g, " ")}
        </span>
      </div>

      {/* Description */}
      <p
        style={{
          fontSize: "13px",
          color: "rgba(245,243,255,0.8)",
          margin: "0 0 12px",
          lineHeight: 1.5,
          whiteSpace: "pre-wrap",
        }}
      >
        {action.description}
      </p>

      {/* Count badge */}
      {action.count != null && action.count > 0 && (
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            background: "rgba(255,255,255,0.07)",
            borderRadius: "8px",
            padding: "6px 12px",
            marginBottom: "12px",
            fontSize: "12px",
            color: "rgba(245,243,255,0.7)",
          }}
        >
          <span style={{ fontSize: "15px" }}>📊</span>
          <strong style={{ color: "#f5f3ff", fontSize: "16px" }}>{action.count}</strong>
          {action.action_type === "linkedin_connections" && " connection requests"}
          {action.action_type === "email_send" && " emails"}
          {action.action_type === "campaign_launch" && " campaign(s)"}
          {action.action_type === "followup_send" && " follow-ups"}
        </div>
      )}

      {/* Item preview */}
      {action.items && action.items.length > 0 && (
        <div
          style={{
            background: "rgba(0,0,0,0.2)",
            borderRadius: "8px",
            padding: "8px 12px",
            marginBottom: "14px",
            maxHeight: "80px",
            overflow: "auto",
          }}
        >
          {action.items.slice(0, 5).map((item, i) => (
            <div
              key={i}
              style={{ fontSize: "11px", color: "rgba(167,139,250,0.7)", padding: "1px 0" }}
            >
              • {item}
            </div>
          ))}
          {action.items.length > 5 && (
            <div style={{ fontSize: "11px", color: "rgba(167,139,250,0.4)", marginTop: "2px" }}>
              + {action.items.length - 5} more…
            </div>
          )}
        </div>
      )}

      {/* Buttons */}
      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        {action.action_type === "linkedin_messages" ? (
          <>
            {/* Regenerate Button */}
            <button
              onClick={() => handleDecision("regenerate")}
              disabled={loading !== null}
              style={{
                flex: "1 1 calc(50% - 5px)",
                padding: "10px 0",
                borderRadius: "10px",
                border: "1px solid rgba(59,130,246,0.3)",
                background:
                  loading === "regenerate"
                    ? "rgba(59,130,246,0.3)"
                    : "rgba(59,130,246,0.08)",
                color: "#60a5fa",
                fontSize: "13px",
                fontWeight: "700",
                cursor: loading !== null ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                transition: "all 0.2s",
                opacity: loading !== null && loading !== "regenerate" ? 0.5 : 1,
              }}
            >
              {loading === "regenerate" ? (
                <>
                  <div
                    style={{
                      width: "14px",
                      height: "14px",
                      border: "2px solid rgba(96,165,250,0.3)",
                      borderTopColor: "#60a5fa",
                      borderRadius: "50%",
                      animation: "spin 0.8s linear infinite",
                    }}
                  />
                  Regenerating…
                </>
              ) : (
                <>🔄 Regenerate</>
              )}
            </button>

            {/* Approve & Send Button */}
            <button
              onClick={() => handleDecision("approve")}
              disabled={loading !== null}
              style={{
                flex: "1 1 calc(50% - 5px)",
                padding: "10px 0",
                borderRadius: "10px",
                border: "none",
                background:
                  loading === "approve"
                    ? "rgba(16,185,129,0.3)"
                    : "linear-gradient(135deg, #10b981, #059669)",
                color: "white",
                fontSize: "13px",
                fontWeight: "700",
                cursor: loading !== null ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                transition: "all 0.2s",
                opacity: loading !== null && loading !== "approve" ? 0.5 : 1,
              }}
            >
              {loading === "approve" ? (
                <>
                  <div
                    style={{
                      width: "14px",
                      height: "14px",
                      border: "2px solid rgba(255,255,255,0.3)",
                      borderTopColor: "white",
                      borderRadius: "50%",
                      animation: "spin 0.8s linear infinite",
                    }}
                  />
                  Sending…
                </>
              ) : (
                <>🚀 Approve & Send</>
              )}
            </button>

            {/* Cancel Button */}
            <button
              onClick={() => handleDecision("reject")}
              disabled={loading !== null}
              style={{
                flex: "1 1 100%",
                padding: "10px 0",
                borderRadius: "10px",
                border: "1px solid rgba(239,68,68,0.3)",
                background: "rgba(239,68,68,0.08)",
                color: "#f87171",
                fontSize: "13px",
                fontWeight: "700",
                cursor: loading !== null ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                transition: "all 0.2s",
                opacity: loading !== null && loading !== "reject" ? 0.5 : 1,
              }}
            >
              {loading === "reject" ? (
                <>
                  <div
                    style={{
                      width: "14px",
                      height: "14px",
                      border: "2px solid rgba(239,68,68,0.3)",
                      borderTopColor: "#f87171",
                      borderRadius: "50%",
                      animation: "spin 0.8s linear infinite",
                    }}
                  />
                  Cancelling…
                </>
              ) : (
                <>❌ Cancel</>
              )}
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => handleDecision("approve")}
              disabled={loading !== null}
              style={{
                flex: 1,
                padding: "10px 0",
                borderRadius: "10px",
                border: "none",
                background:
                  loading === "approve"
                    ? "rgba(16,185,129,0.3)"
                    : "linear-gradient(135deg, #10b981, #059669)",
                color: "white",
                fontSize: "13px",
                fontWeight: "700",
                cursor: loading !== null ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                transition: "all 0.2s",
                opacity: loading !== null && loading !== "approve" ? 0.5 : 1,
              }}
            >
              {loading === "approve" ? (
                <>
                  <div
                    style={{
                      width: "14px",
                      height: "14px",
                      border: "2px solid rgba(255,255,255,0.3)",
                      borderTopColor: "white",
                      borderRadius: "50%",
                      animation: "spin 0.8s linear infinite",
                    }}
                  />
                  Approving…
                </>
              ) : (
                <>✅ Approve</>
              )}
            </button>

            <button
              onClick={() => handleDecision("reject")}
              disabled={loading !== null}
              style={{
                flex: 1,
                padding: "10px 0",
                borderRadius: "10px",
                border: "1px solid rgba(239,68,68,0.3)",
                background: "rgba(239,68,68,0.08)",
                color: "#f87171",
                fontSize: "13px",
                fontWeight: "700",
                cursor: loading !== null ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                transition: "all 0.2s",
                opacity: loading !== null && loading !== "reject" ? 0.5 : 1,
              }}
            >
              {loading === "reject" ? (
                <>
                  <div
                    style={{
                      width: "14px",
                      height: "14px",
                      border: "2px solid rgba(239,68,68,0.3)",
                      borderTopColor: "#f87171",
                      borderRadius: "50%",
                      animation: "spin 0.8s linear infinite",
                    }}
                  />
                  Rejecting…
                </>
              ) : (
                <>❌ Reject</>
              )}
            </button>
          </>
        )}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
