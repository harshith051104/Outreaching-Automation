"use client";

import { useEffect, useState } from "react";
import api from "@/services/api";
import Link from "next/link";

interface MemberProgress {
  user_id: string;
  display_name: string;
  total_leads: number;
  completed: number;
  in_progress: number;
  meeting_scheduled: number;
  opportunity_closed: number;
  completion_rate: number;
}

interface TeamProgressResponse {
  total_members: number;
  total_leads: number;
  total_completed: number;
  members: MemberProgress[];
}

const PALETTE = [
  "#7c5cff",
  "#0ac18e",
  "#0a66c2",
  "#f59e0b",
  "#ef4444",
  "#a78bfa",
  "#34d399",
  "#60a5fa",
];

function MiniBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div
      style={{
        height: "4px",
        borderRadius: "2px",
        background: "rgba(255,255,255,0.08)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${pct}%`,
          background: "linear-gradient(90deg, #7c5cff, #a78bfa)",
          borderRadius: "2px",
          transition: "width 0.6s ease",
        }}
      />
    </div>
  );
}

export default function TeamOverviewWidget() {
  const [data, setData] = useState<TeamProgressResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get("/outreach-tracker/team-progress");
        setData(res.data);
      } catch (err: any) {
        setError("Team data unavailable");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div
        style={{
          borderRadius: "20px",
          border: "1px solid rgba(124,92,255,0.2)",
          background: "rgba(15,15,30,0.6)",
          padding: "24px",
          backdropFilter: "blur(12px)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "20px" }}>
          <div style={{ width: "32px", height: "32px", borderRadius: "10px", background: "rgba(124,92,255,0.15)", animation: "pulse 1.5s infinite" }} />
          <div style={{ height: "16px", width: "140px", borderRadius: "6px", background: "rgba(255,255,255,0.06)", animation: "pulse 1.5s infinite" }} />
        </div>
        {[...Array(3)].map((_, i) => (
          <div key={i} style={{ height: "56px", borderRadius: "12px", background: "rgba(255,255,255,0.04)", marginBottom: "8px", animation: "pulse 1.5s infinite" }} />
        ))}
        <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }`}</style>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div
        style={{
          borderRadius: "20px",
          border: "1px solid rgba(239,68,68,0.2)",
          background: "rgba(15,15,30,0.6)",
          padding: "24px",
          backdropFilter: "blur(12px)",
          fontSize: "13px",
          color: "#f87171",
          textAlign: "center",
        }}
      >
        {error || "No team data"}
      </div>
    );
  }

  const maxLeads = Math.max(...(data.members.map((m) => m.total_leads) || [1]), 1);

  return (
    <div
      style={{
        borderRadius: "20px",
        border: "1px solid rgba(124,92,255,0.2)",
        background: "rgba(15,15,30,0.6)",
        padding: "24px",
        backdropFilter: "blur(12px)",
        fontFamily: "Inter, -apple-system, sans-serif",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "12px",
              background: "linear-gradient(135deg, rgba(124,92,255,0.3), rgba(167,139,250,0.15))",
              border: "1px solid rgba(124,92,255,0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "18px",
            }}
          >
            👥
          </div>
          <div>
            <div style={{ fontSize: "14px", fontWeight: "700", color: "#f5f3ff" }}>Team Progress</div>
            <div style={{ fontSize: "11px", color: "rgba(167,139,250,0.6)", marginTop: "1px" }}>
              {data.total_members} members · {data.total_leads} leads
            </div>
          </div>
        </div>
        <Link
          href="/dashboard/outreach-tracker"
          style={{
            fontSize: "11px",
            fontWeight: "600",
            color: "rgba(167,139,250,0.8)",
            textDecoration: "none",
            padding: "4px 10px",
            borderRadius: "8px",
            border: "1px solid rgba(124,92,255,0.25)",
            background: "rgba(124,92,255,0.1)",
            transition: "all 0.2s",
          }}
        >
          View All →
        </Link>
      </div>

      {/* Team summary row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: "10px",
          marginBottom: "18px",
        }}
      >
        {[
          { label: "Total Leads", value: data.total_leads, icon: "👤" },
          { label: "Completed", value: data.total_completed, icon: "✅" },
          {
            label: "Completion Rate",
            value: data.total_leads > 0
              ? `${Math.round((data.total_completed / data.total_leads) * 100)}%`
              : "0%",
            icon: "📈",
          },
        ].map((stat) => (
          <div
            key={stat.label}
            style={{
              borderRadius: "12px",
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.07)",
              padding: "12px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "16px", marginBottom: "4px" }}>{stat.icon}</div>
            <div style={{ fontSize: "18px", fontWeight: "800", color: "#f5f3ff" }}>{stat.value}</div>
            <div style={{ fontSize: "10px", color: "rgba(167,139,250,0.5)", marginTop: "2px" }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Member rows */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {data.members.length === 0 ? (
          <div style={{ textAlign: "center", fontSize: "12px", color: "rgba(167,139,250,0.5)", padding: "16px 0" }}>
            No team members yet. Assign leads to get started.
          </div>
        ) : (
          data.members.slice(0, 8).map((member, i) => (
            <div
              key={member.user_id}
              style={{
                borderRadius: "12px",
                border: "1px solid rgba(255,255,255,0.06)",
                background: "rgba(255,255,255,0.03)",
                padding: "12px 14px",
              }}
            >
              {/* Top row: avatar + name + badges */}
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                <div
                  style={{
                    width: "30px",
                    height: "30px",
                    borderRadius: "50%",
                    background: `linear-gradient(135deg, ${PALETTE[i % PALETTE.length]}40, ${PALETTE[(i + 2) % PALETTE.length]}20)`,
                    border: `2px solid ${PALETTE[i % PALETTE.length]}50`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "12px",
                    fontWeight: "800",
                    color: PALETTE[i % PALETTE.length],
                    flexShrink: 0,
                  }}
                >
                  {member.display_name.charAt(0).toUpperCase() || "?"}
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: "12px", fontWeight: "700", color: "#f5f3ff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {member.display_name || "Unknown"}
                  </div>
                  <div style={{ fontSize: "10px", color: "rgba(167,139,250,0.5)" }}>
                    {member.total_leads} leads
                  </div>
                </div>

                {/* Key stats */}
                <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
                  {member.meeting_scheduled > 0 && (
                    <span
                      style={{
                        fontSize: "10px",
                        padding: "2px 7px",
                        borderRadius: "8px",
                        background: "rgba(16,185,129,0.15)",
                        color: "#34d399",
                        border: "1px solid rgba(16,185,129,0.2)",
                        fontWeight: "700",
                      }}
                    >
                      📅 {member.meeting_scheduled}
                    </span>
                  )}
                  {member.opportunity_closed > 0 && (
                    <span
                      style={{
                        fontSize: "10px",
                        padding: "2px 7px",
                        borderRadius: "8px",
                        background: "rgba(124,92,255,0.15)",
                        color: "#a78bfa",
                        border: "1px solid rgba(124,92,255,0.2)",
                        fontWeight: "700",
                      }}
                    >
                      ✅ {member.opportunity_closed}
                    </span>
                  )}
                  <span
                    style={{
                      fontSize: "10px",
                      padding: "2px 7px",
                      borderRadius: "8px",
                      background: "rgba(255,255,255,0.06)",
                      color: "rgba(245,243,255,0.7)",
                      fontWeight: "700",
                    }}
                  >
                    {Math.round(member.completion_rate)}%
                  </span>
                </div>
              </div>

              {/* Progress bar */}
              <MiniBar value={member.total_leads} max={maxLeads} />
            </div>
          ))
        )}
      </div>

      {data.members.length > 8 && (
        <div style={{ textAlign: "center", marginTop: "12px" }}>
          <Link
            href="/dashboard/outreach-tracker"
            style={{
              fontSize: "11px",
              color: "rgba(167,139,250,0.6)",
              textDecoration: "none",
              fontWeight: "600",
            }}
          >
            +{data.members.length - 8} more members →
          </Link>
        </div>
      )}
    </div>
  );
}
