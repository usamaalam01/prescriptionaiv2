# MediScan Demo Video — Narration Script (Urdu / English Mix)

Ye script aap ke English wale script ka Urdu translation hai, Roman Urdu mein likha gaya hai taake record karte waqt parhna easy ho. Technical terms (jaise OCR, upload, dashboard, score, evidence, verify, confirm) jaan boojh kar English mein rakhe gaye hain kyunke ye aam taur par Urdu mein bhi isi tarah bole jate hain. Baaki sentences simple, bol-chaal wali Urdu mein hain.

**Target length: 12-15 minute.** Neeche diye gaye alfaaz normal speed se parhein to taqreeban 11 minute lagenge. Baaqi 1-4 minute screens ke darmiyan click karne, page load hone, aur thori pauses se apne aap aa jayenge — speech ko artificially slow karne ki zaroorat nahi. Jahan comfortable ho, apne alfaaz mein bhi bol sakte hain — maqsad ye hai ke natural lage, ratta hua na lage.

**Record karne se pehle:** `create_asad_showcase_rx.py` script ek dafa chala lein taake Pharmacist wale section mein ek pehle se complete aur verified prescription session dikhane ke liye ready ho, live OCR ka wait na karna pare. Uske baad ek live upload bhi dikha dein taake real upload/wait experience bhi camera mein aa jaye.

---

## 1. Introduction (1.5-2 minute)

Assalam-o-Alaikum, ye mera final year project MediScan ka ek short demo hai.

Pehle main problem explain karta hoon. Jab doctor koi prescription likhta hai, khas kar hath se, to pharmacists ko kabhi kabhi usay sahi tarah parhne mein mushkil hoti hai. Bohat se drug names ek dusre se milte julte hote hain, aur agar naam ghalat parha jaye to patient ko galat medicine mil sakti hai. Ye medication errors ki ek real aur well-documented wajah hai.

Ek dusri problem bhi hai. Kabhi kabhi jo medicine doctor ne prescribe ki ho wo available hi nahi hoti — stock mein nahi hoti, ya discontinued ho chuki hoti hai, ya patient ke liye bohat mehngi hoti hai. Us waqt pharmacist ko khud decide karna parta hai ke koi aur medicine iski jagah safely di ja sakti hai ya nahi. Abhi tak pharmacists ye decision sirf apni memory aur experience ke zariye lete hain, koi tool unki madad ke liye nahi hota.

MediScan inhi do problems ko solve karne ke liye bana hai. Ye ek web application hai jahan pharmacist prescription ki photo upload karta hai, aur system OCR ke zariye us handwriting ko parh leta hai — Uske baad pharmacist khud check karta hai aur confirm karta hai ke system ne jo parha wo sahi hai ya nahi — system kabhi bhi apni reading par andhaa bharosa nahi karta, final decision hamesha insaan ka hota hai. Jab medicines confirm ho jati hain, to MediScan therapeutically equivalent alternatives suggest kar sakta hai, yani aisi medicines jo same asar rakhti hon, aur ye bhi batata hai ke har suggestion kyun di gayi — official drug databases se real evidence ke saath, sirf ek black-box answer nahi.

NOT NECESSARY - BEGIN
Ek baat shuru mein hi clear kar dena chahta hoon: ye ek decision-support tool hai, pharmacist ki jagah lene wala tool nahi. Ye kabhi khud final decision nahi karta — jo bhi ye parhta ya suggest karta hai, usay ek qualified pharmacist ko check aur approve karna zaroori hai, tabhi wo count hota hai. Maqsad ye hai ke pharmacist ke judgment ko behtar information ke saath support kiya jaye, unse decision cheen kar nahi.
NOT NECESSARY - END

System mein teen types ke users hain, har ek ka apna area hai: admin jo platform manage karta hai, pharmacist jo roz-marra ka actual kaam karta hai, aur reviewer jo pure platform ki nigrani karta hai. Main aap ko ye teeno ek ek kar ke dikhata hoon.

---

## 2. Admin Area (2.5-3 minute)

Ye hai admin area. Admin ki zimmedari platform ko chalana hai, pharmacy ka actual kaam karna nahi.

