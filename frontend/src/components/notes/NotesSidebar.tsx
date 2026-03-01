"use client";

import { useState, useMemo } from "react";
import {
  ChevronDown,
  ChevronRight,
  FolderClosed,
  FolderOpen,
  FileText,
  Plus,
  Search,
  MoreHorizontal,
  Pin,
  Archive,
  Trash2,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import type { NoteSummary, FolderTreeItem } from "@/lib/api/notes";

interface NotesSidebarProps {
  notes: NoteSummary[];
  folders: FolderTreeItem[];
  activeNoteId: string | null;
  isCollapsed: boolean;
  isLoading?: boolean;
  onSelectNote: (noteId: string) => void;
  onCreateNote: (folderId?: string) => void;
  onCreateFolder: (name: string, parentId?: string) => void;
  onDeleteNote: (noteId: string) => void;
  onDeleteFolder: (folderId: string) => void;
  onPinNote: (noteId: string, isPinned: boolean) => void;
  onArchiveNote: (noteId: string, isArchived: boolean) => void;
  onToggleCollapse: () => void;
  onSearch?: (query: string) => void;
}

export function NotesSidebar({
  notes,
  folders,
  activeNoteId,
  isCollapsed,
  isLoading = false,
  onSelectNote,
  onCreateNote,
  onCreateFolder,
  onDeleteNote,
  onDeleteFolder,
  onPinNote,
  onArchiveNote,
  onToggleCollapse,
  onSearch,
}: NotesSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [showNewFolderInput, setShowNewFolderInput] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [contextMenuNote, setContextMenuNote] = useState<string | null>(null);

  const filteredNotes = useMemo(() => {
    if (!searchQuery.trim()) return notes;
    const query = searchQuery.toLowerCase();
    return notes.filter(
      (note) =>
        note.title.toLowerCase().includes(query) ||
        note.preview?.toLowerCase().includes(query),
    );
  }, [notes, searchQuery]);

  const notesByFolder = useMemo(() => {
    const grouped: Record<string, NoteSummary[]> = { unfiled: [] };
    filteredNotes.forEach((note) => {
      const folderId = note.folder_id || "unfiled";
      if (!grouped[folderId]) grouped[folderId] = [];
      grouped[folderId].push(note);
    });
    return grouped;
  }, [filteredNotes]);

  const toggleFolder = (folderId: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) next.delete(folderId);
      else next.add(folderId);
      return next;
    });
  };

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    onSearch?.(query);
  };

  const handleCreateFolder = () => {
    if (newFolderName.trim()) {
      onCreateFolder(newFolderName.trim());
      setNewFolderName("");
      setShowNewFolderInput(false);
    }
  };

  if (isCollapsed) {
    return (
      <div className="w-12 shrink-0 border-r border-border bg-surface/60 flex flex-col items-center py-3 gap-2">
        <button
          onClick={onToggleCollapse}
          className="h-8 w-8 rounded-md flex items-center justify-center hover:bg-[var(--hover-bg)] text-secondary hover:text-primary"
          title="Expand sidebar"
        >
          <PanelLeft className="h-4 w-4" />
        </button>
        <div className="w-6 border-t border-border my-2" />
        <button
          onClick={() => onCreateNote()}
          className="h-8 w-8 rounded-md flex items-center justify-center border border-accent/35 bg-[var(--accent-soft)] text-[var(--accent)]"
          title="New note"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <aside className="w-64 shrink-0 border-r border-border bg-surface/60 flex flex-col overflow-hidden">
      <div className="p-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleCollapse}
            className="h-7 w-7 rounded-md flex items-center justify-center hover:bg-[var(--hover-bg)] text-secondary hover:text-primary"
            title="Collapse sidebar"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
          <span className="text-[13px] font-medium text-primary">Notes</span>
        </div>
        <button
          onClick={() => onCreateNote()}
          className="h-7 px-2 rounded-md flex items-center gap-1.5 border border-accent/35 bg-[var(--accent-soft)] text-[var(--accent)] text-[12px]"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>New</span>
        </button>
      </div>

      <div className="p-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-secondary" />
          <input
            type="text"
            placeholder="Search notes..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="w-full h-8 pl-8 pr-3 rounded-md bg-surface border border-border text-[12px] text-primary placeholder:text-secondary focus:outline-none focus:ring-1 focus:ring-accent/35"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto thin-scrollbar px-2 pb-2">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-[12px] text-secondary">Loading...</div>
          </div>
        ) : (
          <>
            <div className="mb-4">
              <div className="flex items-center justify-between px-1 py-1.5">
                <span className="text-[11px] uppercase tracking-wider text-tertiary font-medium">Folders</span>
                <button
                  onClick={() => setShowNewFolderInput(true)}
                  className="h-5 w-5 rounded flex items-center justify-center hover:bg-[var(--hover-bg)] text-tertiary hover:text-primary"
                >
                  <Plus className="h-3 w-3" />
                </button>
              </div>

              {showNewFolderInput && (
                <div className="mb-2 flex items-center gap-1">
                  <input
                    type="text"
                    placeholder="Folder name"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleCreateFolder();
                      if (e.key === "Escape") setShowNewFolderInput(false);
                    }}
                    autoFocus
                    className="flex-1 h-7 px-2 rounded bg-surface border border-border text-[12px] text-primary placeholder:text-secondary focus:outline-none focus:ring-1 focus:ring-accent/35"
                  />
                  <button
                    onClick={handleCreateFolder}
                    className="h-7 px-2 rounded border border-accent/35 bg-[var(--accent-soft)] text-[var(--accent)] text-[11px]"
                  >
                    Add
                  </button>
                </div>
              )}

              {(folders || []).map((folder) => (
                <FolderItem
                  key={folder.id}
                  folder={folder}
                  notes={notesByFolder[folder.id] || []}
                  activeNoteId={activeNoteId}
                  isExpanded={expandedFolders.has(folder.id)}
                  onToggle={() => toggleFolder(folder.id)}
                  onSelectNote={onSelectNote}
                  onCreateNote={onCreateNote}
                  onDeleteFolder={onDeleteFolder}
                />
              ))}
            </div>

            <div>
              <div className="px-1 py-1.5">
                <span className="text-[11px] uppercase tracking-wider text-tertiary font-medium">All Notes</span>
              </div>
              <div className="space-y-0.5">
                {(notesByFolder.unfiled || []).map((note) => (
                  <NoteItem
                    key={note.id}
                    note={note}
                    isActive={note.id === activeNoteId}
                    showContextMenu={contextMenuNote === note.id}
                    onSelect={() => onSelectNote(note.id)}
                    onContextMenu={() => setContextMenuNote(note.id)}
                    onCloseContextMenu={() => setContextMenuNote(null)}
                    onPin={() => onPinNote(note.id, !note.is_pinned)}
                    onArchive={() => onArchiveNote(note.id, !note.is_archived)}
                    onDelete={() => onDeleteNote(note.id)}
                  />
                ))}
              </div>
            </div>

            {filteredNotes.length === 0 && (
              <div className="flex flex-col items-center justify-center h-32 text-center">
                <FileText className="h-8 w-8 text-tertiary mb-2" />
                <p className="text-[12px] text-secondary">{searchQuery ? "No notes found" : "No notes yet"}</p>
                {!searchQuery && (
                  <button onClick={() => onCreateNote()} className="mt-2 text-[12px] text-[var(--accent)] hover:underline">
                    Create your first note
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

function FolderItem({
  folder,
  notes,
  activeNoteId,
  isExpanded,
  onToggle,
  onSelectNote,
  onCreateNote,
  onDeleteFolder,
}: {
  folder: FolderTreeItem;
  notes: NoteSummary[];
  activeNoteId: string | null;
  isExpanded: boolean;
  onToggle: () => void;
  onSelectNote: (noteId: string) => void;
  onCreateNote: (folderId: string) => void;
  onDeleteFolder: (folderId: string) => void;
}) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="mb-1">
      <div className="group flex items-center gap-1 px-1 py-1.5 rounded-md hover:bg-[var(--hover-bg)] cursor-pointer" onClick={onToggle}>
        <button className="h-4 w-4 flex items-center justify-center text-secondary">
          {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        </button>
        {isExpanded ? <FolderOpen className="h-4 w-4 text-[var(--accent)]" /> : <FolderClosed className="h-4 w-4 text-[var(--accent)]" />}
        <span className="flex-1 text-[13px] text-primary truncate">{folder.name}</span>
        <span className="text-[11px] text-tertiary">{notes.length}</span>
        <div className="relative opacity-0 group-hover:opacity-100">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowMenu(!showMenu);
            }}
            className="h-5 w-5 rounded flex items-center justify-center hover:bg-[var(--hover-bg)] text-tertiary"
          >
            <MoreHorizontal className="h-3 w-3" />
          </button>
          {showMenu && (
            <div className="absolute right-0 top-full mt-1 z-50 w-32 rounded-md py-1 shadow-lg overlay-menu">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onCreateNote(folder.id);
                  setShowMenu(false);
                }}
                className="w-full px-3 py-1.5 text-left text-[12px] text-secondary hover:bg-[var(--hover-bg)]"
              >
                New note here
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteFolder(folder.id);
                  setShowMenu(false);
                }}
                className="w-full px-3 py-1.5 text-left text-[12px] text-danger hover:bg-danger/10"
              >
                Delete folder
              </button>
            </div>
          )}
        </div>
      </div>

      {isExpanded && notes.length > 0 && (
        <div className="ml-4 mt-0.5 space-y-0.5">
          {notes.map((note) => (
            <NoteItem key={note.id} note={note} isActive={note.id === activeNoteId} onSelect={() => onSelectNote(note.id)} compact />
          ))}
        </div>
      )}
    </div>
  );
}

