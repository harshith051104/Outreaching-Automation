"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  Notification,
} from "@/services/task-api";
import {
  Bell,
  Check,
  CheckCircle,
  ClipboardList,
  MessageSquare,
  Sparkles,
  UserCheck,
  AlertCircle,
  Calendar,
  ChevronRight,
  Linkedin,
} from "lucide-react";

export default function NotificationsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [markingAll, setMarkingAll] = useState(false);

  useEffect(() => {
    fetchNotificationsList();
  }, []);

  const fetchNotificationsList = async () => {
    try {
      setLoading(true);
      const data = await getNotifications();
      setNotifications(data);
    } catch (err) {
      console.error("Failed to fetch notifications:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      setMarkingAll(true);
      await markAllNotificationsRead();
      setNotifications(notifications.map((n) => ({ ...n, is_read: true })));
    } catch (err) {
      console.error("Failed to mark all notifications read:", err);
    } finally {
      setMarkingAll(false);
    }
  };

  const handleNotificationClick = async (notif: Notification) => {
    // 1. Mark as read on backend if not already read
    if (!notif.is_read) {
      try {
        await markNotificationRead(notif.id);
        setNotifications(
          notifications.map((n) => (n.id === notif.id ? { ...n, is_read: true } : n))
        );
      } catch (err) {
        console.error("Failed to mark notification read:", err);
      }
    }

    // 2. Navigate based on reference type
    if (notif.reference_type === "task") {
      router.push(`/dashboard/tasks/${notif.reference_id}`);
    } else if (notif.reference_type === "suggestion") {
      router.push(`/dashboard/suggestions/${notif.reference_id}`);
    } else if (notif.reference_type === "linkedin_reply") {
      router.push(`/dashboard/linkedin`);
    }
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case "task_assigned":
        return <UserCheck className="h-4.5 w-4.5 text-blue-600" />;
      case "task_completed":
        return <CheckCircle className="h-4.5 w-4.5 text-green-600" />;
      case "comment_added":
        return <MessageSquare className="h-4.5 w-4.5 text-blue-600" />;
      case "suggestion_submitted":
        return <Sparkles className="h-4.5 w-4.5 text-amber-600" />;
      case "suggestion_status_changed":
        return <ClipboardList className="h-4.5 w-4.5 text-blue-600" />;
      case "linkedin_reply":
        return <Linkedin className="h-4.5 w-4.5 text-blue-600" />;
      default:
        return <Bell className="h-4.5 w-4.5" style={{ color: "var(--sidebar-text-muted)" }} />;
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 p-4">
      {/* Header Banner */}
      <div
        className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl shadow-xl relative overflow-hidden"
        style={{
          background: "linear-gradient(135deg, var(--banner-bg-from) 0%, var(--banner-bg-to) 100%)",
          border: "1px solid var(--banner-border)",
        }}
      >
        <div className="absolute -right-16 -top-16 h-48 w-48 opacity-10 rounded-full blur-3xl pointer-events-none" style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)" }} />
        <div className="relative z-10 space-y-1">
          <h1 className="text-2xl font-extrabold tracking-tight flex items-center gap-2" style={{ color: "var(--banner-text)" }}>
            <Bell className="h-6 w-6" style={{ color: "var(--primary)" }} />
            Notification Hub
          </h1>
          <p className="text-sm max-w-xl" style={{ color: "var(--banner-desc)" }}>
            Stay updated with assignments, community feedback, and direct teammate interactions.
          </p>
        </div>
        {notifications.some((n) => !n.is_read) && (
          <div className="relative z-10">
            <button
              onClick={handleMarkAllRead}
              disabled={markingAll}
              className="flex items-center gap-1 px-4 py-2 rounded-lg text-xs font-bold transition-all hover:opacity-90 shadow-md"
              style={{
                background: "var(--banner-btn-bg, rgba(0,0,0,0.05))",
                border: "1px solid var(--banner-btn-border, rgba(0,0,0,0.12))",
                color: "var(--banner-btn-text, var(--banner-text))",
              }}
            >
              <Check className="h-4 w-4" /> Mark All Read
            </button>
          </div>
        )}
      </div>

      {/* Main Notifications List */}
      {loading ? (
        <div className="flex h-[40vh] items-center justify-center">
          <div className="text-center space-y-4">
            <div className="h-10 w-10 border-4 border-t-transparent rounded-full animate-spin mx-auto" style={{ borderColor: "var(--primary) transparent transparent transparent" }}></div>
            <p className="font-medium text-sm" style={{ color: "var(--sidebar-text-muted)" }}>Loading notifications...</p>
          </div>
        </div>
      ) : notifications.length === 0 ? (
        <div
          className="rounded-2xl py-16 text-center space-y-3 border"
          style={{
            background: "var(--card-bg)",
            borderColor: "var(--card-border)",
            boxShadow: "var(--card-shadow)",
          }}
        >
          <Bell className="h-10 w-10 mx-auto" style={{ color: "var(--sidebar-text-muted)", opacity: 0.6 }} />
          <h3 className="font-semibold text-sm" style={{ color: "var(--foreground-color)" }}>All caught up!</h3>
          <p className="text-xs max-w-xs mx-auto" style={{ color: "var(--sidebar-text-muted)" }}>
            You don't have any notifications right now. We'll alert you when things change.
          </p>
        </div>
      ) : (
        <div
          className="rounded-2xl border overflow-hidden divide-y divide-[var(--card-border)]"
          style={{
            background: "var(--card-bg)",
            borderColor: "var(--card-border)",
            boxShadow: "var(--card-shadow)",
          }}
        >
          {notifications.map((notif) => (
            <div
              key={notif.id}
              onClick={() => handleNotificationClick(notif)}
              className="flex items-start gap-4 p-4 hover:bg-[var(--sidebar-hover)] transition-all cursor-pointer relative group"
              style={{
                background: !notif.is_read ? "rgba(124, 92, 255, 0.06)" : "transparent",
                borderColor: "var(--card-border)",
              }}
            >
              {/* Unread indicator */}
              {!notif.is_read && (
                <div className="absolute left-0 top-0 bottom-0 w-1 rounded-r" style={{ background: "var(--primary)" }} />
              )}

              {/* Notification type icon */}
              <div
                className="h-9 w-9 rounded-xl border flex items-center justify-center shrink-0"
                style={{
                  background: "var(--sidebar-toggle-bg, rgba(124, 92, 255, 0.05))",
                  borderColor: "var(--card-border)",
                }}
              >
                {getNotificationIcon(notif.type)}
              </div>

              {/* Content block */}
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <h3
                    className={`text-xs truncate ${!notif.is_read ? "font-extrabold" : "font-semibold"}`}
                    style={{ color: "var(--foreground-color)" }}
                  >
                    {notif.title}
                  </h3>
                  <span className="text-[10px] font-light flex items-center gap-0.5 shrink-0" style={{ color: "var(--sidebar-text-muted)", opacity: 0.8 }}>
                    <Calendar className="h-3 w-3" />
                    {new Date(notif.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <p className="text-[11px] leading-relaxed font-medium" style={{ color: "var(--sidebar-text-muted)" }}>
                  {notif.message}
                </p>
              </div>

              {/* Arrow */}
              <div className="self-center transition-colors" style={{ color: "var(--sidebar-text-muted)" }}>
                <ChevronRight className="h-4 w-4" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
