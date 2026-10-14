# Homework 5 – AI Prompt Log

## Problem 1 – Create the AI Prompt Log

### Prompt 1

Yes, so for problem 1, create AI_prompts.md and keep updating it as we go through the hw.
For each problem, add a section with the problem number and title, the prompt I actually gave you in my own words, and if I need a follow-up, include that too with one short sentence explaining what was missing after the first try.
Don’t invent prompts or extra explanations I didn’t give you. We’ll keep filling this file as we work problem by problem.

### Follow-up Prompt

No additional prompt was needed after Prompt 1.

## Problem 2 – Inspect the Database and Open Tickets

### Prompt 1

Now, for problem 2, open data/campus_customs.db and inspect every table and its fields. Don’t assume the schema — use what is actually in the database.
First, make a copy of the original database as data/campus_customs_new.db. We’ll use that working copy in later problems, so keep the original untouched.
Also look at the 3 open tickets and understand how each one connects to the other tables.
Then start output/harness.md. For every table, list its fields and add one short line explaining why that table matters for the agents. We’ll keep expanding this same harness later.

### Follow-up Prompt

No additional prompt was needed after Prompt 1.

## Problem 3 – Build the MCP Server

### Prompt 1

ok, now for problem 3, build the MCP server. For this, 

let’s first inspect tickets 101, 102, and 103 in data/campus_customs_new.db and identify what information each ticket needs in order to be solved.
Based on those actual tickets, create the FastMCP server in mcp_server/ with 3 clear tools that we know the agents will need. Each tool should read only real data from the database and should have a specific purpose tied to one of those tickets.
Don’t choose generic tools just because they sound useful. Pick the 3 tools based on what tickets 101, 102, and 103 actually need.
Then update output/harness.md with each tool, the table it reads, which ticket it helps unlock, and one sentence explaining specifically why that tool is useful for that ticket.
Also create a short mcp_server/README.md explaining what the MCP server is for, which database it uses, and the 3 tools we added.
We don’t need to run or connect the MCP server yet.

### Follow-up Prompt

No additional prompt was needed after Prompt 1.

## Problem 4 – Connect and Test the MCP Server

### Prompt 1

ok, for problem 4, let’s connect the MCP server we just built to this project so you can actually call the 3 tools from Claude Code.
Save the local MCP connection config in `.mcp.json` at the project root, using the correct command/path for our `mcp_server/`.
Once it’s connected, test each of the 3 MCP tools we created in Problem 3. Use a simple prompt for each one that makes sense for the ticket it supports, and make sure the returned values actually match `data/campus_customs_new.db`.
Then save the test evidence in `output/mcp_smoke.json`. For each of the 3 tools, include:

* the prompt I asked
* the tool name
* the tool output

Please use the real outputs from the MCP calls, not manually made-up examples.

### Follow-up Prompt

What was lacking after Prompt 1: the MCP tools had not been called through Claude Code itself yet.

Let’s use option 2. I’ll open a new Claude Code session from inside the Homework5/ folder and approve the campus-customs MCP server when prompted. Once it is approved and available, please test the 3 MCP tools through Claude Code itself and then create output/mcp_smoke.json with the actual prompt, tool name, and real tool output for each test. Explain how to do it

### Follow-up Prompt 2

What was lacking after the previous follow-up: the session was not running inside Homework5/, so the campus-customs MCP tools were not loaded and had not been called yet.

H5 follow up, be sure to be in homework 5 folder, 

Use the campus-customs MCP tools (not Bash, not sqlite, not importing server.py) to run these 3 tests, one tool call each:

1. Prompt: "Ticket 101 is blocked on invoice 501. Check invoice 501's status and whether the vendor will ship."
   Tool: get_vendor_invoice_status with invoice_id=501
2. Prompt: "Ticket 102 is a rent notice for lease 1. How much rent is due on lease 1, when, and can checking cover it?"
   Tool: get_lease_rent_due with lease_id=1
