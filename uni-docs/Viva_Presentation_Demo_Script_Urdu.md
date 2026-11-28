# MediScan — Final Viva Presentation + Live Demo Script (Urdu/English Mix)

Ye script aap ke official Week-18 presentation + viva ke liye hai (committee ke saamne 20-minute slot). Isme slides (PPTX) aur live demo dono shamil hain — demo Architecture slide ke baad, beech mein hota hai. Viva ka Q&A hissa is script mein shamil nahi hai (wo committee ke sawalon par depend karta hai), sirf ye scripted presentation+demo part hai jo aap khud deliver karte hain.

**Target length: ~18-20 minute** (committee ka official slot 20 minute hai). Neeche har slide/section ke saamne approximate waqt diya gaya hai.

**Record/present karne se pehle:**
- `create_asad_showcase_rx.py` script chala lein taake ek pehle se complete, verified prescription session ready ho — demo ke dauran live OCR ka wait na karna pare.
- Slides already khud bol rahi hain (bullet points committee ke saamne hain) — is liye narration slides ke text ke bohat qareeb rakha gaya hai, taake jo aap bolein aur jo screen par ho, dono match karein.
- Technical terms (OCR, upload, score, evidence, dashboard, verify, confirm, catalogue) English mein hi bolein — ye normal hai. Baaki Urdu mein.

---

## SLIDE 1 — Title Slide (~30 second)

Assalam-o-Alaikum. Mera naam Muhammad Usama Alam hai, aur ye mera final project hai — MediScan: A Human-in-the-Loop, Explainable AI Decision-Support System for Prescription Reading and Therapeutically-Equivalent Medicine Substitution. Ye PGD in Generative AI, Batch 5 ke under hai, aur mere supervisor Sajid Majeed sahab hain.

---

## SLIDE 2 — Student Details (~15 second)

Ye meri basic details hain — naam, roll number, batch, aur supervisor ka naam. *(Jaldi se aage barhein, zyada time na lein.)*

---

## SLIDE 3 — Introduction (~1.5 minute)

Pehle main problem explain karta hoon — isi slide par teen main points hain.

Pehla: jab prescription hath se likhi jati hai, to kai dafa usay sahi tarah parhna mushkil hota hai. Bohat se drug names ek dusre se milte julte hote hain, aur ek galat character bhi patient ko ek different medicine tak le ja sakta hai.

Dusra: jab prescribed medicine available nahi hoti — stock mein nahi, discontinued ho chuki, ya patient ke liye bohat mehngi — to pharmacist ko khud se decide karna parta hai ke koi alternative medicine di ja sakti hai ya nahi, aur abhi tak iske liye koi formal tool maujood nahi.

Teesra, aur cross-cutting problem: koi bhi automated tool jo yahan use ho, usay trust kamana zaroori hai — agar system koi answer de raha hai bina reason ke, to clinical setting mein us par act karna safe nahi.

To key point ye hai: koi existing tool prescription reading ko regulated therapeutic-equivalence reasoning ke saath ek system mein combine nahi karta — yehi gap hai jo MediScan address karta hai.

---

## SLIDE 4 — Objectives (~1 minute)

Project ke chay (6) objectives hain, jo slide par list hain:

Ek, multi-engine OCR pipeline banana jo medicine ka naam, strength, form, aur route extract kare.

Do, pharmacist se mandatory verification lena, is se pehle ke koi bhi downstream processing shuru ho.

Teen, ek recommendation engine banana jo trusted catalogue, eligibility filters, aur ek transparent score use kare.

Char, regulatory therapeutic-equivalence layer add karna, FDA Orange Book ke zariye.

Paanch, evidence-grounded explanations dena, FDA label text se.

Chay, explainable-AI attribution dikhana — yani ye batana ke score kyun diya gaya.

Aur ek cross-cutting commitment jo pure project mein follow ki gayi: koi bhi metric ya claim tab tak report nahi ki jati jab tak uske peeche real data na ho.

---

## SLIDE 5 — Scope of Work (~1 minute)

Ye slide do columns mein hai — jo is project mein shamil hai, aur jo jaan boojh kar shamil nahi kiya gaya.

