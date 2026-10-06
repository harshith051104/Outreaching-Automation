import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "Tasks & AI Suggestions Hub",
  description: "Standalone Tasks & Suggestions Management Portal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        style={{
          margin: 0,
          padding: 0,
          backgroundColor: "#0b0f19",
          color: "#f8fafc",
          fontFamily: "'Inter', sans-serif",
          minHeight: "100vh",
        }}
      >
        <Navbar />
        <main style={{ padding: "24px", maxWidth: "1400px", margin: "0 auto" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