3. Prompt: "Ticket 103: Yale AI Club wants 20 CC-HOOD-NAVY hoodies in size M with a bulk discount. Check stock and pricing."
   Tool: get_stock_and_pricing with sku="CC-HOOD-NAVY", size="M", qty=20

After the calls, verify each output against data/campus_customs_new.db with sqlite3 (read-only queries).

Then create output/mcp_smoke.json as a JSON list with one object per test:
{"ticket": ..., "prompt": "...", "tool": "mcp__campus-customs__<name>", "arguments": {...}, "output": <exact JSON the MCP tool returned>, "db_check": "matches" or what differed}
Copy the outputs exactly as returned; do not retype or edit values. Do not modify the database.

## Problem 5 – Build the PydanticAI Agent Team

### Prompt 1

keeps logs like that. For problem 5, let’s build the full PydanticAI agent team: Boss, Inventory, Accounting, Facilities, and Customer Service.
Give each agent its own prompt file in backend/prompts/, put the shared data types in backend/models.py, and keep the agent code under backend/. The 5 agents should be able to delegate work to each other, so the team is fully connected.
I will send in the next prompt the prompts for each agent (Make each prompt specific to that role and include the shop rules that matter to it, not just generic instructions, otherwise adjust accordingly if needed)
 Use only gpt-6-luna through Portkey for every agent.
Also grow the MCP server with any extra tools the agents need for the open tickets. All shop facts should still come through MCP from data/campus_customs_new.db — don’t add another direct database tool layer in the backend.
As the agents run, append each agent-loop step to output/audit_trail.json with enough information to understand later what happened. Don’t erase previous runs.
Then update output/harness.md with all 5 agents, every MCP tool and the table it uses, plus a short safety section with the main guardrails for customers/money and some limits to avoid unnecessary token use.
Finally, update mcp_server/README.md so its tool list matches the tools we actually have now.

### Follow-up Prompt

What was lacking after Prompt 1: the role prompts were not the final versions, and the delegation and shortage behavior had not been set.

Let’s keep `approval_requests` and `customer_drafts` as new tables in the working database only. The original database should stay untouched, and resetting the working copy should also reset these tables.
Don’t update the role prompts yet because I haven’t given you the final versions. I’ll send those next and they should be the source of truth.
Two things I want incorporated when we wire the agents:

* avoid delegating the same task twice if another agent already handled it
* for shortages, don’t immediately mark the ticket blocked. Consider realistic alternatives like partial fulfillment now and the remainder later, as long as Inventory confirms the stock and Accounting/Boss confirms the economics and approval.

Ill send now each one of the prompts (one by one) take them as a base, and adjust accordingly if needed with all the context you have:

1. Boss — `backend/prompts/boss.md`
You are the Boss agent for Campus Customs. You own the open-ticket queue and coordinate the other agents to get each ticket to the best possible resolution.
Start by understanding the ticket and gathering only the information actually needed. Use `desk.date_today` as today’s date, never the real-world date. All shop facts should come from the MCP tools; don’t invent inventory, prices, invoices, cash, lease terms, vendor information, or dates.
Delegate based on ownership:

* Inventory: stock, SKUs/sizes, shortages, restocking, vendors and lead times
* Accounting: cash, invoices, margins, discounts, payments and approvals
* Facilities: leases, rent and physical-store issues
* Customer Service: customer-facing drafts only

Tickets can require more than one agent. Put their findings together before making the final decision.
Before delegating something, check whether that same subtask has already been completed or delegated during the ticket. Reuse existing results instead of asking another agent to do the same work again.
Don’t treat a shortage as automatically blocked. Consider reasonable options such as partial fulfillment with the inventory available now and fulfilling the rest later. Only present this as an option if Inventory confirms the quantities and Accounting confirms the pricing/margin implications. Don’t invent a split-order policy if none exists.
Follow these shop rules:

* a vendor will not ship while it has an unpaid invoice
* every payment requires human approval
* a payment can never make cash negative
* no new revenue comes into the business during this homework
* never actually contact a customer, landlord, or vendor
* Customer Service may draft messages, but never send them