In-scope mein: OCR extraction aur mandatory verification gate, 9-component recommendation scoring FDA Orange Book evidence ke saath, evidence-grounded explanation aur explainable-AI attribution, aur role-based access — pharmacist, reviewer, aur administrator, self-registration ke saath jisay admin approve karta hai, aur ek full audit trail.

Out-of-scope mein: koi bhi autonomous prescribing, dispensing, ya automatic substitution — system kabhi khud decision nahi leta. Koi real patient data ya PII use nahi hui, sirf synthetic prescriptions. Ye ek clinical source of truth nahi hai, aur drug-drug interaction checking abhi future work hai. Aur ye ek research-grade prototype hai, production clinical system nahi.

---

## SLIDE 6 — Literature Review (~1.5-2 minute)

Is slide par ek table hai jo panch research strands dikhati hai, aur har ek mein ye batati hai ke existing literature kya kehti hai, aur MediScan us mein kahan fit hota hai.

Prescription OCR mein, literature kehti hai ke handwriting print se zyada mushkil hai, aur look-alike/sound-alike names ek well-documented error class hain. MediScan OCR ko sirf transcription tak mehdood nahi rakhta, balke usay substitution decision se directly jointa hai.

Therapeutic equivalence mein, literature ye batati hai ke equivalence ek regulatory determination hai — FDA Orange Book ke zariye — sirf chemical similarity se infer nahi ki jati. MediScan mein equivalence hi primary ranking signal hai.

Explainable AI mein, Rudin (2019) ke mutabiq high-stakes use ke liye interpretable-by-design models ko post-hoc black-box explanation par prefer kiya jana chahiye. MediScan ka score additive hai, matlab exact attribution milti hai — jo real SHAP/LIME ke against independently verify bhi ki gayi hai.

Evidence grounding, ya RAG, mein Lewis et al. (2020) kehte hain ke retrieval, ek unconstrained LLM ke muqable mein, unsupported claims kam karta hai. MediScan is principle ko aage le jata hai — jab koi evidence nahi milta, to narrative bilkul withhold kar deta hai.

Aur human-in-the-loop mein, Parasuraman and Manzey (2010) kehte hain ke agar system pehle act kare aur baad mein confirmation li jaye, to automation bias ka khatra hota hai. MediScan mein ye gate har recommendation generate hone se pehle enforce hota hai, baad mein nahi.

Key point ye hai: har ek property individually prior work mein address ki gayi hai, lekin koi existing system in paanchon ko ek saath integrate nahi karta. Poori detail report ke Chapter 2 mein hai.

---

## SLIDE 7 — Methodology (~1.5 minute)

Ye diagram MediScan ke end-to-end flow ko dikhata hai: prescription image upload hoti hai, multi-engine OCR — Azure, Vision, aur Tesseract — usay parhta hai, phir verification gate aata hai, uske baad eligibility filters — jo paanch hain — phir ek nau-component weighted score banta hai, uske saath equivalence, evidence, aur explainable-AI dikhayi jati hai, aur aakhir mein decision pharmacist ki hoti hai.

Methodology ke teen main points hain. Pehla, ye project Design Science Research follow karta hai — Hevner et al. (2004) aur Peffers et al. (2007) ke framework ke mutabiq — jahan design banaya jata hai, demonstrate kiya jata hai, evaluate kiya jata hai, aur ye cycle iterate hota hai.

Dusra, verification gate server-side par enforce hoti hai — jab tak pharmacist confirm na kare, koi bhi aage nahi barhta.

Teesra, score additive hai aur hamesha exactly 100 tak sum hota hai; FDA Orange Book equivalence sirf evidence ke taur par dikhai jati hai, ye kabhi candidates ko re-rank nahi karti.

---

## SLIDE 8 — System Architecture (~1 minute)

Ye diagram system ki technical architecture dikhata hai — ek FastAPI backend aur React single-page frontend, dono ek hi Docker container mein, aur ek read-only SQLite drug catalogue jo structurally Postgres application database se alag rakha gaya hai, taake reference data kabhi ghalati se modify na ho sake.