DASHBOARD
Sabse pehle ek dashboard nazar aata hai jis mein kuch quick numbers hain — kitne pharmacists register hue hain, kitne active hain, ab tak kitni prescriptions upload hui hain, aur drug database mein kitni medicines hain. Ye bas ek quick-glance summary hai ke poora platform kaise use ho raha hai.

REGISTRATIONS
Iske baad registrations tab hai. Jab koi naya pharmacist sign up karta hai, to uska account automatically active nahi hota — pehle ye yahan ek pending request ki tarah aata hai. Admin isay check kar ke approve ya reject karta hai. Ye isliye zaroori hai kyunke ye healthcare ka maamla hai, is liye hum nahi chahte ke koi bhi bina check kiye account bana le.

CATALOG
Ye catalog tab hai. Ye hamara poora drug database dikhata hai — taqreeban 41,000 medicines, jo real public sources se banaya gaya hai: FDA ki official drug listings, DrugBank, aur FDA product labels. Ye wahi reference data hai jis par baad mein poora recommendation engine depend karta hai.

PRESCRIPTIONS
Ye raha prescriptions tab, jahan admin pure platform ki har prescription dekh sakta hai, chahe kisi bhi pharmacist ne upload ki ho — kis ne upload ki, uska status kya hai, aur us mein kitni medicines confirm hui hain.

ANALYTICS
Aur akhir mein, analytics. Ye batata hai ke hamara OCR system in saari prescriptions par kitna accurate raha hai — jaise average kitne words ya characters ghalat parhe gaye. Isse hamein pata chalta hai ke reading quality bharosa karne ke layak hai ya nahi, aur kahan improvement ki zaroorat hai.

To overall, admin area ka kaam hai platform ko manage karna, use karne walon ko approve karna, aur overall quality aur usage par nazar rakhna.

---

## 3. Pharmacist Area (5-6 minute — ye demo ka sabse important hissa hai)

Ab ye hai project ka sabse main hissa — pharmacist ka workspace, jahan actual roz-marra ka kaam hota hai.

Process char simple steps mein hota hai, jo aap screen ke upar dekh sakte hain: upload, text parhna, verify karna, aur confirm karna.

**Step one hai upload.** Pharmacist bas prescription ki photo kheenchta hai, ya pehle se maujood image upload karta hai, aur submit kar deta hai.

**Step two mein system usay parhta hai.** Yahi OCR hota hai. Hum yahan ek se zyada reading engines use karte hain — main engine Microsoft ka Azure Document Intelligence hai, aur agar kisi wajah se wo theek kaam na kare to system automatically Google Vision par switch ho jata hai, aur agar wo bhi fail ho to aakhri option ke taur par Tesseract naam ka ek offline engine use hota hai. Itne saare engines istemal karne se reading sirf ek engine par depend karne se zyada reliable ho jati hai. Agar different engines kisi word par disagree karen, to system usay flag kar deta hai taake pharmacist us jagah zyada dhyan de. Aur ye bhi zaroori baat hai — agar handwriting waqai itni unclear ho ke parhi na ja sake, to system guess nahi karta ya khud se kuch bana kar nahi dikhata. Wo saaf tor par pharmacist ko bata deta hai ke sahi tarah parh nahi saka, isliye ke galat confidence ke saath ghalat medicine ka naam dikhana zyada khatarnak hai.

**Step three hai verification.** Ye sabse important step hai, kyunke yahi system ka human-in-the-loop hissa hai — matlab ye ke computer ke kaam ko hamesha ek real insaan check karta hai, uske baad hi agla step hota hai. System har medicine ke liye jo parha hai wo dikhata hai: drug ka naam, strength, dose, aur kitni dafa li jaani hai. Pharmacist har ek ko dekh kar ya to confirm karta hai ke sahi hai, ya ghalat hone par correct karta hai, ya "unable to verify" mark kar deta hai agar image itni unclear ho ke pata hi na chale. System pharmacist ko alternative medicines ke suggestions tak tab tak nahi jaane deta jab tak ye step poora na ho jaye. Ye ek jaan-boojh kar banaya gaya safety design hai — AI kabhi bhi human check ko bypass nahi kar sakta.