If an action needs human approval, create the approval request and clearly explain what is being approved, the amount, and why it is needed. Do not treat approval as granted until a human approves it.
Only consider a ticket complete when the necessary work has actually been resolved, or when you have clearly identified what human approval or external dependency is still blocking it. Avoid unnecessary delegation and stop when you have enough information to make the decision.

### Follow-up Prompt 2

What was lacking after the previous follow-up: only the Boss prompt had been provided; the Inventory prompt was still missing.

2. Inventory — `backend/prompts/inventory.md`
You are the Inventory agent for Campus Customs. You handle stock, SKUs, sizes, shortages, restocking options, vendors, and lead times.
Use MCP tools for all shop information. Never guess stock quantities, product details, vendors, costs, or delivery timing.
For an order or inventory ticket, check the exact SKU and size, quantity requested, quantity currently available, and the resulting shortage.
If there is enough stock, report what can be fulfilled. If there is not enough, don’t just say “blocked.” Show the Boss the realistic options, including how much can be fulfilled now and how much would remain.
If restocking is needed, identify the appropriate vendor from the available database information and use the vendor’s actual lead time. Before saying that a vendor can ship, check whether that vendor has an unpaid invoice. If an invoice is blocking the shipment, delegate that issue to Accounting.
For example, if a customer wants 20 units and only 8 are available, clearly report 8 available and 12 short. Partial fulfillment can be surfaced as an option, but the Boss makes the final business decision and Accounting handles any pricing or margin question.
Use `desk.date_today` whenever timing matters.
Do not approve discounts, make payments, contact vendors/customers, or make financial decisions. Delegate:

* cash, invoices, margins, discounts and payments → Accounting
* customer communication → Customer Service
* final operational decisions → Boss

If another agent already obtained the information you need, use that result instead of repeating the same work.

### Follow-up Prompt 3

What was lacking after the previous follow-up: the Accounting prompt was still missing.

3. Accounting — `backend/prompts/accounting.md`
You are the Accounting agent for Campus Customs. You handle cash, invoices, costs, margins, discounts, rent payments, vendor payments, and payment approvals.
Get financial facts through MCP tools. Never invent amounts or assume future revenue. During this homework, no new revenue comes in, so every financial decision has to work with the cash the shop already has.
Use `desk.date_today` when deciding whether an invoice, rent payment, or other obligation is due or overdue.
Before any payment:

1. confirm the actual amount due
2. check the current cash balance
3. make sure the payment would not make cash negative
4. create a human approval request
5. do not execute the payment until approval is actually granted

Every payment requires human approval, even if there is enough cash.
Remember that a vendor will not ship new inventory while it has an unpaid invoice. If Inventory needs that vendor, explain what invoice is blocking it and what payment would be needed to unblock the vendor.
For discount or bulk-order requests, use the real unit cost, list price, requested quantity, and available inventory. Show the economics clearly, including the price/margin impact. Do not invent a discount policy or automatically approve the discount. Give the Boss enough information to decide.
If only part of an order is currently available, you can evaluate the economics of selling the available quantity now and the remainder later, but don’t assume that is the final decision.
Do not increase cash for a potential sale during this homework.
Delegate:

* stock/shortage/vendor logistics → Inventory
* lease details → Facilities
* customer-facing wording → Customer Service
* final business decisions → Boss

Avoid duplicate work. If another agent already checked an invoice, cash balance, or margin calculation and nothing has changed, use that result.

### Follow-up Prompt 4

What was lacking after the previous follow-up: the Facilities prompt was still missing.

4. Facilities — `backend/prompts/facilities.md`
You are the Facilities agent for Campus Customs. You handle leases, rent, landlords, and other physical-store or space-related issues.
Use MCP tools for the actual lease information. Never guess the landlord, rent amount, due date, lease details, or other shop facts.
Always use `desk.date_today` when deciding whether rent or another facilities obligation is upcoming, due, or overdue.
For a rent ticket, identify:

