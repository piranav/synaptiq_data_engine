"use client";

import { api } from "./client";

// =============================================================================
// TYPES
// =============================================================================

export interface Conversation {
    id: string;
    user_id: string;
    title: string | null;
    preview: string | null;
    created_at: string;
    updated_at: string;
}

export interface Citation {
    id?: number;
    // Backend sends 'title', frontend historically used 'source_title'
    title?: string;
    source_title?: string;
    url?: string;
    source_url?: string;
    source_id?: string;
    source_type?: string;
    timestamp?: string;
    chunk_text?: string;
}

export interface Message {
    id: string;
    conversation_id: string;
    role: "user" | "assistant";
    content: string;
    citations: Citation[];
    concepts_referenced: string[];
    confidence?: number;
    source_type?: string;
    created_at: string;
}

export interface ChatResponse {
    user_message: Message;
    assistant_message: Message;
}

// =============================================================================
// CHAT SERVICE
// =============================================================================

class ChatService {
    /**
     * Create a new conversation
     */
    async createConversation(title?: string): Promise<Conversation> {
        const { data } = await api.post<Conversation>("/chat/conversations", {
            title,
        });
        return data;
    }

    /**
     * List all conversations for the current user
     */
    async listConversations(
        limit: number = 50,
        offset: number = 0
    ): Promise<{ conversations: Conversation[]; total: number }> {
        const { data } = await api.get(
            `/chat/conversations?limit=${limit}&offset=${offset}`
        );
        return data;
    }

    /**
     * Get a specific conversation
     */
    async getConversation(conversationId: string): Promise<Conversation> {
        const { data } = await api.get<Conversation>(
            `/chat/conversations/${conversationId}`
        );
        return data;
    }

    /**
     * Update a conversation
     */
    async updateConversation(
        conversationId: string,
        title: string
    ): Promise<Conversation> {
        const { data } = await api.put<Conversation>(
            `/chat/conversations/${conversationId}`,
            { title }
        );
        return data;
    }

    /**
     * Delete a conversation
     */
    async deleteConversation(conversationId: string): Promise<void> {
        await api.delete(`/chat/conversations/${conversationId}`);
    }

    /**
     * Get messages for a conversation
     */
    async getMessages(
        conversationId: string,
        limit: number = 100,
        offset: number = 0
    ): Promise<{ messages: Message[]; conversation_id: string }> {
        const { data } = await api.get(
            `/chat/conversations/${conversationId}/messages?limit=${limit}&offset=${offset}`
        );
        return data;
    }

    /**
     * Send a message (non-streaming)
     */
    async sendMessage(
        conversationId: string,
        content: string,
        model?: string,
    ): Promise<ChatResponse> {
        const { data } = await api.post<ChatResponse>(
            `/chat/conversations/${conversationId}/messages`,
            { content, model }
        );
        return data;
    }

    /**
     * Send a message with streaming response
     */
    async sendMessageStream(
        conversationId: string,
        content: string,
        onToken: (token: string) => void,
        onUserMessage?: (messageId: string) => void,
        onDone?: (messageId: string) => void,
        onError?: (error: string) => void
    ): Promise<void> {
        const token = this.getToken();
        const response = await fetch(
            `http://localhost:8000/api/v1/chat/conversations/${conversationId}/messages/stream`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({ content }),
            }
        );

        if (!response.ok) {
            throw new Error(`Stream request failed: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (line.startsWith("event: ")) {
                    const event = line.slice(7);
                    // Next line should be data
                    continue;
                }
                if (line.startsWith("data: ")) {
                    const data = line.slice(6);
                    // Parse based on previous event type
                    // For simplicity, we detect by content
                    if (data.includes("message_id")) {
                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.message_id && onDone) {
                                onDone(parsed.message_id);
                            }
                        } catch {
                            // Not JSON, treat as token
                            onToken(data);
                        }
                    } else {
                        onToken(data);
                    }
                }
            }
        }
    }

    /**
     * Quick chat - creates conversation if needed
     */
    async quickChat(
        query: string,
        conversationId?: string
    ): Promise<ChatResponse> {
        const { data } = await api.post<ChatResponse>("/chat", {
            query,
            conversation_id: conversationId,
        });
        return data;
    }

    /**
     * Regenerate an assistant response
     */
    async regenerateResponse(
        conversationId: string,
        messageId: string
    ): Promise<Message> {
        const { data } = await api.post<Message>(
            `/chat/conversations/${conversationId}/messages/${messageId}/regenerate`
        );
        return data;
    }

    private getToken(): string | null {
        if (typeof window === "undefined") return null;
        try {
            const tokens = JSON.parse(
                localStorage.getItem("synaptiq_tokens") || "{}"
            );
            return tokens.access_token || null;
        } catch {
            return null;
        }
    }
}

export const chatService = new ChatService();
