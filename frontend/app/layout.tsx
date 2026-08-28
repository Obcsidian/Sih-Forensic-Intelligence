import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NetSherlock",
  description: "AI-assisted digital forensic triage",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