* which lease/location it relates to
* the rent amount
* the due date
* how urgent it is based on the shop date

Then delegate the financial side to Accounting if a payment needs to be prepared. Accounting owns the cash check and approval process.
Before delegating, check whether Accounting has already handled that payment issue in the current ticket. Don’t send the same rent task to Accounting twice just because it appears in more than one part of the workflow.
You cannot make or approve payments yourself. Every payment requires human approval and cannot make cash negative.
Never actually contact the landlord. If a message is needed, Customer Service can draft one for human review.
Send the Boss a concise summary of the facilities issue, deadline, and anything still required before it can be resolved. If the issue belongs to another role, delegate it instead of guessing.

### Follow-up Prompt 5

What was lacking after the previous follow-up: the Customer Service prompt was still missing.

5. Customer Service — `backend/prompts/customer_service.md`
You are the Customer Service agent for Campus Customs. You handle the customer-facing communication needed to support ticket resolution.
Your job is to draft clear, helpful messages. Never actually send an email, message, or contact a customer, vendor, landlord, or anyone else.
Save customer-facing drafts through the approved draft mechanism so a human can review them.
Never invent stock, price, discount, delivery date, payment status, or any other shop fact. Use information already confirmed by the other agents or through MCP-backed data.
For an out-of-stock item, wait for Inventory to confirm what is available and the realistic timing before drafting a response.
If partial fulfillment is being considered, explain only the option that the Boss has actually approved. Don’t promise that the customer can receive part now and part later unless that decision has been made.
For a discount request, wait until Accounting has evaluated the economics and the Boss has made the pricing decision before putting a price in the draft.
If a vendor/payment issue affects fulfillment, don’t expose unnecessary internal financial details to the customer. Explain the practical outcome clearly without overexplaining the shop’s internal operations.
Keep drafts concise, friendly, and professional.
Delegate:

* stock and delivery questions → Inventory
* financial/discount questions → Accounting
* facilities issues → Facilities
* unclear or final business decisions → Boss

If the information required to write an accurate message is still missing, ask the appropriate agent instead of guessing.

### Follow-up Prompt 6

What was lacking after the previous follow-up: the agents had not yet been confirmed as fully connected with protection against duplicate delegation and loops.

keep them. before moving on, make the agents fully connected so they can delegate to each other when the prompts call for it, but avoid duplicate delegation and unnecessary loops.

## Problem 6 – Desk Tickets Expected Plan

### Prompt 1

For problem 6, let’s create `output/desk_tickets.html` before we run the agents, so we can write down what we expect the team to do on each of the 3 open tickets.
Make one tab for Ticket 101, Ticket 102, and Ticket 103, plus empty `Cash` and `Reflection` tabs for later. For now, the Cash and Reflection tabs can just say “coming later.”
On each ticket tab, create an Expected section and leave an empty Actual section that we’ll fill after the agents run.
For each Expected section, use the ticket details from the database and the agent roles/prompts we already created. Include:

* which agent the Boss should call first and why
* the agent-to-agent handoffs we expect after that
* the specific MCP tools we expect them to use

Keep the plan efficient. The Boss should not call every specialist directly. We want the first specialist to handle its part and delegate to another agent when needed.
Use our actual MCP tool names from the project, not made-up ones. Before filling the Expected sections, show me your proposed plan for tickets 101, 102, and 103 so I can review it before you put it into the HTML.

### Follow-up Prompt

What was lacking after Prompt 1: the proposed plan needed small changes to how cash, the ticket 101 arrival date, and the ticket 103 partial fulfillment and discount were described.

This looks good overall. Go ahead with it, but make these small changes before building `desk_tickets.html`:

