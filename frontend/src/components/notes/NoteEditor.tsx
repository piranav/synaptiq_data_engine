"use client";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Placeholder } from "@tiptap/extension-placeholder";
import { Underline } from "@tiptap/extension-underline";
import { Link } from "@tiptap/extension-link";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import { TaskList } from "@tiptap/extension-task-list";
import { TaskItem } from "@tiptap/extension-task-item";
import { Image } from "@tiptap/extension-image";
import { CodeBlockLowlight } from "@tiptap/extension-code-block-lowlight";
import { common, createLowlight } from "lowlight";
import type { Content, JSONContent } from "@tiptap/core";
import { useCallback, useEffect, useRef, useState } from "react";
import {
    Heading1,
    Heading2,
    Heading3,
    List,
    ListOrdered,
    CheckSquare,
    Quote,
    Minus,
    Table as TableIcon,
    Image as ImageIcon,
    Code2,
    MoreHorizontal,
} from "lucide-react";
import { notesService } from "@/lib/api/notes";
import { MermaidRenderer } from "./MermaidRenderer";

const lowlight = createLowlight(common);

// Use TipTap's native content types for compatibility
type NoteContent = JSONContent[] | Content | undefined;

interface NoteEditorProps {
    initialContent?: NoteContent;
    placeholder?: string;
    onChange?: (content: JSONContent[], plainText: string) => void;
    onImageUpload?: (file: File) => Promise<string>;
    editable?: boolean;
    className?: string;
}

