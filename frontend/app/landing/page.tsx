"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

export default function LandingPage() {
  const router = useRouter();

  const FEATURES = [
    {
      title: "Facial Recognition",
      desc: "Detect, cluster, and identify faces across large media collections using AI",
      icon: "◉",
      color: "text-cyan-300",
    },
    {
      title: "Speech-to-Text",
      desc: "Transcribe call recordings and voice notes for full-text searchable evidence",
      icon: "¶",
      color: "text-violet-300",
    },
    {
      title: "Semantic Search",
      desc: "Search across transcripts and messages using AI embeddings, not just keywords",
      icon: "⊕",
      color: "text-emerald-300",
    },
    {
      title: "Timeline Reconstruction",
      desc: "Merge calls, messages, GPS, and EXIF data into chronological investigation timeline",
      icon: "▶",
      color: "text-sky-300",
    },
    {
      title: "Anomaly Detection",
      desc: "Flag deleted-recovered files, briefly installed apps, and unusual patterns",
      icon: "⚠",
      color: "text-amber-300",
    },
    {
      title: "NSFW Pre-Screening",
      desc: "Flag sensitive media for priority human review without auto-classification",
      icon: "⊘",
      color: "text-rose-300",
    },
    {
      title: "Entity Graph",
      desc: "Auto-extract contacts and phone numbers, visualize communication relationships",
      icon: "◈",
      color: "text-indigo-300",
    },
    {
      title: "Chain of Custody",
      desc: "SHA-256 hashing and hash-chained audit log for tamper-evident evidence integrity",
      icon: "⧉",
      color: "text-cyan-300",
    },
  ];

  return (
    <div className="relative min-h-screen bg-[#0b0d12] overflow-hidden">
      {/* Background orbs */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute -top-40 -left-40 h-[500px] w-[500px] rounded-full bg-cyan-500/10 blur-[120px]" />
        <div className="absolute top-1/3 -right-40 h-[500px] w-[500px] rounded-full bg-violet-500/10 blur-[120px]" />
        <div className="absolute -bottom-40 left-1/3 h-[500px] w-[500px] rounded-full bg-teal-500/10 blur-[120px]" />
      </div>

      {/* Header */}
      <header className="relative z-10 flex items-center justify-between border-b border-white/5 px-8 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400/15 text-xl text-cyan-300 shadow-[0_0_30px_rgba(34,211,238,0.25)]">
            ◆
          </div>
          <div>
            <div className="text-xl font-bold tracking-tight text-white">ForensAI</div>
            <div className="text-[11px] uppercase tracking-[0.15em] text-gray-500">AI Forensic Intelligence</div>
          </div>
        </div>
        <button
          onClick={() => router.push("/login")}
          className="liquid-btn px-6 py-2.5 text-sm font-semibold"
        >
          Sign In
        </button>
      </header>

      {/* Hero */}
      <section className="relative z-10 mt-20 mb-16 flex flex-col items-center text-center px-4">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/5 px-4 py-1.5 text-xs font-medium text-cyan-300">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
          Open Source Digital Forensics Platform
        </div>
        <h1 className="mb-6 max-w-3xl text-5xl font-bold leading-tight tracking-tight text-white sm:text-6xl">
          Investigate faster.{" "}
          <span className="bg-gradient-to-r from-cyan-300 to-violet-300 bg-clip-text text-transparent">
            with AI intelligence.
          </span>
        </h1>
        <p className="mb-10 max-w-2xl text-lg text-gray-400">
          ForensAI is an open-source digital forensic platform that layers AI-driven triage and reporting on top of proven forensic ingestion. Cut investigation time from weeks to hours.
        </p>
        <div className="flex gap-4">
          <button
            onClick={() => router.push("/login")}
            className="liquid-btn px-8 py-3 text-base font-semibold"
          >
            Get Started
          </button>
          <button className="input-glass px-8 py-3 text-base font-medium text-gray-300 hover:text-white transition-colors">
            View Documentation
          </button>
        </div>
      </section>

      {/* Features Grid */}
      <section className="relative z-10 mx-auto w-full max-w-7xl px-6 pb-24">
        <h2 className="mb-2 text-center text-xs font-bold uppercase tracking-[0.2em] text-gray-500">Core Capabilities</h2>
        <p className="mb-12 text-center text-sm text-gray-500">Everything you need for modern digital forensic investigations</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="glass-card flex flex-col gap-3 p-5">
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg text-xl ${f.color} bg-white/5`}>
                {f.icon}
              </div>
              <div>
                <h3 className="mb-1 text-sm font-semibold text-white">{f.title}</h3>
                <p className="text-[12px] leading-relaxed text-gray-400">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/5 px-8 py-6">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <span>ForensAI — AI-assisted digital forensic triage</span>
          <span>Open Source · MIT License</span>
        </div>
      </footer>
    </div>
  );
}
