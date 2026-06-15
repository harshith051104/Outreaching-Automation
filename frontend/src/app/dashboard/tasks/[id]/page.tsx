"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getTask,
  updateTask,
  getTaskComments,
  addTaskComment,
  getTeamMembers,
  Task,
  TaskComment,
  UserMin,
} from "@/services/task-api";
import {
  ArrowLeft,
  Calendar,
  User,
  AlertCircle,
  MessageSquare,
  Send,
  Edit2,
  Check,
  X,
  Clock,
  UserCheck,
} from "lucide-react";

const COLUMNS = [
  { id: "todo", label: "To Do", bgClass: "bg-slate-50 text-slate-700 border-slate-200" },
  { id: "in_progress", label: "In Progress", bgClass: "bg-blue-50 text-blue-700 border-blue-200" },
  { id: "review", label: "In Review", bgClass: "bg-amber-50 text-amber-700 border-amber-200" },
  { id: "blocked", label: "Blocked", bgClass: "bg-red-50 text-red-700 border-red-200" },
  { id: "completed", label: "Completed", bgClass: "bg-emerald-50 text-emerald-700 border-emerald-200" },
];

const PRIORITY_THEMES = {
  low: "bg-slate-100 text-slate-700 border-slate-200",
  medium: "bg-blue-50 text-blue-700 border-blue-100",
  high: "bg-orange-50 text-orange-700 border-orange-100",
  critical: "bg-red-50 text-red-700 border-red-100 animate-pulse border",
};

