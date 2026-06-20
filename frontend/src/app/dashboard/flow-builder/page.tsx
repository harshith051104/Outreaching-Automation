"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function FlowBuilderRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-screen text-slate-400 text-sm">
      Redirecting to dashboard...
    </div>
  );
}
