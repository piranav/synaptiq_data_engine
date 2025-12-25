import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                canvas: "var(--canvas)",
                surface: "var(--surface)",
                elevated: "var(--elevated)",
                primary: "var(--text-primary)",
                secondary: "var(--text-secondary)",
                tertiary: "var(--text-tertiary)",
                border: "var(--border)",
                "border-subtle": "var(--border-subtle)",

                // Semantic
                accent: "var(--accent)",
                success: "var(--success)",
                warning: "var(--warning)",
                danger: "var(--danger)",

                // Graph
                "node-concept": "var(--node-concept)",
                "node-definition": "var(--node-definition)",
                "node-source": "var(--node-source)",
                "edge-relation": "var(--edge-relation)",
                "edge-inferred": "var(--edge-inferred)",
            },
            borderRadius: {
                sm: "var(--radius-sm)",
                md: "var(--radius-md)",
                lg: "var(--radius-lg)",
                xl: "var(--radius-xl)",
            },
            spacing: {
                1: "var(--space-1)",
                2: "var(--space-2)",
                3: "var(--space-3)",
                4: "var(--space-4)",
                5: "var(--space-5)",
                6: "var(--space-6)",
                8: "var(--space-8)",
                10: "var(--space-10)",
                12: "var(--space-12)",
                16: "var(--space-16)",
            },
            boxShadow: {
                card: "var(--shadow-card)",
                hover: "var(--shadow-hover)",
                elevated: "var(--shadow-elevated)",
            },
            fontSize: {
                display: ["48px", { lineHeight: "52px", letterSpacing: "-0.02em", fontWeight: "600" }],
                "title-1": ["32px", { lineHeight: "40px", letterSpacing: "-0.01em", fontWeight: "600" }],
                "title-2": ["24px", { lineHeight: "32px", letterSpacing: "-0.01em", fontWeight: "600" }],
                "title-3": ["20px", { lineHeight: "28px", letterSpacing: "0", fontWeight: "500" }],
                body: ["17px", { lineHeight: "26px", letterSpacing: "0", fontWeight: "400" }],
                "body-small": ["15px", { lineHeight: "22px", letterSpacing: "0", fontWeight: "400" }],
                callout: ["13px", { lineHeight: "18px", letterSpacing: "0.01em", fontWeight: "400" }],
                caption: ["11px", { lineHeight: "14px", letterSpacing: "0.02em", fontWeight: "500" }],
                mono: ["14px", { lineHeight: "20px", fontFamily: "SF Mono, ui-monospace, monospace" }],
            }
        },
    },
    plugins: [],
};
export default config;
