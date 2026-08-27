"use client";

import type { CaseStatus, ChainVerification, EvidenceFile } from "@/lib/types";

export default function StatusBar({
  evidence,
  chain,
  caseStatus,
}: {
  evidence: EvidenceFile[];
  chain: ChainVerification | null;
  caseStatus: CaseStatus;
}) {
  const hashed = evidence.filter((e) => e.sha256).length;

  return (
    <div className="glass-panel flex shrink-0 items-center gap-4 px-4 py-2 text-[11px] text-gray-400">
      <span className="flex items-center gap-1.5 text-emerald-300">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
        SHA-256 verified {hashed} / {evidence.length}
      </span>
      {chain && (
        <span className={`flex items-center gap-1.5 ${chain.valid ? "text-cyan-300" : "text-red-300"}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${chain.valid ? "bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]" : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.8)]"}`} />
          audit #{chain.total_entries} entries {chain.valid ? "chained" : "BROKEN"}
        </span>
      )}
      <span className="flex items-center gap-1.5 capitalize">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400/80" />
        case status: {caseStatus}
      </span>
      <span className="ml-auto text-gray-600">AI outputs are assistive — examiner verification required</span>
    </div>
  );
}