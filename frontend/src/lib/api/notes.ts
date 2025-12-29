"use client";

import { api } from "./client";

// =============================================================================
// TYPES
// =============================================================================

export interface NoteBlock {
    type: string;
    content?: unknown;
    attrs?: Record<string, unknown>;
}

export interface Note {
    id: string;
    user_id: string;
    folder_id: string | null;
    title: string;
    content: NoteBlock[];
    linked_concepts: string[];
    word_count: number;
    is_pinned: boolean;
    is_archived: boolean;
    last_extracted_at: string | null;
    created_at: string;
    updated_at: string;
}

export interface NoteSummary {
    id: string;
    folder_id: string | null;
    title: string;
    preview: string | null;
    word_count: number;
    is_pinned: boolean;
    is_archived: boolean;
    updated_at: string;
}

export interface Folder {
    id: string;
    name: string;
    parent_id: string | null;
    created_at: string;
    updated_at: string;
}

export interface FolderTreeItem {
    id: string;
    name: string;
    parent_id: string | null;
    children: FolderTreeItem[];
}

export interface NoteStats {
    total_notes: number;
    active_notes: number;
    archived_notes: number;
    total_words: number;
    folders: number;
}

export interface ImageUploadResult {
    url: string;
    key: string;
    size_bytes: number;
    original_filename: string;
}

export interface KnowledgeExtractionResult {
    note_id: string;
    text_chunks: number;
    artifacts: number;
    concepts: string[];
    processing_time_ms: number;
    breakdown: Record<string, number>;
}

export interface KnowledgeExtractionDispatch {
    status: "dispatched";
    task_id: string;
    note_id: string;
    message: string;
}

// =============================================================================
// NOTES SERVICE
// =============================================================================

class NotesService {
    // =========================================================================
    // NOTE OPERATIONS
    // =========================================================================

    /**
     * Create a new note
     */
    async createNote(
        title: string = "Untitled",
        content: NoteBlock[] = [],
        folderId?: string
    ): Promise<Note> {
        const { data } = await api.post<Note>("/notes", {
            title,
            content,
            folder_id: folderId,
        });
        return data;
    }

    /**
     * Get a note by ID
     */
    async getNote(noteId: string): Promise<Note> {
        const { data } = await api.get<Note>(`/notes/${noteId}`);
        return data;
    }

    /**
     * List notes for the current user
     */
    async listNotes(params?: {
        folderId?: string;
        includeArchived?: boolean;
        pinnedFirst?: boolean;
        limit?: number;
        offset?: number;
    }): Promise<{ notes: NoteSummary[]; total: number }> {
        const searchParams = new URLSearchParams();
        if (params?.folderId !== undefined) searchParams.set("folder_id", params.folderId);
        if (params?.includeArchived) searchParams.set("include_archived", "true");
        if (params?.pinnedFirst === false) searchParams.set("pinned_first", "false");
        if (params?.limit) searchParams.set("limit", String(params.limit));
        if (params?.offset) searchParams.set("offset", String(params.offset));

        const query = searchParams.toString();
        const { data } = await api.get(`/notes${query ? `?${query}` : ""}`);
        return data;
    }

    /**
     * Update a note
     */
    async updateNote(
        noteId: string,
        updates: {
            title?: string;
            content?: NoteBlock[];
            folderId?: string | null;
            isPinned?: boolean;
            isArchived?: boolean;
        }
    ): Promise<Note> {
        const body: Record<string, unknown> = {};
        if (updates.title !== undefined) body.title = updates.title;
        if (updates.content !== undefined) body.content = updates.content;
        if (updates.folderId !== undefined) body.folder_id = updates.folderId === null ? "" : updates.folderId;
        if (updates.isPinned !== undefined) body.is_pinned = updates.isPinned;
        if (updates.isArchived !== undefined) body.is_archived = updates.isArchived;

        const { data } = await api.patch<Note>(`/notes/${noteId}`, body);
        return data;
    }

    /**
     * Delete a note
     */
    async deleteNote(noteId: string): Promise<void> {
        await api.delete(`/notes/${noteId}`);
    }

    /**
     * Search notes by title and content
     */
    async searchNotes(query: string, limit: number = 50): Promise<NoteSummary[]> {
        const { data } = await api.get<{ notes: NoteSummary[] }>(
            `/notes/search?q=${encodeURIComponent(query)}&limit=${limit}`
        );
        return data.notes;
    }