1. For cash, keep the distinction between actual cash and pending approvals clear. Checking is still $3,400 until a payment is actually approved and executed. You can show $2,560 or $160 as projected remaining cash if the pending payments are approved, but don’t describe that as the current balance.
2. For ticket 101, don’t promise that the tee will definitely arrive on 9/5. Say that 9/5 is the estimated earliest availability based on the 5-day vendor lead time if the payment is approved on 8/31.
3. For ticket 103, keep partial fulfillment as an option, not an automatic decision. Accounting should show the economics and margin of the available 8 units and any possible discount, and then the Boss can decide whether offering 8 now makes sense. Don’t choose an arbitrary discount just because anything above $22 is profitable.

Other than that, I approve the proposed expected flow. Please build `output/desk_tickets.html` with the 3 ticket tabs, the Expected sections based on this plan, empty Actual sections for later, and the Cash and Reflection tabs as placeholders.

## Problem 7 – Build the FastAPI Backend

### Prompt 1

For problem 7, let’s build the FastAPI backend in `backend/main.py` so the dashboard can control and monitor the agent team.
Add routes to:

* return the 3 tickets and show whether each one is still open or already resolved
* take a ticket id and run the agent team on that ticket
* return recent agent events, including what each agent said and which MCP tools it used, so the frontend can refresh the activity
* approve a pending payment or purchase only after a human clicks approve. The agents should only prepare the request; this approval route is the step that can actually change cash
* return the current checking balance from `cash_accounts`
* reset `campus_customs_new.db` back to the original database state so we can start a clean run again

Make sure there is no path where an agent can silently execute a payment without the human approval route.
Then test the backend from the `backend/` folder with:
`uvicorn main:app --reload --port 8000`
It should run at `http://localhost:8000`.
Finally, update `output/harness.md` with one short line for every route showing the URL and what it does.

### Follow-up Prompt

No additional prompt was needed after Prompt 1.

## Problem 8 – Build the React Dashboard

### Prompt 1

For Problem 8, let’s build the React dashboard in frontend/ using React + Vite + TypeScript and connect it to the FastAPI backend from Problem 7.
The dashboard should show all 3 tickets, let me pick one and start the agent team, and show what each agent is saying or doing while the ticket runs. When the run finishes, mark the ticket as resolved and show a short summary of what each agent did.
If an agent asks for a payment or purchase approval, show that request clearly in the dashboard with an Approve button so the human has to approve it. Also show the current checking balance and make sure it updates after an approved payment.
Point the frontend to http://localhost:8000, and configure CORS on the backend so the Vite app at http://localhost:5173 can call it.
I also want the dashboard to feel like a real operations desk, not a default Vite page. Make the agents visually easy to distinguish, make resolved tickets obvious, and make cash/approvals easy to notice.
Start it with npm run dev.
Finally, create output/design.md with a short explanation of the layout, how the agents are differentiated visually, how resolved tickets and cash are shown, and the main creative choices we made and why For the colors, also use like yale  colors and theme, and also make the web page like super high-end website with motions and fine details, colors, um, like if, if it was like a super, super high-end company website.

### Follow-up Prompt

No additional prompt was needed after Prompt 1.

## Problem 9 – Full Clean Run Through the Dashboard

### Prompt 1

For Problem 9, let’s do the full clean run and resolve all 3 tickets through the actual React dashboard while I’m watching it.
First reset `data/campus_customs_new.db` from the original database so we start from a clean state, and note the starting checking balance.
Then start the backend and frontend if needed and guide me through tickets 101, 102, and 103 one at a time from the dashboard. I want to see the agents working, the handoffs, MCP tool activity, approval requests, cash changes, and final ticket status live.
Don’t auto-approve payments or purchases for me. If a human approval is required, stop there and let me click Approve myself.
After each ticket finishes, use what actually happened in that run to update `output/desk_tickets.html`. Keep the Expected sections we already wrote, and fill the Actual section with:

* which agents actually worked on the ticket
* what handoffs/delegations actually happened
* which MCP tools were actually used

On the Cash tab, show:

* the starting checking balance after the reset
* the actual cash change caused by each ticket, including what payment/purchase caused it and the amount
* the ending checking balance

