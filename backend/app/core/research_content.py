"""Authoritative PIS and Consent Form v1.0 — do not materially alter approved statements."""

PIS_VERSION = "1.0"
PIS_DATE = "13 April 2026"
CONSENT_VERSION = "1.0"
CONSENT_DATE = "13 April 2026"

STUDY_TITLE_PIS = (
    "Computer Science - Design and Evaluation of an AI-Powered Pharmaceutical Assistant"
)
STUDY_TITLE_CONSENT = (
    "Computer Science: Design and Evaluation of AI-Powered Pharma Assistant"
)

PIS_TITLE = "Participant Information Sheet"
CONSENT_TITLE = "Participant Consent Form"

PIS_ACK_LABEL = "I confirm that I have read and understood the Participant Information Sheet."

ELECTRONIC_AFFIRMATION = (
    "I confirm that my consent is informed, voluntary and provided electronically."
)

PIS_FULL_TEXT = f"""{PIS_TITLE}

Study title:
{STUDY_TITLE_PIS}

Version:
Version {PIS_VERSION}
{PIS_DATE}

Invitation:
You are being invited to participate in a research study. Before deciding whether to participate, it is important to understand why the research is being conducted and what participation will involve. Please read the information carefully. Participation is voluntary.

Purpose:
The study evaluates an AI-powered pharmaceutical assistant designed to support pharmacists in interpreting handwritten prescriptions and reviewing potential therapeutic alternatives.

The system uses OCR to extract prescription information and Explainable AI to provide evidence-based, source-linked explanations using regulatory and pharmaceutical datasets such as FDA data and DrugBank.

Why selected:
You are invited because of your professional expertise as a pharmacist. Your feedback is valuable for assessing system accuracy, clinical relevance, usability, trust and explainability.

Voluntary participation:
Participation is voluntary. You may decline or withdraw before submitting the anonymous questionnaire without giving a reason and without disadvantage.

What participation involves:
- Accessing the PharmaAssist prototype.
- Reviewing 25–30 synthetic handwritten prescription samples.
- Reviewing OCR-extracted medication information.
- Correcting extracted information where required.
- Reviewing suggested therapeutic alternatives.
- Reviewing source-linked Explainable AI outputs.
- Completing an anonymous questionnaire.
- Spending approximately 20–30 minutes.

All prescription samples used in the study are synthetic and contain no real patient information.

Data use:
- The University of Liverpool acts as Data Controller.
- Research data is processed for academic research.
- Research outputs are anonymized.
- Registration data is used only for authentication, administration, consent and access control.
- Account information must be separated from anonymous research results.
- Research exports must not contain names, emails, registration IDs, IP addresses or workplace details.

Storage:
- Data must be encrypted at rest and in transit.
- Access must be restricted.
- Temporary prescription images must be deleted.
- Raw OCR containing PII must not be permanently retained.
- Research data must not be stored long-term on personal devices.
- Data must be retained only for the approved retention period.

Anonymization:
Research responses will be anonymized. After an anonymous questionnaire has been submitted and can no longer be linked to a participant, withdrawal may no longer be possible.

Risks:
The risks are minimal because the study is desk-based and uses synthetic prescription data. The prototype must not be used for real clinical decisions.

Benefits:
There are no guaranteed direct personal benefits. Participation may contribute to research into safer prescription interpretation and transparent AI-assisted pharmacist support.

Research outputs:
Results may be presented in an MSc dissertation and may be disseminated through academic conferences or peer-reviewed publications. Results must be reported anonymously.

Contacts:
Student Researcher:
Muhammad Zohaib
m.zohaib@liverpool.ac.uk

Principal Investigator / Dissertation Advisor:
Dr. Nazmul Hussain
Nazmul.Hussain@liverpool.ac.uk

Ethics and Complaints:
University of Liverpool Research Ethics and Integrity Office
ethics@liv.ac.uk
"""

CONSENT_STATEMENTS: list[str] = [
    "I confirm that I have read and understood the Participant Information Sheet dated 13 April 2026.",
    "I have had the opportunity to consider the information and ask questions.",
    "I understand that participation involves interacting with a web-based AI prototype.",
    "I understand that I will review synthetic handwritten prescriptions containing no real patient data.",
    "I understand that I may verify or correct machine-extracted medication information.",
    "I understand that I may review potential therapeutic alternatives and source-linked explanations.",
    "I understand that I may be asked to complete an anonymous questionnaire about usability, trust, accuracy, clinical relevance and explainability.",
    "I understand that participation is voluntary.",
    "I understand that I may withdraw before submitting the anonymous questionnaire without giving a reason.",
    "I understand that I may decline to answer any questionnaire question.",
    "I understand that after anonymous questionnaire submission, it may no longer be possible to withdraw my response.",
    "I understand that research data will be handled securely under University of Liverpool data-protection requirements.",
    "I understand that registration information will be separated from anonymized research results.",
    "I understand that temporary prescription images will be securely deleted after processing or submission.",
    "I understand that anonymized results may be used in an MSc dissertation and related academic dissemination.",
    "I understand that the data will not be reused for unrelated future research without appropriate approval and consent.",
    "I confirm that I am 18 years of age or older.",
    "I agree to take part in this research study.",
]