**Step four mein, jab sab kuch confirm ho jata hai, tab MediScan alternatives suggest karta hai.** Agar pharmacist ko kisi medicine ka replacement chahiye ho, to system hamare drug database mein search kar ke possible alternatives ko ek 100 mein se score ke zariye rank karta hai. Ye score koi random guess nahi hai — ye 9 different clinical factors ko jama kar ke banaya jata hai, jaise ke kya wo same condition treat karti hai, kya same drug class mein aati hai, kya dosage form aur route of administration match karte hain, kya koi contraindication concerns hain, waghera waghera. Har factor apna fixed weight final score mein add karta hai.

Score ke saath saath, har suggested alternative ke saath real supporting evidence bhi dikhai jati hai — jaise ke kya FDA ne officially isay original medicine ke barabar (therapeutically equivalent) maana hai, aur official FDA drug labels se directly li gayi relevant text. To pharmacist sirf ek number nahi dekh raha, wo ye bhi dekh raha hai ke wo number kyun diya gaya, real official sources ke saath.

Aur akhir mein, ek evidence aur explanation panel hai, jo exactly batata hai ke un nau factors mein se har ek ne specific suggestion ke final score mein kitna contribute kiya — is liye agar pharmacist ya reviewer kabhi poochen "system ne ye suggestion kyun di," to ek clear aur transparent jawab maujood hota hai, black box jaisa kuch nahi.

To is section ko summarize karte hain: upload, parhna, verify karna, aur phir ek explained, evidence-backed suggestion milna — har important step par ek insaan ka check hote hue.

---

## 4. Reviewer Area (2-2.5 minute)

Aakhir mein, ye hai reviewer area. Reviewer ko ek oversight role samjhein — wo khud pharmacy ka kaam nahi karte, aur na hi kuch edit kar sakte hain. Unka kaam sirf ye monitor karna hai ke poore platform par system kaisa perform kar raha hai.

SNAPSHOT
Ye hai evaluation snapshot. Ye pure platform ke har pharmacist ka ek bird's-eye view deta hai — total kitni prescriptions handle hui hain, kitni dafa extract ki gayi medicine names actually hamare drug database mein match hui hain, kitni dafa pharmacists ko system ki suggestion correct ya override karni pari, aur system apni readings par average kitna confident raha. Ye is sawal ka jawab dene mein madad karta hai: overall, kya ye system practice mein waqai achay se kaam kar raha hai?

PRESCRIPTION SESSIONS
Aur ye hai sessions view, jahan reviewer kisi bhi pharmacist ki kisi bhi individual prescription session ko dekh sakta hai, sirf audit karne ke liye — wo original uploaded image dekh sakte hain, konsa OCR engine use hua, aur side-by-side comparison dekh sakte hain ke AI ne shuru mein kya extract kiya tha aur pharmacist ne aakhir mein kya confirm kiya. Ye quality check aur research purposes ke liye useful hai, taake pata chale system kahan achay se kaam kar raha hai aur kahan abhi improvement chahiye.

To reviewer area ka maqsad kisi ek prescription se bara sawal hal karna hai — ye ensure karna ke poora system waqt ke saath trustworthy aur accurate raha.

---

## Closing (15-20 second)

To ye the MediScan ke teen main areas — admin jo platform manage karta hai, pharmacist jo actual verification kar ke evidence-based suggestions leta hai, aur reviewer jo overall system quality par nazar rakhta hai. Dekhne ka shukriya.

---

## Apne liye notes (ye zor se nahi parhne)

- Pharmacist wala section jaan boojh kar sabse lamba rakha gaya hai — ye project ka dil hai aur zyada tar technical kaam yahi hai. Agar time kam ho raha ho, to pehle admin aur reviewer sections choti karein, isay nahi.
- "SHAP," "LIME," "XAI," "DQ1-DQ4," ya "HITL" bolne se bachein — script mein inko pehle hi simple zabaan mein translate kiya ja chuka hai ("evidence aur explanation panel", "human-in-the-loop" ko simple alfaaz mein samjhaya gaya hai). Isi tarah ki language use karein taake samajhna asaan rahe.
- Research-evaluation panel (jo formal research-question metrics dikhata hai) abhi reviewer ke UI mein hidden hai aur demo nahi ho sakta — is liye script mein jaan boojh kar iska zikar nahi kiya gaya.
- Agar recording ke dauran live upload slow ho jaye, to khamoshi baithne ki bajaye screen par jo ho raha hai uske baare mein baat karte rahein (jaise "OCR pipeline" wala step bar mention kar dein) jab tak wo load ho raha ho.
