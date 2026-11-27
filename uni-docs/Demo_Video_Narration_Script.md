# MediScan Demo Video — Narration Script

**Target length: 12-15 minutes.** The words below, read at a normal pace, take about 11 minutes by themselves. The remaining 1-4 minutes comes naturally from clicking between screens, waiting for pages/uploads to load, and brief pauses — you don't need to slow your speech down artificially to fill time. The per-section minutes noted below include that natural navigation time, not just the words. Read these in your own words if that feels more natural — the goal is that it sounds like you, not like a script.

**Before you record:** run the showcase script (`create_asad_showcase_rx.py`) once beforehand so you already have one finished, fully-verified prescription session to show in the Pharmacist section without waiting on live OCR. Then do one quick live upload during filming to show the real upload/wait experience in motion.

---

## 1. Introduction (1.5-2 minutes)

Hello, this is a short demo of my final year project, MediScan.

Let me start with the problem. When a doctor writes a prescription, especially by hand, pharmacists sometimes struggle to read it correctly. Drug names can look very similar to each other, and a misread name can lead to the wrong medicine being given to a patient. That's a real and well-documented source of medication errors.

There's a second problem too. Sometimes the medicine a doctor prescribed simply isn't available — it might be out of stock, discontinued, or too expensive for the patient. In that case, the pharmacist has to decide on their own whether another medicine can safely replace it. Right now, pharmacists do this from memory and experience, with no tool to help them check their decision.

MediScan is built to help with both of these problems. It's a web application where a pharmacist can upload a photo of a prescription, and the system reads the handwriting using OCR, which just means it converts the image of the text into actual digital text the computer can understand. The pharmacist then checks and confirms what the system read — the system never just trusts its own reading blindly, the human always has the final say. Once the medicines are confirmed, MediScan can suggest therapeutically equivalent alternatives, meaning other medicines that would have the same effect, and it shows exactly why it's suggesting each one, with real evidence from official drug databases, not just a black-box answer.

I want to be clear about one thing up front: this is a decision-support tool, not a replacement for the pharmacist. It never makes a final decision on its own — every single thing it reads or suggests has to be checked and approved by a qualified pharmacist before it counts for anything. The goal is to support their judgment with better information, not to take the decision away from them.

The system has three types of users, each with their own area: an admin who manages the platform, the pharmacist who does the actual day-to-day work, and a reviewer who oversees everything happening on the platform. I'll show you each of these one by one.

---

## 2. Admin Area (2.5-3 minutes)

*[Say this while clicking through the admin dashboard, registrations, catalog, prescriptions, and analytics tabs]*

This is the admin area. The admin is responsible for running the platform itself, not for doing the pharmacy work.

The first thing you see is a dashboard with some quick numbers — how many pharmacists have registered, how many are active, how many prescriptions have been uploaded so far, and how many medicines are in our drug database. It's a quick-glance summary of how the whole platform is being used.

Next is the registrations tab. When a new pharmacist signs up, their account doesn't go live automatically — it comes here first, as a pending request. The admin checks it and either approves or rejects it. This is important because we're dealing with healthcare, so we don't want just anyone creating an account without someone checking first.

This is the catalog tab. This shows our full drug database — around forty-one thousand medicines, built from real public sources: the FDA's official drug listings, DrugBank, and FDA product labels. This is the reference data that the whole recommendation engine relies on later.

Here's the prescriptions tab, where the admin can see every prescription that every pharmacist has uploaded across the whole platform — who uploaded it, what status it's in, how many medicines were confirmed in it.

And finally, analytics. This shows how accurate our OCR system has been across all these prescriptions — things like how many words or characters it's getting wrong on average. This helps us understand if the reading quality is good enough to trust, and where it might need improvement.

So overall, the admin area is about managing the platform, approving who gets to use it, and keeping an eye on overall quality and usage.

---

## 3. Pharmacist Area (5-6 minutes — this is the core of the demo)

*[Say this while walking through: uploading an image, the OCR step, the verification table, the alternatives panel, and the evidence panel]*

Now this is the main part of the project — the pharmacist's workspace, where the actual day-to-day work happens.

The process follows four simple steps, which you can see at the top of the screen: upload, read the text, verify it, and confirm.

**Step one is upload.** The pharmacist just takes a photo of the prescription, or uploads an existing image, and submits it.

