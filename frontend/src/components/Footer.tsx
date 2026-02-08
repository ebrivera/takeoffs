import Image from "next/image";

export function Footer() {
  return (
    <footer id="contact" className="blueprint-grid-dark relative border-t border-white/5">
      <div className="relative z-10">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <div className="rounded-2xl border border-white/65 bg-white/68 p-4 shadow-[0_16px_48px_rgba(17,17,17,0.08)] backdrop-blur-sm md:p-5">
            <div className="flex flex-row flex-wrap items-center justify-between gap-3 pb-3">
              <h2 className="text-3xl font-normal tracking-tight text-navy-950 sm:text-4xl">
                Ready to stop counting manually?
              </h2>
              <a
                href="mailto:hello@cantena.dev"
                className="inline-flex shrink-0 items-center justify-center gap-2 rounded-sm bg-accent-500 px-5 py-2.5 text-sm font-bold tracking-wide text-white transition-all hover:bg-accent-400 hover:shadow-md hover:shadow-accent-500/20 sm:px-6 sm:py-3"
              >
                Request a Demo
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 14 14"
                  fill="none"
                >
                  <path
                    d="M1 7h12m0 0L8 2m5 5L8 12"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </a>
            </div>

            <div className="mt-3 border-t border-white/5 pt-3">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div className="mt-2 max-w-[220px] shrink-0">
                  <Image
                    src="/branding/cantena-logo-black-cropped.png"
                    alt="Cantena"
                    width={490}
                    height={170}
                    className="h-auto w-full"
                  />
                </div>
                <p className="ml-auto text-right font-mono text-xs text-navy-800">
                  &copy; {new Date().getFullYear()} Cantena, Inc. All rights
                  reserved.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
