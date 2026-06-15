"use client";

import { useEffect, useState, useMemo } from "react";
import { getGmailAccounts, getGmailInbox } from "@/services/gmail-api";
import type { GmailAccount, GmailMessage } from "@/types/gmail";

type Filter = "all" | "unread" | "replied" | "no_reply";

interface ThreadMessage extends GmailMessage {
  isRead?: boolean;
  isReplied?: boolean;
}

interface Conversation {
  threadId: string;
  subject: string;
  snippet: string;
  fromEmail: string;
  date: string;
  messages: ThreadMessage[];
  unreadCount: number;
}

export default function UniboxPage() {
  const [accounts, setAccounts] = useState<GmailAccount[]>([]);
  const [messages, setMessages] = useState<GmailMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const accountsData = await getGmailAccounts();
      setAccounts(accountsData);

      const allMessages: GmailMessage[] = [];
      for (const account of accountsData) {
        const inbox = await getGmailInbox(account.id);
        allMessages.push(...inbox);
      }
      setMessages(allMessages);
    } catch (err) {
      console.error("Failed to load inbox:", err);
    } finally {
      setLoading(false);
    }
  };

  const conversations = useMemo(() => {
    const threadMap = new Map<string, Conversation>();

    for (const msg of messages) {
      if (!threadMap.has(msg.thread_id)) {
        threadMap.set(msg.thread_id, {
          threadId: msg.thread_id,
          subject: msg.subject || "",
          snippet: msg.snippet || "",
          fromEmail: msg.from_email || "",
          date: msg.date || "",
          messages: [],
          unreadCount: 0,
        });
      }

      const thread = threadMap.get(msg.thread_id)!;
      thread.messages.push({ ...msg, isRead: true, isReplied: false });

      const msgDate = msg.date ? new Date(msg.date) : new Date(0);
      const latestDate = thread.date ? new Date(thread.date) : new Date(0);
      if (msgDate > latestDate) {
        thread.subject = msg.subject || "";
        thread.fromEmail = msg.from_email || "";
        thread.snippet = msg.snippet || "";
        thread.date = msg.date || "";
      }
    }

    let threads = Array.from(threadMap.values());

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      threads = threads.filter(
        (t) =>
          t.subject.toLowerCase().includes(q) ||
          t.fromEmail.toLowerCase().includes(q) ||
          t.snippet.toLowerCase().includes(q)
      );
    }

    if (filter === "unread") {
      threads = threads.filter((t) => t.unreadCount > 0);
    } else if (filter === "replied") {
      threads = threads.filter((t) =>
        t.messages.some((m) => m.isReplied)
      );
    } else if (filter === "no_reply") {
      threads = threads.filter((t) =>
        t.messages.every((m) => !m.isReplied)
      );
    }

    return threads.sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
    );
  }, [messages, filter, searchQuery]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    }
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return date.toLocaleDateString([], { weekday: "short" });
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  };

  const truncate = (text: string | undefined | null, max: number) => {
    if (!text) return "";
    return text.length > max ? text.slice(0, max) + "..." : text;
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-gray-500">Loading inbox...</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Unibox</h1>
          <p className="text-sm text-gray-500">
            Unified inbox across all connected Gmail accounts
          </p>
        </div>
        <button
          onClick={loadData}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
        >
          Refresh
        </button>
      </div>

      {/* Search & Filters */}
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search conversations..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <div className="flex gap-1 rounded-md bg-gray-100 p-1">
          {(["all", "unread", "replied", "no_reply"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded px-3 py-1 text-sm font-medium capitalize transition-colors ${
                filter === f
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {f === "no_reply" ? "No Reply" : f}
            </button>
          ))}
        </div>
      </div>

      {/* Split Panel */}
      <div className="flex h-[calc(100vh-220px)] overflow-hidden rounded-lg bg-white shadow">
        {/* Conversation List */}
        <div className="w-1/2 border-r">
          <div className="border-b px-4 py-3">
            <h2 className="text-sm font-semibold text-gray-900">
              {conversations.length} conversation{conversations.length !== 1 && "s"}
            </h2>
          </div>
          <div className="overflow-y-auto">
            {conversations.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                {accounts.length === 0
                  ? "No Gmail accounts connected. Go to Gmail Integration to connect one."
                  : "No conversations match your filter."}
              </div>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.threadId}
                  onClick={() => setSelectedConversation(conv)}
                  className={`cursor-pointer border-b px-4 py-3 transition-colors hover:bg-gray-50 ${
                    selectedConversation?.threadId === conv.threadId
                      ? "bg-blue-50"
                      : ""
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-gray-900">
                          {truncate(conv.fromEmail, 28)}
                        </span>
                        {conv.unreadCount > 0 && (
                          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-blue-600 px-1.5 text-[10px] font-bold text-white">
                            {conv.unreadCount}
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 text-sm font-medium text-gray-700">
                        {truncate(conv.subject, 50)}
                      </div>
                      <div className="mt-0.5 text-xs text-gray-500">
                        {truncate(conv.snippet, 60)}
                      </div>
                    </div>
                    <div className="ml-3 text-right">
                      <div className="text-xs text-gray-400">
                        {formatDate(conv.date)}
                      </div>
                      <div className="mt-1 text-[10px] text-gray-400">
                        {conv.messages.length} msg{conv.messages.length !== 1 && "s"}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Conversation Detail */}
        <div className="w-1/2 overflow-y-auto">
          {selectedConversation ? (
            <div>
              <div className="border-b px-4 py-3">
                <h3 className="text-sm font-semibold text-gray-900">
                  {selectedConversation.subject}
                </h3>
                <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                  <span>{selectedConversation.fromEmail}</span>
                  <span>-</span>
                  <span>{selectedConversation.messages.length} messages</span>
                </div>
              </div>
              <div className="divide-y">
                {selectedConversation.messages.map((msg) => (
                  <div key={msg.id} className="px-4 py-3">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-200 text-xs font-medium text-gray-600">
                          {msg.from_email ? msg.from_email.charAt(0).toUpperCase() : "?"}
                        </div>
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {msg.from_email || "Unknown Sender"}
                          </div>
                          <div className="text-xs text-gray-500">
                            {new Date(msg.date).toLocaleString()}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {msg.isRead && (
                          <span className="rounded bg-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-700">
                            Read
                          </span>
                        )}
                        {msg.isReplied && (
                          <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                            Replied
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-sm text-gray-700 whitespace-pre-wrap">
                      {msg.snippet || "No content available"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-gray-400">
              Select a conversation to view
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
