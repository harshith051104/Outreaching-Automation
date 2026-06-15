"use client";

import { useEffect, useState } from "react";
import api from "@/services/api";
import { getGmailAccounts, updateGmailAccountName } from "@/services/gmail-api";
import { Mail, Check, X, Edit3, Loader2, AlertCircle, Plus, Info, ShieldCheck, ArrowRight } from "lucide-react";

export default function GmailPage() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  useEffect(() => {
    // Check for OAuth callback status
    const params = new URLSearchParams(window.location.search);
    if (params.get("status") === "connected") {
      setConnected(true);
      // Clean URL
      window.history.replaceState({}, "", "/dashboard/gmail");
    }
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      const data = await getGmailAccounts();
      setAccounts(data);
    } catch (err) {
      console.error("Failed to load Gmail accounts:", err);
    } finally {
      setLoading(false);
    }
  };

  const connectGmail = async () => {
    try {
      const response = await api.get<{ authorization_url: string }>("/gmail/auth");
      window.location.href = response.data.authorization_url;
    } catch (err) {
      console.error("Failed to initiate Gmail auth:", err);
    }
  };

  const startEditing = (id: string, name: string) => {
    setEditingId(id);
    setEditingName(name);
  };

  const saveName = async (id: string) => {
    try {
      await updateGmailAccountName(id, editingName);
      setEditingId(null);
      loadAccounts();
    } catch (err) {
      console.error("Failed to update account name:", err);
    }
  };

  const cardStyle: React.CSSProperties = {
    background: "var(--card-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: "16px",
    boxShadow: "var(--card-shadow)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
  };

  const bannerStyle: React.CSSProperties = {
    background: "linear-gradient(135deg, var(--banner-bg-from) 0%, var(--banner-bg-to) 100%)",
    border: "1px solid var(--banner-border)",
    borderRadius: "16px",
    boxShadow: "var(--card-shadow)",
  };

  const inputStyle: React.CSSProperties = {
    padding: "6px 12px",
    fontSize: "13px",
    background: "var(--sidebar-toggle-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: "6px",
    color: "var(--foreground-color)",
    outline: "none",
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--primary)]" />
        <p className="text-xs text-[var(--sidebar-text-muted)] font-medium">Syncing connected email clients...</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      
      {/* Hero Header */}
      <div style={bannerStyle} className="p-6 relative overflow-hidden">
        <div style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)" }} className="absolute -right-24 -top-24 h-64 w-64 opacity-10 rounded-full blur-3xl" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="bg-[rgba(124,92,255,0.1)] text-[var(--primary)] text-[10px] px-3 py-1 rounded-full font-black uppercase tracking-wider border border-[rgba(124,92,255,0.2)]">
                Email Outreach
              </span>
            </div>
            <h1 style={{ color: "var(--banner-text)" }} className="text-3xl font-black tracking-tight">
              Gmail Integrations
            </h1>
            <p style={{ color: "var(--banner-desc)" }} className="text-xs max-w-xl">
              Connect your sender profiles to automate email sequences, track delivery statuses, and import leads dynamically.
            </p>
          </div>
          
          <div>
            <button
              onClick={connectGmail}
              style={{ boxShadow: "0 4px 16px rgba(124,92,255,0.3)" }}
              className="bg-[var(--primary)] hover:brightness-110 text-white px-5 py-2.5 rounded-full text-xs font-black transition-all flex items-center gap-2 cursor-pointer"
            >
              <Plus className="h-4.5 w-4.5" /> Connect Gmail Account
            </button>
          </div>
        </div>
      </div>

      {/* Connected Accounts Card */}
      <div style={cardStyle} className="p-6 space-y-4">
        <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
          <Mail className="h-5 w-5 text-[var(--primary)]" />
          Active Senders & Accounts
        </h2>

        {connected && (
          <div className="bg-green-500/10 border border-green-500/20 text-green-500 p-3 rounded-lg text-xs font-bold flex items-center gap-2">
            <ShieldCheck className="h-4.5 w-4.5" />
            Gmail account connected successfully!
          </div>
        )}

        {accounts.length === 0 ? (
          <div className="py-12 text-center space-y-4">
            <Mail className="h-10 w-10 mx-auto text-[var(--sidebar-text-muted)] opacity-30" />
            <div className="space-y-1">
              <p className="text-sm font-bold text-[var(--foreground-color)]">No connected email channels found</p>
              <p className="text-xs text-[var(--sidebar-text-muted)] max-w-xs mx-auto">
                Add your business Gmail accounts using secure Google OAuth to dispatch cold email sequences.
              </p>
            </div>
            <button
              onClick={connectGmail}
              className="bg-[var(--sidebar-active-bg)] text-[var(--primary)] hover:bg-[var(--primary)] hover:text-white px-4 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer"
            >
              Configure First Integration
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              {accounts.map((account) => {
                const isEditing = editingId === account.id;
                return (
                  <div
                    key={account.id}
                    style={{ background: "var(--sidebar-toggle-bg)", borderColor: "var(--card-border)" }}
                    className="p-4 border rounded-xl flex flex-col justify-between gap-4"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={editingName}
                              onChange={(e) => setEditingName(e.target.value)}
                              style={inputStyle}
                              className="focus:ring-1 focus:ring-[var(--primary)] font-semibold"
                              placeholder="Sender Name"
                              autoFocus
                            />
                            <button
                              onClick={() => saveName(account.id)}
                              className="bg-green-500 hover:brightness-110 text-white p-1.5 rounded-lg transition-all cursor-pointer"
                              title="Save Name"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => setEditingId(null)}
                              style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}
                              className="border text-[var(--foreground-color)] p-1.5 rounded-lg transition-all cursor-pointer"
                              title="Cancel"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-[var(--foreground-color)] text-sm">
                              {account.name || account.email.split("@")[0].replace(/[._]/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}
                            </span>
                            <button
                              onClick={() => startEditing(account.id, account.name || account.email.split("@")[0].replace(/[._]/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()))}
                              className="text-[var(--sidebar-text-muted)] hover:text-[var(--primary)] transition-colors p-1"
                              title="Edit Sender Name"
                            >
                              <Edit3 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        )}
                        
                        <span className={`text-[9px] font-black border px-2.5 py-0.5 rounded-full ${
                          account.is_active
                            ? "bg-green-500/10 text-green-500 border-green-500/20"
                            : "bg-red-500/10 text-red-500 border-red-500/20"
                        }`}>
                          {account.is_active ? "ACTIVE" : "DISCONNECTED"}
                        </span>
                      </div>
                      
                      <p className="text-xs text-[var(--sidebar-text-muted)] font-medium truncate">{account.email}</p>
                    </div>

                    <div className="flex justify-end pt-2 border-t border-[var(--card-border)]/50">
                      <span className="text-[10px] text-[var(--sidebar-text-muted)] font-bold">
                        Linked via Google OAuth2
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
            
            <button
              onClick={connectGmail}
              className="text-xs text-[var(--primary)] hover:underline flex items-center gap-1 font-bold pt-2 cursor-pointer"
            >
              <Plus className="h-4 w-4" /> Connect another business account
            </button>
          </div>
        )}
      </div>

      {/* Guide Card */}
      <div style={cardStyle} className="p-6 space-y-4">
        <h2 style={{ borderColor: "var(--card-border)" }} className="text-base font-bold text-[var(--foreground-color)] flex items-center gap-2 border-b pb-3">
          <Info className="h-5 w-5 text-[var(--primary)]" />
          Mail Delivery Protocol & Setup
        </h2>
        
        <div className="grid sm:grid-cols-2 gap-4 text-xs text-[var(--sidebar-text-muted)] leading-relaxed">
          <div style={{ background: "var(--sidebar-toggle-bg)" }} className="p-4 rounded-xl space-y-2">
            <h4 className="font-bold text-[var(--foreground-color)] flex items-center gap-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-[var(--primary)]" />
              1. Syncing Channels
            </h4>
            <p>
              Connect G-Suite or personal Gmail accounts. The system authenticates via secure Google OAuth2 API endpoints—no password store is required.
            </p>
          </div>

          <div style={{ background: "var(--sidebar-toggle-bg)" }} className="p-4 rounded-xl space-y-2">
            <h4 className="font-bold text-[var(--foreground-color)] flex items-center gap-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-[var(--primary)]" />
              2. Sequence Dispatch
            </h4>
            <p>
              Automated cold mailing drafts are executed from your active senders. Send spacing and daily limits protect your IP address reputation.
            </p>
          </div>

          <div style={{ background: "var(--sidebar-toggle-bg)" }} className="p-4 rounded-xl space-y-2">
            <h4 className="font-bold text-[var(--foreground-color)] flex items-center gap-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-[var(--primary)]" />
              3. Response Tracking
            </h4>
            <p>
              AI agents periodically read incoming messages to parse replies, evaluate reply sentiment, and stop subsequent follow-up triggers automatically.
            </p>
          </div>

          <div style={{ background: "var(--sidebar-toggle-bg)" }} className="p-4 rounded-xl space-y-2">
            <h4 className="font-bold text-[var(--foreground-color)] flex items-center gap-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-[var(--primary)]" />
              4. Safe Connections
            </h4>
            <p>
              OAuth tokens are encrypted at rest. To terminate connections or clear session data, disconnect directly from settings at any time.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}