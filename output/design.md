# Operations Desk – Design Notes

The dashboard (`frontend/`, React + Vite + TypeScript) is meant to feel like the private operations desk of a high-end firm: calm and precise, with motion that signals what's happening, not decoration. It's styled in Yale colors because Campus Customs is a Yale apparel shop. It talks to the FastAPI backend at `http://localhost:8000` (CORS allows `http://localhost:5173`) and runs with `npm run dev`.

## Layout

The page has a Yale-blue **masthead** and three columns below it, read left to right as *what needs doing → what's happening → what it costs*:

| Area | What it holds |
|---|---|
| Masthead (sticky) | Brand mark, the shop date (`desk.date_today` written out as a date, not the real clock), team status (*Standing by* / *Working* with a live pulse), a signatures counter, and **Reset desk** |
| Left: Ticket board | The 3 tickets as cards. Clicking one selects it. **Dispatch team →** starts a run on that ticket. |
| Center: Agent roster | The 5 agents. The one currently working lifts up and gets a pulsing halo. Agents who took part in the selected run are at full opacity. |
| Center: Live activity | A timeline of the selected ticket's run, polled every 1.4 s while live: handoffs (*Boss → Facilities*, with the task in italics), what each agent said, the MCP tools it called with their arguments, delegations, and each agent's report back. |
| Center: Run summary | After a run: the Boss's decision and next step, then one card per agent with its final report and the MCP tools it used, plus the run's model calls and handoffs. |
| Right: Checking | The cash card, always visible. |
| Right: Awaiting your signature | Approval requests with **Approve** / **Reject**, and a history of past decisions. |

Under 1240 px wide, cash and approvals move below the other columns. Under 860 px, everything stacks in one column.

## How the agents are told apart

Each agent has three cues that always appear together, so it can be recognized even without color:

| Agent | Color | Glyph |
|---|---|---|
| Boss | Yale Blue `#00356b` | crown |
| Inventory | Yale Light Blue `#286dc0` | box |
| Accounting | Yale green `#5f712d` | bar chart |
| Facilities | Yale orange `#bd5319` | storefront |
| Customer Service | plum `#7a4b94` | speech bubble |

The four Yale colors come from the university's web palette. Plum is added so Customer Service doesn't clash with them. The agent's color is used for its name, its circular badge, the left rule on each of its feed entries, the top border of its roster card, its delegation chips, and the "Prepared by" line on approval requests. Delegation chains are shown as colored breadcrumbs (*Boss › Facilities › Accounting*), so nested handoffs are easy to follow.

## Resolved tickets

A ticket counts as **Resolved** once the team has finished a run on it, meaning the Boss has made its final call. The backend works this out from the audit trail, ignoring runs from before the latest reset. A resolved card:
- turns faintly green and gets a green left rule and a diagonal ribbon;
- shows a solid green **✓ Resolved** seal that stamps in, with the check drawing itself.

The Boss's own database status sits next to the seal (for example *Waiting on approval*). It turns into **Approved by you** once you have signed every request for that ticket. So "resolved" never hides money that is still waiting on you. Open tickets keep the **Dispatch team** button, and a running ticket shows an animated blue rule and *Team working*.

## Cash and approvals

- **Cash is the darkest, heaviest element on the page:** a deep Yale-blue card with a large serif balance that counts up or down when it changes. It is labeled **Actual balance**, comes from `cash_accounts`, and changes only when you approve a payment.
- **Pending money is shown separately, never mixed into the balance.** A bar splits the balance into free (light blue) and pending (hatched orange). Below it are *Awaiting approval* and *Projected if all approved*. This follows the Problem 6 rule: $3,400 stays the current balance until a payment is actually approved.
- **Approvals use one warm accent, orange, so they stand out from everything blue:**
  - the masthead pill (*1 awaiting you*) glows;
  - the count badge pulses;
  - each request card has a shimmering orange hairline, a large serif amount, what it pays for, the agent's reason, and who prepared it.
- **Approve needs a name.** The *Approving as* field is required and is stored as `approved_by`.
- **After approval:** the cash card flashes, the number animates to the new balance, and a toast confirms it.

## Main creative choices, and why

- **Yale palette on ivory.** Yale Blue for authority (masthead, cash, primary buttons), warm ivory paper instead of plain white for a printed, institutional feel, and Yale Sky Blue `#63aaff` for "live" signals. It fits a Yale shop and stays readable for long sessions.
- **Editorial serif + clean sans.** Titles, amounts, and ticket subjects are set in a classic book serif (Iowan Old Style / Palatino), the kind luxury and university sites use. Labels and body text use the system sans. Tool names are in monospace, because they're code and must match the server exactly. All are system fonts, so there are no external requests and nothing loads late.
- **Fine details over heavy decoration:** 1 px hairline borders, small-caps eyebrow labels with wide letter spacing, layered soft shadows, tabular numbers so amounts don't jitter while animating, and *No. 101*-style ticket numbers in italic serif.
- **Motion with a purpose:**
  - panels rise in a stagger on load;
  - a slow sheen crosses the masthead;
  - pulses mean *live*, halos mean *working now*, and shimmer means *needs your signature*;
  - feed entries slide in and handoff arrows nudge forward;
  - the resolved seal stamps in, and money counts instead of jumping;
  - button hovers get a light sweep.

  All of it uses one ease-out curve so it feels consistent, and everything turns off under `prefers-reduced-motion`.
- **Honest by design.** Approval is a separate, deliberate act with your name on it. The only path that moves money is the human route from Problem 7. The UI never shows a projected balance as real cash, and it never hides that a "resolved" ticket may still be waiting on your signature.
