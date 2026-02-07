const team = [
  {
    name: "Sarah Chen",
    role: "CEO & Co-Founder",
    bio: "Former estimator at Turner Construction. 12 years in commercial construction before founding Takeoffs.",
    initials: "SC",
  },
  {
    name: "Marcus Rivera",
    role: "CTO & Co-Founder",
    bio: "Ex-Google engineer. Built ML systems for document understanding and computer vision at scale.",
    initials: "MR",
  },
  {
    name: "James Okafor",
    role: "Head of Product",
    bio: "Previously led product at PlanGrid. Deep expertise in construction workflows and estimating tools.",
    initials: "JO",
  },
  {
    name: "Priya Sharma",
    role: "Lead Engineer",
    bio: "ML/CV specialist from MIT. Published research on automated blueprint analysis and structural recognition.",
    initials: "PS",
  },
];

export function Team() {
  return (
    <section id="team" className="relative bg-navy-950 py-24 md:py-32">
      {/* Subtle grid overlay */}
      <div className="pointer-events-none absolute inset-0 opacity-30">
        <div
          className="h-full w-full"
          style={{
            backgroundImage:
              "linear-gradient(rgba(106, 173, 224, 0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(106, 173, 224, 0.07) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />
      </div>

      <div className="relative z-10 mx-auto max-w-6xl px-6">
        {/* Section header */}
        <div className="mb-16 max-w-xl">
          <div className="mb-3 flex items-center gap-3">
            <div className="h-px w-8 bg-blueprint-400" />
            <span className="font-mono text-xs font-medium uppercase tracking-[0.2em] text-blueprint-400">
              Our Team
            </span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Built by people who&apos;ve{" "}
            <span className="text-blueprint-300">done the work.</span>
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-navy-400">
            Our team combines decades of construction industry experience with
            cutting-edge engineering. We&apos;ve sat in the estimating chair
            &mdash; and built the tech to change it.
          </p>
        </div>

        {/* Team grid */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {team.map((member) => (
            <div
              key={member.name}
              className="group rounded-lg border border-white/[0.06] bg-navy-900/40 p-6 transition-all hover:border-blueprint-400/20 hover:bg-navy-900/60"
            >
              {/* Avatar placeholder */}
              <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-sm border border-blueprint-400/20 bg-blueprint-500/10">
                <span className="font-mono text-sm font-bold tracking-wider text-blueprint-300">
                  {member.initials}
                </span>
              </div>

              <h3 className="text-lg font-bold text-white">{member.name}</h3>
              <div className="mt-1 font-mono text-xs font-medium uppercase tracking-wider text-blueprint-400">
                {member.role}
              </div>
              <p className="mt-3 text-sm leading-relaxed text-navy-400">
                {member.bio}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
