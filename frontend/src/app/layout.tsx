import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Clone Platform",
  description: "Create intelligent AI personas from your content",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="bg-[#08080f] text-zinc-100 min-h-screen antialiased">{children}</body>
    </html>
  );
}
