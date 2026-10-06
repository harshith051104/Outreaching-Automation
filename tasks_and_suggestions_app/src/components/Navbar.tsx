"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CheckSquare, Lightbulb, Sparkles } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();

  const navItems = [
    { href: "/tasks", label: "Tasks Tracker", icon: CheckSquare },
    { href: "/suggestions", label: "AI Suggestions", icon: Lightbulb },
  ];

  return (
    <header
      style={{
        backgroundColor: "rgba(15, 23, 42, 0.8)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
        position: "sticky",
        top: 0,
        zIndex: 50,
        padding: "0 24px",
      }}
    >
      <div
        style={{
          maxWidth: "1400px",
          margin: "0 auto",
          height: "64px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #7c5cff 0%, #3b82f6 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 4px 12px rgba(124, 92, 255, 0.3)",
            }}
          >
            <Sparkles size={20} color="#fff" />
          </div>
          <div>
            <span style={{ fontWeight: 700, fontSize: "16px", color: "#fff" }}>
              Tasks & Suggestions
            </span>
            <span
              style={{
                fontSize: "11px",
                marginLeft: "8px",
                padding: "2px 8px",
                borderRadius: "12px",
                backgroundColor: "rgba(124, 92, 255, 0.15)",
                color: "#a78bfa",
                border: "1px solid rgba(124, 92, 255, 0.3)",
              }}
            >
              Standalone App
            </span>
          </div>
        </div>

        <nav style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "8px 16px",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: 500,
                  textDecoration: "none",
                  transition: "all 0.2s ease",
                  backgroundColor: isActive
                    ? "rgba(124, 92, 255, 0.15)"
                    : "transparent",
                  color: isActive ? "#a78bfa" : "#94a3b8",
                  border: isActive
                    ? "1px solid rgba(124, 92, 255, 0.3)"
                    : "1px solid transparent",
                }}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
