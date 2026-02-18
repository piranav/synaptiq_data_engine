"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { AUTH_STATE_CHANGED_EVENT, User, authService } from "@/lib/api/auth";
import { useRouter } from "next/navigation";

interface AuthContextType {
    user: User | null;
    isLoading: boolean;
    logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(() => authService.getUser());
    const [isLoading] = useState(false);
    const router = useRouter();

    useEffect(() => {
        const syncUserFromStorage = () => {
            setUser(authService.getUser());
        };

        syncUserFromStorage();
        void authService.syncCurrentUser();
        window.addEventListener(AUTH_STATE_CHANGED_EVENT, syncUserFromStorage);
        window.addEventListener("storage", syncUserFromStorage);

        return () => {
            window.removeEventListener(AUTH_STATE_CHANGED_EVENT, syncUserFromStorage);
            window.removeEventListener("storage", syncUserFromStorage);
        };
    }, []);

    const logout = async () => {
        await authService.logout();
        router.push("/login");
    };

    return (
        <AuthContext.Provider value={{ user, isLoading, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}
