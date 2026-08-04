"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { homepageImagesApi } from "@/lib/api/homepageImages";
import { planInterestApi } from "@/lib/api/planInterest";
import { announcementsApi } from "@/lib/api/announcements";

/**
 * Redesigned per direct reference screenshots: navy + gold (no red),
 * a real photograph in the hero, a services grid, a pricing-style
 * section, an FAQ accordion, and a fuller footer with contact/social
 * links — structurally following what was asked for. This pass adds a
 * real "how it works" sequence (the one place numbered steps are
 * actually justified — it's a genuine process, not decoration) and a
 * factual capability strip, rather than generic trust-badge filler.
 *
 * HONEST NOTE ON CONTENT, not just design: a few of the reference
 * site's own sections describe features that don't exist in this
 * codebase yet — a bookable one-time on-site collection team with its
 * own priced tiers. This page's copy describes what's ACTUALLY built
 * today (the four-ledger system, the two-approval safeguard, offline
 * support, MoMo/cash/bank on one ledger, role-based dashboards, real
 * memorial pages) rather than silently copying claims about
 * capabilities that aren't real yet — the pricing/booking section stays
 * "coming soon" rather than a live checkout, since building that for
 * real is its own separate, large piece of work, not something to fake.
 */
export default function HomePage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const hydrate = useAuthStore((s) => s.hydrate);
  const [checked, setChecked] = useState(false);
  const [faqOpen, setFaqOpen] = useState<number | null>(0);

  useEffect(() => {
    hydrate();
    setChecked(true);
  }, [hydrate]);

  useEffect(() => {
    if (checked && user) router.replace("/dashboard");
  }, [checked, user, router]);

  if (!checked || user) return null;

  return (
    <div className="nb-home">
      <style>{`
        .nb-home {
          --nb-navy: #0f2745;
          --nb-navy-deep: #081627;
          --nb-gold: #c9a227;
          --nb-gold-soft: #f2e6bf;
          --nb-cream: #f7f8fa;
          --nb-ink: #1a2433;
          --nb-ink-soft: #5b6675;
          font-family: "Inter", system-ui, sans-serif;
          color: var(--nb-ink);
          background: var(--nb-cream);
        }
        .nb-home h1, .nb-home h2, .nb-home .nb-display {
          font-family: "Fraunces", Georgia, serif;
        }
        .nb-card {
          transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
        }
        .nb-card:hover {
          transform: translateY(-3px);
          box-shadow: 0 12px 28px -12px rgba(15, 39, 69, 0.18);
          border-color: var(--nb-gold);
        }
        @media (prefers-reduced-motion: reduce) {
          .nb-card { transition: none; }
          .nb-card:hover { transform: none; }
        }
      `}</style>

      {/* ---------- Nav ---------- */}
      <nav className="sticky top-0 z-20 flex items-center justify-between border-b border-black/5 bg-white px-6 py-4 sm:px-10">
        <div className="flex items-center gap-2.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-512.png" alt="Nsaabodeɛ Smart" className="h-9 w-9 rounded-full object-cover" />
          <div>
            <p className="nb-display text-lg leading-tight text-[var(--nb-navy)]">Nsaabodeɛ Smart</p>
            <p className="text-[10px] uppercase tracking-wide text-[var(--nb-ink-soft)]">Wo Nsaa, Yɛn Adwuma</p>
          </div>
        </div>
        <div className="hidden items-center gap-8 text-sm font-medium text-[var(--nb-navy)] sm:flex">
          <a href="#home" className="border-b-2 border-[var(--nb-navy)] pb-1">Home</a>
          <a href="#how-it-works" className="hover:text-[var(--nb-gold)]">How It Works</a>
          <a href="#about" className="hover:text-[var(--nb-gold)]">About</a>
          <a href="#services" className="hover:text-[var(--nb-gold)]">Services</a>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm font-medium text-[var(--nb-navy)] hover:text-[var(--nb-gold)]">Login</Link>
          <a href="#contact" className="rounded-sm bg-[var(--nb-navy)] px-5 py-2.5 text-sm font-medium text-white hover:bg-[var(--nb-navy-deep)]">
            Contact Us
          </a>
        </div>
      </nav>

      {/* ---------- Hero ---------- */}
      <header id="home" className="bg-[var(--nb-navy)]">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-16 sm:px-10 sm:py-24 lg:grid-cols-2 lg:items-center">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-[var(--nb-gold)]/40 bg-white/5 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.15em] text-[var(--nb-gold)]">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--nb-gold)]" /> Built for Ghanaian community welfare
            </span>
            <h1 className="nb-display mt-5 text-4xl leading-[1.1] text-white sm:text-5xl">
              Every Contribution Counted.
              <br />
              <span className="text-[var(--nb-gold)]">Every Family Honoured.</span>
            </h1>
            <p className="mt-6 max-w-lg text-lg leading-relaxed text-white/75">
              Nsaabodeɛ Smart records every funeral contribution digitally — cash, Mobile
              Money, or bank — with a live ledger the whole family can see and a two
              -person safeguard before anyone is ever billed.
            </p>
            <div className="mt-9 flex flex-wrap gap-4">
              <Link href="/login" className="rounded-sm bg-[var(--nb-gold)] px-7 py-3 font-medium text-[var(--nb-navy-deep)] hover:brightness-110">
                Sign in to your community
              </Link>
              <a href="#how-it-works" className="rounded-sm border border-white/25 px-7 py-3 font-medium text-white hover:border-[var(--nb-gold)]">
                See how it works
              </a>
            </div>
          </div>

          <HeroImageRotator />
        </div>

        {/* Capability strip — real, factual claims about the system's own design, not fabricated usage numbers */}
        <div className="border-t border-white/10 bg-[var(--nb-navy-deep)]">
          <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-6 py-8 sm:px-10 lg:grid-cols-4">
            {STATS.map((s) => (
              <div key={s.label} className="text-center lg:text-left">
                <p className="nb-display text-3xl text-[var(--nb-gold)]">{s.value}</p>
                <p className="mt-1 text-xs uppercase tracking-wide text-white/60">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </header>

      {/* ---------- How it works — a real sequence, so numbering earns its place here ---------- */}
      <section id="how-it-works" className="mx-auto max-w-6xl px-6 py-20 sm:px-10 sm:py-28">
        <p className="text-center font-mono text-xs uppercase tracking-[0.3em] text-[var(--nb-gold)]">How It Works</p>
        <h2 className="nb-display mt-3 text-center text-3xl sm:text-4xl">From Request to Receipt</h2>
        <p className="mx-auto mt-4 max-w-2xl text-center text-[var(--nb-ink-soft)]">
          The actual safeguard behind every funeral opened on the platform — not a diagram of
          an idea, the real workflow every community follows.
        </p>
        <div className="mt-14 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, i) => (
            <div key={step.title} className="relative">
              <p className="nb-display text-5xl text-[var(--nb-gold-soft)]">{String(i + 1).padStart(2, "0")}</p>
              <h3 className="nb-display -mt-3 text-lg text-[var(--nb-navy)]">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--nb-ink-soft)]">{step.body}</p>
              {i < STEPS.length - 1 && (
                <div className="mt-6 hidden h-px w-full bg-gradient-to-r from-[var(--nb-gold)] to-transparent sm:block lg:hidden" />
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ---------- Services ---------- */}
      <section id="services" className="bg-white py-20 sm:py-28">
        <div className="mx-auto max-w-6xl px-6 sm:px-10">
          <p className="text-center font-mono text-xs uppercase tracking-[0.3em] text-[var(--nb-gold)]">Our Services</p>
          <h2 className="nb-display mt-3 text-center text-3xl sm:text-4xl">One Platform, Built Around How It Actually Works</h2>
          <p className="mx-auto mt-4 max-w-2xl text-center text-[var(--nb-ink-soft)]">
            The same safeguards and transparency, whether it's a Community Admin running
            things day to day or a Family Head opening a single funeral's ledger.
          </p>

          <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {SERVICES.map((s) => (
              <div key={s.title} className="nb-card rounded-sm border border-black/5 bg-[var(--nb-cream)] p-7" style={{ borderTop: "3px solid var(--nb-navy)" }}>
                <div className="flex h-11 w-11 items-center justify-center rounded-sm bg-[var(--nb-navy)] text-[var(--nb-gold)]">
                  <s.Icon />
                </div>
                <h3 className="nb-display mt-4 text-lg">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--nb-ink-soft)]">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Who we serve ---------- */}
      <section id="about" className="py-20 sm:py-28">
        <div className="mx-auto max-w-6xl px-6 sm:px-10">
          <p className="text-center font-mono text-xs uppercase tracking-[0.3em] text-[var(--nb-gold)]">Who We Serve</p>
          <h2 className="nb-display mt-3 text-center text-3xl sm:text-4xl">Every Kind of Community</h2>
          <div className="mt-14 grid gap-6 sm:grid-cols-2">
            {SEGMENTS.map((seg) => (
              <div key={seg.title} className="nb-card rounded-sm border border-black/5 bg-white p-7">
                <div className="flex h-11 w-11 items-center justify-center rounded-sm bg-[var(--nb-gold-soft)] text-[var(--nb-navy)]">
                  <seg.Icon />
                </div>
                <h3 className="nb-display mt-4 text-lg">{seg.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--nb-ink-soft)]">{seg.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <CommunityNewsSection />

      {/* ---------- Pricing-style section (forward-looking, not a live checkout yet) ---------- */}
      <section className="bg-[var(--nb-navy)] py-20 sm:py-28">
        <div className="mx-auto max-w-6xl px-6 sm:px-10">
          <p className="text-center font-mono text-xs uppercase tracking-[0.3em] text-[var(--nb-gold)]">Coming Soon</p>
          <h2 className="nb-display mt-3 text-center text-3xl text-white sm:text-4xl">Choose How Long You Need It</h2>
          <p className="mx-auto mt-4 max-w-2xl text-center text-white/70">
            Most communities run Nsaabodeɛ Smart as an ongoing platform. For a single
            funeral, a short-term plan is on its way too — set up in minutes, active only
            as long as you actually need it.
          </p>
          <div className="mt-14 grid gap-6 lg:grid-cols-3">
            {PLANS.map((p) => <PlanCard key={p.name} plan={p} />)}
          </div>
        </div>
      </section>

      {/* ---------- FAQ ---------- */}
      <section className="mx-auto max-w-4xl px-6 py-20 sm:px-10 sm:py-28">
        <p className="text-center font-mono text-xs uppercase tracking-[0.3em] text-[var(--nb-gold)]">Frequently Asked Questions</p>
        <h2 className="nb-display mt-3 text-center text-3xl sm:text-4xl">Got Questions?</h2>
        <div className="mt-12 space-y-3">
          {FAQS.map((faq, i) => (
            <div key={faq.q} className="rounded-sm border border-black/10 bg-white">
              <button
                onClick={() => setFaqOpen(faqOpen === i ? null : i)}
                className="flex w-full items-center justify-between px-6 py-4 text-left font-medium"
              >
                {faq.q}
                <span className="text-[var(--nb-gold)]">{faqOpen === i ? "−" : "+"}</span>
              </button>
              {faqOpen === i && <p className="px-6 pb-4 text-sm leading-relaxed text-[var(--nb-ink-soft)]">{faq.a}</p>}
            </div>
          ))}
        </div>
      </section>

      {/* ---------- Footer ---------- */}
      <footer id="contact" className="bg-[var(--nb-navy-deep)] py-16 text-white/70">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 sm:grid-cols-4 sm:px-10">
          <div className="sm:col-span-2">
            <div className="flex items-center gap-2.5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-512.png" alt="Nsaabodeɛ Smart" className="h-8 w-8 rounded-full object-cover" />
              <h3 className="nb-display text-lg text-white">Nsaabodeɛ Smart</h3>
            </div>
            <p className="mt-3 max-w-sm text-sm leading-relaxed">
              Digital funeral welfare management for Ghanaian communities — every ledger
              transparent, every contribution accounted for.
            </p>
          </div>
          <div>
            <h3 className="font-mono text-xs uppercase tracking-widest text-white">Contact</h3>
            <p className="mt-3 text-sm">Accra, Ghana</p>
            <p className="mt-1 text-sm">Powered by Desward Group Ltd</p>
          </div>
          <div>
            <h3 className="font-mono text-xs uppercase tracking-widest text-white">Platform</h3>
            <div className="mt-3 flex flex-col gap-2 text-sm">
              <Link href="/login" className="hover:text-[var(--nb-gold)]">Sign in</Link>
              <a href="#how-it-works" className="hover:text-[var(--nb-gold)]">How it works</a>
              <a href="#services" className="hover:text-[var(--nb-gold)]">Services</a>
              <a href="#about" className="hover:text-[var(--nb-gold)]">About</a>
            </div>
          </div>
        </div>
        <p className="mt-12 border-t border-white/10 pt-8 text-center text-xs text-white/40">© 2026 Nsaabodeɛ Smart. All rights reserved.</p>
      </footer>
    </div>
  );
}

/**
 * "The homepage live pictures which will be changing should be
 * uploaded by the super admin." Replaces what used to be a single
 * hotlinked stock photo (which broke in real use — external hotlinks
 * are exactly this fragile) with real images stored on the platform's
 * own server, rotating automatically. Falls back to a tasteful pattern
 * when nothing's been uploaded yet — a fresh deployment starts with
 * zero images, the same way it starts with zero communities.
 */
/**
 * "When it needs it on the homepage he has to send a request to the
 * platform admin." A community admin requests homepage placement when
 * submitting an announcement; a platform admin decides whether to
 * actually grant it, independent of ordinary Notice Board approval.
 * Renders nothing at all when no community has ever been granted
 * placement — a fresh deployment starts with none, the same way it
 * starts with zero communities and zero homepage images.
 */
function CommunityNewsSection() {
  const { data: featured } = useQuery({ queryKey: ["homepage-featured-announcements"], queryFn: announcementsApi.homepageFeatured });
  if (!featured || featured.length === 0) return null;

  return (
    <section className="bg-white py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-6 sm:px-10">
        <p className="text-center font-mono text-xs uppercase tracking-[0.3em] text-[var(--nb-gold)]">Community News</p>
        <h2 className="nb-display mt-3 text-center text-3xl sm:text-4xl">From Our Communities</h2>
        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {featured.map((a) => (
            <div key={a.id} className="nb-card rounded-sm border border-black/5 bg-[var(--nb-cream)] p-7" style={{ borderTop: "3px solid var(--nb-gold)" }}>
              {a.image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={a.image_url} alt="" className="mb-4 h-36 w-full rounded-sm object-cover" />
              )}
              <p className="font-mono text-xs uppercase tracking-wide text-[var(--nb-gold)]">{a.community_name}</p>
              <h3 className="nb-display mt-2 text-lg">{a.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--nb-ink-soft)]">{a.content}</p>
              {a.video_url && (
                <a href={a.video_url} target="_blank" rel="noreferrer" className="mt-3 inline-block text-sm text-[var(--nb-navy)] hover:text-[var(--nb-gold)]">
                  Watch video →
                </a>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function HeroImageRotator() {
  const { data: images } = useQuery({ queryKey: ["homepage-images-public"], queryFn: homepageImagesApi.listPublic });
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!images || images.length < 2) return;
    const timer = setInterval(() => setIndex((i) => (i + 1) % images.length), 6000);
    return () => clearInterval(timer);
  }, [images]);

  const current = images && images.length > 0 ? images[index % images.length] : null;

  return (
    <div className="relative overflow-hidden rounded-sm border border-white/10 shadow-2xl">
      {current?.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img key={current.id} src={current.image_url} alt={current.caption || ""} className="h-[420px] w-full object-cover sm:h-[480px]" />
      ) : (
        <div className="flex h-[420px] w-full items-center justify-center bg-gradient-to-br from-[var(--nb-navy)] to-[var(--nb-navy-deep)] sm:h-[480px]">
          <BadgeMark className="h-24 w-24 text-[var(--nb-gold)] opacity-40" />
        </div>
      )}
      {(current?.caption || current?.subcaption) && (
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-6">
          {current.caption && <p className="nb-display text-2xl text-white">{current.caption}</p>}
          {current.subcaption && <p className="mt-1 text-sm text-white/70">{current.subcaption}</p>}
        </div>
      )}
      {images && images.length > 1 && (
        <div className="absolute bottom-3 right-4 flex gap-1.5">
          {images.map((img, i) => (
            <span key={img.id} className={`h-1.5 w-1.5 rounded-full ${i === index ? "bg-[var(--nb-gold)]" : "bg-white/40"}`} />
          ))}
        </div>
      )}
    </div>
  );
}

function BadgeMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden="true">
      <path d="M20 3l14 6v11c0 9-6 15.5-14 17-8-1.5-14-8-14-17V9z" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="20" cy="18" r="5" fill="none" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}
/**
 * "Make sure all coming soon are completely designed." Replaces what
 * used to be a single disabled grey button with a real, working form —
 * genuine lead capture the platform admin can act on, not a decoration
 * pretending a checkout exists that doesn't.
 */
function PlanCard({ plan }: { plan: (typeof PLANS)[number] }) {
  const [expanded, setExpanded] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await planInterestApi.submit({ plan_type: plan.planType, name, email: email || undefined, phone: phone || undefined });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit — please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={`rounded-sm border p-8 ${plan.featured ? "border-[var(--nb-gold)] bg-white shadow-lg" : "border-white/10 bg-white/[0.03]"}`}>
      {plan.featured && (
        <span className="rounded-full bg-[var(--nb-gold)] px-3 py-1 text-xs font-medium text-[var(--nb-navy-deep)]">Most requested</span>
      )}
      <h3 className={`nb-display mt-3 text-xl ${plan.featured ? "" : "text-white"}`}>{plan.name}</h3>
      <p className={`mt-1 text-sm ${plan.featured ? "text-[var(--nb-ink-soft)]" : "text-white/60"}`}>{plan.tagline}</p>
      <p className={`nb-display mt-4 text-3xl ${plan.featured ? "" : "text-white"}`}>{plan.duration}</p>
      <ul className={`mt-5 space-y-2 text-sm ${plan.featured ? "text-[var(--nb-ink-soft)]" : "text-white/60"}`}>
        {plan.features.map((f) => (
          <li key={f} className="flex gap-2"><CheckIcon className="mt-0.5 shrink-0 text-[var(--nb-gold)]" /> {f}</li>
        ))}
      </ul>

      {submitted ? (
        <p className="mt-6 rounded-sm bg-[var(--nb-gold-soft)] px-4 py-3 text-center text-sm text-[var(--nb-navy)]">
          Thanks — we&apos;ll be in touch once this plan is available.
        </p>
      ) : !expanded ? (
        <button
          onClick={() => setExpanded(true)}
          className={`mt-6 w-full rounded-sm border py-2.5 text-sm font-medium transition ${
            plan.featured
              ? "border-[var(--nb-navy)] text-[var(--nb-navy)] hover:bg-[var(--nb-navy)] hover:text-white"
              : "border-white/25 text-white hover:border-[var(--nb-gold)] hover:text-[var(--nb-gold)]"
          }`}
        >
          Notify me when it&apos;s ready
        </button>
      ) : (
        <form onSubmit={submit} className="mt-6 space-y-2">
          <input
            required value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name"
            className="w-full rounded-sm border border-black/10 bg-white px-3 py-2 text-sm text-[var(--nb-ink)] outline-none focus:border-[var(--nb-navy)]"
          />
          <input
            value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email"
            className="w-full rounded-sm border border-black/10 bg-white px-3 py-2 text-sm text-[var(--nb-ink)] outline-none focus:border-[var(--nb-navy)]"
          />
          <input
            value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone (instead of email is fine too)"
            className="w-full rounded-sm border border-black/10 bg-white px-3 py-2 text-sm text-[var(--nb-ink)] outline-none focus:border-[var(--nb-navy)]"
          />
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={submitting || !name.trim() || (!email.trim() && !phone.trim())}
            className="w-full rounded-sm bg-[var(--nb-gold)] py-2.5 text-sm font-medium text-[var(--nb-navy-deep)] disabled:opacity-60"
          >
            {submitting ? "Submitting…" : "Register interest"}
          </button>
        </form>
      )}
    </div>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return <svg viewBox="0 0 16 16" className={`h-4 w-4 ${className}`} fill="currentColor"><circle cx="8" cy="8" r="7" fillOpacity="0.15" /><path d="M4.5 8.2l2.2 2.2 4.5-4.8" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>;
}
function IconLedger() { return <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3.5" y="2.5" width="13" height="15" rx="1" /><path d="M7 7h6M7 10.5h6M7 14h3" /></svg>; }
function IconApproval() { return <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 2.5l6 2.3v5c0 4-2.6 7-6 7.7-3.4-.7-6-3.7-6-7.7v-5z" /><path d="M7.3 10l2 2 3.4-3.6" /></svg>; }
function IconPhone() { return <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="5.5" y="2.5" width="9" height="15" rx="1.5" /><path d="M8.5 15.5h3" /></svg>; }
function IconOffline() { return <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M16.5 8.5A6.5 6.5 0 005 5.6M3.5 4v3h3M3.5 11.5A6.5 6.5 0 0015 14.4M16.5 16v-3h-3" /></svg>; }
function IconMemorial() { return <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 2.5v6M6 8.5h8l1.5 9h-11z" /><path d="M4 17.5h12" /></svg>; }
function IconShield() { return <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 2.5l6 2.3v5c0 4-2.6 7-6 7.7-3.4-.7-6-3.7-6-7.7v-5z" /></svg>; }
function IconFamily() { return <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 2.5l7 4v7l-7 4-7-4v-7z" /></svg>; }
function IconChurch() { return <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 2v3M6 9V6l4-2 4 2v3M4 18h12M5 18V9h10v9" /></svg>; }
function IconCorporate() { return <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="4" y="3" width="12" height="15" rx="1" /><path d="M7 7h1M12 7h1M7 10.5h1M12 10.5h1" /></svg>; }
function IconGlobe() { return <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="10" cy="10" r="7.5" /><path d="M2.5 10h15M10 2.5c2.2 2 3.5 4.8 3.5 7.5s-1.3 5.5-3.5 7.5c-2.2-2-3.5-4.8-3.5-7.5S7.8 4.5 10 2.5z" /></svg>; }

const STATS = [
  { value: "4", label: "Separate ledgers, never mixed" },
  { value: "2", label: "Approvals before any billing" },
  { value: "3", label: "Payment methods, one ledger" },
  { value: "0", label: "Signal required at the front desk" },
];

const STEPS = [
  { title: "Family requests", body: "A Family Head opens a request to start collecting for a funeral — nothing is billed yet." },
  { title: "Two leaders confirm", body: "A second and third community leader review and approve before a single member owes anything." },
  { title: "Collectors record", body: "Cash, Mobile Money, or bank — every payment lands on the same live ledger, online or off." },
  { title: "Family sees it live", body: "Contributions, gifts, and balances update in real time, visible to exactly who's meant to see them." },
];

const SERVICES = [
  { title: "Four-Ledger Transparency", body: "Family dues, community dues, town elders, and guest gifts — tracked separately, never mixed, exactly the way the community already runs it.", Icon: IconLedger },
  { title: "Two-Approval Safeguard", body: "A family head requests a funeral opening; two community leaders confirm it before a single member is billed.", Icon: IconApproval },
  { title: "Cash, MoMo & Bank", body: "A member pays however they actually pay, and it lands on the same ledger — no separate systems to reconcile.", Icon: IconPhone },
  { title: "Works With No Signal", body: "The front desk keeps taking cash payments offline, syncing automatically the moment a connection returns.", Icon: IconOffline },
  { title: "Memorial Pages", body: "A dignified public page per funeral — no login needed to view it or leave a tribute, with event details and a place to remember.", Icon: IconMemorial },
  { title: "Private & Auditable", body: "Every entry is time-stamped; gift and donation totals stay visible only to the family and community admin, never the whole committee.", Icon: IconShield },
];

const SEGMENTS = [
  { title: "Family Welfare Societies", body: "The core of what Nsaabodeɛ Smart runs today — a full community, its families, its funerals, all in one place.", Icon: IconFamily },
  { title: "Church & Religious Organizations", body: "Help a congregation collect and manage member funeral support with the same transparency.", Icon: IconChurch },
  { title: "Corporate Bereavement Support", body: "Let a company's own welfare fund run through the same ledger discipline.", Icon: IconCorporate },
  { title: "Diaspora Families", body: "Family abroad can log in and see the same live totals and receipts as everyone at home.", Icon: IconGlobe },
];

const PLANS = [
  { planType: "single_funeral", name: "Single Funeral", tagline: "For one family, one event", duration: "Short-term access", featured: false, features: ["Full four-ledger system", "Front desk, cash & MoMo", "Instant receipts", "Access for the funeral's duration"] },
  { planType: "community", name: "Community", tagline: "Ongoing, for an established society", duration: "Always-on", featured: true, features: ["Everything in Single Funeral", "Unlimited concurrent funerals", "All role dashboards", "Offline-capable front desk"] },
  { planType: "multi_community", name: "Multi-Community", tagline: "For an organization running several", duration: "Platform-wide", featured: false, features: ["Everything in Community", "Platform Admin oversight console", "Isolated data per community", "Priority support"] },
];

const FAQS = [
  { q: "What is Nsaabodeɛ Smart?", a: "A digital funeral welfare management platform built specifically around how Ghanaian community funeral societies actually run — family ledgers, community ledgers, town elders, and guest gifts, kept separate and transparent." },
  { q: "Can family abroad follow the contributions?", a: "Yes — anyone with a login sees the same live totals and receipts, wherever they are." },
  { q: "Can donors pay with Mobile Money?", a: "Yes — MoMo, cash, and bank all record onto the same ledger." },
  { q: "How secure is our information?", a: "Every community's data is completely isolated from every other community on the platform, and every entry is time-stamped and auditable." },
  { q: "What happens if a payment is recorded against the wrong person?", a: "An authorized officer can request a correction, which a second officer must approve before it takes effect — the same two-person safeguard used everywhere else, with a permanent record of who changed what and why." },
  { q: "Does it work at the funeral itself, with no internet?", a: "Yes — the front desk keeps recording cash payments offline and syncs everything automatically the moment a connection comes back." },
];