**Step two, the system reads it.** This is where the OCR happens. We actually use more than one reading engine here — the main one is Microsoft's Azure Document Intelligence, and if that doesn't work well for some reason, it automatically falls back to Google Vision, and then to an offline engine called Tesseract as a last resort. Using multiple engines like this makes the reading more reliable than depending on just one. If the different engines disagree on what a word says, the system flags that so the pharmacist knows to pay closer attention there. And importantly — if the handwriting is genuinely too unclear to read, the system will not guess or make something up. It will clearly tell the pharmacist it couldn't read it properly, rather than risk showing a wrong medicine name with false confidence.

**Step three is verification.** This is the most important step, because this is the human-in-the-loop part of the system — meaning a real person always checks the computer's work before anything happens next. The system shows what it read for each medicine: the drug name, the strength, the dose, how often it's taken. The pharmacist goes through each one and either confirms it's correct, corrects it if it's wrong, or marks it as "unable to verify" if the image is too unclear to tell. The system will not let the pharmacist move forward to get alternative medicine suggestions until this step is properly completed. This is a deliberate safety design — the AI never gets to skip past a human check.

**Step four, once everything is confirmed, is where MediScan suggests alternatives.** If a pharmacist needs to find a replacement for a medicine, the system searches our drug database and ranks possible alternatives by a score out of 100. This score isn't a random guess — it's built from nine different clinical factors added together, like whether it treats the same condition, whether it belongs to the same drug class, whether the dosage form and route into the body match, whether there are contraindication concerns, and so on. Each factor contributes its own weight to the final score.

Alongside the score, each suggested alternative also shows real supporting evidence — for example, whether the FDA has officially recognized it as therapeutically equivalent to the original medicine, and relevant text pulled directly from official FDA drug labels. So the pharmacist isn't just seeing a number, they're seeing why that number was given, with real official sources backing it up.

And finally, there's an evidence and explanation panel, which breaks down exactly how much each of those nine factors contributed to the final score for a specific suggestion — so if a pharmacist or a reviewer ever asks "why did the system suggest this," there's a clear, transparent answer rather than a black box.

So to summarize this section: upload, read, verify, and get an explained, evidence-backed suggestion — with a human checking the work at every important step.

---

## 4. Reviewer Area (2-2.5 minutes)

*[Say this while clicking through the evaluation snapshot and the prescription sessions list/detail view]*

Finally, this is the reviewer area. Think of the reviewer as an oversight role — they don't do the pharmacy work themselves, and they can't edit anything. Their job is purely to monitor how the system is performing across the entire platform.

This is the evaluation snapshot. It gives a bird's-eye view across every pharmacist on the platform — total prescriptions handled, how often the extracted medicine names actually matched something in our drug database, how often pharmacists had to correct or override what the system suggested, and the system's average confidence in its own readings. This helps answer the question: overall, is this system actually working well in practice?

And this is the sessions view, where a reviewer can look into any individual prescription session from any pharmacist, purely to audit it — they can see the original uploaded image, which OCR engine handled it, and a side-by-side comparison of what the AI originally extracted versus what the pharmacist ultimately confirmed. This is useful for quality checking and research purposes, to see where the system is doing well and where it still needs improvement.

*(If your supervisor asks a follow-up question about a specific accuracy percentage here, it's fine to say the exact figures depend on how much real usage data has built up so far — the dashboard numbers update as more prescriptions get processed.)*

So the reviewer area exists to answer a bigger question than any single prescription — it's about making sure the whole system stays trustworthy and accurate over time.

---

## Closing (15-20 seconds)

That covers the three main areas of MediScan — the admin managing the platform, the pharmacist doing the actual verification and getting evidence-based suggestions, and the reviewer keeping an eye on overall system quality. Thank you for watching.

---

## Notes for yourself (not to read aloud)

- The pharmacist section is intentionally the longest — it's the heart of the project and where most of the technical work is. If you're running short on time, trim the admin and reviewer sections first, not this one.
- Avoid saying "SHAP," "LIME," "XAI," "DQ1-DQ4," or "HITL" out loud — the script above already translates these into plain language ("evidence and explanation panel," "human-in-the-loop" explained in plain words). Stick to that phrasing so it stays easy to follow.
- The research-evaluation panel (the formal research-question metrics) is currently hidden in the reviewer UI and not demo-able — the script above does not mention it, intentionally.
- If a live upload is slow during filming, you can talk through what's happening on screen (mention the "OCR pipeline" step bar) while it loads, rather than sitting in silence.