Ab main aap ko ye system live chala kar dikhata hoon.

---

## LIVE DEMO (~6-7 minute total)

*(Note: neeche likhe alfaaz khud 3 minute se bhi kam ke hain — baaki waqt clicking, page load, aur screen dekhne mein apne aap guzar jayega. Bolna artificially slow na karein; jab app load ho raha ho to chup baithne ki bajaye agla point bolte rahein.)*

*(Yahan presentation se switch kar ke browser mein live app kholein.)*

### Pharmacist Area (~5-5.5 minute — demo ka main hissa)

Ye hai pharmacist ka workspace, jahan actual roz-marra ka kaam hota hai. Process char steps mein hota hai, jo screen ke upar nazar aa rahe hain: upload, text parhna, verify karna, aur confirm karna.

**Step one, upload.** Pharmacist prescription ki photo upload karta hai aur submit kar deta hai.

**Step two mein system usay parhta hai — yahi OCR hai.** Hum yahan ek se zyada reading engines use karte hain — main engine Azure Document Intelligence hai, agar wo kaam na kare to Google Vision, aur agar wo bhi fail ho to Tesseract offline engine. Agar engines kisi word par disagree karen, to system usay flag kar deta hai. Aur agar handwriting itni unclear ho ke parhi na ja sake, to system guess nahi karta — saaf bata deta hai ke sahi tarah parh nahi saka.

**Step three, verification.** Yahi human-in-the-loop hissa hai — computer ka kaam hamesha ek real insaan check karta hai. System har medicine ka naam, strength, dose, aur frequency dikhata hai, aur pharmacist har field ko confirm, correct, ya "unable to verify" mark karta hai. System tab tak aage nahi jaane deta jab tak ye step poora na ho — ye ek jaan-boojh kar banaya gaya safety design hai.

**Step four mein, confirm hone ke baad, MediScan alternatives suggest karta hai.** System drug database mein search kar ke alternatives ko 100 mein se ek score ke zariye rank karta hai — ye score 9 alag clinical factors ko mila kar banta hai, jaise indication match, drug class, route, aur dosage form.

Score ke saath real supporting evidence bhi dikhai jati hai — FDA Orange Book se therapeutic equivalence, aur FDA drug labels se directly li gayi text.

Aur akhir mein, evidence aur explanation panel — ye batata hai ke har ek factor ne final score mein kitna contribute kiya, taake "system ne ye suggestion kyun di" ka clear aur transparent jawab ho, black box jaisa kuch nahi.

### Admin aur Reviewer Area — quick glance (~30-45 second)

Yahan do aur roles hain. Admin platform manage karta hai — pharmacist registrations approve karta hai, drug catalogue aur overall analytics dekhta hai. *(Jaldi se admin dashboard dikhayein.)* Aur reviewer ek oversight role hai — wo khud kaam nahi karte, sirf pure platform ka evaluation snapshot aur har session ka audit dekhte hain, taake system ki overall quality track ki ja sake. *(Jaldi se reviewer dashboard dikhayein, phir wapis slides par aayein.)*

---

## SLIDE 9 — Findings (~2-2.5 minute)

*(Yahan wapis presentation par switch karein.)*

Ye slide project ke actual findings char boxes mein dikhati hai.

**Worked example mein:** Ibuprofen 200mg ko Naproxen ke against test kiya gaya. Score 100 mein se 100 aaya, nau mein se nau components match hue. Isme real DrugBank evidence aur real FDA Orange Book AB-rating shamil thi, jisme 167 products the. Isi run mein ek real gap bhi mila: panch mein se do candidates clinically implausible thay. Route aur dosage-form filters jaisa design kiya gaya tha, waisi sakhti se gate nahi kar rahe thay. Ye Limitations mein detail se discuss kiya gaya hai.

**Verified working mein:** paanch cheezein confirm hui hain. Human verification gate server-enforced hai, sirf UI-level nahi. Score hamesha exactly 100 tak sum hota hai. Equivalence layer confirm hui ke wo sirf passive hai. Evidence-withholding bhi confirm hui. Catalogue production scale par hai — nau sau thousand se zyada records. Aur real SHAP/LIME libraries ka output hamare analytical score se match karta hai, taqreeban 1e-14 ki precision ke saath.

