"use client";

import { useEffect, useState } from "react";
import { getAllOpportunities } from "@/services/signals-api";
import { 
  Lightbulb, 
  TrendingUp, 
  ChevronRight,
  Zap
} from "lucide-react";
import Link from "next/link";

export default function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedOpp, setSelectedOpp] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await getAllOpportunities();
      setOpportunities(data);
    } catch (err) {
      console.error("Failed to load opportunities:", err);
    } finally {
      setLoading(false);
    }
  };

  const highOpps = opportunities.filter(o => o.urgency === "High");
  const medOpps = opportunities.filter(o => o.urgency === "Medium");
  const lowOpps = opportunities.filter(o => o.urgency === "Low");

  const bannerStyle: React.CSSProperties = {
    background: "linear-gradient(135deg, var(--banner-bg-from) 0%, var(--banner-bg-to) 100%)",
    border: "1px solid var(--banner-border)",
    borderRadius: "16px",
    boxShadow: "var(--card-shadow)",
  };

  const cardStyle: React.CSSProperties = {
    background: "var(--card-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: "16px",
    boxShadow: "var(--card-shadow)",
    backdropFilter: "blur(12px)",
  };

  const columnColors: Record<string, { dot: string; label: string; badge: string }> = {
    red: { dot: "#ef4444", label: "#ef4444", badge: "rgba(239,68,68,0.15)" },
    amber: { dot: "#f59e0b", label: "#f59e0b", badge: "rgba(245,158,11,0.15)" },
    blue: { dot: "var(--primary)", label: "var(--primary)", badge: "rgba(124,92,255,0.15)" },
  };

  if (loading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <div className="text-center space-y-3">
          <div className="h-10 w-10 border-4 border-[var(--primary)] border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p style={{ color: "var(--sidebar-text-muted)" }} className="font-medium animate-pulse">Running Opportunity Intelligence agents...</p>
        </div>
      </div>
    );
  }

  const columnHeaders = [
    { title: "High Urgency Opportunity", count: highOpps.length, data: highOpps, color: "red" },
    { title: "Medium Urgency Opportunity", count: medOpps.length, data: medOpps, color: "amber" },
    { title: "Low Urgency Opportunity", count: lowOpps.length, data: lowOpps, color: "blue" }
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4">
      {/* Hero Banner */}
      <div style={bannerStyle} className="p-6 relative overflow-hidden">
        <div style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)" }} className="absolute -right-24 -top-24 h-64 w-64 opacity-10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 space-y-2">
          <span className="bg-[rgba(124,92,255,0.1)] text-[var(--primary)] text-[10px] px-3 py-1 rounded-full font-black uppercase tracking-wider border border-[rgba(124,92,255,0.2)]">
            Opportunity Intelligence Agent
          </span>
          <h1 style={{ color: "var(--banner-text)" }} className="text-2xl font-black tracking-tight">
            AI Qualified Sales Pipeline
          </h1>
          <p style={{ color: "var(--banner-desc)" }} className="text-sm max-w-xl">
            Autonomous Agno evaluations scoring company growth triggers, ideal buyer contact personas, and offer angles.
          </p>
        </div>
      </div>

      {/* Columns Grid */}
      <div className="grid gap-5 md:grid-cols-3">
        {columnHeaders.map((col) => {
          const colors = columnColors[col.color];
          return (
            <div key={col.title} style={{ ...cardStyle, padding: "16px", display: "flex", flexDirection: "column", gap: "16px", minHeight: "500px" }}>
              <div className="flex items-center justify-between" style={{ borderBottom: "1px solid var(--card-border)", paddingBottom: "10px" }}>
                <span className="font-bold text-xs uppercase tracking-wider flex items-center gap-1.5" style={{ color: "var(--foreground-color)" }}>
                  <span className="h-2.5 w-2.5 rounded-full flex-shrink-0" style={{ background: colors.dot }} />
                  {col.title}
                </span>
                <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full" style={{ background: colors.badge, color: colors.label }}>
                  {col.count}
                </span>
              </div>

              <div className="space-y-4 flex-1 overflow-y-auto max-h-[70vh] pr-1">
                {col.data.length > 0 ? (
                  col.data.map((opp, idx) => (
                    <div
                      key={idx}
                      onClick={() => setSelectedOpp(opp)}
                      style={{
                        background: "var(--sidebar-toggle-bg)",
                        border: "1px solid var(--card-border)",
                        borderRadius: "12px",
                        padding: "16px",
                        cursor: "pointer",
                        transition: "box-shadow 0.2s ease, transform 0.2s ease",
                      }}
                      className="space-y-3 hover:-translate-y-0.5 hover:shadow-md"
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <h4 className="font-extrabold text-xs" style={{ color: "var(--foreground-color)" }}>{opp.lead?.name || "Target Lead"}</h4>
                          <p className="text-[10px] font-semibold mt-0.5" style={{ color: "var(--sidebar-text-muted)" }}>{opp.lead?.company || "SaaSify"}</p>
                        </div>
                        <span className="text-[10px] font-bold flex items-center gap-0.5" style={{ color: "var(--primary)" }}>
                          <TrendingUp className="h-3 w-3" /> {opp.confidence_score}%
                        </span>
                      </div>

                      <div className="p-2.5 rounded-lg space-y-1 text-[11px]" style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)" }}>
                        <div className="text-[9px] font-bold uppercase" style={{ color: "var(--sidebar-text-muted)" }}>Target Persona</div>
                        <div className="font-semibold" style={{ color: "var(--foreground-color)" }}>{opp.best_contact}</div>
                      </div>

                      <div className="text-[11px] leading-relaxed line-clamp-2" style={{ color: "var(--sidebar-text-muted)" }}>
                        {opp.reasoning}
                      </div>

                      <div className="flex items-center justify-between text-[10px]" style={{ borderTop: "1px solid var(--card-border)", paddingTop: "8px" }}>
                        <span className="font-bold flex items-center hover:underline" style={{ color: "var(--primary)" }}>
                          Details <ChevronRight className="h-3 w-3" />
                        </span>
                        {opp.lead?.id && (
                          <Link
                            href={`/dashboard/leads/${opp.lead.id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="hover:opacity-80 transition-opacity"
                            style={{ color: "var(--sidebar-text-muted)" }}
                          >
                            Profile →
                          </Link>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <Lightbulb className="h-8 w-8 mb-2" style={{ color: "var(--card-border)" }} />
                    <p className="text-xs font-semibold" style={{ color: "var(--sidebar-text-muted)" }}>No opportunities</p>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Detail Modal */}
      {selectedOpp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)" }}>
          <div style={{ ...cardStyle, maxWidth: "520px", width: "100%", padding: "24px", maxHeight: "85vh", overflowY: "auto" }} className="space-y-4">
            <div className="flex justify-between items-start" style={{ borderBottom: "1px solid var(--card-border)", paddingBottom: "12px" }}>
              <div>
                <h3 className="text-base font-black" style={{ color: "var(--foreground-color)" }}>Opportunity Intelligence</h3>
                <p className="text-xs" style={{ color: "var(--sidebar-text-muted)" }}>Urgency evaluation details for {selectedOpp.lead?.name}</p>
              </div>
              <button
                onClick={() => setSelectedOpp(null)}
                className="font-bold text-lg px-2 hover:opacity-80 transition-opacity"
                style={{ color: "var(--sidebar-text-muted)" }}
              >
                &times;
              </button>
            </div>

            <div className="space-y-4 text-xs leading-relaxed">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 rounded-xl" style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}>
                  <span className="block uppercase text-[9px] font-bold mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Best Target Contact</span>
                  <span className="font-bold" style={{ color: "var(--foreground-color)" }}>{selectedOpp.best_contact}</span>
                </div>
                <div className="p-3 rounded-xl" style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}>
                  <span className="block uppercase text-[9px] font-bold mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Urgency Status</span>
                  <span className="font-bold capitalize" style={{ color: "var(--foreground-color)" }}>{selectedOpp.urgency} Urgency</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 rounded-xl" style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}>
                  <span className="block uppercase text-[9px] font-bold mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Confidence Rating</span>
                  <span className="font-bold" style={{ color: "var(--foreground-color)" }}>{selectedOpp.confidence_score}%</span>
                </div>
                <div className="p-3 rounded-xl" style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}>
                  <span className="block uppercase text-[9px] font-bold mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Lead Details</span>
                  <span className="font-bold truncate block" style={{ color: "var(--foreground-color)" }}>
                    {selectedOpp.lead?.role} ({selectedOpp.lead?.company})
                  </span>
                </div>
              </div>

              <div className="p-4 rounded-xl space-y-1" style={{ background: "rgba(124,92,255,0.08)", border: "1px solid rgba(124,92,255,0.2)" }}>
                <span className="font-bold uppercase text-[9px] block" style={{ color: "var(--primary)" }}>Recommended Outbound Offer</span>
                <p className="font-semibold italic" style={{ color: "var(--foreground-color)" }}>"{selectedOpp.recommended_offer}"</p>
              </div>

              <div className="space-y-1">
                <span className="uppercase text-[9px] font-bold block" style={{ color: "var(--sidebar-text-muted)" }}>Evaluation Reasoning</span>
                <p className="p-3 rounded-xl whitespace-pre-line leading-relaxed" style={{ color: "var(--sidebar-text-muted)", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}>
                  {selectedOpp.reasoning}
                </p>
              </div>
            </div>

            <div className="flex justify-between items-center text-xs" style={{ borderTop: "1px solid var(--card-border)", paddingTop: "16px" }}>
              {selectedOpp.lead?.id && (
                <Link
                  href={`/dashboard/leads/${selectedOpp.lead.id}`}
                  onClick={() => setSelectedOpp(null)}
                  className="px-4 py-2 font-bold rounded-lg transition-opacity hover:opacity-90"
                  style={{ background: "var(--primary)", color: "#fff" }}
                >
                  Configure Lead Outreach
                </Link>
              )}
              <button
                onClick={() => setSelectedOpp(null)}
                className="px-4 py-2 font-bold rounded-lg transition-opacity hover:opacity-80"
                style={{ background: "var(--sidebar-toggle-bg)", color: "var(--foreground-color)", border: "1px solid var(--card-border)" }}
              >
                Close details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