Be careful that pending approvals do not count as cash changes. Only approved and executed payments should reduce cash. At the end, verify the ending balance matches `cash_accounts` in `campus_customs_new.db`.
Also create `output/resolved_tickets.json`. For each ticket include the ticket id, final status, short outcome, what each agent contributed, and any human approvals that happened.
Create `output/resolved_board.html` using screenshots from the real React dashboard showing tickets 101, 102, and 103 resolved. Make sure I can double-click the HTML and see the screenshots correctly.
Keep appending the real agent runs to `output/audit_trail.json`.
Finally, finish `output/harness.md` so it covers the database tables, MCP tools, all 5 agents, API routes, dashboard, approvals, and safety rules.
Please don’t silently run everything in the background. Guide me through the live run step by step and use the real results from that run for all the final outputs.

### Follow-up Prompt

What was lacking after Prompt 1: the app had been started in the background, so I could not see it running or follow how to run it myself.

but first help me run the application/site or whatever an guide me how to do it. I want to see everthing happening also de agents all

### Follow-up Prompt 2

What was lacking after the previous follow-up: the links to open the dashboard in the browser were not shared.

where are de links to open in the browesr? you didnt share them

### Follow-up Prompt 3

What was lacking after the previous follow-up: the explanation pointed to terminal tabs, and it was not clear that the browser dashboard alone shows everything.

Iis not easier to see this instead of in terminan in the app in the browser or explain because i am lost

### Follow-up Prompt 4

What was lacking after the previous follow-up: I needed advice on the approval request shown for ticket 101 before clicking.

shoudl I approve?

### Follow-up Prompt 5

What was lacking after the previous follow-up: the approvals for ticket 101 had to be recorded before moving on.

i have approved both

### Follow-up Prompt 6

What was lacking after the previous follow-up: I needed a plain summary of what happened in ticket 101 before continuing.

can you make a summary of what happened? before I jump into ticket 102. To understand all that happen in 101

### Follow-up Prompt 7

What was lacking after the previous follow-up: the ticket 102 run summary looked repetitive and I wanted to understand what each agent actually did.

its not kind of repetititve? wha theyve done? (just answear dont do anyting)

### Follow-up Prompt 8

What was lacking after the previous follow-up: the rent approval for ticket 102 had to be recorded before moving on.

i approved the rent, 102 done

### Follow-up Prompt 9

What was lacking after the previous follow-up: I needed a plain summary of what happened in ticket 103.

now give a summary of that happene in 103 i am lost

### Follow-up Prompt 10

What was lacking after the previous follow-up: the final outputs (Actual sections, Cash tab, resolved_tickets.json, resolved_board.html, harness) were still to be written from the run.

ok lets continue with this you mention

## Problem 10 – Reflection

### Prompt 1

let's do option 2. 

Now for problem 10, let’s finish the Reflection tab in `output/desk_tickets.html` using what actually happened in the clean run.
Keep the existing Expected, Actual, and Cash tabs unchanged. I don’t want to rewrite the run after the fact.
Replace the “Coming later” placeholder with this reflection:
Overall, I think the agents performed well, but the runs also showed where having multiple agents can add unnecessary complexity.
Ticket 101: The team found the stock problem, the unpaid vendor invoice, got the payment approved, and drafted the customer response correctly. The main difference from what I expected was that it also created an extra $8 purchase order for the tee. I originally thought paying invoice 501 would already release the reprint, but the database did not fully confirm that, so the agent took the safer route.
Ticket 102: This was the cleanest run and was almost exactly what I expected: Boss → Facilities → Accounting, then I approved the $2,400 rent payment. The only unnecessary step was that Facilities checked cash and Accounting checked it again.
Ticket 103: I think the team handled this one well because it did not just mark the order as impossible. It recognized that 8 hoodies were available, that restocking the other 12 would cost $264 when only $152 of cash remained, and the Boss offered $55 each with partial fulfillment as an option. No payment was made and the customer message was only drafted.
The cash controls also worked well. We started with $3,400, paid $848 for Ticket 101 and $2,400 for Ticket 102, and finished with $152, which matches the database.
One issue I noticed is that the ticket status and the real outcome can get out of sync after human approvals. Tickets 101 and 102 still say `waiting_on_approval` in the database because that was the Boss’s last update before I approved the requests, even though the approvals were completed afterward. The dashboard works around this by showing “Approved by you,” but I think the cleaner design would be for the approval flow to update the ticket once its final pending approval is completed.
One part that probably would have been simpler with one agent + tools is Ticket 102. Checking a lease, checking cash, and requesting the rent payment is pretty linear, so having Facilities and Accounting hand work back and forth added some overhead without much extra reasoning.
With the tools the team already has, I think it could also handle:

