"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { MessageSquare, Loader2 } from "lucide-react";
import { chatService, type Conversation, type Message } from "@/lib/api/chat";
import { ConversationList, ChatComposer, MessageBubble } from "@/components/chat";

export default function ChatPage() {
    // State
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoadingConversations, setIsLoadingConversations] = useState(true);
    const [isLoadingMessages, setIsLoadingMessages] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Scroll to bottom of messages
    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, []);

    // Load conversations on mount
    useEffect(() => {
        loadConversations();
    }, []);

    // Load messages when conversation changes
    useEffect(() => {
        if (activeConversationId) {
            loadMessages(activeConversationId);
        } else {
            setMessages([]);
        }
    }, [activeConversationId]);

    // Scroll to bottom when messages change
    useEffect(() => {
        scrollToBottom();
    }, [messages, scrollToBottom]);

    const loadConversations = async () => {
        try {
            setIsLoadingConversations(true);
            const { conversations: convs } = await chatService.listConversations();
            setConversations(convs);

            // Select first conversation if none selected
            if (convs.length > 0 && !activeConversationId) {
                setActiveConversationId(convs[0].id);
            }
        } catch (error) {
            console.error("Failed to load conversations", error);
        } finally {
            setIsLoadingConversations(false);
        }
    };

    const loadMessages = async (conversationId: string) => {
        try {
            setIsLoadingMessages(true);
            const { messages: msgs } = await chatService.getMessages(conversationId);
            setMessages(msgs);
        } catch (error) {
            console.error("Failed to load messages", error);
        } finally {
            setIsLoadingMessages(false);
        }
    };

    const handleNewConversation = async () => {
        try {
            const conversation = await chatService.createConversation();
            setConversations((prev) => [conversation, ...prev]);
            setActiveConversationId(conversation.id);
            setMessages([]);
        } catch (error) {
            console.error("Failed to create conversation", error);
        }
    };

    const handleSelectConversation = (id: string) => {
        setActiveConversationId(id);
    };

    const handleDeleteConversation = async (id: string) => {
        // Optimistically remove from UI first
        setConversations((prev) => prev.filter((c) => c.id !== id));

        if (activeConversationId === id) {
            const remaining = conversations.filter((c) => c.id !== id);
            setActiveConversationId(remaining.length > 0 ? remaining[0].id : null);
        }

        try {
            await chatService.deleteConversation(id);
        } catch (error) {
            // Silently handle - conversation may already be deleted (404)
            // We've already removed it from the UI, so no action needed
            console.warn("Delete conversation request failed (may already be deleted)", id);
        }
    };

    const handleSendMessage = async (content: string) => {
        // Create conversation if none exists
        let conversationId = activeConversationId;
        if (!conversationId) {
            try {
                const conversation = await chatService.createConversation();
                setConversations((prev) => [conversation, ...prev]);
                setActiveConversationId(conversation.id);
                conversationId = conversation.id;
            } catch (error) {
                console.error("Failed to create conversation", error);
                return;
            }
        }

        setIsSending(true);

        try {
            // Use non-streaming for now (simpler)
            const response = await chatService.sendMessage(conversationId, content);

            // Add both messages to the list
            setMessages((prev) => [...prev, response.user_message, response.assistant_message]);

            // Update conversation in list
            setConversations((prev) =>
                prev.map((c) =>
                    c.id === conversationId
                        ? {
                            ...c,
                            title: c.title || response.user_message.content.slice(0, 50),
                            preview: response.user_message.content.slice(0, 100),
                            updated_at: new Date().toISOString(),
                        }
                        : c
                )
            );
        } catch (error) {
            console.error("Failed to send message", error);
        } finally {
            setIsSending(false);
        }
    };

    const handleToggleSidebar = () => {
        setIsSidebarCollapsed(!isSidebarCollapsed);
    };

    return (
        <div className="flex h-full bg-[#0B0D12]">
            {/* Sidebar */}
            <ConversationList
                conversations={conversations}
                activeId={activeConversationId}
                isLoading={isLoadingConversations}
                isCollapsed={isSidebarCollapsed}
                onSelect={handleSelectConversation}
                onNew={handleNewConversation}
                onDelete={handleDeleteConversation}
                onToggleCollapse={handleToggleSidebar}
            />

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col h-full overflow-hidden">
                {activeConversationId || messages.length > 0 ? (
                    <>
                        {/* Messages */}
                        <div className="flex-1 w-full overflow-y-auto no-scrollbar px-4 md:px-8 lg:px-16 py-4">
                            <div className="max-w-3xl mx-auto space-y-4">
                                {isLoadingMessages ? (
                                    <div className="flex items-center justify-center h-32">
                                        <Loader2 className="w-6 h-6 animate-spin text-white/60" />
                                    </div>
                                ) : messages.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-64 text-center">
                                        <MessageSquare className="w-12 h-12 text-white/40 mb-4" strokeWidth={1.5} />
                                        <h3 className="text-[18px] leading-[24px] font-semibold text-white mb-2" style={{ fontFamily: "'SF Pro Display', sans-serif" }}>
                                            Ask anything
                                        </h3>
                                        <p className="text-[13px] leading-[18px] text-white/60 max-w-md">
                                            Query your knowledge base in natural language. Get answers with citations from your sources.
                                        </p>
                                    </div>
                                ) : (
                                    messages.map((message) => (
                                        <MessageBubble key={message.id} message={message} />
                                    ))
                                )}

                                {/* Streaming indicator */}
                                {isSending && (
                                    <div className="max-w-3xl">
                                        <div className="mb-1 text-[12px] leading-[16px] text-white/60">Synaptiq</div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                                            <div className="flex items-center gap-2 text-white/60">
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                                <span className="text-[13px] leading-[18px]">Thinking...</span>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                <div ref={messagesEndRef} />
                            </div>
                        </div>

                        {/* Composer */}
                        <ChatComposer onSend={handleSendMessage} isSending={isSending} />
                    </>
                ) : (
                    /* Empty state when no conversation */
                    <div className="flex-1 w-full flex flex-col items-center justify-center text-center px-6">
                        <div className="w-16 h-16 rounded-full bg-[#256BEE]/10 border border-[#256BEE]/30 flex items-center justify-center mb-6">
                            <MessageSquare className="w-8 h-8 text-[#256BEE]" strokeWidth={1.5} />
                        </div>
                        <h2 className="text-[24px] leading-[28px] font-semibold text-white mb-2" style={{ fontFamily: "'SF Pro Display', sans-serif" }}>
                            Ask anything
                        </h2>
                        <p className="text-[13px] leading-[18px] text-white/60 max-w-md mb-8">
                            Query your knowledge base in natural language. Get answers with citations from your sources.
                        </p>
                        <button
                            onClick={handleNewConversation}
                            className="h-10 px-6 bg-[#256BEE] hover:bg-[#1F5BCC] text-white rounded-md text-[13px] leading-[18px] font-medium border border-white/10 transition-colors"
                        >
                            Start a conversation
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