export default function TaskDetailsPage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();
  
  const [task, setTask] = useState<Task | null>(null);
  const [comments, setComments] = useState<TaskComment[]>([]);
  const [teamMembers, setTeamMembers] = useState<UserMin[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [commentText, setCommentText] = useState("");
  const [sendingComment, setSendingComment] = useState(false);
  
  // Edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editPriority, setEditPriority] = useState<Task["priority"]>("medium");
  const [editStatus, setEditStatus] = useState<Task["status"]>("todo");
  const [editDueDate, setEditDueDate] = useState("");
  const [editAssignee, setEditAssignee] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (id) {
      loadTaskData();
    }
  }, [id]);

  const loadTaskData = async () => {
    try {
      setLoading(true);
      const [taskData, commentsData, teamData] = await Promise.all([
        getTask(id),
        getTaskComments(id).catch(() => []),
        getTeamMembers().catch(() => []),
      ]);
      
      setTask(taskData);
      setComments(commentsData);
      setTeamMembers(teamData);
      
      // Initialize edit fields
      setEditTitle(taskData.title);
      setEditDescription(taskData.description || "");
      setEditPriority(taskData.priority);
      setEditStatus(taskData.status);
      setEditDueDate(taskData.due_date || "");
      setEditAssignee(taskData.assigned_to || "");
    } catch (err) {
      console.error("Failed to load task details:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveEdits = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTitle.trim()) return;

    try {
      setSaving(true);
      const updated = await updateTask(id, {
        title: editTitle,
        description: editDescription,
        status: editStatus,
        priority: editPriority,
        due_date: editDueDate || null,
        assigned_to: editAssignee || null,
      });
      setTask(updated);
      setIsEditing(false);
      
      // Reload comments to catch any automated edit remarks
      const freshComments = await getTaskComments(id).catch(() => []);
      setComments(freshComments);
    } catch (err) {
      console.error("Failed to save task updates:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;

    try {
      setSendingComment(true);
      const newComment = await addTaskComment(id, commentText);
      setComments([...comments, newComment]);
      setCommentText("");
    } catch (err) {
      console.error("Failed to add comment:", err);
    } finally {
      setSendingComment(false);
    }
  };

  const isOverdue = () => {
    if (!task || !task.due_date || task.status === "completed") return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const due = new Date(task.due_date);
    return due < today;
  };

  if (loading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <div className="text-center space-y-4">
          <div className="h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-gray-500 font-medium">Retrieving task details...</p>
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center space-y-4">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto" />
        <h2 className="text-lg font-bold text-slate-900">Task Not Found</h2>
        <p className="text-sm text-slate-500">
          The task you are looking for does not exist or has been deleted.
        </p>
        <Link
          href="/dashboard/tasks"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-xs font-bold text-white transition-all shadow-md"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Tasks
        </Link>
      </div>
    );
  }

  const currentColumn = COLUMNS.find((c) => c.id === task.status) || COLUMNS[0];
  const priorityBadgeClass = PRIORITY_THEMES[task.priority] || PRIORITY_THEMES.medium;
  const overdue = isOverdue();

  return (
    <div className="max-w-6xl mx-auto space-y-6 p-4">
      {/* Top Navigation */}
      <div>
        <Link
          href="/dashboard/tasks"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Tasks Board
        </Link>
      </div>

      {/* Main Task View Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Details / Editing and Comments */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm space-y-6">
            {isEditing ? (
              /* Edit Form Layout */
              <form onSubmit={handleSaveEdits} className="space-y-4">
                <div className="flex justify-between items-center border-b pb-3 mb-2">
                  <h3 className="font-extrabold text-slate-900 text-sm">Edit Task Details</h3>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setIsEditing(false)}
                      className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 transition-all"
                      title="Cancel changes"
                    >
                      <X className="h-4 w-4" />
                    </button>
                    <button
                      type="submit"
                      disabled={saving || !editTitle.trim()}
                      className="p-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-emerald-300 transition-all"
                      title="Save changes"
                    >
                      {saving ? (
                        <span className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin block" />
                      ) : (
                        <Check className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Title
                  </label>
                  <input
                    type="text"
                    required
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="w-full px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all text-slate-950 font-semibold"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Description
                  </label>
                  <textarea
                    rows={6}
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    className="w-full px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all text-slate-950 leading-relaxed"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                      Status
                    </label>
                    <select
                      value={editStatus}
                      onChange={(e) => setEditStatus(e.target.value as Task["status"])}
                      className="w-full px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-950 font-medium"
                    >
                      <option value="todo">To Do</option>
                      <option value="in_progress">In Progress</option>
                      <option value="review">In Review</option>
                      <option value="blocked">Blocked</option>
                      <option value="completed">Completed</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                      Priority
                    </label>
                    <select
                      value={editPriority}
                      onChange={(e) => setEditPriority(e.target.value as Task["priority"])}
                      className="w-full px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-950 font-medium"
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                      Due Date
                    </label>
                    <input
                      type="date"
                      value={editDueDate}
                      onChange={(e) => setEditDueDate(e.target.value)}
                      className="w-full px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-950 font-medium"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                      Assign To
                    </label>
                    <select
                      value={editAssignee}
                      onChange={(e) => setEditAssignee(e.target.value)}
                      className="w-full px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-950 font-medium"
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
              </form>
            ) : (
              /* View Mode */
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <h1 className="text-xl font-extrabold text-slate-900 tracking-tight leading-snug">
                    {task.title}
                  </h1>
                  <button
                    onClick={() => setIsEditing(true)}
                    className="flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors py-1.5 px-3 bg-blue-50 border border-blue-100 hover:bg-blue-100 rounded-lg"
                  >
                    <Edit2 className="h-3.5 w-3.5" /> Edit
                  </button>
                </div>

                <div className="border-t border-slate-100 pt-4">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                    Description
                  </h3>
                  {task.description ? (
                    <p className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">
                      {task.description}
                    </p>
                  ) : (
                    <p className="text-xs text-slate-400 italic">No description provided.</p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Discussion Thread */}
          <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm space-y-6">
            <h2 className="font-extrabold text-slate-900 text-sm border-b pb-3 flex items-center gap-2">
              <MessageSquare className="h-4.5 w-4.5 text-indigo-500" />
              Comments & Discussion ({comments.length})
            </h2>

            {/* List of comments */}
            <div className="space-y-4 max-h-[360px] overflow-y-auto pr-1">
              {comments.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  No comments yet. Start the conversation!
                </div>
              ) : (
                comments.map((comment) => (
                  <div key={comment.id} className="flex items-start gap-3 text-xs">
                    <div className="h-8 w-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-600 shrink-0">
                      {comment.author_info?.name?.charAt(0)?.toUpperCase() || "U"}
                    </div>
                    <div className="flex-1 bg-slate-50 border border-slate-100 p-3 rounded-xl space-y-1">
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-slate-800">
                          {comment.author_info?.name || "System Message"}
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {new Date(comment.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
                        {comment.message}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Add Comment Input */}
            <form onSubmit={handleAddComment} className="flex gap-2 pt-2">
              <input
                type="text"
                placeholder="Write a comment..."
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                className="flex-1 px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all text-slate-950"
              />
              <button
                type="submit"
                disabled={sendingComment || !commentText.trim()}
                className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-300 transition-colors flex items-center justify-center shrink-0"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Metadata Sidebar */}
        <div className="space-y-6">
          <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm space-y-5">
            <h2 className="font-extrabold text-slate-900 text-sm border-b pb-3">Task Details</h2>

            {/* Status */}
            <div className="space-y-1.5">
              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Status
              </span>
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold border ${currentColumn.bgClass}`}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
                {currentColumn.label}
              </span>
            </div>

            {/* Priority */}
            <div className="space-y-1.5">
              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Priority
              </span>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider border ${priorityBadgeClass}`}
              >
                {task.priority}
              </span>
            </div>

            {/* Assignee */}
            <div className="space-y-1.5">
              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Assignee
              </span>
              {task.assignee_info ? (
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded-full bg-indigo-50 border border-indigo-200 flex items-center justify-center text-[10px] font-bold text-indigo-600 shrink-0">
                    {task.assignee_info.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-800">{task.assignee_info.name}</div>
                    <div className="text-[10px] text-slate-400 truncate max-w-[150px]">
                      {task.assignee_info.email}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 text-xs text-slate-400 font-medium">
                  <User className="h-4 w-4" /> Unassigned
                </div>
              )}
            </div>

            {/* Due Date */}
            <div className="space-y-1.5">
              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Due Date
              </span>
              {task.due_date ? (
                <div
                  className={`flex items-center gap-1.5 text-xs font-semibold ${
                    overdue ? "text-red-600" : "text-slate-700"
                  }`}
                >
                  {overdue ? <AlertCircle className="h-4 w-4" /> : <Calendar className="h-4 w-4" />}
                  <span>
                    {new Date(task.due_date).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </span>
                  {overdue && (
                    <span className="text-[9px] font-black uppercase text-red-600 bg-red-50 border border-red-100 px-1 rounded">
                      Overdue
                    </span>
                  )}
                </div>
              ) : (
                <div className="text-xs text-slate-400 italic font-medium">No due date set</div>
              )}
            </div>

            {/* Creator */}
            <div className="border-t border-slate-100 pt-4 space-y-3">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400 font-medium flex items-center gap-1">
                  <UserCheck className="h-3.5 w-3.5" /> Created by
                </span>
                <span className="font-bold text-slate-800">
                  {task.creator_info?.name || "System Admin"}
                </span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400 font-medium flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" /> Created on
                </span>
                <span className="text-slate-600">
                  {new Date(task.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
              </div>

              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400 font-medium flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" /> Last updated
                </span>
                <span className="text-slate-600">
                  {new Date(task.updated_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
