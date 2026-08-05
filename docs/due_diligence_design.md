# Mainline A: HK IPO Due Diligence Design

## Product boundary

The system accepts a company name and a Hong Kong IPO prospectus, then produces:

1. an evidence-grounded company due diligence report;
2. a prioritized P0/P1/P2 follow-up due diligence checklist;
3. an evidence ledger and reproducible financial calculation trail.

It does not recommend an investment amount, valuation ceiling, holding period, or exit plan. Post-listing price prediction is outside Mainline A.

## Three governing questions

All research must answer one of three questions:

1. **Past and present financial quality:** Has the company earned money, converted profit into cash, and maintained a sound balance sheet?
2. **Future earning power:** What does the company sell, why do customers pay, and can it earn sustainably in its industry structure?
3. **Material negative risk:** Are there financial, legal, governance, concentration, valuation, liquidity, or reputation issues that undermine the company case?

## Agent boundary

### Due Diligence Lead

- Plans company-specific tasks and evidence requirements.
- Controls task and follow-up budgets.
- Synthesizes validated findings without creating new facts.
- Issues one of: `proceed`, `conditional_proceed`, `pause`, `stop`.

### Company & Business Agent (inside-out)

Answers what the company does and how it earns money. It owns:

- history, ownership, controller, management, and subsidiaries;
- products, services, revenue segments, geographies, and pricing model;
- ToB/ToC/project/subscription/equipment-plus-consumables classification;
- named customers and suppliers, concentration, contracts, channels, and order model;
- capacity, R&D, qualifications, fundraising use, and company-claimed advantages.

It may extract company claims about market position, but it cannot validate industry leadership or market share.

### Financial Penetration Agent

Answers whether accounting earnings are real, cash-generative, and sustainable. It owns:

- revenue, gross profit/margin, net profit/margin, and segment trends;
- operating cash flow and cash conversion;
- receivables, payables, inventory, and turnover cycles;
- short/long-term debt, liquidity, and refinancing pressure;
- non-recurring gains, government grants, capitalized R&D, dividends, and related balances;
- deterministic calculations and forensic-rule triggers.

### Industry & Competition Agent (outside-in)

Answers whether the market supports the company case and how the company compares externally. It owns:

- market definition, size, growth, and incremental versus mature competition;
- value-chain structure, demand drivers, regulation, technology, and pricing trends;
- verified competitors, substitutes, concentration, and bargaining power;
- external validation of market share, leadership, barriers, and claimed advantages;
- comparable-company operating and financial evidence when available.

At least one non-prospectus source is required for an externally validated industry Finding. Otherwise the item remains an open question.

### Legal, Compliance & Governance Agent

Answers whether non-financial issues materially weaken the company case. It owns:

- redemption, anti-dilution, VAM and other special shareholder rights;
- related-party transactions, controller risk, shareholding history, pledges, and fund occupation;
- litigation, penalties, regulatory inquiries, licensing, IP, product, data, and labor compliance;
- pre-listing dividends and unusual shareholder transactions;
- external adverse information and inconsistencies with prospectus disclosure.

### Skeptic / Cross-validation Agent

- Does not repeat specialist research.
- Compares business claims with financial and external evidence.
- Selects at most three material challenges.
- Routes at most one targeted follow-up round.
- Converts unresolved challenges into the follow-up checklist.

## Shared topics and ownership

| Topic | Company & Business | Industry & Competition |
|---|---|---|
| Customers | identity, concentration, contracts, payment terms | bargaining power and demand durability |
| Products | actual offering and revenue contribution | substitutability and differentiation |
| Pricing | contract mechanism and company margin | industry price trend and price war |
| Competitors | names and claims disclosed by company | external peer validation |
| Market share | extract the disclosed claim | validate source, definition, date, and ranking |
| Competitive advantage | record claimed advantage | test it against peers and contrary evidence |
| Growth | orders, capacity, pipeline, new products | whether industry demand can support it |

## Structured handoff

Specialists do not exchange free-form reports. They append:

- `Evidence`: original page, calculation trace, or real external URL;
- `Finding`: conclusion plus referenced Evidence IDs;
- `Challenge`: a material conflict or evidence gap;
- `DiligenceQuestion`: a prioritized request for further documents or explanation.

### Follow-up priority

- **P0:** may stop or pause diligence;
- **P1:** materially changes the company-quality conclusion;
- **P2:** useful completeness item without immediate impact on the core view.

Every follow-up question states why it matters, current evidence, requested material, and the downside if unresolved.

## Final report contract

1. Due diligence summary
2. Company profile and ownership
3. Products, business model, customers, and suppliers
4. Industry and competition
5. Historical financial performance
6. Earnings quality, cash flow, and working capital
7. Balance sheet and debt
8. Future earning power
9. Legal, governance, and adverse matters
10. Cross-agent contradictions and evidence gaps
11. Overall due diligence conclusion
12. P0/P1/P2 follow-up checklist
13. Evidence index

The report writer is a deterministic renderer. It must not introduce facts absent from the Research Ledger.

## Acceptance criteria for Mainline A

- Every material conclusion cites a prospectus page, calculation, or real URL.
- Financial calculations are deterministic and reproducible.
- Missing external industry evidence is explicitly marked unresolved.
- Specialist responsibilities follow the ownership table above.
- The graph permits no more than one follow-up round.
- The final conclusion contains separate assessments of historical financial quality, future earning power, and material risk.
- A human reviewer can trace all Agent messages, tool calls, evidence, findings, and challenges.

