"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { MessageSquare, Loader2, PanelRightOpen, X } from "lucide-react";
import { chatService, type Conversation, type Message } from "@/lib/api/chat";
import { userService, type ChatModel } from "@/lib/api/user";
import { ConversationList, ChatComposer, MessageBubble, ChatContextPanel, ModelSelector, type ModelOption } from "@/components/chat";

const DEFAULT_MODEL_ID = "gpt-5.2";

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [showContextDrawer, setShowContextDrawer] = useState(false);

  const [models, setModels] = useState<ModelOption[]>([]);
  const [selectedModelId, setSelectedModelId] = useState(DEFAULT_MODEL_ID);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    userService.listModels().then((m) => {
      if (m && m.length > 0) setModels(m);
    }).catch(() => {});
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      setIsLoadingConversations(true);
      const { conversations: convs } = await chatService.listConversations();
      setConversations(convs);
      setActiveConversationId((previousId) => previousId || convs[0]?.id || null);
    } catch (error) {
      console.error("Failed to load conversations", error);
    } finally {
      setIsLoadingConversations(false);
    }
  }, []);

  const loadMessages = useCallback(async (conversationId: string) => {
    try {
      setIsLoadingMessages(true);
      const { messages: msgs } = await chatService.getMessages(conversationId);
      setMessages(msgs);
    } catch (error) {
      console.error("Failed to load messages", error);
    } finally {
      setIsLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId);
    } else {
      setMessages([]);
    }
  }, [activeConversationId, loadMessages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

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
    setConversations((prev) => prev.filter((c) => c.id !== id));

    if (activeConversationId === id) {
      const remaining = conversations.filter((c) => c.id !== id);
      setActiveConversationId(remaining.length > 0 ? remaining[0].id : null);
    }

    try {
      await chatService.deleteConversation(id);
    } catch {
      console.warn("Delete conversation request failed (may already be deleted)", id);
    }
  };

  const handleSendMessage = async (content: string, modelId: string) => {
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
      const response = await chatService.sendMessage(conversationId, content, modelId);
      setMessages((prev) => [...prev, response.user_message, response.assistant_message]);

      setConversations((prev) =>
        prev.map((c) =>
          c.id === conversationId
            ? {
              ...c,
              title: c.title || response.user_message.content.slice(0, 50),
              preview: response.user_message.content.slice(0, 100),
              updated_at: new Date().toISOString(),
            }
            : c,
        ),
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

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeConversationId) || null,
    [activeConversationId, conversations],
  );

  return (
    <div className="grid h-full grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)]">
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

      <div className="min-w-0 flex flex-col h-full overflow-hidden">
        {activeConversationId || messages.length > 0 ? (
          <>
            <div className="flex-1 w-full overflow-y-auto thin-scrollbar px-4 md:px-8 py-5">
              <div className="mx-auto w-full max-w-[840px] space-y-4">
                <div className="sticky top-0 z-10 flex justify-end">
                  <button
                    onClick={() => setShowContextDrawer(true)}
                    className="h-8 px-2.5 rounded-md border border-border bg-surface/95 backdrop-blur text-[12px] text-secondary hover:text-primary hover:bg-elevated inline-flex items-center gap-1.5"
                  >
                    <PanelRightOpen className="w-3.5 h-3.5" />
                    Context
                  </button>
                </div>
                {isLoadingMessages ? (
                  <div className="flex items-center justify-center h-32">
                    <Loader2 className="w-6 h-6 animate-spin text-secondary" />
                  </div>
                ) : messages.length === 0 ? (
                  <div className="dashboard-card flex flex-col items-center justify-center h-64 text-center px-6">
                    <MessageSquare className="w-12 h-12 text-secondary mb-4" strokeWidth={1.5} />
                    <h3 className="text-[18px] leading-[24px] font-semibold text-primary mb-2">Ask anything</h3>
                    <p className="text-[13px] leading-[18px] text-secondary max-w-md">
                      Query your knowledge base in natural language. Get answers with citations from your sources.
                    </p>
                  </div>
                ) : (
                  messages.map((message) => <MessageBubble key={message.id} message={message} />)
                )}

                {isSending && (
                  <div className="w-full">
                    <div className="mb-1 text-[12px] leading-[16px] text-secondary">Synaptiq</div>
                    <div className="rounded-lg border border-border bg-surface p-3">
                      <div className="flex items-center gap-2 text-secondary">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span className="text-[13px] leading-[18px]">Thinking...</span>
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>

            <ChatComposer
              onSend={handleSendMessage}
              isSending={isSending}
              className="mx-auto max-w-[840px]"
              models={models}
              selectedModelId={selectedModelId}
              onModelChange={setSelectedModelId}
            />
          </>
        ) : (
          <div className="flex-1 w-full flex flex-col items-center justify-center text-center px-6">
            <div className="w-16 h-16 rounded-full bg-[var(--accent-soft)] border border-accent/30 flex items-center justify-center mb-6">
              <MessageSquare className="w-8 h-8 text-[var(--accent)]" strokeWidth={1.5} />
            </div>
            <h2 className="text-[24px] leading-[28px] font-semibold text-primary mb-2">Ask anything</h2>
            <p className="text-[13px] leading-[18px] text-secondary max-w-md mb-6">
              Query your knowledge base in natural language. Get answers with citations from your sources.
            </p>
            {models.length > 0 && (
              <div className="mb-6">
                <ModelSelector
                  models={models}
                  selectedModelId={selectedModelId}
                  onSelect={setSelectedModelId}
                />
              </div>
            )}
            <button
              onClick={handleNewConversation}
              className="h-10 px-6 border border-accent/35 bg-[var(--accent-soft)] hover:bg-[var(--hover-bg)] text-[var(--accent)] rounded-md text-[13px] leading-[18px] font-medium transition-colors"
            >
              Start a conversation
            </button>
          </div>
        )}
      </div>

      {showContextDrawer && (
        <div className="fixed inset-0 z-[70]">
          <div className="absolute inset-0 bg-black/35" onClick={() => setShowContextDrawer(false)} />
          <div className="absolute inset-y-0 right-0 w-[min(360px,90vw)] bg-canvas border-l border-border shadow-elevated">
            <div className="h-12 px-3 border-b border-border flex items-center justify-between">
              <h3 className="text-sm font-semibold text-primary">Conversation Context</h3>
              <button
                onClick={() => setShowContextDrawer(false)}
                className="h-8 w-8 rounded-md border border-border text-secondary hover:text-primary hover:bg-[var(--hover-bg)] inline-flex items-center justify-center"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="h-[calc(100%-48px)]">
              <ChatContextPanel conversation={activeConversation} messages={messages} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
