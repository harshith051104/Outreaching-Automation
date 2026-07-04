import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Outreach Platform",
  description: "Metadata-driven autonomous AI outreach platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}