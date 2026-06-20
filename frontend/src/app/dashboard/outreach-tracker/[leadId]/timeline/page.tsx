"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  CHECKBOX_FIELDS,
  CHECKBOX_ICONS,
  CHECKBOX_LABELS,
  TimelineEvent,
  TrackerLead,
  getTimeline,
  logTimelineEvent,
  updateCheckboxes,
} from "@/services/outreach-tracker-api";
import api from "@/services/api";

function formatDateTime(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function eventColor(type: string) {
  const map: Record<string, string> = {
    connection_accepted: "text-emerald-400 bg-emerald-500/20",
    linkedin_reply: "text-cyan-400 bg-cyan-500/20",
    email_replied: "text-blue-400 bg-blue-500/20",
    meeting_scheduled: "text-violet-400 bg-violet-500/20",
    email_sent: "text-slate-400 bg-slate-500/20",
    opportunity_closed: "text-amber-400 bg-amber-500/20",
    note_added: "text-slate-300 bg-slate-500/10",
    sheet_synced: "text-indigo-400 bg-indigo-500/20",
  };
  return map[type] || "text-slate-400 bg-slate-500/20";
}

function eventIcon(type: string) {
  const map: Record<string, string> = {
    followed: "👋", connection_sent: "📤", connection_accepted: "🤝",
    first_message_sent: "💬", linkedin_reply: "💭", email_sent: "📧",
    email_opened: "👁", email_replied: "↩️", followup_1_sent: "📨",
    followup_2_sent: "📩", followup_3_sent: "📬", meeting_scheduled: "📅",
    opportunity_closed: "✅", status_changed: "🔄", note_added: "📝",
    checkbox_updated: "☑️", sheet_synced: "📊", assigned: "👤",
  };
  return map[type] || "📌";
}

export default function LeadTimelinePage() {
  const params = useParams();
  const router = useRouter();
  const leadId = params.leadId as string;

  const [lead, setLead] = useState<TrackerLead | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [checkUpdating, setCheckUpdating] = useState<Set<string>>(new Set());

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const [leadData, tl] = await Promise.all([
          api.get(`/outreach-tracker/${leadId}`).then((r) => r.data),
          getTimeline(leadId, 200),
        ]);
        setLead(leadData);
        setTimeline(tl);
      } catch (e) {
        console.error("Failed to load timeline:", e);
      } finally {
        setLoading(false);
      }
    }
    if (leadId) fetchData();
  }, [leadId]);

  const handleCheckboxChange = async (field: string, val: boolean) => {
    if (!lead) return;
    setCheckUpdating(prev => new Set(prev).add(field));
    setLead(prev => prev ? { ...prev, [field]: val } : null);
    try {
      const updated = await updateCheckboxes(leadId, { [field]: val });
      setLead(updated);
      const tl = await getTimeline(leadId, 200);
      setTimeline(tl);
    } catch (e) {
      setLead(prev => prev ? { ...prev, [field]: !val } : null);
    } finally {
      setCheckUpdating(prev => { const s = new Set(prev); s.delete(field); return s; });
    }
  };

  const handleNoteSubmit = async () => {
    if (!note.trim() || !lead) return;
    setSaving(true);
    try {
      await updateCheckboxes(leadId, { notes: note.trim() });
      await logTimelineEvent(leadId, "note_added", note.trim());
      setNote("");
      const tl = await getTimeline(leadId, 200);
      setTimeline(tl);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="w-10 h-10 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6 max-w-5xl mx-auto">
      {/* Back button */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-slate-400 hover:text-white mb-6 transition-colors text-sm"
      >
        ← Back to Tracker
      </button>

      {/* Lead info header */}
      {lead ? (
        <div className="bg-[#12121a] border border-white/10 rounded-2xl p-6 mb-6">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500/30 to-cyan-500/30 flex items-center justify-center text-2xl font-bold text-white">
              {lead.name[0]?.toUpperCase()}
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-white">{lead.name}</h1>
              <div className="flex items-center gap-4 mt-1 text-sm text-slate-400">
                <span>📧 {lead.email}</span>
                {lead.company && <span>🏢 {lead.company}</span>}
                {lead.focus && <span>🎯 {lead.focus}</span>}
                {lead.assigned_user && (
                  <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-400 rounded-lg">
                    👤 {lead.assigned_user}
                  </span>
                )}
              </div>
              {lead.linkedin && (
                <a
                  href={lead.linkedin}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 text-sm mt-1 inline-block transition-colors"
                >
                  💼 LinkedIn Profile →
                </a>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-[#12121a] border border-white/10 rounded-2xl p-6 mb-6 text-slate-400">
          Lead not found.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Checkboxes panel */}
        <div className="lg:col-span-1">
          <div className="bg-[#12121a] border border-white/10 rounded-2xl p-5">
            <h2 className="font-semibold text-white mb-4">Outreach Milestones</h2>
            <div className="space-y-2">
              {CHECKBOX_FIELDS.map(field => {
                const checked = lead ? !!lead[field as keyof TrackerLead] : false;
                const isUpdating = checkUpdating.has(field);
                return (
                  <button
                    key={field}
                    onClick={() => handleCheckboxChange(field, !checked)}
                    disabled={isUpdating}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-left ${
                      checked
                        ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30"
                        : "bg-white/[0.03] text-slate-400 hover:bg-white/[0.06]"
                    } ${isUpdating ? "opacity-50 cursor-wait" : ""}`}
                  >
                    <span className="text-lg">{CHECKBOX_ICONS[field]}</span>
                    <span className="flex-1 text-sm">{CHECKBOX_LABELS[field]}</span>
                    <span className={`w-4 h-4 rounded-full border flex items-center justify-center text-xs ${
                      checked ? "bg-emerald-500 border-emerald-500 text-white" : "border-white/20"
                    }`}>
                      {checked && "✓"}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Notes */}
            <div className="mt-5 pt-5 border-t border-white/10">
              <h3 className="text-sm font-medium text-slate-300 mb-2">Add Note</h3>
              <textarea
                value={note}
                onChange={e => setNote(e.target.value)}
                placeholder="Add a note about this lead..."
                rows={3}
                className="w-full bg-[#0a0a0f] border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50 resize-none"
              />
              <button
                onClick={handleNoteSubmit}
                disabled={saving || !note.trim()}
                className="mt-2 w-full py-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-40 text-white rounded-xl text-sm font-medium transition-all"
              >
                {saving ? "Saving..." : "Add Note"}
              </button>
            </div>
          </div>
        </div>

        {/* Timeline panel */}
        <div className="lg:col-span-2">
          <div className="bg-[#12121a] border border-white/10 rounded-2xl p-5">
            <h2 className="font-semibold text-white mb-5">Activity Timeline</h2>

            {timeline.length === 0 ? (
              <div className="text-center py-10 text-slate-500">
                No activity yet. Toggle milestones to start tracking.
              </div>
            ) : (
              <div className="relative">
                {/* Vertical line */}
                <div className="absolute left-5 top-0 bottom-0 w-px bg-white/10" />

                <div className="space-y-4 pl-14">
                  {timeline.map((event, idx) => (
                    <div key={event.id || idx} className="relative">
                      {/* Icon bubble */}
                      <div className={`absolute -left-[52px] w-8 h-8 rounded-full flex items-center justify-center text-sm ${eventColor(event.event_type)}`}>
                        {eventIcon(event.event_type)}
                      </div>
                      <div className="bg-white/[0.03] border border-white/8 rounded-xl p-3.5 hover:bg-white/[0.05] transition-colors">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm text-white font-medium">{event.description || event.event_type}</p>
                          <time className="text-xs text-slate-500 whitespace-nowrap shrink-0">
                            {formatDateTime(event.created_at)}
                          </time>
                        </div>
                        {event.metadata && Object.keys(event.metadata).length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1.5">
                            {Object.entries(event.metadata).map(([k, v]) => (
                              k !== "old_value" && (
                                <span key={k} className="text-xs px-2 py-0.5 bg-white/5 text-slate-400 rounded-lg">
                                  {k}: {String(v)}
                                </span>
                              )
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
