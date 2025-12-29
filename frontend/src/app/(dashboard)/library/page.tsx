"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { libraryService, LibraryItem, LibraryStats, LibraryItemType } from "@/lib/api/library";
import {
    LibraryHeader,
    LibraryTabs,
    LibrarySortBar,
    LibraryGrid,
    TabType,
    SortOption,
    ViewMode,
} from "@/components/library";
import { AddSourceModal } from "@/components/dashboard/AddSourceModal";

export default function LibraryPage() {
    const router = useRouter();

    // State
    const [items, setItems] = useState<LibraryItem[]>([]);
    const [stats, setStats] = useState<LibraryStats>({ all: 0, videos: 0, articles: 0, notes: 0, files: 0 });
    const [isLoading, setIsLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<TabType>("all");
    const [sort, setSort] = useState<SortOption>("recent");
    const [view, setView] = useState<ViewMode>("grid");
    const [searchQuery, setSearchQuery] = useState("");
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [clickPosition, setClickPosition] = useState({ x: 0, y: 0 });

    // Map tab to API filter type
    const getFilterType = (tab: TabType): LibraryItemType | "all" => {
        const map: Record<TabType, LibraryItemType | "all"> = {
            all: "all",
            videos: "video",
            articles: "article",
            notes: "note",
            files: "file",
        };
        return map[tab];
    };

    // Fetch data
    const fetchData = useCallback(async () => {
        setIsLoading(true);
        try {
            const [itemsData, statsData] = await Promise.all([
                libraryService.getLibraryItems({
                    type: getFilterType(activeTab),
                    sort,
                    search: searchQuery,
                }),
                libraryService.getLibraryStats(),
            ]);
            setItems(itemsData);
            setStats(statsData);
        } catch (error) {
            console.error("Failed to fetch library data:", error);
        } finally {
            setIsLoading(false);
        }
    }, [activeTab, sort, searchQuery]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Handlers
    const handleSearch = (query: string) => {
        setSearchQuery(query);
    };

    const handleAdd = (e?: React.MouseEvent) => {
        if (e) {
            setClickPosition({ x: e.clientX, y: e.clientY });
        }
        setIsAddModalOpen(true);
    };

    const handleTabChange = (tab: TabType) => {
        setActiveTab(tab);
    };

    const handleSortChange = (newSort: SortOption) => {
        setSort(newSort);
    };

    const handleViewChange = (newView: ViewMode) => {
        setView(newView);
    };

    const handleOpenItem = (item: LibraryItem) => {
        // Open the source URL in a new tab
        if (item.url) {
            window.open(item.url, "_blank", "noopener,noreferrer");
        }
    };

    const handleDeleteItem = async (item: LibraryItem) => {
        const confirmed = window.confirm(`Delete "${item.title}"? This cannot be undone.`);
        if (!confirmed) return;

        const success = await libraryService.deleteItem(item.id);
        if (success) {
            // Remove from local state
            setItems((prev) => prev.filter((i) => i.id !== item.id));
            // Update stats
            setStats((prev) => ({
                ...prev,
                all: Math.max(0, prev.all - 1),
                [item.type === "video" ? "videos" : item.type === "article" ? "articles" : item.type === "note" ? "notes" : "files"]:
                    Math.max(0, prev[item.type === "video" ? "videos" : item.type === "article" ? "articles" : item.type === "note" ? "notes" : "files"] - 1),
            }));
        }
    };

    const handleReprocess = (item: LibraryItem) => {
        // TODO: Implement re-processing logic
        console.log("Re-process:", item);
    };

    const handleModalClose = () => {
        setIsAddModalOpen(false);
        // Refresh data after adding
        fetchData();
    };

    return (
        <div className="max-w-[1200px] mx-auto">
            <LibraryHeader
                searchQuery={searchQuery}
                onSearch={handleSearch}
                onAdd={handleAdd}
            />

            <LibraryTabs
                activeTab={activeTab}
                stats={stats}
                onTabChange={handleTabChange}
            />

            <LibrarySortBar
                sort={sort}
                view={view}
                onSortChange={handleSortChange}
                onViewChange={handleViewChange}
            />

            <LibraryGrid
                items={items}
                viewMode={view}
                isLoading={isLoading}
                onOpen={handleOpenItem}
                onDelete={handleDeleteItem}
                onReprocess={handleReprocess}
                onAddSource={handleAdd}
            />

            <AddSourceModal
                isOpen={isAddModalOpen}
                onClose={handleModalClose}
                clickPosition={clickPosition}
            />
        </div>
    );
}