function NoteItem({
  note,
  isActive,
  compact = false,
  showContextMenu = false,
  onSelect,
  onContextMenu,
  onCloseContextMenu,
  onPin,
  onArchive,
  onDelete,
}: {
  note: NoteSummary;
  isActive: boolean;
  compact?: boolean;
  showContextMenu?: boolean;
  onSelect: () => void;
  onContextMenu?: () => void;
  onCloseContextMenu?: () => void;
  onPin?: () => void;
  onArchive?: () => void;
  onDelete?: () => void;
}) {
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  return (
    <div className="relative">
      <button
        onClick={onSelect}
        onContextMenu={(e) => {
          e.preventDefault();
          onContextMenu?.();
        }}
        className={`
          w-full text-left px-2 py-1.5 rounded-md transition-colors group border
          ${isActive ? "bg-[var(--accent-soft)] border-accent/30" : "hover:bg-[var(--hover-bg)] border-transparent"}
        `}
      >
        <div className="flex items-center gap-2">
          {note.is_pinned && <Pin className="h-3 w-3 text-[var(--accent)] shrink-0" />}
          <span className={`flex-1 truncate text-[13px] ${isActive ? "text-[var(--accent)]" : "text-primary"}`}>{note.title || "Untitled"}</span>
          {!compact && onContextMenu && (
            <div
              onClick={(e) => {
                e.stopPropagation();
                onContextMenu();
              }}
              className="opacity-0 group-hover:opacity-100 h-5 w-5 rounded flex items-center justify-center hover:bg-[var(--hover-bg)] text-tertiary cursor-pointer"
            >
              <MoreHorizontal className="h-3 w-3" />
            </div>
          )}
        </div>
        {!compact && (
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[11px] text-secondary">{formatDate(note.updated_at)}</span>
            {note.preview && <span className="text-[11px] text-tertiary truncate">{note.preview.slice(0, 40)}</span>}
          </div>
        )}
      </button>

      {showContextMenu && onDelete && (
        <>
          <div className="fixed inset-0 z-40" onClick={onCloseContextMenu} />
          <div className="absolute right-0 top-full mt-1 z-50 w-36 rounded-md py-1 shadow-lg overlay-menu">
            {onPin && (
              <button
                onClick={() => {
                  onPin();
                  onCloseContextMenu?.();
                }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-[12px] text-secondary hover:bg-[var(--hover-bg)]"
              >
                <Pin className="h-3 w-3" />
                {note.is_pinned ? "Unpin" : "Pin"}
              </button>
            )}
            {onArchive && (
              <button
                onClick={() => {
                  onArchive();
                  onCloseContextMenu?.();
                }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-[12px] text-secondary hover:bg-[var(--hover-bg)]"
              >
                <Archive className="h-3 w-3" />
                {note.is_archived ? "Unarchive" : "Archive"}
              </button>
            )}
            <button
              onClick={() => {
                onDelete();
                onCloseContextMenu?.();
              }}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-[12px] text-danger hover:bg-danger/10"
            >
              <Trash2 className="h-3 w-3" />
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
}
