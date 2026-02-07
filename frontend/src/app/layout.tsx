import type { Metadata } from "next";
import { Barlow, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const barlow = Barlow({
  variable: "--font-barlow",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Takeoffs | Automated Construction Cost Estimation",
  description:
    "Takeoffs automates cost estimation for construction takeoffs. Upload plans, get accurate material quantities and cost estimates in minutes, not days.",
  keywords: [
    "construction estimating",
    "takeoff software",
    "cost estimation",
    "construction technology",
    "material quantities",
    "bid management",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="scroll-smooth">
      <body
        className={`${barlow.variable} ${ibmPlexMono.variable} font-heading antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
