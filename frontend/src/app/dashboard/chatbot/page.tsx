"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  getChatSessions,
  createChatSession,
  getChatSessionMessages,
  deleteChatSession,
  sendChatMessage,
  ChatSession,
} from "@/services/monitor-api";
import api from "@/services/api";
import ApprovalCard, { type ApprovalAction } from "@/components/chat/ApprovalCard";

const renderFormattedMessage = (content: string) => {
  const lines = content.split("\n");
  const elements: React.JSX.Element[] = [];
  
  let currentTable: string[][] = [];
  let inTable = false;
  let currentList: { type: "bullet" | "number"; items: string[] } | null = null;
  
  const parseInlineStyles = (text: string) => {
    const regex = /(\*\*.*?\*\*|`.*?`|\*.*?\*)/g;
    const parts = text.split(regex);
    
    return parts.map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={index} className="font-extrabold text-[var(--foreground-color)]">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={index} className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-xs font-mono text-purple-600 dark:text-purple-400">
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={index} className="italic">{part.slice(1, -1)}</em>;
      }
      return part;
    });
  };

  const flushList = (key: number) => {
    if (!currentList) return null;
    const list = currentList;
    currentList = null;
    if (list.type === "bullet") {
      return (
        <ul key={`list-${key}`} className="list-disc pl-5 my-2 space-y-1">
          {list.items.map((item, idx) => (
            <li key={idx} className="text-sm leading-relaxed">{parseInlineStyles(item)}</li>
          ))}
        </ul>
      );
    } else {
      return (
        <ol key={`list-${key}`} className="list-decimal pl-5 my-2 space-y-1">
          {list.items.map((item, idx) => (
            <li key={idx} className="text-sm leading-relaxed">{parseInlineStyles(item)}</li>
          ))}
        </ol>
      );
    }
  };

  const flushTable = (key: number) => {
    if (!inTable || currentTable.length === 0) return null;
    inTable = false;
    const tableData = [...currentTable];
    currentTable = [];

    const filteredRows = tableData.filter(row => !row.every(cell => /^:?-+:?$/.test(cell.trim())));
    if (filteredRows.length === 0) return null;

    const headers = filteredRows[0];
    const rows = filteredRows.slice(1);

    return (
      <div key={`table-${key}`} className="overflow-x-auto my-3 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] shadow-sm">
        <table className="min-w-full divide-y divide-[var(--card-border)] text-left border-collapse">
          <thead className="bg-gray-150/40 dark:bg-gray-900/40">
            <tr>
              {headers.map((header, idx) => (
                <th key={idx} className="px-4 py-3 text-xs font-bold text-[var(--foreground-color)] uppercase tracking-wider border-b border-[var(--card-border)]">
                  {parseInlineStyles(header.trim())}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--card-border)]">
            {rows.map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-gray-50/40 dark:hover:bg-gray-800/20 transition-colors">
                {row.map((cell, cellIdx) => (
                  <td key={cellIdx} className="px-4 py-3 text-xs text-[var(--foreground-color)] font-medium leading-relaxed">
                    {parseInlineStyles(cell.trim())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const isTableRow = line.trim().startsWith("|") && line.trim().endsWith("|");

    if (isTableRow) {
      if (currentList) {
        elements.push(flushList(i)!);
      }
      inTable = true;
      const cells = line.split("|").slice(1, -1);
      currentTable.push(cells);
      continue;
    } else if (inTable) {
      const tbl = flushTable(i);
      if (tbl) elements.push(tbl);
    }

    const isBullet = line.trim().startsWith("- ") || line.trim().startsWith("* ");
    const isNumber = /^\d+\.\s+/.test(line.trim());

    if (isBullet) {
      const content = line.trim().slice(2);
      if (currentList && currentList.type === "bullet") {
        currentList.items.push(content);
      } else {
        if (currentList) elements.push(flushList(i)!);
        currentList = { type: "bullet", items: [content] };
      }
      continue;
    } else if (isNumber) {
      const content = line.trim().replace(/^\d+\.\s+/, "");
      if (currentList && currentList.type === "number") {
        currentList.items.push(content);
      } else {
        if (currentList) elements.push(flushList(i)!);
        currentList = { type: "number", items: [content] };
      }
      continue;
    } else if (currentList) {
      elements.push(flushList(i)!);
    }

    if (line.trim().startsWith("#")) {
      const level = (line.match(/^#+/) || ["#"])[0].length;
      const text = line.replace(/^#+\s*/, "");
      const fontSize = level === 1 ? "text-xl font-extrabold my-3" : level === 2 ? "text-lg font-bold my-2" : "text-base font-semibold my-1";
      elements.push(
        <h3 key={i} className={`${fontSize} text-[var(--foreground-color)] tracking-tight`}>
          {parseInlineStyles(text)}
        </h3>
      );
      continue;
    }

    if (line.trim() === "") {
      elements.push(<div key={i} className="h-2" />);
    } else {
      elements.push(
        <p key={i} className="text-sm leading-relaxed text-[var(--foreground-color)] font-medium my-1">
          {parseInlineStyles(line)}
        </p>
      );
    }
  }

  if (currentList) {
    elements.push(flushList(lines.length)!);
  }
  if (inTable) {
    const tbl = flushTable(lines.length);
    if (tbl) elements.push(tbl);
  }

  return elements;
};

interface ChatMessage {
  role: string;
  content: string;
  pendingApproval?: ApprovalAction | null;
}

export default function ChatbotPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [actions, setActions] = useState<any[]>([]);
  const [showSidebar, setShowSidebar] = useState(true);
  const [uploadedFiles, setUploadedFiles] = useState<{ name: string; url: string; type: string; id: string }[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalAction[]>([]);

  const [llmProvider, setLlmProvider] = useState<string>("nvidia");
  const [llmModel, setLlmModel] = useState<string>("qwen/qwen3.5-122b-a10b");
  const [modelsData, setModelsData] = useState<any>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const activeSessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  const fetchPendingApprovals = async () => {
    try {
      const currentSessionId = activeSessionIdRef.current;
      // Scope approvals to the current session so they don't bleed into other tabs
      const params = currentSessionId ? { chat_session_id: currentSessionId } : {};
      const response = await api.get("/chatbot/approvals", { params });
      if (response.status === 200) {
        const data = response.data;
        setPendingApprovals(data);
        
        // Auto-inject new approvals into the active chat session
        if (currentSessionId) {
          setMessages((currentMessages) => {
            const existingIds = new Set(currentMessages.map(m => m.pendingApproval?.action_id).filter(Boolean));
            const newApprovals = data.filter((app: ApprovalAction) => !existingIds.has(app.action_id));
            
            if (newApprovals.length > 0) {
              let updatedMessages = [...currentMessages];
              newApprovals.forEach((app: ApprovalAction) => {
                api.post(`/chatbot/sessions/${currentSessionId}/inject-approval`, { action_id: app.action_id })
                  .catch(console.error);
                
                updatedMessages.push({
                  role: "assistant",
                  content: "I have generated a new draft for your approval:",
                  pendingApproval: app,
                });
              });
              return updatedMessages;
            }
            return currentMessages;
          });
        }
      }
    } catch (err) {
      console.error("Failed to fetch pending approvals:", err);
    }
  };

  const handleApprovalDecision = async (actionId: string, decision: "approve" | "reject", resultData?: any) => {
    // Remove from the polled list
    setPendingApprovals((prev) => prev.filter((app) => app.action_id !== actionId));
    
    if (decision === "approve") {
      const prompt = `[System: The user approved the pending action (ID: ${actionId}). The backend execution was successful. Please acknowledge this completion to the user.]`;
      await executeMessage(prompt);
    } else if (decision === "reject") {
      const prompt = `[System: The user rejected the pending action (ID: ${actionId}). Please acknowledge the cancellation.]`;
      await executeMessage(prompt);
    }
  };

  // Auto-grow textarea height on input change
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 200)}px`;
    }
  }, [input]);

  // Load sessions, LLM models and setup polling for approvals on mount
  useEffect(() => {
    loadSessions();
    fetchPendingApprovals();
    
    const fetchModels = async () => {
      try {
        const response = await api.get("/chatbot/models");
        if (response.status === 200) {
          setModelsData(response.data.providers);
          setLlmProvider(response.data.default_provider);
          setLlmModel(response.data.default_model);
        }
      } catch (err) {
        console.error("Failed to load LLM models:", err);
      }
    };
    fetchModels();

    const interval = setInterval(fetchPendingApprovals, 5000);
    return () => clearInterval(interval);
  }, []);

  // Load messages and sticky model/provider settings when session changes
  useEffect(() => {
    if (activeSessionId) {
      loadSessionMessages(activeSessionId);
      const currentSession = sessions.find((s) => s.id === activeSessionId);
      if (currentSession) {
        if (currentSession.llm_provider) {
          setLlmProvider(currentSession.llm_provider);
        }
        if (currentSession.llm_model) {
          setLlmModel(currentSession.llm_model);
        }
      }
    }
  }, [activeSessionId, sessions]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadSessions = async () => {
    try {
      const data = await getChatSessions();
      setSessions(data);
    } catch (err) {
      console.error("Failed to load sessions:", err);
    }
  };

  const loadSessionMessages = async (sessionId: string) => {
    try {
      const data = await getChatSessionMessages(sessionId);
      // Map to simple message format for display
      const mappedMessages = data.map((m: any) => ({
        role: m.role,
        content: m.content,
        pendingApproval: m.pending_approval ?? null,
      }));
      setMessages(mappedMessages);
      // Load actions from messages
      const allActions = data
        .filter((m) => m.actions_taken && m.actions_taken.length > 0)
        .flatMap((m) => m.actions_taken || []);
      setActions(allActions);
    } catch (err) {
      console.error("Failed to load messages:", err);
    }
  };

  const handleNewSession = async () => {
    try {
      const session = await createChatSession("New Chat");
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setMessages([
        {
          role: "assistant",
          content:
            "Hello! I am your Autonomous Campaign Management Agent with 23+ tools.\n\n" +
            "**Campaign Management:**\n" +
            "- Create, start, pause, delete, duplicate campaigns\n" +
            "- Get analytics and search campaigns\n\n" +
            "**Lead Management:**\n" +
            "- Add single or bulk leads\n" +
            "- Search, move, and delete leads\n\n" +
            "**Email & Accounts:**\n" +
            "- List Gmail accounts and sent emails\n" +
            "- View replies and track engagement\n\n" +
            "**Lists & Blocklist:**\n" +
            "- Create lead lists and manage blocklist\n\n" +
            "What would you like to do?",
        },
      ]);
      setActions([]);
    } catch (err) {
      console.error("Failed to create session:", err);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteChatSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
        setActions([]);
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await api.post("/files/upload", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        });

        if (response.status === 200 || response.status === 201) {
          const data = response.data;
          setUploadedFiles((prev) => [
            ...prev,
            { 
              name: data.filename, 
              url: data.download_url, 
              type: data.content_type,
              id: data.id,
            },
          ]);
        } else {
          console.error("Upload failed:", response.statusText);
        }
      } catch (err) {
        console.error("Failed to upload file:", err);
      }
    }

    // Reset input
    e.target.value = "";
  };

  const removeFile = (index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const executeMessage = async (userMessage: string) => {
    if (loading) return;

    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        const session = await createChatSession(
          userMessage.slice(0, 50) + (userMessage.length > 50 ? "..." : "")
        );
        setSessions((prev) => [session, ...prev]);
        sessionId = session.id;
        setActiveSessionId(sessionId);
      } catch (err) {
        console.error("Failed to create session:", err);
        return;
      }
    }

    const newMessages: ChatMessage[] = [
      ...messages,
      { role: "user", content: userMessage },
    ];
    setMessages(newMessages);
    const filesToSend = [...uploadedFiles];
    setUploadedFiles([]);
    setLoading(true);

    try {
      const data = await sendChatMessage(sessionId, userMessage, filesToSend, llmProvider, llmModel);

      // Check for pending approval embedded in response
      const pendingApproval: ApprovalAction | null = data.pending_approval ?? null;

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response, pendingApproval },
      ]);

      if (data.actions_taken && data.actions_taken.length > 0) {
        setActions((prev) => [...prev, ...data.actions_taken]);
      }

      loadSessions();
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "I'm sorry, I failed to process your request. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e?: React.FormEvent | React.KeyboardEvent) => {
    if (e) e.preventDefault();
    if ((!input.trim() && uploadedFiles.length === 0) || loading) return;

    let userMessage = input.trim();
    setInput("");

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    if (uploadedFiles.length > 0) {
      const fileInfo = uploadedFiles.map((f) => `${f.name} (${f.url})`).join(", ");
      userMessage = userMessage
        ? `${userMessage}\n\n[Attached files: ${fileInfo}]`
        : `[Attached files: ${fileInfo}]`;
    }

    await executeMessage(userMessage);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const getActionBadgeColor = (toolName: string) => {
    switch (toolName) {
      case "create_campaign":
        return "bg-green-100 text-green-800 border-green-200";
      case "start_campaign":
        return "bg-blue-100 text-blue-800 border-blue-200";
      case "pause_campaign":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      case "delete_campaign":
        return "bg-red-100 text-red-800 border-red-200";
      case "duplicate_campaign":
        return "bg-indigo-100 text-indigo-800 border-indigo-200";
      case "add_lead":
        return "bg-purple-100 text-purple-800 border-purple-200";
      case "bulk_add_leads":
        return "bg-purple-100 text-purple-800 border-purple-200";
      case "move_leads":
        return "bg-orange-100 text-orange-800 border-orange-200";
      case "search_leads":
        return "bg-cyan-100 text-cyan-800 border-cyan-200";
      case "get_campaign_analytics":
        return "bg-teal-100 text-teal-800 border-teal-200";
      case "list_campaigns":
      case "list_leads":
      case "list_emails":
      case "list_replies":
      case "list_gmail_accounts":
      case "list_lead_lists":
      case "list_block_list":
        return "bg-gray-100 text-gray-800 border-gray-200";
      case "create_lead_list":
        return "bg-violet-100 text-violet-800 border-violet-200";
      case "add_to_block_list":
        return "bg-rose-100 text-rose-800 border-rose-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const formatToolName = (name: string) => {
    return name
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  };

  return (
    <div className="flex h-full bg-gray-50/50 overflow-hidden">
      {/* Session Sidebar */}
      {showSidebar && (
        <div className="w-64 border-r border-gray-100 bg-white flex flex-col">
          <div className="p-4 border-b border-gray-100">
            <button
              onClick={handleNewSession}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              New Chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {sessions.length === 0 ? (
              <div className="p-4 text-xs text-gray-400 text-center">
                No chat sessions yet
              </div>
            ) : (
              <div className="p-2 space-y-1">
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    className={`group flex items-center justify-between rounded-lg px-3 py-2.5 cursor-pointer transition-colors ${
                      activeSessionId === session.id
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-700 hover:bg-gray-50"
                    }`}
                    onClick={() => setActiveSessionId(session.id)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">
                        {session.title}
                      </div>
                      <div className="text-xs text-gray-400">
                        {session.message_count} messages
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSession(session.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 ml-2 p-1 rounded hover:bg-red-100 hover:text-red-600 transition-all"
                    >
                      <svg
                        className="h-3.5 w-3.5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4" style={{ background: "var(--card-bg)", borderBottom: "1px solid var(--card-border)" }}>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <svg
                className="h-5 w-5 text-gray-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            </button>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white shadow-md shadow-blue-200">
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 leading-tight">
                Elly
              </h1>
              <p className="text-xs text-gray-500 font-medium">
                {activeSessionId
                  ? `Session: ${sessions.find((s) => s.id === activeSessionId)?.title || "Chat"}`
                  : "Start a new conversation"}
              </p>
            </div>
          </div>

          {/* Model Selection Dropdown */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex flex-col">
              <label className="text-[9px] font-bold uppercase tracking-wider mb-0.5" style={{ color: "var(--sidebar-text-muted)" }}>
                Provider
              </label>
              <select
                value={llmProvider}
                onChange={(e) => {
                  const newProvider = e.target.value;
                  setLlmProvider(newProvider);
                  if (modelsData && modelsData[newProvider]) {
                    setLlmModel(modelsData[newProvider].default_model);
                  }
                }}
                className="text-xs font-semibold px-2 py-1 rounded-lg border outline-none cursor-pointer transition-all shadow-sm"
                style={{
                  background: "var(--sidebar-toggle-bg)",
                  borderColor: "var(--card-border)",
                  color: "var(--foreground-color)"
                }}
              >
                {modelsData ? (
                  Object.entries(modelsData).map(([key, val]: [string, any]) => (
                    <option key={key} value={key} className="bg-[var(--card-bg)] text-[var(--foreground-color)] font-semibold">
                      {val.name}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="nvidia">Nvidia NIM</option>
                    <option value="groq">Groq</option>
                    <option value="xiaomi">Xiaomi</option>
                  </>
                )}
              </select>
            </div>

            <div className="flex flex-col">
              <label className="text-[9px] font-bold uppercase tracking-wider mb-0.5" style={{ color: "var(--sidebar-text-muted)" }}>
                Model
              </label>
              <select
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className="text-xs font-semibold px-2 py-1 rounded-lg border outline-none cursor-pointer transition-all shadow-sm max-w-[170px] truncate"
                style={{
                  background: "var(--sidebar-toggle-bg)",
                  borderColor: "var(--card-border)",
                  color: "var(--foreground-color)"
                }}
              >
                {modelsData && modelsData[llmProvider] ? (
                  modelsData[llmProvider].models.map((m: any) => (
                    <option key={m.id} value={m.id} title={m.name} className="bg-[var(--card-bg)] text-[var(--foreground-color)] font-semibold">
                      {m.name}
                    </option>
                  ))
                ) : (
                  llmProvider === "nvidia" ? (
                    <>
                      <option value="qwen/qwen3.5-122b-a10b">Qwen 3.5 122B (NIM)</option>
                      <option value="meta/llama-3.1-70b-instruct">Llama 3.1 70B (NIM)</option>
                      <option value="meta/llama-3.3-70b-instruct">Llama 3.3 70B (NIM)</option>
                      <option value="deepseek/deepseek-r1">DeepSeek R1 (NIM)</option>
                    </>
                  ) : llmProvider === "xiaomi" ? (
                    <>
                      <option value="mimo-v2.5">MiMo v2.5</option>
                      <option value="mimo-v2.5-pro">MiMo v2.5 Pro</option>
                    </>
                  ) : (
                    <>
                      <option value="llama-3.3-70b-versatile">Llama 3.3 70B Versatile</option>
                      <option value="llama3-70b-8192">Llama 3 70B (8192)</option>
                      <option value="llama3-8b-8192">Llama 3 8B (8192)</option>
                      <option value="mixtral-8x7b-32768">Mixtral 8x7B</option>
                    </>
                  )
                )}
              </select>
            </div>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Chat Messages */}
          <div className="flex flex-1 flex-col overflow-hidden" style={{ background: "var(--card-bg)" }}>
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-center max-w-2xl mx-auto space-y-6">
                  <div className="flex flex-col items-center">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl mb-3 shadow-sm animate-bounce" style={{ background: "rgba(124,92,255,0.1)", border: "1px solid rgba(124,92,255,0.2)", color: "var(--primary)" }}>
                      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <h2 className="text-lg font-black" style={{ color: "var(--foreground-color)" }}>
                      AI Outreach Command Center
                    </h2>
                    <p className="text-xs max-w-sm mt-1 leading-relaxed" style={{ color: "var(--sidebar-text-muted)" }}>
                      Control campaign scheduling, lead discovery Fallbacks, and signal scoring pipelines using natural language.
                    </p>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-3 w-full max-w-lg">
                    {[
                      "Find CTOs of SaaS companies in India",
                      "Create campaign for healthcare startups",
                      "Generate outreach for Rahul Sharma",
                      "Show highest opportunity leads",
                      "Generate LinkedIn content"
                    ].map((cmd) => (
                      <button
                        key={cmd}
                        onClick={() => executeMessage(cmd)}
                        className="p-3 text-left rounded-xl font-semibold text-xs transition-all flex justify-between items-center group hover:opacity-80"
                        style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", color: "var(--foreground-color)" }}
                      >
                        <span>{cmd}</span>
                        <span style={{ color: "var(--sidebar-text-muted)" }}>&rarr;</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.filter(msg => !msg.content.startsWith("[System:")).map((msg, index) => (
                <div
                  key={index}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} animate-fadeIn`}
                >
                  <div
                    className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm font-sans shadow-sm ${
                      msg.role === "user"
                        ? "rounded-br-none"
                        : "rounded-bl-none"
                    }`}
                    style={msg.role === "user" ? {
                      background: "var(--primary)",
                      color: "#fff",
                      wordBreak: "break-word",
                      overflowWrap: "break-word",
                    } : {
                      background: "var(--sidebar-toggle-bg)",
                      color: "var(--foreground-color)",
                      border: "1px solid var(--card-border)",
                      wordBreak: "break-word",
                      overflowWrap: "break-word",
                    }}
                  >
                    {msg.role === "assistant" ? (
                      <div className="space-y-1">
                        {renderFormattedMessage(msg.content)}
                        {msg.pendingApproval && (
                          <ApprovalCard
                            action={msg.pendingApproval}
                            onDecision={handleApprovalDecision}
                          />
                        )}
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap font-medium">{msg.content}</div>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start animate-pulse">
                  <div className="rounded-2xl rounded-bl-none px-4 py-3 text-sm flex items-center gap-2" style={{ background: "var(--sidebar-toggle-bg)", color: "var(--sidebar-text-muted)", border: "1px solid var(--card-border)" }}>
                    <div className="flex space-x-1">
                      <div className="h-2 w-2 rounded-full animate-bounce" style={{ background: "var(--sidebar-text-muted)", animationDelay: "0ms" }}></div>
                      <div className="h-2 w-2 rounded-full animate-bounce" style={{ background: "var(--sidebar-text-muted)", animationDelay: "150ms" }}></div>
                      <div className="h-2 w-2 rounded-full animate-bounce" style={{ background: "var(--sidebar-text-muted)", animationDelay: "300ms" }}></div>
                    </div>
                    <span>Thinking...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Polled Pending Approvals Bar (not already shown inline) */}
            {(() => {
              const visibleActionIds = messages
                .map((m) => m.pendingApproval?.action_id)
                .filter(Boolean) as string[];
              const filteredApprovals = pendingApprovals.filter(
                (app) => !visibleActionIds.includes(app.action_id)
              );

              if (filteredApprovals.length === 0) return null;

              return (
                <div className="px-6 py-3 border-t border-[var(--card-border)] bg-yellow-500/5 dark:bg-yellow-400/5 space-y-3 max-h-[300px] overflow-y-auto">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[var(--foreground-color)] flex items-center gap-1.5">
                      <span className="animate-pulse h-2 w-2 rounded-full bg-yellow-500"></span>
                      Pending Approvals ({filteredApprovals.length})
                    </span>
                  </div>
                  {filteredApprovals.map((app) => (
                    <ApprovalCard
                      key={app.action_id}
                      action={app}
                      onDecision={handleApprovalDecision}
                    />
                  ))}
                </div>
              );
            })()}

            {/* Input Form */}
            <form
              onSubmit={handleSubmit}
              className="p-4"
              style={{ borderTop: "1px solid var(--card-border)", background: "var(--card-bg)" }}
            >
              {/* File Preview */}
              {uploadedFiles.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-2">
                  {uploadedFiles.map((file, i) => (
                    <div key={i} className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs" style={{ background: "rgba(124,92,255,0.1)", color: "var(--primary)" }}>
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <span>{file.name}</span>
                      <button type="button" onClick={() => removeFile(i)} className="hover:opacity-60 transition-opacity">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
              
              <div className="relative flex items-end rounded-2xl transition-all px-2 py-2" style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}>
                {/* Upload Button */}
                <label className="p-2 cursor-pointer transition-opacity hover:opacity-60 shrink-0" style={{ color: "var(--sidebar-text-muted)" }}>
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                  </svg>
                  <input
                    type="file"
                    className="hidden"
                    multiple
                    accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.png,.jpg,.jpeg,.gif"
                    onChange={handleFileUpload}
                  />
                </label>
                
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask Elly to automate a task..."
                  disabled={loading}
                  rows={1}
                  className="flex-1 bg-transparent px-2 py-2 text-sm outline-none resize-none overflow-y-auto max-h-[200px] leading-relaxed"
                  style={{ color: "var(--foreground-color)" }}
                />
                <button
                  type="submit"
                  disabled={(!input.trim() && uploadedFiles.length === 0) || loading}
                  className="p-2 rounded-xl text-white font-bold disabled:opacity-40 shadow-sm transition-all hover:opacity-90 shrink-0 ml-1"
                  style={{ background: "var(--primary)" }}
                >
                  <svg
                    className="h-4.5 w-4.5 transform rotate-90"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2.5}
                      d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                    />
                  </svg>
                </button>
              </div>
            </form>
          </div>

          {/* Actions Sidebar */}
          <div className="w-80 p-6 overflow-y-auto hidden lg:block" style={{ borderLeft: "1px solid var(--card-border)", background: "var(--sidebar-toggle-bg)" }}>
            <h2 className="text-sm font-bold uppercase tracking-wider mb-4" style={{ color: "var(--foreground-color)" }}>
              Actions Logged
            </h2>
            {actions.length === 0 ? (
              <div className="text-xs italic py-4" style={{ color: "var(--sidebar-text-muted)" }}>
                No automation tasks executed in this session.
              </div>
            ) : (
              <div className="space-y-3">
                {actions.map((act, index) => (
                  <div
                    key={index}
                    className="rounded-xl p-3.5 space-y-2"
                    style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)" }}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getActionBadgeColor(act.tool)}`}
                      >
                        {formatToolName(act.tool)}
                      </span>
                      <span className="text-[10px] font-semibold" style={{ color: "#10b981" }}>
                        Success
                      </span>
                    </div>
                    <div className="text-xs space-y-1" style={{ color: "var(--foreground-color)" }}>
                      {act.arguments && Object.entries(act.arguments).map(
                        ([key, val]: [string, any]) => (
                          <div key={key} className="flex justify-between">
                            <span className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>{key}:</span>
                            <span className="font-semibold truncate max-w-[120px]" style={{ color: "var(--foreground-color)" }}>{String(val)}</span>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
