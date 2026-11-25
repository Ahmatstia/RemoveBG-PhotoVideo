import type { Metadata } from "next";
import { JobActivityCenter } from "@/components/job-activity-center";
import "./globals.css";

export const metadata: Metadata = {
  title: "MyTools — Studio lokal",
  description: "Studio lokal untuk mengolah foto, video, transkrip, dan unduhan.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <body>{children}<JobActivityCenter /></body>
    </html>
  );
}
