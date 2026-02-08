import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

const professionalSans = IBM_Plex_Sans({
  variable: "--font-josefin",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Cantena | Automated Construction Cost Estimation",
  description:
    "Cantena automates cost estimation for construction takeoffs. Upload plans, get accurate material quantities and cost estimates in minutes, not days.",
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
        className={`${professionalSans.variable} ${ibmPlexMono.variable} font-heading antialiased`}
      >
        {/* Fixed background image layer (content scrolls over it) */}
        <div
          aria-hidden="true"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 0,
            pointerEvents: "none",
            backgroundColor: "#efefeb",
            backgroundImage:
              "url('/backgrounds/construction-plan-bg.jpg?v=20260208-3')",
            backgroundPosition: "center center",
            backgroundRepeat: "no-repeat",
            backgroundSize: "cover",
          }}
        />
        <div className="relative z-[1]">{children}</div>
      </body>
    </html>
  );
}