1. Another out-of-stock customer order and decide whether it can be restocked.
2. Another upcoming rent or unpaid vendor invoice and prepare the required approval.
3. Another bulk-order discount request by checking stock, costs, margins, and cash.

Things it could not solve today would include:

1. Tracking where a vendor shipment physically is — we would need a vendor/carrier tracking tool.
2. Handling payroll or employee issues — we would need payroll/HR data and probably an HR agent.
3. Deciding which marketing campaign is performing best — we would need sales/marketing analytics tools and probably a Marketing agent.

Keep the reflection inside the existing Reflection tab of `output/desk_tickets.html`. Don’t create a separate reflection file.
Also, for the system going forward, let’s fix the status issue without changing this clean run. When a human approves a ticket’s last pending request, the approval flow should also mark that ticket as `resolved` and add a note like “all approvals granted by [approver].”
Do not retroactively change the current clean-run database, `resolved_tickets.json`, screenshots, or Actual sections. Those should continue showing what really happened in this run. 
Also, for ticket 103, probably we should add something like, since we don't have the money to pay that, we can ask the client to prepay those 12 and we are gonna ship them immediately in X number of days or something like that. So we can get the money and it's not like in the loose. We are actually doing something and we are working on it. And we use the client's money to do that.

### Follow-up Prompt

What was lacking after Prompt 1: the prepayment idea for ticket 103 was only written into the reflection, not built into the agents' behavior for future cases.

I mean, you should be already making the change, not in the actual database, but in the code, so it does this for future situations.

## Problem 11 – Final Submission and GitHub Repo

### Prompt 1

For problem 11, let’s prepare the final submission and GitHub repo.
First clean up the project and make sure the final `hw5/` structure matches the homework. Remove temporary files like `joke.txt` or anything else that isn’t part of the assignment.
Make sure we include:

* `AI_prompts.md`
* `requirements.txt`
* `.env.example`
* `.gitignore`
* `.mcp.json`
* `README.md`
* both databases in `data/`: `campus_customs.db` and `campus_customs_new.db`
* `mcp_server/` with `server.py` and its README
* the full `frontend/`
* the full `backend/`, including all 5 agent prompts
* all required files in `output/`, especially `harness.md`, `mcp_smoke.json`, `desk_tickets.html`, `design.md`, `resolved_tickets.json`, `resolved_board.html`, and `audit_trail.json`

Do not include my real `.env` or any API keys. Check the repo for secrets before pushing.
Update `README.md` so someone cloning the repo can understand how to:

1. copy the original database to the working database for a clean run
2. start the MCP server
3. start the FastAPI backend
4. start the React dashboard
5. reset the database before running all 3 tickets again

Then push the project to a public GitHub repository. Once it’s pushed, save the repo URL in `output/github_url.txt`.
Also create the final `hw5.zip` from the same cleaned project structure so the zip and GitHub repo match.
Before we finish, do one final check that all required files exist, the repo is public, no secrets were committed, and the GitHub URL in `output/github_url.txt` is correct.
Also, before finishing, please make sure to do like a big audit of everything we've done. Put yourself into the grader, the teacher, and do a review, like if you were grading the exercise, the outputs, etc. Make sure that everything's there, that anything's missing, that uh, we follow all the instructions, etc. From what I tell you.

### Follow-up Prompt

No additional prompt was needed after Prompt 1.
