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
    <div className="flex shrink-0 items-center gap-4 border-t border-border bg-panel px-3 py-1.5 text-[11px] text-gray-500">
      <span className="text-good">
        SHA-256 verified {hashed} / {evidence.length}
      </span>
      {chain && (
        <span className={chain.valid ? "text-accent" : "text-bad"}>
          audit #{chain.total_entries} entries {chain.valid ? "chained" : "BROKEN"}
        </span>
      )}
      <span className="capitalize">case status: {caseStatus}</span>
      <span className="ml-auto text-gray-600">AI outputs are assistive — examiner verification required</span>
    </div>
  );
}
