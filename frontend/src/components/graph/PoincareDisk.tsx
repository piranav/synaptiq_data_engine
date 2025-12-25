"use client";

import { useEffect, useRef } from "react";

export function PoincareDisk() {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        let animationFrameId: number;
        let time = 0;

        const render = () => {
            time += 0.005;
            const width = canvas.width;
            const height = canvas.height;
            const centerX = width / 2;
            const centerY = height / 2;
            const radius = Math.min(width, height) * 0.4;

            // Clear
            ctx.clearRect(0, 0, width, height);

            // Draw Disk Boundary
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
            ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
            ctx.lineWidth = 2;
            ctx.stroke();

            // Draw some moving nodes/arcs to simulate hyperbolic geometry
            for (let i = 0; i < 5; i++) {
                const offset = (i / 5) * Math.PI * 2;
                const x = centerX + Math.cos(time + offset) * (radius * 0.5);
                const y = centerY + Math.sin(time + offset) * (radius * 0.5);

                ctx.beginPath();
                ctx.arc(x, y, 4, 0, Math.PI * 2);
                ctx.fillStyle = "rgba(99, 102, 241, 0.8)"; // Indigo (concept color)
                ctx.fill();

                // Connect to center
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.quadraticCurveTo(
                    centerX + Math.cos(time + offset + Math.PI / 2) * (radius * 0.2),
                    centerY + Math.sin(time + offset + Math.PI / 2) * (radius * 0.2),
                    x, y
                );
                ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
                ctx.lineWidth = 1;
                ctx.stroke();
            }

            animationFrameId = requestAnimationFrame(render);
        };

        const resize = () => {
            const parent = canvas.parentElement;
            if (parent) {
                canvas.width = parent.clientWidth;
                canvas.height = parent.clientHeight;
            }
        };

        window.addEventListener("resize", resize);
        resize();
        render();

        return () => {
            window.removeEventListener("resize", resize);
            cancelAnimationFrame(animationFrameId);
        };
    }, []);

    return (
        <div className="w-full h-full flex items-center justify-center bg-[#1C1C1E] relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-black/50 to-transparent pointer-events-none" />
            <canvas ref={canvasRef} className="w-full h-full" />
        </div>
    );
}
