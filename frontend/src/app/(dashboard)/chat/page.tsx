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
    const [streamingContent, setStreamingContent] = useState("");

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
    }, [messages, streamingContent, scrollToBottom]);

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
        try {
            await chatService.deleteConversation(id);
            setConversations((prev) => prev.filter((c) => c.id !== id));

            if (activeConversationId === id) {
                const remaining = conversations.filter((c) => c.id !== id);
                setActiveConversationId(remaining.length > 0 ? remaining[0].id : null);
            }
        } catch (error) {
            console.error("Failed to delete conversation", error);
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

    return (
        <div className="flex h-full bg-canvas">
            {/* Sidebar */}
            <ConversationList
                conversations={conversations}
                activeId={activeConversationId}
                isLoading={isLoadingConversations}
                onSelect={handleSelectConversation}
                onNew={handleNewConversation}
                onDelete={handleDeleteConversation}
            />

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col h-full overflow-hidden">
                {activeConversationId || messages.length > 0 ? (
                    <>
                        {/* Messages */}
                        <div className="flex-1 overflow-y-auto no-scrollbar px-6 py-6">
                            <div className="max-w-3xl mx-auto space-y-4">
                                {isLoadingMessages ? (
                                    <div className="flex items-center justify-center h-32">
                                        <Loader2 className="w-6 h-6 animate-spin text-secondary" />
                                    </div>
                                ) : messages.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-64 text-center">
                                        <MessageSquare className="w-12 h-12 text-tertiary mb-4" />
                                        <h3 className="text-title-3 text-primary mb-2">
                                            Ask anything
                                        </h3>
                                        <p className="text-body-small text-secondary max-w-md">
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
                                    <div className="flex justify-start">
                                        <div className="bg-surface border border-border-subtle rounded-lg px-4 py-3">
                                            <div className="flex items-center gap-2 text-secondary">
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                                <span className="text-body-small">Thinking...</span>
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
                    <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
                        <div className="w-16 h-16 rounded-full bg-accent/10 flex items-center justify-center mb-6">
                            <MessageSquare className="w-8 h-8 text-accent" />
                        </div>
                        <h2 className="text-title-2 text-primary mb-2">
                            Ask anything
                        </h2>
                        <p className="text-body text-secondary max-w-md mb-8">
                            Query your knowledge base in natural language. Get answers with citations from your sources.
                        </p>
                        <button
                            onClick={handleNewConversation}
                            className="px-6 py-3 bg-accent text-white rounded-md text-body font-medium hover:opacity-90 transition-opacity"
                        >
                            Start a conversation
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