export function NoteEditor({
    initialContent = [],
    placeholder = "Start typing... Use / for commands",
    onChange,
    onImageUpload,
    editable = true,
    className = "",
}: NoteEditorProps) {
    const [showInsertMenu, setShowInsertMenu] = useState(false);
    const [insertMenuPosition, setInsertMenuPosition] = useState({ x: 0, y: 0 });
    const insertMenuRef = useRef<HTMLDivElement>(null);

    // Convert content to TipTap format
    const convertToTipTapContent = useCallback((content: NoteContent): Content | undefined => {
        if (!content) return undefined;
        if (Array.isArray(content)) {
            if (content.length === 0) return undefined;
            // If it's already TipTap format (has 'type: doc')
            if (content.length === 1 && (content[0] as JSONContent).type === "doc") {
                return content[0] as Content;
            }
            // Otherwise wrap in doc
            return {
                type: "doc",
                content: content as JSONContent[],
            };
        }
        return content;
    }, []);

    const editor = useEditor({
        immediatelyRender: false, // Required for SSR/Next.js
        extensions: [
            StarterKit.configure({
                codeBlock: false, // We use CodeBlockLowlight instead
            }),
            Placeholder.configure({
                placeholder,
                emptyEditorClass: "is-editor-empty",
            }),
            Underline,
            Link.configure({
                openOnClick: false,
                HTMLAttributes: {
                    class: "text-accent underline cursor-pointer hover:opacity-80",
                },
            }),
            Table.configure({
                resizable: true,
                HTMLAttributes: {
                    class: "border-collapse table-auto w-full",
                },
            }),
            TableRow,
            TableCell.configure({
                HTMLAttributes: {
                    class: "border border-border p-2 min-w-[100px]",
                },
            }),
            TableHeader.configure({
                HTMLAttributes: {
                    class: "border border-border p-2 bg-elevated font-medium",
                },
            }),
            TaskList.configure({
                HTMLAttributes: {
                    class: "not-prose pl-0",
                },
            }),
            TaskItem.configure({
                nested: true,
                HTMLAttributes: {
                    class: "flex gap-2 items-start",
                },
            }),
            Image.configure({
                HTMLAttributes: {
                    class: "rounded-lg max-w-full",
                },
            }),
            CodeBlockLowlight.configure({
                lowlight,
                HTMLAttributes: {
                    class: "rounded-md bg-canvas/60 p-4 font-mono text-sm overflow-x-auto",
                },
            }),
        ],
        content: convertToTipTapContent(initialContent),
        editable,
        onUpdate: ({ editor }) => {
            const json = editor.getJSON();
            const text = editor.getText();
            onChange?.(json.content || [], text);
        },
        editorProps: {
            attributes: {
                class: "prose prose-sm max-w-none focus:outline-none min-h-[200px] text-primary",
            },
            handleDrop: (view, event, slice, moved) => {
                if (!moved && event.dataTransfer?.files.length) {
                    const file = event.dataTransfer.files[0];
                    if (file.type.startsWith("image/")) {
                        handleImageUpload(file);
                        return true;
                    }
                }
                return false;
            },
            handlePaste: (view, event) => {
                const items = event.clipboardData?.items;
                if (items) {
                    for (const item of items) {
                        if (item.type.startsWith("image/")) {
                            const file = item.getAsFile();
                            if (file) {
                                handleImageUpload(file);
                                return true;
                            }
                        }
                    }
                }
                return false;
            },
        },
    });

    const handleImageUpload = async (file: File) => {
        if (!editor) return;

        try {
            let url: string;
            if (onImageUpload) {
                url = await onImageUpload(file);
            } else {
                // Use default upload
                const result = await notesService.uploadImage(file);
                url = result.url;
            }

            editor.chain().focus().setImage({ src: url }).run();
        } catch (error) {
            console.error("Failed to upload image:", error);
        }
    };

    const handleInsertTable = () => {
        editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
        setShowInsertMenu(false);
    };

    const handleInsertCodeBlock = () => {
        editor?.chain().focus().toggleCodeBlock().run();
        setShowInsertMenu(false);
    };

    const handleInsertMermaid = () => {
        editor
            ?.chain()
            .focus()
            .insertContent({
                type: "codeBlock",
                attrs: { language: "mermaid" },
                content: [{ type: "text", text: "graph TD\n    A[Start] --> B[Process]\n    B --> C[End]" }],
            })
            .run();
        setShowInsertMenu(false);
    };

    // Close insert menu on outside click
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (insertMenuRef.current && !insertMenuRef.current.contains(e.target as Node)) {
                setShowInsertMenu(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    if (!editor) return null;

    return (
        <div className={`note-editor relative ${className}`}>
            {/* Fixed Toolbar */}
            <div className="sticky top-0 z-10 flex items-center gap-0.5 p-2 border-b border-border bg-canvas/90 backdrop-blur">
                <ToolbarButton
                    onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
                    isActive={editor.isActive("heading", { level: 1 })}
                    title="Heading 1"
                >
                    <Heading1 className="h-4 w-4" />
                </ToolbarButton>
                <ToolbarButton
                    onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
                    isActive={editor.isActive("heading", { level: 2 })}
                    title="Heading 2"
                >
                    <Heading2 className="h-4 w-4" />
                </ToolbarButton>
                <ToolbarButton
                    onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
                    isActive={editor.isActive("heading", { level: 3 })}
                    title="Heading 3"
                >
                    <Heading3 className="h-4 w-4" />
                </ToolbarButton>

                <div className="w-px h-4 bg-elevated mx-1" />

                <ToolbarButton
                    onClick={() => editor.chain().focus().toggleBulletList().run()}
                    isActive={editor.isActive("bulletList")}
                    title="Bullet List"
                >
                    <List className="h-4 w-4" />
                </ToolbarButton>
                <ToolbarButton
                    onClick={() => editor.chain().focus().toggleOrderedList().run()}
                    isActive={editor.isActive("orderedList")}
                    title="Numbered List"
                >
                    <ListOrdered className="h-4 w-4" />
                </ToolbarButton>
                <ToolbarButton
                    onClick={() => editor.chain().focus().toggleTaskList().run()}
                    isActive={editor.isActive("taskList")}
                    title="Task List"
                >
                    <CheckSquare className="h-4 w-4" />
                </ToolbarButton>

                <div className="w-px h-4 bg-elevated mx-1" />

                <ToolbarButton
                    onClick={() => editor.chain().focus().toggleBlockquote().run()}
                    isActive={editor.isActive("blockquote")}
                    title="Quote"
                >
                    <Quote className="h-4 w-4" />
                </ToolbarButton>
                <ToolbarButton
                    onClick={() => editor.chain().focus().setHorizontalRule().run()}
                    title="Divider"
                >
                    <Minus className="h-4 w-4" />
                </ToolbarButton>
                <ToolbarButton
                    onClick={handleInsertCodeBlock}
                    isActive={editor.isActive("codeBlock")}
                    title="Code Block"
                >
                    <Code2 className="h-4 w-4" />
                </ToolbarButton>

                <div className="w-px h-4 bg-elevated mx-1" />

                <ToolbarButton onClick={handleInsertTable} title="Insert Table">
                    <TableIcon className="h-4 w-4" />
                </ToolbarButton>
                <ToolbarButton
                    onClick={() => {
                        const input = document.createElement("input");
                        input.type = "file";
                        input.accept = "image/*";
                        input.onchange = (e) => {
                            const file = (e.target as HTMLInputElement).files?.[0];
                            if (file) handleImageUpload(file);
                        };
                        input.click();
                    }}
                    title="Insert Image"
                >
                    <ImageIcon className="h-4 w-4" />
                </ToolbarButton>

                <div className="w-px h-4 bg-elevated mx-1" />

                {/* More menu */}
                <div className="relative">
                    <ToolbarButton
                        onClick={(e) => {
                            const rect = (e.target as HTMLElement).getBoundingClientRect();
                            setInsertMenuPosition({ x: rect.left, y: rect.bottom + 4 });
                            setShowInsertMenu(!showInsertMenu);
                        }}
                        title="More options"
                    >
                        <MoreHorizontal className="h-4 w-4" />
                    </ToolbarButton>
                </div>
            </div>

            {/* Insert Menu Dropdown */}
            {showInsertMenu && (
                <div
                    ref={insertMenuRef}
                    className="fixed z-50 w-48 rounded-lg border border-border bg-surface p-1 shadow-elevated"
                    style={{ left: insertMenuPosition.x, top: insertMenuPosition.y }}
                >
                    <InsertMenuItem
                        icon={<TableIcon className="h-4 w-4" />}
                        label="Table"
                        onClick={handleInsertTable}
                    />
                    <InsertMenuItem
                        icon={<Code2 className="h-4 w-4" />}
                        label="Code Block"
                        onClick={handleInsertCodeBlock}
                    />
                    <InsertMenuItem
                        icon={<div className="h-4 w-4 text-[10px] font-bold">◇</div>}
                        label="Mermaid Diagram"
                        onClick={handleInsertMermaid}
                    />
                </div>
            )}

            {/* Editor Content */}
            <div className="p-4">
                <EditorContent editor={editor} />
            </div>

            {/* Mermaid Preview (for mermaid code blocks) */}
            <MermaidPreview editor={editor} />

            {/* Editor Styles */}
            <style jsx global>{`
                .note-editor .ProseMirror {
                    outline: none;
                }
                
                .note-editor .is-editor-empty:first-child::before {
                    content: attr(data-placeholder);
                    float: left;
                    color: var(--text-tertiary);
                    pointer-events: none;
                    height: 0;
                }
                
                .note-editor .ProseMirror h1 {
                    font-size: 2rem;
                    font-weight: 600;
                    line-height: 1.3;
                    margin-top: 1.5rem;
                    margin-bottom: 0.5rem;
                }
                
                .note-editor .ProseMirror h2 {
                    font-size: 1.5rem;
                    font-weight: 600;
                    line-height: 1.3;
                    margin-top: 1.25rem;
                    margin-bottom: 0.5rem;
                }
                
                .note-editor .ProseMirror h3 {
                    font-size: 1.25rem;
                    font-weight: 600;
                    line-height: 1.3;
                    margin-top: 1rem;
                    margin-bottom: 0.5rem;
                }
                
                .note-editor .ProseMirror p {
                    margin-bottom: 0.75rem;
                }
                
                .note-editor .ProseMirror ul:not([data-type="taskList"]) {
                    padding-left: 1.5rem;
                    margin-bottom: 0.75rem;
                    list-style-type: disc;
                }
                
                .note-editor .ProseMirror ol {
                    padding-left: 1.5rem;
                    margin-bottom: 0.75rem;
                    list-style-type: decimal;
                }
                
                .note-editor .ProseMirror li {
                    display: list-item;
                }
                
                .note-editor .ProseMirror blockquote {
                    border-left: 3px solid var(--accent);
                    padding-left: 1rem;
                    font-style: italic;
                    color: var(--text-secondary);
                    margin: 1rem 0;
                }
                
                .note-editor .ProseMirror hr {
                    border: none;
                    border-top: 1px solid var(--border);
                    margin: 1.5rem 0;
                }
                
                .note-editor .ProseMirror code {
                    background: var(--elevated);
                    padding: 0.2rem 0.4rem;
                    border-radius: 4px;
                    font-family: var(--font-mono);
                    font-size: 0.9em;
                }
                
                .note-editor .ProseMirror pre {
                    background: color-mix(in srgb, var(--canvas) 82%, transparent);
                    border-radius: 8px;
                    padding: 1rem;
                    margin: 1rem 0;
                    overflow-x: auto;
                }
                
                .note-editor .ProseMirror pre code {
                    background: none;
                    padding: 0;
                }
                
                .note-editor .ProseMirror table {
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1rem 0;
                }
                
                .note-editor .ProseMirror th,
                .note-editor .ProseMirror td {
                    border: 1px solid var(--border);
                    padding: 0.5rem;
                    text-align: left;
                }
                
                .note-editor .ProseMirror th {
                    background: var(--elevated);
                    font-weight: 500;
                }
                
                .note-editor .ProseMirror img {
                    max-width: 100%;
                    border-radius: 8px;
                    margin: 1rem 0;
                }
                
                .note-editor .ProseMirror ul[data-type="taskList"] {
                    list-style: none;
                    padding-left: 0;
                }
                
                .note-editor .ProseMirror ul[data-type="taskList"] li {
                    display: flex;
                    align-items: flex-start;
                    gap: 0.5rem;
                }
                
                .note-editor .ProseMirror ul[data-type="taskList"] input[type="checkbox"] {
                    margin-top: 0.25rem;
                }
            `}</style>
        </div>
    );
}

// Toolbar Button Component
function ToolbarButton({
    onClick,
    isActive = false,
    title,
    children,
}: {
    onClick: (e: React.MouseEvent) => void;
    isActive?: boolean;
    title: string;
    children: React.ReactNode;
}) {
    return (
        <button
            onClick={onClick}
            title={title}
            className={`
                h-7 w-7 rounded flex items-center justify-center
                transition-colors
                ${isActive
                    ? "bg-accent/20 text-accent"
                    : "text-secondary hover:text-primary hover:bg-elevated"
                }
            `}
        >
            {children}
        </button>
    );
}

// Insert Menu Item Component
function InsertMenuItem({
    icon,
    label,
    onClick,
}: {
    icon: React.ReactNode;
    label: string;
    onClick: () => void;
}) {
    return (
        <button
            onClick={onClick}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-[13px] text-primary hover:bg-elevated hover:text-primary"
        >
            {icon}
            <span>{label}</span>
        </button>
    );
}

// Mermaid Preview Component
function MermaidPreview({ editor }: { editor: ReturnType<typeof useEditor> }) {
    const [mermaidBlocks, setMermaidBlocks] = useState<{ id: string; code: string }[]>([]);

    useEffect(() => {
        if (!editor) return;

        const updateMermaidBlocks = () => {
            const blocks: { id: string; code: string }[] = [];
            editor.state.doc.descendants((node, pos) => {
                if (node.type.name === "codeBlock" && node.attrs.language === "mermaid") {
                    blocks.push({
                        id: `mermaid-${pos}`,
                        code: node.textContent,
                    });
                }
            });
            setMermaidBlocks(blocks);
        };

        updateMermaidBlocks();
        editor.on("update", updateMermaidBlocks);

        return () => {
            editor.off("update", updateMermaidBlocks);
        };
    }, [editor]);

    if (mermaidBlocks.length === 0) return null;

    return (
        <div className="px-4 pb-4 space-y-4">
            {mermaidBlocks.map((block) => (
                <div key={block.id} className="rounded-lg border border-border bg-surface p-4">
                    <div className="text-[11px] text-tertiary uppercase tracking-wider mb-2">
                        Mermaid Preview
                    </div>
                    <MermaidRenderer code={block.code} />
                </div>
            ))}
        </div>
    );
}
