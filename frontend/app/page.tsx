"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Workspace from "@/components/Workspace";
import LoadingScreen from "@/components/LoadingScreen";

export default function Page() {
  const router = useRouter();
  const [showLoading, setShowLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    // Check token after loading screen
    setTimeout(() => {
      const storedToken = localStorage.getItem("forensai_token");
      setToken(storedToken);
      setShowLoading(false);
      
      if (!storedToken) {
        router.replace("/landing");
      }
    }, 1500);
  }, [router]);

  if (showLoading) {
    return <LoadingScreen />;
  }

  if (!token) {
    return null; // Will redirect to /landing
  }

  return <Workspace />;
}
