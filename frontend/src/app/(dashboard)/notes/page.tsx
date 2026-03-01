"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Loader2, FileText } from "lucide-react";
import type { JSONContent } from "@tiptap/core";
import { notesService, type Note, type NoteSummary, type NoteBlock, type FolderTreeItem } from "@/lib/api/notes";
import { NoteEditor, NotesSidebar, NotesRightPanel } from "@/components/notes";

export default function NotesPage() {
  const router = useRouter();

  const [notes, setNotes] = useState<NoteSummary[]>([]);
  const [folders, setFolders] = useState<FolderTreeItem[]>([]);
  const [activeNote, setActiveNote] = useState<Note | null>(null);
  const [activeNoteId, setActiveNoteId] = useState<string | null>(null);
  const [isLoadingNotes, setIsLoadingNotes] = useState(true);
  const [isLoadingNote, setIsLoadingNote] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [showRightPanel] = useState(true);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);

  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pendingContentRef = useRef<{ title: string; content: NoteBlock[] } | null>(null);

  useEffect(() => {
    loadNotesAndFolders();
  }, []);

  useEffect(() => {
    if (activeNoteId) {
      loadNote(activeNoteId);
    } else {
      setActiveNote(null);
    }
  }, [activeNoteId]);

  const loadNotesAndFolders = async () => {
    try {
      setIsLoadingNotes(true);
      const [notesRes, foldersRes] = await Promise.all([
        notesService.listNotes({ limit: 100 }),
        notesService.getFolderTree(),
      ]);
      setNotes(notesRes?.notes || []);
      setFolders(foldersRes || []);

      if (notesRes?.notes?.length > 0 && !activeNoteId) {
        setActiveNoteId(notesRes.notes[0].id);
      }
    } catch (error) {
      console.error("Failed to load notes:", error);
      setNotes([]);
      setFolders([]);
    } finally {
      setIsLoadingNotes(false);
    }
  };

  const loadNote = async (noteId: string) => {
    try {
      setIsLoadingNote(true);
      const note = await notesService.getNote(noteId);
      setActiveNote(note);
    } catch (error) {
      console.error("Failed to load note:", error);
    } finally {
      setIsLoadingNote(false);
    }
  };

  const saveNote = useCallback(async (title: string, content: NoteBlock[]) => {
    if (!activeNoteId) return;

    try {
      setIsSaving(true);
      await notesService.updateNote(activeNoteId, { title, content });
      setLastSavedAt(new Date());

      setNotes((prev) =>
        prev.map((n) =>
          n.id === activeNoteId
            ? { ...n, title, updated_at: new Date().toISOString() }
            : n,
        ),
      );
    } catch (error) {
      console.error("Failed to save note:", error);
    } finally {
      setIsSaving(false);
    }
  }, [activeNoteId]);

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTitle = e.target.value;
    if (!activeNote) return;

    setActiveNote({ ...activeNote, title: newTitle });

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    pendingContentRef.current = { title: newTitle, content: activeNote.content };
    saveTimeoutRef.current = setTimeout(() => {
      if (pendingContentRef.current) {
        saveNote(pendingContentRef.current.title, pendingContentRef.current.content);
      }
    }, 1000);
  };

  const handleContentChange = (content: JSONContent[], plainText: string) => {
    if (!activeNote) return;

    const noteContent = content as unknown as NoteBlock[];
    setActiveNote({ ...activeNote, content: noteContent });

    const conceptMatches = plainText.match(/\[\[([^\]]+)\]\]/g) || [];
    const concepts = conceptMatches.map((m) => m.slice(2, -2).toLowerCase());
    if (JSON.stringify(concepts) !== JSON.stringify(activeNote.linked_concepts)) {
      setActiveNote((prev) => (prev ? { ...prev, linked_concepts: concepts } : null));
    }

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    pendingContentRef.current = { title: activeNote.title, content: noteContent };
    saveTimeoutRef.current = setTimeout(() => {
      if (pendingContentRef.current) {
        saveNote(pendingContentRef.current.title, pendingContentRef.current.content);
      }
    }, 1000);
  };

  const handleCreateNote = async (folderId?: string) => {
    try {
      const note = await notesService.createNote("Untitled", [], folderId);
      setNotes((prev) => [
        {
          id: note.id,
          folder_id: note.folder_id,
          title: note.title,
          preview: null,
          word_count: 0,
          is_pinned: false,
          is_archived: false,
          updated_at: note.updated_at,
        },
        ...prev,
      ]);
      setActiveNoteId(note.id);
    } catch (error) {
      console.error("Failed to create note:", error);
    }
  };

  const handleCreateFolder = async (name: string, parentId?: string) => {
    try {
      await notesService.createFolder(name, parentId);
      const newFolders = await notesService.getFolderTree();
      setFolders(newFolders);
    } catch (error) {
      console.error("Failed to create folder:", error);
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    try {
      await notesService.deleteNote(noteId);
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
      if (activeNoteId === noteId) {
        const remaining = notes.filter((n) => n.id !== noteId);
        setActiveNoteId(remaining.length > 0 ? remaining[0].id : null);
      }
    } catch (error) {
      console.error("Failed to delete note:", error);
    }
  };

  const handleDeleteFolder = async (folderId: string) => {
    try {
      await notesService.deleteFolder(folderId, false);
      const newFolders = await notesService.getFolderTree();
      setFolders(newFolders);
    } catch (error) {
      console.error("Failed to delete folder:", error);
    }
  };

  const handlePinNote = async (noteId: string, isPinned: boolean) => {
    try {
      await notesService.updateNote(noteId, { isPinned });
      setNotes((prev) => prev.map((n) => (n.id === noteId ? { ...n, is_pinned: isPinned } : n)));
    } catch (error) {
      console.error("Failed to pin note:", error);
    }
  };

  const handleArchiveNote = async (noteId: string, isArchived: boolean) => {
    try {
      await notesService.updateNote(noteId, { isArchived });
      if (isArchived) {
        setNotes((prev) => prev.filter((n) => n.id !== noteId));
        if (activeNoteId === noteId) {
          const remaining = notes.filter((n) => n.id !== noteId);
          setActiveNoteId(remaining.length > 0 ? remaining[0].id : null);
        }
      }
    } catch (error) {
      console.error("Failed to archive note:", error);
    }
  };

  const handleConceptClick = (concept: string) => {
    router.push(`/graph?concept=${encodeURIComponent(concept)}`);
  };

  const handleAddAsInsight = async () => {
    if (!activeNoteId || !activeNote) return;

    try {
      setIsExtracting(true);
      const result = await notesService.extractKnowledge(activeNoteId, true);

      if ("task_id" in result) {
        console.log("Knowledge extraction dispatched:", result);
        alert(`✓ Knowledge extraction started. Task ID: ${result.task_id.slice(0, 8)}...`);
      } else {
        console.log("Knowledge extraction completed:", result);
        alert(`✓ Extracted ${result.text_chunks} chunks and ${result.concepts.length} concepts.`);
      }
    } catch (error) {
      console.error("Knowledge extraction failed:", error);
      alert(`✗ Failed to extract knowledge: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsExtracting(false);
    }
  };

  const extractHeadings = (content: NoteBlock[]): { level: number; text: string }[] => {
    const headings: { level: number; text: string }[] = [];
    const traverse = (blocks: NoteBlock[]) => {
      for (const block of blocks) {
        if (block.type === "heading" && block.attrs && typeof block.attrs.level === "number") {
          const text = typeof block.content === "string"
            ? block.content
            : Array.isArray(block.content)
              ? (block.content as unknown as { text?: string }[]).map((c) => c.text || "").join("")
              : "";
          headings.push({ level: block.attrs.level as number, text });
        }
      }
    };
    traverse(content);
    return headings;
  };

  return (
    <div className="flex h-[calc(100vh-var(--topbar-height)-76px)] md:h-[calc(100vh-var(--topbar-height))] -mx-4 md:-mx-7 xl:-mx-9 -mb-24 md:-mb-8">
      <NotesSidebar
        notes={notes}
        folders={folders}
        activeNoteId={activeNoteId}
        isCollapsed={isSidebarCollapsed}
        isLoading={isLoadingNotes}
        onSelectNote={setActiveNoteId}
        onCreateNote={handleCreateNote}
        onCreateFolder={handleCreateFolder}
        onDeleteNote={handleDeleteNote}
        onDeleteFolder={handleDeleteFolder}
        onPinNote={handlePinNote}
        onArchiveNote={handleArchiveNote}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
      />

      <main className="flex-1 flex flex-col overflow-hidden bg-surface/35">
        {activeNote ? (
          <>
            <div className="px-4 pt-4 pb-2 border-b border-border bg-surface/55">
              <input
                type="text"
                value={activeNote.title}
                onChange={handleTitleChange}
                placeholder="Untitled"
                className="w-full bg-transparent text-[28px] font-semibold text-primary outline-none placeholder:text-secondary"
                style={{ fontFamily: "var(--font-display)" }}
              />
              <div className="flex items-center gap-2 mt-2 text-[12px] text-secondary">
                {isSaving ? (
                  <span className="flex items-center gap-1">
                    <Loader2 className="h-3 w-3 animate-spin" /> Saving...
                  </span>
                ) : lastSavedAt ? (
                  <span>Saved at {lastSavedAt.toLocaleTimeString()}</span>
                ) : null}
                <span>•</span>
                <span>{activeNote.word_count} words</span>
              </div>
            </div>

            {isLoadingNote ? (
              <div className="flex-1 flex items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-secondary" />
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto thin-scrollbar">
                <NoteEditor
                  key={activeNote.id}
                  initialContent={activeNote.content}
                  onChange={handleContentChange}
                  placeholder="Start writing... Use [[concept]] to link concepts"
                />
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
            <div className="w-16 h-16 rounded-full bg-[var(--accent-soft)] border border-accent/30 flex items-center justify-center mb-6">
              <FileText className="w-8 h-8 text-[var(--accent)]" strokeWidth={1.5} />
            </div>
            <h2 className="text-[24px] font-semibold text-primary mb-2" style={{ fontFamily: "var(--font-display)" }}>
              {isLoadingNotes ? "Loading notes..." : "No notes yet"}
            </h2>
            <p className="text-[13px] text-secondary max-w-md mb-6">
              Create notes with rich formatting, tables, code blocks, and mermaid diagrams. Link concepts using [[concept]] syntax.
            </p>
            {!isLoadingNotes && (
              <button
                onClick={() => handleCreateNote()}
                className="h-10 px-6 border border-accent/35 bg-[var(--accent-soft)] hover:bg-[var(--hover-bg)] text-[var(--accent)] rounded-md text-[13px] font-medium transition-colors"
              >
                Create your first note
              </button>
            )}
          </div>
        )}
      </main>

      {activeNote && showRightPanel && (
        <NotesRightPanel
          linkedConcepts={activeNote.linked_concepts}
          headings={extractHeadings(activeNote.content)}
          onConceptClick={handleConceptClick}
          onAddAsInsight={handleAddAsInsight}
          isExtractingConcepts={isExtracting}
        />
      )}
    </div>
  );
}