    /**
     * Get recent notes
     */
    async getRecentNotes(limit: number = 10): Promise<NoteSummary[]> {
        const { data } = await api.get<{ notes: NoteSummary[] }>(`/notes/recent?limit=${limit}`);
        return data.notes;
    }

    /**
     * Get notes linked to a concept
     */
    async getNotesByConcept(conceptUri: string, limit: number = 50): Promise<NoteSummary[]> {
        const { data } = await api.get<{ notes: NoteSummary[] }>(
            `/notes/by-concept/${encodeURIComponent(conceptUri)}?limit=${limit}`
        );
        return data.notes;
    }

    /**
     * Get note statistics
     */
    async getStats(): Promise<NoteStats> {
        const { data } = await api.get<NoteStats>("/notes/stats");
        return data;
    }

    /**
     * Extract concepts from a note
     */
    async extractConcepts(noteId: string): Promise<string[]> {
        const { data } = await api.post<{ concepts: string[] }>(`/notes/${noteId}/extract-concepts`);
        return data.concepts;
    }

    /**
     * Extract knowledge from a note (triggers full multimodal ingestion pipeline)
     * @param noteId - The note ID to extract knowledge from
     * @param background - If true, dispatches to Celery worker (recommended for production)
     */
    async extractKnowledge(
        noteId: string,
        background: boolean = true
    ): Promise<KnowledgeExtractionResult | KnowledgeExtractionDispatch> {
        const { data } = await api.post(
            `/notes/${noteId}/extract-knowledge?background=${background}`
        );
        return data;
    }

    // =========================================================================
    // FOLDER OPERATIONS
    // =========================================================================

    /**
     * Create a new folder
     */
    async createFolder(name: string, parentId?: string): Promise<Folder> {
        const { data } = await api.post<Folder>("/notes/folders", {
            name,
            parent_id: parentId,
        });
        return data;
    }

    /**
     * Get a folder by ID
     */
    async getFolder(folderId: string): Promise<Folder> {
        const { data } = await api.get<Folder>(`/notes/folders/${folderId}`);
        return data;
    }

    /**
     * List folders at a specific level
     */
    async listFolders(parentId?: string): Promise<Folder[]> {
        const query = parentId ? `?parent_id=${parentId}` : "";
        const { data } = await api.get<Folder[]>(`/notes/folders${query}`);
        return data || [];
    }

    /**
     * Get complete folder tree hierarchy
     */
    async getFolderTree(): Promise<FolderTreeItem[]> {
        const { data } = await api.get<FolderTreeItem[]>("/notes/folders/tree");
        return data || [];
    }

    /**
     * Update a folder
     */
    async updateFolder(
        folderId: string,
        updates: { name?: string; parentId?: string | null }
    ): Promise<Folder> {
        const body: Record<string, unknown> = {};
        if (updates.name !== undefined) body.name = updates.name;
        if (updates.parentId !== undefined) body.parent_id = updates.parentId === null ? "" : updates.parentId;

        const { data } = await api.patch<Folder>(`/notes/folders/${folderId}`, body);
        return data;
    }

    /**
     * Delete a folder
     */
    async deleteFolder(folderId: string, cascade: boolean = false): Promise<void> {
        await api.delete(`/notes/folders/${folderId}?cascade=${cascade}`);
    }

    // =========================================================================
    // IMAGE OPERATIONS
    // =========================================================================

    /**
     * Upload an image for use in notes
     */
    async uploadImage(file: File): Promise<ImageUploadResult> {
        const formData = new FormData();
        formData.append("file", file);

        const token = this.getToken();
        const response = await fetch("http://localhost:8000/api/v1/notes/images", {
            method: "POST",
            headers: {
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`Image upload failed: ${response.status}`);
        }

        return response.json();
    }

    /**
     * Get a presigned URL for an image
     */
    async getImageUrl(imageKey: string): Promise<string> {
        const { data } = await api.get<{ url: string }>(`/notes/images/${encodeURIComponent(imageKey)}`);
        return data.url;
    }

    private getToken(): string | null {
        if (typeof window === "undefined") return null;
        try {
            const tokens = JSON.parse(localStorage.getItem("synaptiq_tokens") || "{}");
            return tokens.access_token || null;
        } catch {
            return null;
        }
    }
}

export const notesService = new NotesService();
