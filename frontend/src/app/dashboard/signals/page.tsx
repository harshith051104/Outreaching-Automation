"use client";

import { useEffect, useState } from "react";
import { getSignals } from "@/services/signals-api";
import { getLeads } from "@/services/lead-api";
import { 
  Brain, 
  Search, 
  SlidersHorizontal, 
  ExternalLink,
  ChevronRight,
  TrendingUp,
  Zap
} from "lucide-react";
import Link from "next/link";

export default function SignalsPage() {
  const [signals, setSignals] = useState<any[]>([]);
  const [leads, setLeads] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [minScore, setMinScore] = useState(0);
  const [freshnessFilter, setFreshnessFilter] = useState("all");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [signalsData, leadsData] = await Promise.all([
        getSignals().catch(() => []),
        getLeads().catch(() => [])
      ]);
      setSignals(signalsData);
      setLeads(leadsData);
    } catch (err) {
      console.error("Failed to load signals:", err);
    } finally {
      setLoading(false);
    }
  };

  const leadMap = new Map(leads.map(l => [l.id, l]));
  const categories = Array.from(new Set(signals.map(s => s.category).filter(Boolean)));

  const filteredSignals = signals.filter(sig => {
    const lead = leadMap.get(sig.lead_id);
    const matchesSearch = 
      sig.signal?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sig.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      lead?.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sig.company_name?.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesCategory = categoryFilter === "all" || sig.category === categoryFilter;
    const matchesScore = sig.score >= minScore;
    
    let matchesFreshness = true;
    if (freshnessFilter === "high") {
      matchesFreshness = sig.signal_freshness_score >= 80;
    } else if (freshnessFilter === "decayed") {
      matchesFreshness = sig.signal_freshness_score < 50;
    }

    return matchesSearch && matchesCategory && matchesScore && matchesFreshness;
  });

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

  const inputStyle: React.CSSProperties = {
    padding: "8px 12px",
    fontSize: "13px",
    background: "var(--sidebar-toggle-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: "8px",
    color: "var(--foreground-color)",
    outline: "none",
  };

  const selectStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 12px",
    fontSize: "13px",
    background: "var(--sidebar-toggle-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: "8px",
    color: "var(--foreground-color)",
    outline: "none",
  };

  if (loading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <div className="text-center space-y-3">
          <div className="h-10 w-10 border-4 border-[var(--primary)] border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p style={{ color: "var(--sidebar-text-muted)" }} className="font-medium animate-pulse">Running signal extraction engines...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4">
      {/* Hero Banner */}
      <div style={bannerStyle} className="p-6 relative overflow-hidden">
        <div style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)" }} className="absolute -right-24 -top-24 h-64 w-64 opacity-10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 space-y-2">
          <span className="bg-[rgba(124,92,255,0.1)] text-[var(--primary)] text-[10px] px-3 py-1 rounded-full font-black uppercase tracking-wider border border-[rgba(124,92,255,0.2)]">
            Signal Intelligence Agent
          </span>
          <h1 style={{ color: "var(--banner-text)" }} className="text-2xl font-black tracking-tight">
            Scraped Buying Signals
          </h1>
          <p style={{ color: "var(--banner-desc)" }} className="text-sm max-w-xl">
            Real-time intent events extracted from Tavily news reports and Firecrawl careers website scrapers.
          </p>
        </div>
      </div>

      {/* Filter Panel */}
      <div style={cardStyle} className="p-4 space-y-4">
        <div className="flex flex-wrap gap-3 items-center justify-between">
          <span style={{ color: "var(--sidebar-text-muted)" }} className="font-bold uppercase tracking-wider text-[10px] flex items-center gap-1.5">
            <SlidersHorizontal className="h-4 w-4" /> Filters Context
          </span>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5" style={{ color: "var(--sidebar-text-muted)" }} />
              <input
                type="text"
                placeholder="Search by signal, company or lead..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ ...inputStyle, paddingLeft: "32px", minWidth: "280px" }}
              />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4" style={{ borderTop: "1px solid var(--card-border)", paddingTop: "12px" }}>
          <div>
            <label style={{ color: "var(--sidebar-text-muted)" }} className="block text-[10px] font-bold uppercase tracking-wider mb-1">Category type</label>
            <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} style={selectStyle}>
              <option value="all">All Categories</option>
              {categories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ color: "var(--sidebar-text-muted)" }} className="block text-[10px] font-bold uppercase tracking-wider mb-1">
              Minimum Score ({minScore})
            </label>
            <input
              type="range"
              min={0}
              max={100}
              value={minScore}
              onChange={(e) => setMinScore(parseInt(e.target.value) || 0)}
              className="w-full h-2 rounded-lg cursor-pointer accent-[var(--primary)] mt-2.5"
              style={{ background: "var(--card-border)" }}
            />
          </div>

          <div>
            <label style={{ color: "var(--sidebar-text-muted)" }} className="block text-[10px] font-bold uppercase tracking-wider mb-1">Freshness status</label>
            <select value={freshnessFilter} onChange={(e) => setFreshnessFilter(e.target.value)} style={selectStyle}>
              <option value="all">All Signals</option>
              <option value="high">High Freshness (&gt;80%)</option>
              <option value="decayed">Decayed (&lt;50%)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Signals Cards Grid */}
      {filteredSignals.length > 0 ? (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {filteredSignals.map((sig, idx) => {
            const lead = leadMap.get(sig.lead_id);
            return (
              <div
                key={idx}
                style={{
                  background: "var(--card-bg)",
                  border: "1px solid var(--card-border)",
                  borderRadius: "16px",
                  boxShadow: "var(--card-shadow)",
                  backdropFilter: "blur(12px)",
                  transition: "box-shadow 0.2s ease, transform 0.2s ease",
                }}
                className="p-5 flex flex-col justify-between space-y-4 hover:-translate-y-0.5 hover:shadow-lg"
              >
                <div className="space-y-3">
                  <div className="flex justify-between items-start">
                    <span className="inline-flex items-center gap-1 text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full" style={{ background: "rgba(124,92,255,0.1)", color: "var(--primary)", border: "1px solid rgba(124,92,255,0.2)" }}>
                      {sig.category}
                    </span>
                    <div className="text-right shrink-0">
                      <span className="text-xs font-bold block flex items-center gap-0.5 justify-end" style={{ color: "var(--primary)" }}>
                        <TrendingUp className="h-3 w-3" /> Score: {sig.score}
                      </span>
                      <span className="text-[10px] block mt-0.5" style={{ color: "var(--sidebar-text-muted)" }}>Freshness: {sig.signal_freshness_score}%</span>
                    </div>
                  </div>

                  <div>
                    <h3 className="font-extrabold text-sm" style={{ color: "var(--foreground-color)" }}>{sig.signal || "Signal Event"}</h3>
                    <p className="text-xs font-medium mt-0.5" style={{ color: "var(--sidebar-text-muted)" }}>
                      Company: <span className="font-bold" style={{ color: "var(--foreground-color)" }}>{sig.company_name}</span>
                    </p>
                  </div>

                  <p className="text-xs leading-relaxed p-2.5 rounded-xl" style={{ color: "var(--sidebar-text-muted)", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}>
                    {sig.description}
                  </p>

                  {sig.hook && (
                    <div className="p-3 rounded-xl" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.15)" }}>
                      <span className="font-bold uppercase text-[9px] block" style={{ color: "#10b981" }}>Opener Hook Angle:</span>
                      <p className="text-xs italic mt-1 leading-relaxed" style={{ color: "#10b981" }}>"{sig.hook}"</p>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between text-[11px]" style={{ borderTop: "1px solid var(--card-border)", paddingTop: "12px" }}>
                  {lead ? (
                    <Link href={`/dashboard/leads/${lead.id}`} className="font-bold flex items-center gap-0.5 hover:underline" style={{ color: "var(--primary)" }}>
                      View Lead Profile <ChevronRight className="h-3 w-3" />
                    </Link>
                  ) : (
                    <span style={{ color: "var(--sidebar-text-muted)" }}>Lead unlinked</span>
                  )}
                  {sig.url_source && (
                    <a href={sig.url_source} target="_blank" rel="noreferrer" className="flex items-center gap-0.5 hover:opacity-80 transition-opacity" style={{ color: "var(--sidebar-text-muted)" }}>
                      Source <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-16 text-center rounded-2xl" style={{ background: "var(--card-bg)", border: "1px dashed var(--card-border)" }}>
          <Brain className="h-10 w-10 mx-auto mb-2" style={{ color: "var(--sidebar-text-muted)" }} />
          <h3 className="font-semibold text-sm" style={{ color: "var(--foreground-color)" }}>No signals match current filter</h3>
          <p className="text-xs mt-1" style={{ color: "var(--sidebar-text-muted)" }}>Try resetting search parameters or scraping new targets.</p>
        </div>
      )}
    </div>
  );
}
