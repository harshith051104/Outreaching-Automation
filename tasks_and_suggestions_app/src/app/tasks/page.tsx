"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  getTasks,
  createTask,
  updateTask,
  deleteTask,
  getTeamMembers,
  exportTasksToSheets,
  Task,
  UserMin,
} from "@/services/task-api";
import {
  ClipboardList,
  Plus,
  Search,
  Filter,
  Calendar,
  User,
  AlertCircle,
  Trash2,
  LayoutGrid,
  List,
  X,
  PlusCircle,
  FileSpreadsheet,
} from "lucide-react";

const COLUMNS: { id: Task["status"]; label: string; color: string; dotColor: string }[] = [
  { id: "todo", label: "To Do", color: "var(--sidebar-text-muted)", dotColor: "#64748b" },
  { id: "in_progress", label: "In Progress", color: "#3b82f6", dotColor: "#3b82f6" },
  { id: "review", label: "In Review", color: "#f59e0b", dotColor: "#f59e0b" },
  { id: "blocked", label: "Blocked", color: "#ef4444", dotColor: "#ef4444" },
  { id: "completed", label: "Completed", color: "#10b981", dotColor: "#10b981" },
];

const PRIORITY_THEMES = {
  low: { badgeColor: "var(--sidebar-text-muted)", badgeBg: "rgba(100,116,139,0.1)", borderColor: "#64748b" },
  medium: { badgeColor: "#3b82f6", badgeBg: "rgba(59,130,246,0.1)", borderColor: "#3b82f6" },
  high: { badgeColor: "#f59e0b", badgeBg: "rgba(245,158,11,0.1)", borderColor: "#f59e0b" },
  critical: { badgeColor: "#ef4444", badgeBg: "rgba(239,68,68,0.1)", borderColor: "#ef4444" },
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [teamMembers, setTeamMembers] = useState<UserMin[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"kanban" | "list">("kanban");

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");

  // Create Task Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newPriority, setNewPriority] = useState<Task["priority"]>("medium");
  const [newStatus, setNewStatus] = useState<Task["status"]>("todo");
  const [newDueDate, setNewDueDate] = useState("");
  const [newAssignee, setNewAssignee] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Drag and drop state
  const [activeDragColumn, setActiveDragColumn] = useState<Task["status"] | null>(null);

  // Sheets Export State
  const [exporting, setExporting] = useState(false);
  const [sheetNotification, setSheetNotification] = useState<{ title: string; url: string } | null>(null);
  const [sheetError, setSheetError] = useState<string | null>(null);

  const handleExportSheets = async () => {
    try {
      setExporting(true);
      setSheetNotification(null);
      setSheetError(null);
      
      const result = await exportTasksToSheets({
        search: searchQuery || undefined,
        priority: priorityFilter || undefined,
        assigned_to: assigneeFilter || undefined
      });
      
      if (result && result.spreadsheet_url) {
        setSheetNotification({ title: result.title, url: result.spreadsheet_url });
      }
    } catch (err: any) {
      console.error("Failed to export tasks to Google Sheets:", err);
      const errMsg = err.response?.data?.detail || "Failed to sync. Please make sure your Google account is connected under Settings.";
      setSheetError(errMsg);
    } finally {
      setExporting(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [tasksData, teamData] = await Promise.all([
        getTasks().catch(() => []),
        getTeamMembers().catch(() => []),
      ]);
      setTasks(tasksData);
      setTeamMembers(teamData);
    } catch (err) {
      console.error("Failed to load tasks dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    try {
      setSubmitting(true);
      await createTask({
        title: newTitle,
        description: newDescription,
        status: newStatus,
        priority: newPriority,
        due_date: newDueDate || null,
        assigned_to: newAssignee || null,
      });

      // Reset Form
      setNewTitle("");
      setNewDescription("");
      setNewPriority("medium");
      setNewStatus("todo");
      setNewDueDate("");
      setNewAssignee("");
      setIsModalOpen(false);

      // Refresh list
      const updated = await getTasks();
      setTasks(updated);
    } catch (err) {
      console.error("Failed to create task:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteTask = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this task?")) return;

    try {
      await deleteTask(id);
      setTasks(tasks.filter((t) => t.id !== id));
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  };

  // Drag and Drop implementation
  const handleDragStart = (e: React.DragEvent, taskId: string) => {
    e.dataTransfer.setData("text/plain", taskId);
  };

  const handleDragOver = (e: React.DragEvent, columnId: Task["status"]) => {
    e.preventDefault();
    if (activeDragColumn !== columnId) {
      setActiveDragColumn(columnId);
    }
  };

  const handleDrop = async (e: React.DragEvent, targetStatus: Task["status"]) => {
    e.preventDefault();
    setActiveDragColumn(null);
    const taskId = e.dataTransfer.getData("text/plain");
    if (!taskId) return;

    // Optimistic UI update
    const originalTasks = [...tasks];
    setTasks(
      tasks.map((t) => (t.id === taskId ? { ...t, status: targetStatus } : t))
    );

    try {
      await updateTask(taskId, { status: targetStatus });
    } catch (err) {
      console.error("Failed to update task status via drag-and-drop:", err);
      setTasks(originalTasks); // rollback
    }
  };

  const isOverdue = (task: Task) => {
    if (!task.due_date || task.status === "completed") return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const due = new Date(task.due_date);
    return due < today;
  };

  // Filter Tasks
  const filteredTasks = tasks.filter((task) => {
    const matchesSearch =
      task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (task.description || "").toLowerCase().includes(searchQuery.toLowerCase());
    const matchesPriority = priorityFilter ? task.priority === priorityFilter : true;
    const matchesAssignee = assigneeFilter ? task.assigned_to === assigneeFilter : true;
    return matchesSearch && matchesPriority && matchesAssignee;
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

  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4">
      {/* Hero Banner */}
      <div style={bannerStyle} className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 relative overflow-hidden">
        <div className="absolute -right-16 -top-16 h-48 w-48 opacity-10 rounded-full blur-3xl pointer-events-none" style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)" }} />
        <div className="relative z-10 space-y-1">
          <h1 style={{ color: "var(--banner-text)" }} className="text-2xl font-extrabold tracking-tight flex items-center gap-2">
            <ClipboardList className="h-6 w-6" style={{ color: "var(--primary)" }} />
            Task Hub & Collaborator
          </h1>
          <p style={{ color: "var(--banner-desc)" }} className="text-sm max-w-xl">
            Organize campaigns, follow-up queues, content calendars, and team assignments in real-time.
          </p>
        </div>
        <div className="flex items-center gap-3 relative z-10">
          <div className="flex p-1 rounded-lg" style={{ background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}>
            <button
              onClick={() => setViewMode("kanban")}
              className="p-1.5 rounded-md transition-all"
              style={{ background: viewMode === "kanban" ? "var(--primary)" : "transparent", color: viewMode === "kanban" ? "#fff" : "var(--sidebar-text-muted)" }}
              title="Kanban Board View"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className="p-1.5 rounded-md transition-all"
              style={{ background: viewMode === "list" ? "var(--primary)" : "transparent", color: viewMode === "list" ? "#fff" : "var(--sidebar-text-muted)" }}
              title="List View"
            >
              <List className="h-4 w-4" />
            </button>
          </div>
          <button
            onClick={handleExportSheets}
            disabled={exporting}
            className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold transition-all shadow-md hover:opacity-90 disabled:opacity-50"
            style={{ background: "rgba(16,185,129,0.15)", color: "#10b981", border: "1px solid rgba(16,185,129,0.3)" }}
          >
            <FileSpreadsheet className="h-4 w-4" /> {exporting ? "Syncing..." : "Sync to Sheets"}
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold transition-all shadow-md hover:opacity-90"
            style={{ background: "var(--primary)", color: "#fff" }}
          >
            <Plus className="h-4 w-4" /> New Task
          </button>
        </div>
      </div>

      {/* Google Sheets Export Notifications */}
      {sheetNotification && (
        <div className="p-4 rounded-xl flex items-center justify-between gap-4 animate-in fade-in slide-in-from-top-4 duration-300" style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)", color: "#10b981" }}>
          <div className="flex items-center gap-2 text-xs font-medium">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
            <span>
              Google Spreadsheet created successfully: <strong>{sheetNotification.title}</strong>
            </span>
          </div>
          <div className="flex items-center gap-3">
            <a
              href={sheetNotification.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-bold underline hover:opacity-80 transition-opacity flex items-center gap-1"
            >
              Open Spreadsheet →
            </a>
            <button onClick={() => setSheetNotification(null)} className="hover:opacity-75 transition-opacity">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {sheetError && (
        <div className="p-4 rounded-xl flex items-center justify-between gap-4 animate-in fade-in slide-in-from-top-4 duration-300" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)", color: "#ef4444" }}>
          <div className="flex items-center gap-2 text-xs font-medium">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{sheetError}</span>
          </div>
          <button onClick={() => setSheetError(null)} className="hover:opacity-75 transition-opacity">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Filters Toolbar */}
      <div style={cardStyle} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: "var(--sidebar-text-muted)" }} />
          <input
            type="text"
            placeholder="Search tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ ...inputStyle, paddingLeft: "36px", width: "100%" }}
          />
        </div>

        {/* dropdown filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--sidebar-text-muted)" }}>
            <Filter className="h-3.5 w-3.5" /> Filters
          </div>

          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            style={{ ...inputStyle, padding: "6px 12px" }}
          >
            <option value="">All Priorities</option>
            <option value="low">Low Priority</option>
            <option value="medium">Medium Priority</option>
            <option value="high">High Priority</option>
            <option value="critical">Critical Priority</option>
          </select>

          <select
            value={assigneeFilter}
            onChange={(e) => setAssigneeFilter(e.target.value)}
            style={{ ...inputStyle, padding: "6px 12px", maxWidth: "160px" }}
          >
            <option value="">All Assignees</option>
            {teamMembers.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>

          {(priorityFilter || assigneeFilter || searchQuery) && (
            <button
              onClick={() => {
                setPriorityFilter("");
                setAssigneeFilter("");
                setSearchQuery("");
              }}
              className="text-xs font-semibold transition-colors hover:opacity-80"
              style={{ color: "var(--primary)" }}
            >
              Clear All
            </button>
          )}
        </div>
      </div>

      {/* Loading state */}
      {loading ? (
        <div className="flex h-[40vh] items-center justify-center">
          <div className="text-center space-y-4">
            <div className="h-10 w-10 border-4 border-t-transparent rounded-full animate-spin mx-auto" style={{ borderColor: "var(--primary)", borderTopColor: "transparent" }}></div>
            <p className="font-medium" style={{ color: "var(--sidebar-text-muted)" }}>Syncing work boards...</p>
          </div>
        </div>
      ) : viewMode === "kanban" ? (
        /* Kanban Board View */
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 items-start">
          {COLUMNS.map((col) => {
            const columnTasks = filteredTasks.filter((t) => t.status === col.id);
            const isDraggingOver = activeDragColumn === col.id;

            return (
              <div
                key={col.id}
                onDragOver={(e) => handleDragOver(e, col.id)}
                onDrop={(e) => handleDrop(e, col.id)}
                onDragLeave={() => setActiveDragColumn(null)}
                style={{
                  background: "var(--sidebar-toggle-bg)",
                  border: isDraggingOver ? `2px solid ${col.dotColor}` : "1px solid var(--card-border)",
                  borderRadius: "12px",
                  padding: "12px",
                  minHeight: "500px",
                  display: "flex",
                  flexDirection: "column",
                  transition: "border 0.15s ease",
                  boxShadow: isDraggingOver ? `0 0 0 3px ${col.dotColor}22` : undefined,
                }}
              >
                {/* Column Title */}
                <div className="flex items-center justify-between mb-3 pb-2" style={{ borderBottom: "1px solid var(--card-border)" }}>
                  <span className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5" style={{ color: col.color }}>
                    <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ background: col.dotColor }} />
                    {col.label}
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: `${col.dotColor}22`, color: col.dotColor }}>
                    {columnTasks.length}
                  </span>
                </div>

                {/* Column Items */}
                <div className="space-y-3 flex-1 overflow-y-auto max-h-[600px] pr-0.5">
                  {columnTasks.length === 0 ? (
                    <div className="h-28 flex flex-col items-center justify-center rounded-xl text-xs p-4 text-center" style={{ border: "1px dashed var(--card-border)", color: "var(--sidebar-text-muted)" }}>
                      <ClipboardList className="h-5 w-5 mb-1.5 opacity-50" />
                      Empty column
                    </div>
                  ) : (
                    columnTasks.map((task) => {
                      const priorityTheme = PRIORITY_THEMES[task.priority] || PRIORITY_THEMES.medium;
                      const hasOverdue = isOverdue(task);

                      return (
                        <div
                          key={task.id}
                          draggable
                          onDragStart={(e) => handleDragStart(e, task.id)}
                          style={{
                            background: "var(--card-bg)",
                            border: "1px solid var(--card-border)",
                            borderLeft: `3px solid ${priorityTheme.borderColor}`,
                            borderRadius: "10px",
                            padding: "12px",
                            cursor: "grab",
                            transition: "box-shadow 0.2s ease",
                          }}
                          className="hover:shadow-md active:cursor-grabbing"
                        >
                          <Link href={`/dashboard/tasks/${task.id}`} className="block space-y-2.5">
                            {/* Header Row */}
                            <div className="flex justify-between items-start gap-1">
                              <span
                                className="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider"
                                style={{ background: priorityTheme.badgeBg, color: priorityTheme.badgeColor, border: `1px solid ${priorityTheme.badgeColor}44` }}
                              >
                                {task.priority}
                              </span>
                              <button
                                onClick={(e) => handleDeleteTask(task.id, e)}
                                className="p-0.5 rounded transition-colors hover:opacity-80"
                                style={{ color: "var(--sidebar-text-muted)" }}
                                title="Delete task"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>

                            {/* Title & Desc */}
                            <div className="space-y-1">
                              <h3 className="font-bold text-xs leading-snug line-clamp-2" style={{ color: "var(--foreground-color)" }}>
                                {task.title}
                              </h3>
                              {task.description && (
                                <p className="text-[11px] line-clamp-2 leading-relaxed" style={{ color: "var(--sidebar-text-muted)" }}>
                                  {task.description}
                                </p>
                              )}
                            </div>

                            {/* Due Date & Assignee */}
                            <div className="flex items-center justify-between text-[10px] pt-2 mt-1" style={{ borderTop: "1px solid var(--card-border)", color: "var(--sidebar-text-muted)" }}>
                              {task.due_date ? (
                                <div
                                  className="flex items-center gap-1 font-medium"
                                  style={{ color: hasOverdue ? "#ef4444" : "var(--sidebar-text-muted)" }}
                                >
                                  {hasOverdue ? (
                                    <AlertCircle className="h-3 w-3 shrink-0" />
                                  ) : (
                                    <Calendar className="h-3 w-3 shrink-0" />
                                  )}
                                  <span>
                                    {new Date(task.due_date).toLocaleDateString(undefined, {
                                      month: "short",
                                      day: "numeric",
                                    })}
                                  </span>
                                </div>
                              ) : (
                                <span style={{ color: "var(--sidebar-text-muted)" }}>No due date</span>
                              )}

                              {task.assignee_info ? (
                                <div
                                  className="flex items-center gap-1 max-w-[100px]"
                                  title={task.assignee_info.name}
                                >
                                  <div className="h-5 w-5 rounded-full flex items-center justify-center text-[9px] font-bold shrink-0" style={{ background: "rgba(124,92,255,0.15)", color: "var(--primary)", border: "1px solid rgba(124,92,255,0.3)" }}>
                                    {task.assignee_info.name.charAt(0).toUpperCase()}
                                  </div>
                                  <span className="truncate font-semibold" style={{ color: "var(--foreground-color)" }}>
                                    {task.assignee_info.name.split(" ")[0]}
                                  </span>
                                </div>
                              ) : (
                                <div className="flex items-center gap-1" style={{ color: "var(--sidebar-text-muted)" }}>
                                  <User className="h-3 w-3" />
                                  <span>Unassigned</span>
                                </div>
                              )}
                            </div>
                          </Link>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* List View */
        <div style={cardStyle} className="overflow-hidden">
          {filteredTasks.length === 0 ? (
            <div className="py-16 text-center space-y-3">
              <ClipboardList className="h-10 w-10 mx-auto" style={{ color: "var(--card-border)" }} />
              <h3 className="font-semibold text-sm" style={{ color: "var(--foreground-color)" }}>No tasks found</h3>
              <p className="text-xs max-w-xs mx-auto" style={{ color: "var(--sidebar-text-muted)" }}>
                Try widening your filters or create a new task to get started.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="text-[11px] font-bold uppercase tracking-wider" style={{ borderBottom: "1px solid var(--card-border)", background: "var(--sidebar-toggle-bg)", color: "var(--sidebar-text-muted)" }}>
                    <th className="p-4">Task Title</th>
                    <th className="p-4">Status</th>
                    <th className="p-4">Priority</th>
                    <th className="p-4">Due Date</th>
                    <th className="p-4">Assignee</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="text-xs">
                  {filteredTasks.map((task) => {
                    const priorityTheme = PRIORITY_THEMES[task.priority] || PRIORITY_THEMES.medium;
                    const col = COLUMNS.find((c) => c.id === task.status) || COLUMNS[0];
                    const hasOverdue = isOverdue(task);

                    return (
                      <tr key={task.id} className="transition-colors hover:opacity-90" style={{ borderBottom: "1px solid var(--card-border)" }}>
                        <td className="p-4">
                          <Link href={`/dashboard/tasks/${task.id}`} className="block">
                            <span className="font-bold block max-w-sm truncate hover:opacity-80 transition-opacity" style={{ color: "var(--foreground-color)" }}>
                              {task.title}
                            </span>
                            {task.description && (
                              <span className="text-[10px] line-clamp-1 max-w-sm mt-0.5" style={{ color: "var(--sidebar-text-muted)" }}>
                                {task.description}
                              </span>
                            )}
                          </Link>
                        </td>
                        <td className="p-4">
                          <span
                            className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold"
                            style={{ background: `${col.dotColor}18`, color: col.dotColor, border: `1px solid ${col.dotColor}44` }}
                          >
                            <span className="h-1.5 w-1.5 rounded-full" style={{ background: col.dotColor }} />
                            {col.label}
                          </span>
                        </td>
                        <td className="p-4">
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider"
                            style={{ background: priorityTheme.badgeBg, color: priorityTheme.badgeColor, border: `1px solid ${priorityTheme.badgeColor}44` }}
                          >
                            {task.priority}
                          </span>
                        </td>
                        <td className="p-4">
                          {task.due_date ? (
                            <span
                              className="flex items-center gap-1"
                              style={{ color: hasOverdue ? "#ef4444" : "var(--sidebar-text-muted)", fontWeight: hasOverdue ? "bold" : undefined }}
                            >
                              {hasOverdue && <AlertCircle className="h-3 w-3" />}
                              {new Date(task.due_date).toLocaleDateString(undefined, {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                              })}
                            </span>
                          ) : (
                            <span style={{ color: "var(--sidebar-text-muted)" }}>No due date</span>
                          )}
                        </td>
                        <td className="p-4">
                          {task.assignee_info ? (
                            <div className="flex items-center gap-1.5">
                              <div className="h-5 w-5 rounded-full flex items-center justify-center text-[9px] font-bold shrink-0" style={{ background: "rgba(124,92,255,0.15)", color: "var(--primary)", border: "1px solid rgba(124,92,255,0.3)" }}>
                                {task.assignee_info.name.charAt(0).toUpperCase()}
                              </div>
                              <span className="font-medium" style={{ color: "var(--foreground-color)" }}>
                                {task.assignee_info.name}
                              </span>
                            </div>
                          ) : (
                            <span style={{ color: "var(--sidebar-text-muted)" }}>Unassigned</span>
                          )}
                        </td>
                        <td className="p-4 text-right">
                          <button
                            onClick={(e) => handleDeleteTask(task.id, e)}
                            className="p-1 rounded transition-colors inline-flex hover:opacity-80"
                            style={{ color: "var(--sidebar-text-muted)" }}
                            title="Delete task"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* New Task Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)" }}>
          <div style={{ ...cardStyle, width: "100%", maxWidth: "520px", overflow: "hidden" }} className="animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: "1px solid var(--card-border)", background: "var(--sidebar-toggle-bg)" }}>
              <h2 className="font-extrabold text-sm flex items-center gap-2" style={{ color: "var(--foreground-color)" }}>
                <PlusCircle className="h-4 w-4" style={{ color: "var(--primary)" }} />
                Create New Task
              </h2>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 rounded-lg transition-all hover:opacity-80"
                style={{ color: "var(--sidebar-text-muted)" }}
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleCreateTask} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>
                  Task Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Schedule LinkedIn followup posts"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", borderRadius: "8px", color: "var(--foreground-color)", outline: "none" }}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>
                  Description
                </label>
                <textarea
                  placeholder="Detail the objectives and criteria of the task..."
                  rows={3}
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", borderRadius: "8px", color: "var(--foreground-color)", outline: "none", resize: "none" }}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Priority</label>
                  <select
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value as Task["priority"])}
                    style={{ width: "100%", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", borderRadius: "8px", color: "var(--foreground-color)", outline: "none" }}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Initial Status</label>
                  <select
                    value={newStatus}
                    onChange={(e) => setNewStatus(e.target.value as Task["status"])}
                    style={{ width: "100%", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", borderRadius: "8px", color: "var(--foreground-color)", outline: "none" }}
                  >
                    <option value="todo">To Do</option>
                    <option value="in_progress">In Progress</option>
                    <option value="review">In Review</option>
                    <option value="blocked">Blocked</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Due Date</label>
                  <input
                    type="date"
                    value={newDueDate}
                    onChange={(e) => setNewDueDate(e.target.value)}
                    style={{ width: "100%", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", borderRadius: "8px", color: "var(--foreground-color)", outline: "none" }}
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--sidebar-text-muted)" }}>Assign To</label>
                  <select
                    value={newAssignee}
                    onChange={(e) => setNewAssignee(e.target.value)}
                    style={{ width: "100%", padding: "8px 12px", fontSize: "13px", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)", borderRadius: "8px", color: "var(--foreground-color)", outline: "none" }}
                  >
                    <option value="">Unassigned</option>
                    {teamMembers.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Form Actions */}
              <div className="flex items-center justify-end gap-2 pt-4 mt-2" style={{ borderTop: "1px solid var(--card-border)" }}>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-xs font-bold transition-all hover:opacity-80"
                  style={{ color: "var(--sidebar-text-muted)", background: "var(--sidebar-toggle-bg)", border: "1px solid var(--card-border)" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !newTitle.trim()}
                  className="px-4 py-2 rounded-lg text-white text-xs font-bold transition-all shadow-md flex items-center gap-1.5 disabled:opacity-50"
                  style={{ background: "var(--primary)" }}
                >
                  {submitting ? "Creating..." : "Create Task"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
