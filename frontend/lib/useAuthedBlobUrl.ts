"use client";

import { useEffect, useState } from "react";
import { fetchProtectedBlob } from "./api";

/** Fetches a protected file (image/audio) via an authenticated request and
 * exposes it as a local blob: URL, since <img src> can't carry an Authorization
 * header. Revokes the previous URL whenever the path changes or unmounts. */
export function useAuthedBlobUrl(path: string | null): { url: string | null; loading: boolean; error: string | null } {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!path) {
      setUrl(null);
      return;
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    setLoading(true);
    setError(null);

    fetchProtectedBlob(path)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  return { url, loading, error };
}
