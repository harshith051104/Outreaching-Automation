import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Outreach Platform",
  description: "AI-powered outreach automation with CrewAI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}