**Evaluation status mein:** teen pre-registered research questions hain jinke pass/fail thresholds hain, aur ek chautha, exploratory research question hai. RQ1 aur RQ2 ke evaluation harnesses ko redirect karna hai — real single-engine signal, aur structural-similarity coverage ki taraf. Sirf zyada data se ye theek nahi hoga. RQ3 ke liye dataset complete karna hai. Aur RQ4 ke liye institutional ethics approval aur pharmacist panel chahiye, jo abhi tak complete nahi hua.

**Known limitations mein:** chay cheezein slide par hain. Chemical-similarity bonus ek path par zyada influence kar raha hai. Evidence layer poori tarah passive nahi. Scoring model apni internal specification se thora divert karta hai. Audit trail convention se append-only hai, database-enforced nahi. Worked example mein filters under-enforced thay. Aur equivalence determination ek specific regulatory jurisdiction tak mehdood hai. Report mein total nau limitations hain, jin mein se chay yahan dikhayi gayi hain.

Key point ye hai: ek system ko itni closely examine karna, aur itni honesty se report karna, yehi Design Science Research ka asal maqsad hai — ye koi weakness chupane ki baat nahi hai.

---

## SLIDE 10 — Conclusions (~1 minute)

Char main conclusions hain. Design buildable hai, internally coherent hai, aur deployed hai. Har layer ko real catalogue ke against ek real query par end-to-end exercise kiya gaya. Ye ek disciplined demonstration hai ke integration kaam karta hai — abhi ye ek fully validated performance claim scale par nahi hai. Aur jo baaki reh gaya hai wo hai system ko scale par evaluate karna, jiske liye infrastructure pehle se tayar hai.

---

## SLIDE 11 — Recommendations (~1 minute)

Char recommendations hain. Pehla, 25 se 30 cases wala synthetic evaluation dataset complete karna hai, RQ3 ke liye. Dusra, RQ1 ko real single-engine accuracy signal ki taraf redirect karna hai, aur RQ2 ko structural-similarity coverage ki taraf. Phir dono ko dobara run karna hai. Teesra, ethics approval lena hai, phir pharmacist panel recruit karna hai, RQ4 ke liye. Aur chautha, report mein khud teen design-related sawal flag kiye gaye hain jo supervisor se discuss karne hain — chemical-similarity bonus, evidence-layer passivity, aur scoring-model specification divergence. In teenon ko resolve karna hai, aur worked example mein jo route/dosage-form filter gaps mili thin, unhein bhi fix karna hai.

---

## SLIDE 12 — Thank You (~15-20 second)

Ye raha MediScan — live deployed, is URL par available hai jo screen par hai. Dekhne aur sunne ka shukriya. Ab main aap ke sawalaat ke liye tayar hoon.

---

## Apne liye notes (ye zor se nahi parhne)

- Total waqt budget: slides 1-8 taqreeban 8-9 minute, live demo 6-7 minute, slides 9-12 taqreeban 4-5 minute — total ~18-20 minute, jo official 20-minute slot ke andar fit hota hai.
- Agar waqt kam parh raha ho, to Slide 2 (Student Details) par sabse kam time lagayein — wo sirf facts hain, discussion ki zaroorat nahi.
- Literature Review (Slide 6) aur Findings (Slide 9) committee ke liye sabse important slides hain — inhein jaldi se na nikalein, chahe time thora zyada lag jaye.
- Agar committee beech mein hi sawal poochein (jo viva mein normal hai), to pehle unka jawab dein, phir wapis script par aa jayein — poora script wapis se shuru karne ki koshish na karein.
- Live demo se pehle confirm kar lein ke `create_asad_showcase_rx.py` chal chuka hai, taake OCR ka wait na karna pare.
- Agar live demo mein koi cheez expected se slow chale, to khamoshi baithne ki bajaye bolte rahein — jaise "ye OCR pipeline hai, system ab prescription parh raha hai."
