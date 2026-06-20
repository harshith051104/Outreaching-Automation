"use client";

import { useEffect, useState } from "react";
import {
  PROVIDER_FIELDS,
  PROVIDER_ICONS,
  IntegrationStatus,
  TestResult,
  HealthStatus,
  getIntegrations,
  saveIntegration,
  deleteIntegration,
  testIntegration,
  getHealthStatus,
  extractSpreadsheetId,
} from "@/services/integrations-api";

// ── Status Badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: IntegrationStatus }) {
  if (!status.connected) {
    return <span className="px-2 py-0.5 rounded-full text-xs bg-slate-700 text-slate-400">Not configured</span>;
  }
  if (status.last_test_ok === true) {
    return <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30">✓ Connected</span>;
  }
  if (status.last_test_ok === false) {
    return <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/20 text-red-400 ring-1 ring-red-500/30">✗ Error</span>;
  }
  return <span className="px-2 py-0.5 rounded-full text-xs bg-blue-500/20 text-blue-400 ring-1 ring-blue-500/30">Saved</span>;
}

// ── Provider Card ─────────────────────────────────────────────────────────────

function ProviderCard({
  status,
  onSave,
  onTest,
  onDelete,
}: {
  status: IntegrationStatus;
  onSave: (provider: string, creds: Record<string, string>) => Promise<void>;
  onTest: (provider: string) => Promise<TestResult>;
  onDelete: (provider: string) => Promise<void>;
}) {
  const { provider, label } = status;
  const fields = PROVIDER_FIELDS[provider] || [];
  const [values, setValues] = useState<Record<string, string>>({});
  const [showFields, setShowFields] = useState(false);
  const [showValues, setShowValues] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleSave = async () => {
    // Pre-process: extract spreadsheet ID from URL if needed
    const processed = { ...values };
    if (provider === "google_sheets" && processed.spreadsheet_id) {
      processed.spreadsheet_id = extractSpreadsheetId(processed.spreadsheet_id);
    }
    setSaving(true);
    try {
      await onSave(provider, processed);
      setShowFields(false);
      setValues({});
      setTestResult(null);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await onTest(provider);
      setTestResult(result);
    } finally {
      setTesting(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Remove ${label} credentials?`)) return;
    setDeleting(true);
    try {
      await onDelete(provider);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className={`bg-[#0d0d14] border rounded-2xl p-5 transition-all ${
      status.connected
        ? status.last_test_ok === true
          ? "border-emerald-500/30"
          : status.last_test_ok === false
          ? "border-red-500/30"
          : "border-blue-500/30"
        : "border-white/8 hover:border-white/15"
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{PROVIDER_ICONS[provider] || "🔑"}</span>
          <div>
            <h3 className="font-semibold text-white text-sm">{label}</h3>
            {status.last_tested_at && (
              <p className="text-xs text-slate-500 mt-0.5">
                Last tested: {new Date(status.last_tested_at).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Last error */}
      {status.last_error && (
        <div className="mb-3 p-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400">
          ⚠️ {status.last_error}
        </div>
      )}

      {/* Test result */}
      {testResult && (
        <div className={`mb-3 p-2.5 rounded-xl text-xs ${
          testResult.ok
            ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
            : "bg-red-500/10 border border-red-500/20 text-red-400"
        }`}>
          {testResult.ok ? "✓" : "✗"} {testResult.message}
        </div>
      )}

      {/* Input fields (shown when editing) */}
      {showFields && fields.length > 0 && (
        <div className="space-y-3 mb-4">
          {fields.map(f => (
            <div key={f.key}>
              <label className="block text-xs text-slate-400 mb-1">{f.label}</label>
              {f.isTextarea ? (
                <div className="relative">
                  <textarea
                    value={values[f.key] || ""}
                    onChange={e => setValues(v => ({ ...v, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    rows={4}
                    className="w-full bg-[#0a0a0f] border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50 resize-none font-mono"
                  />
                </div>
              ) : (
                <div className="relative">
                  <input
                    type={showValues ? "text" : "password"}
                    value={values[f.key] || ""}
                    onChange={e => setValues(v => ({ ...v, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    className="w-full bg-[#0a0a0f] border border-white/10 rounded-xl px-3 py-2 pr-10 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50"
                  />
                  <button
                    type="button"
                    onClick={() => setShowValues(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  >
                    {showValues ? "🙈" : "👁"}
                  </button>
                </div>
              )}
            </div>
          ))}
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSave}
              disabled={saving || !Object.values(values).some(v => v.trim())}
              className="flex-1 py-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-40 text-white rounded-xl text-sm font-medium transition-all"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => { setShowFields(false); setValues({}); }}
              className="px-4 py-2 bg-white/5 text-slate-400 rounded-xl text-sm hover:bg-white/10 transition-all"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Action buttons */}
      {!showFields && (
        <div className="flex gap-2 flex-wrap">
          {fields.length > 0 && (
            <button
              onClick={() => setShowFields(true)}
              className="px-3 py-1.5 bg-white/5 text-slate-300 rounded-xl text-xs hover:bg-white/10 transition-all"
            >
              {status.connected ? "Update Key" : "Configure"}
            </button>
          )}
          {status.connected && (
            <>
              <button
                onClick={handleTest}
                disabled={testing}
                className="px-3 py-1.5 bg-blue-500/20 text-blue-400 rounded-xl text-xs hover:bg-blue-500/30 transition-all disabled:opacity-50"
              >
                {testing ? "Testing..." : "Test Connection"}
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-3 py-1.5 bg-red-500/10 text-red-400 rounded-xl text-xs hover:bg-red-500/20 transition-all disabled:opacity-50 ml-auto"
              >
                {deleting ? "..." : "Remove"}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Health Badge ──────────────────────────────────────────────────────────────

function HealthBadge({ ok, name }: { ok: boolean | null; name: string }) {
  if (ok === null) return (
    <div className="flex items-center gap-2 px-3 py-2 bg-white/5 rounded-xl text-xs text-slate-400">
      <span className="w-2 h-2 rounded-full bg-slate-500" /> {name}: Not configured
    </div>
  );
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs ${
      ok ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
    }`}>
      <span className={`w-2 h-2 rounded-full ${ok ? "bg-emerald-500 animate-pulse" : "bg-red-500"}`} />
      {name}: {ok ? "Connected" : "Error"}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function IntegrationsCenter() {
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const loadAll = async () => {
    try {
      const [ints, h] = await Promise.all([getIntegrations(), getHealthStatus()]);
      setIntegrations(ints);
      setHealth(h);
    } catch (e) {
      console.error("Failed to load integrations:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const handleSave = async (provider: string, creds: Record<string, string>) => {
    await saveIntegration(provider, creds);
    showToast(`✓ ${provider} credentials saved securely.`);
    await loadAll();
  };

  const handleTest = async (provider: string): Promise<TestResult> => {
    const result = await testIntegration(provider);
    await loadAll(); // refresh status badges
    return result;
  };

  const handleDelete = async (provider: string) => {
    await deleteIntegration(provider);
    showToast(`${provider} credentials removed.`);
    await loadAll();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Toast */}
      {toast && (
        <div className="fixed top-5 right-5 z-50 px-4 py-3 bg-emerald-900/90 text-emerald-300 rounded-2xl text-sm border border-emerald-500/30 shadow-2xl backdrop-blur-sm animate-in slide-in-from-top-2">
          {toast}
        </div>
      )}

      {/* Info Banner */}
      <div className="p-4 bg-violet-500/10 border border-violet-500/20 rounded-2xl text-sm text-violet-300">
        🔐 All credentials are encrypted at rest using AES-256 and never stored in your browser.
        Keys are used server-side only and never appear in logs or responses.
      </div>

      {/* Infrastructure Health */}
      {health && (
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Platform Health</h3>
          <div className="flex flex-wrap gap-2">
            <HealthBadge ok={health.mongodb?.ok} name="MongoDB" />
            <HealthBadge ok={health.qdrant?.ok} name="Qdrant" />
            <HealthBadge ok={health.redis?.ok} name="Redis" />
          </div>
        </div>
      )}

      {/* Provider Cards Grid */}
      <div>
        <h3 className="text-sm font-semibold text-slate-300 mb-4">API Integrations</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {integrations
            .filter(i => i.provider !== "gmail_oauth")
            .map(status => (
              <ProviderCard
                key={status.provider}
                status={status}
                onSave={handleSave}
                onTest={handleTest}
                onDelete={handleDelete}
              />
            ))}
        </div>
      </div>

      {/* Note about Gmail */}
      <div className="p-4 bg-white/[0.03] border border-white/8 rounded-2xl text-sm text-slate-400">
        📧 <span className="text-slate-300 font-medium">Gmail</span> is connected via OAuth — managed in the Gmail tab above.
        Go to the Gmail tab to connect or disconnect email accounts.
      </div>
    </div>
  );
}
