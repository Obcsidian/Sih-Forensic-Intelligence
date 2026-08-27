"use client";

import { useEffect, useState } from "react";

export default function LoadingScreen() {
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(true);
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    // Simulate loading progress
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          return 100;
        }
        // Smooth increment with slight randomness for natural feel
        const increment = Math.random() * 15 + 5;
        return Math.min(prev + increment, 100);
      });
    }, 80);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (progress >= 100) {
      setTimeout(() => setFadeOut(true), 200);
      setTimeout(() => setVisible(false), 700);
    }
  }, [progress]);

  if (!visible) return null;

  return (
    <div
      className={`fixed inset-0 z-[100] flex items-center justify-center bg-[#0b0d12] transition-opacity duration-500 ${
        fadeOut ? "opacity-0" : "opacity-100"
      }`}
    >
      {/* Background gradient */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -left-1/4 -top-1/4 h-[500px] w-[500px] rounded-full bg-cyan-500/10 blur-[100px] animate-pulse" />
        <div className="absolute -bottom-1/4 -right-1/4 h-[500px] w-[500px] rounded-full bg-violet-500/10 blur-[100px] animate-pulse" />
      </div>

      <div className="relative z-10 flex flex-col items-center gap-8">
        {/* Logo */}
        <div className="flex h-20 w-20 items-center justify-center rounded-2xl border border-cyan-400/30 bg-cyan-400/10 text-3xl text-cyan-300 shadow-[0_0_40px_rgba(34,211,238,0.3)] animate-pulse">
          ◆
        </div>

        {/* Brand name */}
        <div className="text-center">
          <div className="text-2xl font-bold tracking-tight text-white">ForensAI</div>
          <div className="mt-1 text-xs uppercase tracking-[0.2em] text-gray-500">
            AI Forensic Intelligence
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-48 overflow-hidden rounded-full bg-white/5">
          <div
            className="h-1 rounded-full bg-gradient-to-r from-cyan-400 to-violet-400 shadow-[0_0_10px_rgba(34,211,238,0.5)] transition-all duration-100 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Loading text */}
        <div className="text-[10px] uppercase tracking-widest text-gray-600">
          {progress < 30 && "Initializing..."}
          {progress >= 30 && progress < 60 && "Loading modules..."}
          {progress >= 60 && progress < 90 && "Preparing workspace..."}
          {progress >= 90 && "Almost ready..."}
        </div>
      </div>
    </div>
  );
}
