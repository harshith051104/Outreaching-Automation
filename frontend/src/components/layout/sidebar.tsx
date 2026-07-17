"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { useState } from "react";
import {
  LayoutDashboard,
  Search,
  Users,
  Megaphone,
  Brain,
  Lightbulb,
  BarChart3,
  Bot,
  Bell,
  // Linkedin, // LINKEDIN DISABLED — uncomment to re-enable LinkedIn nav
  BookOpen,
  FileText,
  Mail,
  Settings,
  Menu,
  LogOut,
  ChevronLeft,
  CheckSquare,
  MessageSquare,
  Inbox,
  Sun,
  Moon,
  MailCheck,
  Zap,
  ClipboardList,
} from "lucide-react";
import { getMonitorStats } from "@/services/monitor-api";
import { getUnreadNotificationCount } from "@/services/dashboard-api";
import { useEffect } from "react";

interface NavItem {
  href: string;
  label: string;
  icon: any;
  badgeCount?: number;
  badge?: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const [collapsed, setCollapsed] = useState(false);
  const [pendingRepliesCount, setPendingRepliesCount] = useState(0);
  const [unreadNotificationsCount, setUnreadNotificationsCount] = useState(0);
  const [theme, setTheme] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") as "light" | "dark" | null;
    const initialTheme = savedTheme || "dark";
    setTheme(initialTheme);
    if (initialTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("theme", nextTheme);
    if (nextTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  useEffect(() => {
    async function loadStats() {
      try {
        const [stats, unread] = await Promise.all([
          getMonitorStats().catch(() => ({ pending_drafts: 0 })),
          getUnreadNotificationCount(user?.id).catch(() => 0),
        ]);
        setPendingRepliesCount(stats.pending_drafts || 0);
        setUnreadNotificationsCount(unread || 0);
      } catch (err) {
        console.error("Failed to load sidebar stats:", err);
      }
    }
    loadStats();
    const interval = setInterval(loadStats, 10000);
    return () => clearInterval(interval);
  }, [user?.id]);

  const navGroups: NavGroup[] = [
    {
      label: "Overview",
      items: [
        { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
        { href: "/dashboard/tasks", label: "Tasks", icon: CheckSquare },
        { href: "/dashboard/notifications", label: "Notifications", icon: Bell, badgeCount: unreadNotificationsCount },
        { href: "/dashboard/suggestions", label: "Suggestions", icon: MessageSquare },
      ]
    },
    {
      label: "Outreach",
      items: [
        { href: "/dashboard/leads-discovery", label: "Lead Discovery", icon: Search },
        { href: "/dashboard/leads", label: "Leads", icon: Users },
        { href: "/dashboard/campaigns", label: "Campaigns", icon: Megaphone },
        { href: "/dashboard/outreach-tracker", label: "Outreach Tracker", icon: ClipboardList },
        // DISABLED: { href: "/dashboard/signals", label: "Signals", icon: Brain, badge: "New" },
        // DISABLED: { href: "/dashboard/opportunities", label: "Opportunities", icon: Lightbulb },
      ]
    },
    {
      label: "Intelligence",
      items: [
        { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
        { href: "/dashboard/chatbot", label: "Elly", icon: Bot },
        { href: "/dashboard/reply-monitor", label: "Reply Monitor", icon: Inbox, badgeCount: pendingRepliesCount },
        // DISABLED: { href: "/dashboard/inbox-placement", label: "Inbox Placement", icon: MailCheck },
      ]
    },
    {
      label: "Channels",
      items: [
        // LINKEDIN DISABLED — uncomment to re-enable LinkedIn channel
        // { href: "/dashboard/linkedin", label: "LinkedIn", icon: Linkedin },
        { href: "/dashboard/gmail", label: "Gmail", icon: Mail },
      ]
    },
    {
      label: "Resources",
      items: [
        // DISABLED: { href: "/dashboard/knowledge-base", label: "Knowledge Base", icon: BookOpen },
        // DISABLED: { href: "/dashboard/pitch-deck", label: "Pitch Decks", icon: FileText },
        { href: "/dashboard/settings", label: "Settings", icon: Settings },
      ]
    },
  ];

  // Flatten all items for collapsed state
  const allItems = navGroups.flatMap(g => g.items);

  const avatarLetter = user?.name?.charAt(0)?.toUpperCase() || "U";

  return (
    <aside
      style={{
        background: `linear-gradient(180deg, var(--sidebar-bg-from) 0%, var(--sidebar-bg-to) 100%)`,
        borderRight: `1px solid var(--sidebar-border)`,
        color: `var(--sidebar-text)`,
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        width: collapsed ? '64px' : '240px',
        minWidth: collapsed ? '64px' : '240px',
        position: 'relative',
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'space-between',
        padding: collapsed ? '16px 12px' : '16px 16px',
        borderBottom: `1px solid var(--sidebar-border)`,
        flexShrink: 0,
      }}>
        {!collapsed && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #7c5cff, #a78bfa)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              boxShadow: '0 4px 12px rgba(124, 92, 255, 0.4)',
            }}>
              <Zap size={16} color="white" strokeWidth={2.5} />
            </div>
            <div style={{ overflow: 'hidden' }}>
              <div style={{
                fontSize: '13px',
                fontWeight: '800',
                letterSpacing: '-0.02em',
                background: 'linear-gradient(135deg, #7c5cff, #a78bfa)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                whiteSpace: 'nowrap',
              }}>
                AI Outreach
              </div>
              <div style={{ fontSize: '10px', color: 'var(--sidebar-text-muted)', marginTop: '-2px' }}>
                Command Platform
              </div>
            </div>
          </div>
        )}
        {collapsed && (
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #7c5cff, #a78bfa)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(124, 92, 255, 0.4)',
          }}>
            <Zap size={16} color="white" strokeWidth={2.5} />
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '28px',
            height: '28px',
            borderRadius: '8px',
            border: `1px solid var(--sidebar-border)`,
            background: 'transparent',
            cursor: 'pointer',
            color: 'var(--sidebar-text-muted)',
            transition: 'all 0.2s ease',
            flexShrink: 0,
            marginLeft: collapsed ? '0' : '8px',
          }}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onMouseEnter={e => {
            (e.currentTarget as HTMLButtonElement).style.background = 'var(--sidebar-hover)';
            (e.currentTarget as HTMLButtonElement).style.color = 'var(--sidebar-text-active)';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
            (e.currentTarget as HTMLButtonElement).style.color = 'var(--sidebar-text-muted)';
          }}
        >
          {collapsed ? <Menu size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '8px 0' }}>
        {collapsed ? (
          // Collapsed: flat icon list
          allItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            const hasBadge = item.badgeCount !== undefined && item.badgeCount > 0;
            return (
              <Link
                key={item.href}
                href={item.href}
                title={item.label}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '40px',
                  height: '40px',
                  margin: '2px auto',
                  borderRadius: '10px',
                  position: 'relative',
                  background: isActive ? 'var(--sidebar-active-bg)' : 'transparent',
                  color: isActive ? 'var(--sidebar-text-active)' : 'var(--sidebar-text-muted)',
                  textDecoration: 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                <Icon size={18} strokeWidth={isActive ? 2.2 : 1.8} />
                {hasBadge && (
                  <span style={{
                    position: 'absolute',
                    top: '6px',
                    right: '6px',
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: '#7c5cff',
                    animation: 'pulse 2s infinite',
                  }} />
                )}
              </Link>
            );
          })
        ) : (
          // Expanded: grouped nav
          navGroups.map((group) => (
            <div key={group.label} style={{ marginBottom: '4px' }}>
              <div style={{
                fontSize: '10px',
                fontWeight: '700',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: 'var(--sidebar-text-muted)',
                padding: '10px 16px 4px',
                opacity: 0.7,
              }}>
                {group.label}
              </div>
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
                const hasBadge = item.badgeCount !== undefined && item.badgeCount > 0;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '8px 12px 8px 14px',
                      margin: '1px 6px',
                      borderRadius: '10px',
                      position: 'relative',
                      background: isActive ? 'var(--sidebar-active-bg)' : 'transparent',
                      color: isActive ? 'var(--sidebar-text-active)' : 'var(--sidebar-text-muted)',
                      textDecoration: 'none',
                      transition: 'all 0.15s ease',
                      fontSize: '13px',
                      fontWeight: isActive ? '600' : '400',
                    }}
                    onMouseEnter={e => {
                      if (!isActive) {
                        (e.currentTarget as HTMLAnchorElement).style.background = 'var(--sidebar-hover)';
                        (e.currentTarget as HTMLAnchorElement).style.color = 'var(--sidebar-text)';
                      }
                    }}
                    onMouseLeave={e => {
                      if (!isActive) {
                        (e.currentTarget as HTMLAnchorElement).style.background = 'transparent';
                        (e.currentTarget as HTMLAnchorElement).style.color = 'var(--sidebar-text-muted)';
                      }
                    }}
                  >
                    {isActive && (
                      <span style={{
                        position: 'absolute',
                        left: 0,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        width: '3px',
                        height: '18px',
                        background: 'linear-gradient(180deg, #7c5cff, #a78bfa)',
                        borderRadius: '0 3px 3px 0',
                      }} />
                    )}
                    <Icon size={16} strokeWidth={isActive ? 2.2 : 1.8} style={{ flexShrink: 0 }} />
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.label}
                    </span>
                    {item.badge && (
                      <span style={{
                        fontSize: '9px',
                        fontWeight: '700',
                        padding: '1px 6px',
                        borderRadius: '999px',
                        background: 'rgba(124, 92, 255, 0.15)',
                        color: '#7c5cff',
                        border: '1px solid rgba(124, 92, 255, 0.25)',
                        letterSpacing: '0.06em',
                        textTransform: 'uppercase',
                      }}>
                        {item.badge}
                      </span>
                    )}
                    {hasBadge && (
                      <span style={{
                        minWidth: '20px',
                        height: '20px',
                        borderRadius: '10px',
                        background: 'linear-gradient(135deg, #7c5cff, #a78bfa)',
                        color: 'white',
                        fontSize: '10px',
                        fontWeight: '700',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '0 5px',
                      }}>
                        {item.badgeCount}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          ))
        )}
      </nav>

      {/* Theme Toggle */}
      <div style={{
        borderTop: `1px solid var(--sidebar-border)`,
        padding: collapsed ? '8px 12px' : '8px 10px',
        flexShrink: 0,
      }}>
        {collapsed ? (
          <button
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to Light" : "Switch to Dark"}
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: theme === "dark" ? '#fbbf24' : '#7c5cff',
              margin: '0 auto',
            }}
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        ) : (
          <button
            onClick={toggleTheme}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '8px 10px',
              borderRadius: '10px',
              border: `1px solid var(--sidebar-border)`,
              background: 'var(--sidebar-toggle-bg)',
              cursor: 'pointer',
              color: 'var(--sidebar-text)',
              fontSize: '12px',
              fontWeight: '500',
              transition: 'all 0.2s ease',
            }}
          >
            {theme === "dark" ? (
              <>
                <Moon size={14} style={{ color: '#818cf8', flexShrink: 0 }} />
                <span style={{ flex: 1, textAlign: 'left', color: 'var(--sidebar-text-muted)' }}>Dark Mode</span>
              </>
            ) : (
              <>
                <Sun size={14} style={{ color: '#f59e0b', flexShrink: 0 }} />
                <span style={{ flex: 1, textAlign: 'left', color: 'var(--sidebar-text-muted)' }}>Light Mode</span>
              </>
            )}
            <div style={{
              width: '32px',
              height: '18px',
              borderRadius: '9px',
              background: theme === "dark" ? '#7c5cff' : '#d1d5db',
              position: 'relative',
              transition: 'background 0.3s',
              flexShrink: 0,
            }}>
              <div style={{
                width: '14px',
                height: '14px',
                borderRadius: '50%',
                background: 'white',
                position: 'absolute',
                top: '2px',
                left: theme === "dark" ? '16px' : '2px',
                transition: 'left 0.3s',
                boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
              }} />
            </div>
          </button>
        )}
      </div>

      {/* User Section */}
      <div style={{
        borderTop: `1px solid var(--sidebar-border)`,
        padding: collapsed ? '10px 12px' : '12px 14px',
        flexShrink: 0,
      }}>
        {collapsed ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #7c5cff, #a78bfa)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '12px',
              fontWeight: '700',
              color: 'white',
              boxShadow: '0 2px 8px rgba(124, 92, 255, 0.3)',
            }}>
              {avatarLetter}
            </div>
            <button
              onClick={logout}
              title="Sign out"
              style={{
                padding: '4px',
                borderRadius: '6px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                color: '#f87171',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <LogOut size={14} />
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '34px',
              height: '34px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #7c5cff, #a78bfa)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '13px',
              fontWeight: '700',
              color: 'white',
              flexShrink: 0,
              boxShadow: '0 2px 8px rgba(124, 92, 255, 0.3)',
            }}>
              {avatarLetter}
            </div>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--sidebar-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {user?.name || "User"}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--sidebar-text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {user?.email}
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              style={{
                padding: '6px',
                borderRadius: '8px',
                border: `1px solid transparent`,
                background: 'transparent',
                cursor: 'pointer',
                color: '#f87171',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s ease',
                flexShrink: 0,
              }}
            >
              <LogOut size={14} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}