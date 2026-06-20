"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import Sidebar from "@/components/layout/sidebar";
import { Zap } from "lucide-react";

// Pages that need zero padding (full-bleed)
const FULL_BLEED_PAGES = ["/dashboard/chatbot"];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loadFromStorage } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();
  const [isInitializing, setIsInitializing] = useState(true);

  const isFullBleed = FULL_BLEED_PAGES.includes(pathname);

  useEffect(() => {
    loadFromStorage();
    setIsInitializing(false);
  }, [loadFromStorage]);

  useEffect(() => {
    if (!isInitializing && !user) {
      router.push("/login");
    }
  }, [user, isInitializing, router]);

  if (isInitializing || !user) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh',
        background: 'linear-gradient(145deg, #060413 0%, #0d0823 100%)',
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '14px',
            background: 'linear-gradient(135deg, #7c5cff, #a78bfa)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: '0 8px 24px rgba(124,92,255,0.4)',
            animation: 'float 2s ease-in-out infinite',
          }}>
            <Zap size={22} color="white" strokeWidth={2.5} />
          </div>
          <style>{`
            @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)} }
          `}</style>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      background: 'transparent',
      overflow: 'hidden',
    }}>
      <Sidebar />
      <main style={{
        flex: 1,
        overflowY: 'auto',
        overflowX: 'hidden',
        padding: isFullBleed ? '0' : '0',
        position: 'relative',
      }}>
        {children}
      </main>
    </div>
  );
}