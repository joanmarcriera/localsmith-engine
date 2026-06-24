# Localsmith — Portfolio Release Design

_Spec, 2026-06-24. Brainstormed with Marc. Status: awaiting Marc's review._

## Goal & success criteria

Ship the existing **AI-workflow orchestrator** ("Localsmith") as a **portfolio / lead-gen asset**
for Marc's AI/cloud-architect job hunt. Success = credibility and attention that lead to interviews:
GitHub stars, a strong write-up that hiring managers and r/selfhosted both respect, and a repo Marc
can point to in applications. **Monetisation is secondary** (a "hire me / sponsor / coffee" CTA, not
a paid product).

Lead angle = **employability-first**: cost-engineered LLM orchestration + pragmatic/auditable design
(the signals hiring managers value), with local-first/privacy and homelab-native as supporting depth.
All four angles appear; the *narrative order* leads with the architect signals.

## Scope

**In:** repackaging + repositioning the *existing, working* engine (stdlib Python + bash, ~25 tests,
JSONL cost ledger, resumable `scaffold→plan→implement→verify` pipeline) for a credible public release.

**Not building:** the engine itself (it exists and works). **Dropping:** the £99 Pro paywall, license
validation, the queue-dashboard UI, multi-tenant/hosted modes (all YAGNI for a portfolio asset).

**The Z.AI change:** the old pitch ("cents, not credits") depended on Z.AI GLM at the implement step,
now cancelled. Reframe to **"free & private, not metered credits"** — the implement step defaults to
**local Ollama**, or routes through Marc's **TrueNAS LiteLLM gateway** (~10 free-tier providers:
Groq/Cerebras/Gemini-flash/OpenRouter-free/…). This is a *stronger* story, not a weaker one.

## Deliverables

### 1. Public engine repo — `joanmarcriera/localsmith` (public, MIT)
- **Clean extraction** from `~/Documents/Claude/Projects/AI workflow` into a *fresh* repo — no
  secret-bearing git history. Scrub: the dead `ZAI_API_KEY` + `BRAVE_API_SEARCH` in `.env`
  (gitignore `.env`, ship `.env.example`), any personal paths in the launchd plist, real hostnames.
- `LICENSE` (MIT), `.gitignore`, `CONTRIBUTING.md` (light), the existing setup wizard.
- **Reconfigure providers:** implement step → local Ollama default; optional `LITELLM_BASE_URL`
  pointing at a LiteLLM gateway for free-tier cloud. Remove Z.AI as a named provider.
- All tests green from a clean checkout (`make test` or documented command).
- Naming: rename the current **private** landing repo `joanmarcriera/localsmith` → `localsmith-web`
  first, to free the name for the engine (the star of the show).

### 2. README (employability-first, 4 angles)
Structure: hero (cost-engineered orchestration, the `£0` cost-ledger demo) → how it works (pragmatic
pipeline diagram, "one stage costs money, now often £0") → local-first/privacy → homelab-native →
quickstart → architecture link → demo embed → "hire me / sponsor" footer. Badges (license, tests).

### 3. `docs/ARCHITECTURE.md` — the case-study centerpiece
The principal-engineer deep-dive: the cost-routing strategy + math (per-stage model selection, the
free-tier/local fallback ladder), **why plain bash+Python over LangGraph/Temporal**, the resumable
idempotent `state.json` machine, the verify/quality gates, trade-offs and what Marc would do at scale.

### 4. Demo
- `asciinema` recording: one idea file → verified repo → cost ledger showing `£0`.
- A reproducible `make demo` (deterministic-ish sample idea) so anyone can run it. Embed in README.

### 5. Write-up + launch copy
- One **long-form architecture post** (the story), hosted on Marc's site (Pages CNAME, e.g.
  `localsmith.riera.co.uk`, via `cf.py`).
- Cross-post copy: HN ("Show HN"), r/selfhosted, LinkedIn, dev.to — updated post-Z.AI. Reuse/refresh
  the existing launch copy in `candidates/ai-workflow-product/dist/launch/`.

### 6. Landing reposition (`~/code/localsmith/index.html`)
- "cents, not credits" → **"free & private, not metered credits"**; fix the hero terminal demo
  (`implement` line) to show free-tier/local instead of `z.ai glm-4.6 $0.014`.
- Replace the **£99 Pro tier** with a **"Hire me / sponsor"** CTA + link to the repo. Keep the
  Lemon Squeezy "buy me a coffee" as the only money ask.
- Deploys via the existing CI to `localsmith.joanmarcriera.es` (or the new Pages CNAME).

## Key decisions (defaults — change at review)
- **Repo:** `joanmarcriera/localsmith` public, MIT. Rename existing private landing → `localsmith-web`.
- **Source strategy:** fresh repo from a scrubbed copy (not `git filter-branch` on existing history —
  the AI-workflow dir isn't yet a git repo, so a clean copy is simplest and safest).
- **Implement provider:** local Ollama default; free-tier cloud via LiteLLM gateway optional.
- **Money ask:** coffee/sponsor + "hire me" only; no paid Pro.

## Risks & mitigations
- **Secret leakage** → fresh repo (no history), `.env` gitignored, **gitleaks pre-commit** (now global)
  scans every commit, manual `git ls-files` review before first `gh repo create --public`.
- **Over-claiming** → the demo must be genuinely reproducible; the cost-ledger numbers must be real
  (free-tier/local), not the old Z.AI figure.
- **"Just another agent"** → differentiation is the *cost-routing + self-hosted + auditable* angle,
  made explicit in README/architecture; don't compete on raw capability with Claude Code/aider.

## Build order (for the plan)
1. Scrub + extract clean repo; reconfigure providers; tests green.
2. README + ARCHITECTURE.md.
3. Demo (asciinema + `make demo`).
4. Landing reposition + deploy.
5. Write-up + cross-post copy.
6. Make repo public; publish write-up; post.
