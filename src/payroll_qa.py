#!/usr/bin/env python3
"""Builds a realistic dataset: owners.json, test_cases.json and one PDF per document.

Fictional scenario: Brightline Consulting BV delivers "Project Helios" (ERP migration)
for its long-standing associate client Norvik Engineering NV (Ghent, Belgium).
The data deliberately contains redundancy, typos, outdated versions, rounded/wrong figures,
homonymous entities (Norvik France SAS) and informal sources.
"""
import json
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "data")

# --------------------------------------------------------------------------- owners
OWNERS = [
    ("OWN-101", "Nathalie Declercq", "Project Manager - Project Helios", "Delivery", 9, "senior",
     ["Project status reporting", "Milestones and planning", "Risk management"], ["Dutch", "French", "English"]),
    ("OWN-102", "Bart Willems", "Finance Controller", "Finance", 10, "senior",
     ["Project budgets", "Invoicing and payments", "Financial reporting"], ["Dutch", "English", "French"]),
    ("OWN-103", "Élodie Fontaine", "Key Account Manager - Norvik", "Sales", 8, "senior",
     ["Client relationship", "Client company profile", "Client contacts"], ["French", "English", "Dutch"]),
    ("OWN-104", "Kevin Jacobs", "Junior Project Analyst", "Delivery", 2, "junior",
     ["Budget tracking", "Reporting support"], ["Dutch", "English"]),
    ("OWN-105", "Anouk Verhaegen", "Legal Counsel", "Legal", 12, "senior",
     ["Contracts and amendments", "Penalties and liability", "Payment terms"], ["Dutch", "French", "English"]),
    ("OWN-106", "Dimitri Lambert", "Solution Architect", "Delivery", 11, "senior",
     ["ERP integration", "MES and system interfaces", "Data migration"], ["French", "English"]),
    ("OWN-107", "Laura Stevens", "CRM and Master Data Administrator", "Finance", 6, "mid",
     ["Client master data", "CRM data quality", "Client legal entities"], ["Dutch", "English"]),
    ("OWN-108", "Yannick Peeters", "Quality and Information Security Officer", "Quality", 9, "senior",
     ["ISO certifications", "Supplier qualification", "Information security"], ["French", "English", "Dutch"]),
    ("OWN-109", "Marie Gilson", "Credit Risk Analyst", "Finance", 7, "mid",
     ["Client financial statements", "Credit risk", "Company revenue and annual reports"], ["French", "English"]),
    ("OWN-110", "Olivier Dupont", "Delivery Director", "Delivery", 18, "expert",
     ["Project governance", "Escalation management", "Steering committees"], ["French", "English", "Dutch"]),
]
OWNER_NAME = {o[0]: o[1] for o in OWNERS}


def D(id, slug, title, type_, created, modified, owner, country, score, reasons, body):
    return dict(id=id, slug=slug, title=title, type=type_, created=created, modified=modified,
                owner=owner, country=country, score=score, reasons=reasons, body=body)


# --------------------------------------------------------------------------- documents
C1 = [  # company identity
    D("DOC-101", "client_master_record", "Master Data - Client record: Norvik Engineering NV", "document",
      "2024-02-12", "2026-09-02", "OWN-107", "Belgium", 91,
      ["Last modified less than 1 month ago", "Owner identified", "Applicable to Belgium",
       "Validated by the Finance master data team", "Consistent with other sources"],
      ["Client master record validated by the Finance master data team on 2026-09-02.",
       "- Legal name: Norvik Engineering NV.",
       "- VAT number: BE 0456.789.123.",
       "- Registered address: Kortrijksesteenweg 1120, 9051 Ghent, Belgium (since 1 March 2025).",
       "- Industry: industrial automation and engineering services.",
       "- Billing entity for Project Helios: Norvik Engineering NV."]),
    D("DOC-102", "msa_parties", "Master Services Agreement Brightline - Norvik: parties and definitions", "document",
      "2025-04-10", "2025-04-10", "OWN-105", "Belgium", 84,
      ["Signed contract", "Owner identified", "Applicable to Belgium", "Consistent with other sources"],
      ["This Master Services Agreement is concluded between Brightline Consulting BV and Norvik Engineering NV, "
       "a company incorporated under Belgian law.",
       "Norvik Engineering NV has its registered office at Kortrijksesteenweg 1120, 9051 Ghent, Belgium, "
       "and is registered under VAT number BE0456.789.123.",
       "The agreement is signed for Norvik by Jan De Smet, Chief Operating Officer."]),
    D("DOC-103", "email_invoice_rejected", "Email - Invoice INV-2026-0412 rejected: VAT mismatch", "email",
      "2026-06-18", "2026-06-18", "OWN-102", "Belgium", 68,
      ["Last modified less than 4 months ago", "Owner identified", "Informal source (email)",
       "Applicable to Belgium", "Mentions an erroneous VAT number (typo on an invoice)"],
      ["Hi team, Norvik accounts payable rejected invoice INV-2026-0412 because the VAT number printed "
       "on it was BE 0456.789.132.",
       "The correct VAT number of Norvik Engineering NV is BE 0456.789.123, as in the master record.",
       "Please reissue the invoice with the correct VAT number by Friday.",
       "Regards, Bart"]),
    D("DOC-104", "crm_export_legacy", "CRM export - Norvik (legacy)", "document",
      "2023-11-06", "2023-11-06", None, "Belgium", 39,
      ["Last modified more than 2 years ago", "No owner identified",
       "Contradicts a more recent document (DOC-101)"],
      ["- Company: Norvik Engineering N.V.",
       "- VAT number: BE 0456.789.123.",
       "- Registered address: Noorderlaan 147, 2030 Antwerp, Belgium.",
       "- Main contact: Jan De Smet."]),
    D("DOC-105", "teams_relocation", "Teams discussion - Norvik relocation to Ghent", "teams_discussion",
      "2025-03-12", "2025-03-12", "OWN-103", "Belgium", 72,
      ["Last modified more than 1 year ago", "Owner identified", "Informal source (Teams discussion)",
       "Applicable to Belgium", "Consistent with DOC-101"],
      ["Élodie: FYI Norvik moved its head office on 1 March 2025.",
       "Élodie: The new registered address is Kortrijksesteenweg 1120, 9051 Ghent. "
       "Please update the CRM and our invoice template.",
       "Laura: Done, the CRM is updated. The old Antwerp address is no longer valid for invoicing."]),
    D("DOC-106", "norvik_france_profile", "Company profile - Norvik France SAS", "document",
      "2026-02-09", "2026-02-09", "OWN-103", "France", 80,
      ["Last modified less than 8 months ago", "Owner identified", "Applicable to France, not Belgium",
       "Different legal entity (subsidiary)"],
      ["- Legal name: Norvik France SAS.",
       "- VAT number: FR 12 345678901.",
       "- Registered address: 18 Rue de la Bassée, 59000 Lille, France.",
       "- Parent company: Norvik Engineering NV."]),
]

C2 = [  # project status
    D("DOC-111", "steerco_minutes_sept", "Steering Committee minutes - 18 September 2026", "meeting_minutes",
      "2026-09-18", "2026-09-21", "OWN-101", "Belgium", 90,
      ["Last modified less than 1 month ago", "Owner identified", "Applicable to Belgium",
       "Approved by the steering committee", "Consistent with DOC-112"],
      ["Project Helios overall status: amber.",
       "- Milestones M1 (kick-off and analysis), M2 (data migration design) and M3 (build and configuration) "
       "are completed.",
       "- Milestone M4 (user acceptance testing, UAT) is in progress: 70% of test scripts executed, "
       "planned end 16 October 2026.",
       "- Milestone M5 (go-live) is forecast for 23 November 2026 following change request CR-07.",
       "- Open risk 1: supplier master data quality, about 12% duplicates still to be cleansed.",
       "- Open risk 2: key-user availability during UAT.",
       "- Open risk 3: the MES interface is not yet stable after two failed integration tests."]),
    D("DOC-112", "weekly_status_w38", "Weekly status report - Week 38 2026", "document",
      "2026-09-21", "2026-09-21", "OWN-101", "Belgium", 84,
      ["Last modified less than 1 month ago", "Owner identified", "Applicable to Belgium",
       "Consistent with DOC-111"],
      ["Overall status: amber. Milestones M1 to M3 completed, M4 (UAT) in progress.",
       "Forecast go-live: 23/11/2026 (re-baselined, CR-07).",
       "Top risks: supplier data quality (12% duplicates), UAT key-user availability, MES interface stability.",
       "UAT test scripts executed: 70%."]),
    D("DOC-113", "weekly_status_w31", "Weekly status report - Week 31 2026", "document",
      "2026-08-03", "2026-08-03", "OWN-101", "Belgium", 52,
      ["Last modified less than 3 months ago", "Owner identified", "Superseded by more recent status reports",
       "Contradicts more recent documents (DOC-111, DOC-112)"],
      ["Overall status: green. Milestones M1 to M3 completed, M4 (UAT) in progress.",
       "UAT planned end: 28/08/2026.",
       "Forecast go-live: 14/09/2026.",
       "Top risk: supplier data quality (20% duplicates)."]),
    D("DOC-114", "project_plan_baseline_v1", "Project plan - Baseline v1", "document",
      "2025-05-12", "2025-05-12", "OWN-101", "Belgium", 47,
      ["Last modified more than 1 year ago", "Owner identified", "Superseded by change request CR-07",
       "Planned dates no longer valid"],
      ["Baseline plan approved at kick-off.",
       "- M1 kick-off and analysis: 30 June 2025.",
       "- M2 data migration design: 31 October 2025.",
       "- M3 build and configuration: 27 February 2026.",
       "- M4 user acceptance testing: 28 August 2026.",
       "- M5 go-live: 14 September 2026."]),
    D("DOC-115", "email_sponsor_expectations", "Email - Norvik sponsor: go-live expectations", "email",
      "2026-09-05", "2026-09-05", None, "Belgium", 55,
      ["Last modified less than 1 month ago", "No owner identified in our organization",
       "Informal source (forwarded email)", "Content not verified", "Contradicts DOC-111"],
      ["Hi Nathalie, I understand from the team that UAT is going well and that the forecast go-live "
       "is 19 October 2026.",
       "Please confirm the date so I can inform our plant managers."]),
    D("DOC-116", "teams_mes_interface", "Teams discussion - MES interface test results", "teams_discussion",
      "2026-09-24", "2026-09-24", "OWN-106", "Belgium", 71,
      ["Last modified less than 1 month ago", "Owner identified", "Informal source (Teams discussion)",
       "Applicable to Belgium", "Consistent with DOC-111"],
      ["Dimitri: The MES interface integration test failed again this morning, second failure in two weeks.",
       "Dimitri: The root cause is the order status message format, Norvik IT will deliver a corrected "
       "specification by 2 October 2026.",
       "Nathalie: OK, I raise the MES interface risk to high in the risk register."]),
]

C3 = [  # budget
    D("DOC-121", "financial_report_sept", "Project financial report - September 2026", "document",
      "2026-09-01", "2026-09-15", "OWN-102", "Belgium", 89,
      ["Last modified less than 1 month ago", "Owner identified", "Applicable to Belgium",
       "Consistent with DOC-122 and DOC-123"],
      ["Financial position of Project Helios as of 15 September 2026 (all amounts excl. VAT).",
       "- Approved budget: EUR 480,000, including change request CR-07 (EUR 60,000).",
       "- Invoiced to date: EUR 273,000 (milestones M1, M2 and M3).",
       "- Remaining to invoice: EUR 207,000.",
       "- Next invoice: milestone M4 (UAT completion), planned for October 2026."]),
    D("DOC-122", "change_request_cr07", "Change Request CR-07 - Signed", "document",
      "2026-05-28", "2026-06-05", "OWN-101", "Belgium", 85,
      ["Last modified less than 4 months ago", "Owner identified", "Signed by both parties",
       "Applicable to Belgium"],
      ["Change request CR-07 was approved and signed by both parties on 5 June 2026.",
       "The fixed price of the contract increases by EUR 60,000, from EUR 420,000 to EUR 480,000 (excl. VAT).",
       "The additional scope covers the MES interface and two extra data migration cycles.",
       "The go-live date is re-baselined to 23 November 2026."]),
    D("DOC-123", "invoice_register", "Invoice register extract - Norvik Engineering NV", "spreadsheet",
      "2026-09-10", "2026-09-10", "OWN-102", "Belgium", 80,
      ["Last modified less than 1 month ago", "Owner identified", "Extract from the accounting system",
       "Consistent with DOC-121"],
      ["Invoices issued to Norvik Engineering NV for Project Helios:",
       "- INV-2025-0198, milestone M1, EUR 63,000, paid.",
       "- INV-2025-0341, milestone M2, EUR 84,000, paid.",
       "- INV-2026-0145, milestone M3, EUR 126,000, payment pending.",
       "Total invoiced: EUR 273,000."]),
    D("DOC-124", "email_budget_update", "Email - Helios budget update to Norvik", "email",
      "2026-07-02", "2026-07-02", "OWN-103", "Belgium", 57,
      ["Last modified less than 3 months ago", "Owner identified", "Informal source (email)",
       "Contains rounded figures", "Contradicts DOC-121 and DOC-122"],
      ["Hi Hilde, following CR-07 the total budget of Helios is now EUR 450,000.",
       "So far we have invoiced around EUR 270,000."]),
    D("DOC-125", "proposal_v1", "Proposal - Helios ERP migration (v1)", "presentation",
      "2025-02-18", "2025-02-18", "OWN-103", "Belgium", 46,
      ["Last modified more than 1 year ago", "Owner identified", "Superseded by the signed contract and CR-07",
       "Budget figures no longer valid"],
      ["The estimated budget for Project Helios is EUR 420,000.",
       "Invoicing follows five milestones: M1 15%, M2 20%, M3 30%, M4 20%, M5 15%."]),
    D("DOC-126", "budget_tracking_v3", "Budget tracking sheet v3 - working notes", "document",
      "2026-08-20", "2026-09-03", "OWN-104", "Belgium", 60,
      ["Last modified less than 1 month ago", "Owner identified (junior analyst)",
       "Informal working file, not reviewed", "Arithmetic inconsistency detected"],
      ["Working notes, not reviewed by the controller.",
       "Invoiced to date: 63,000 + 84,000 + 126,000 = 263,000.",
       "Budget: 480,000 including CR-07.",
       "Remaining to invoice: 217,000."]),
]

C4 = [  # governance / contacts
    D("DOC-131", "governance_charter", "Project governance charter v2.1", "document",
      "2025-06-02", "2026-05-20", "OWN-110", "Belgium", 86,
      ["Last modified less than 5 months ago", "Owner identified", "Applicable to Belgium",
       "Approved by both sponsors", "Consistent with DOC-133"],
      ["- Project sponsor (Norvik): Hilde Vermeulen, Chief Financial Officer.",
       "- Project sponsor (Brightline): Olivier Dupont, Delivery Director.",
       "- Technical contact for ERP interfaces (Norvik): Pieter Claes, IT Manager.",
       "- Project manager (Brightline): Nathalie Declercq.",
       "Escalation path: a blocking issue is first handled by the two project managers; if it is not solved "
       "within 2 working days, it is escalated to the sponsors of both companies.",
       "The steering committee meets monthly and validates all escalation decisions."]),
    D("DOC-132", "kickoff_deck", "Kick-off presentation - Project Helios", "presentation",
      "2025-06-10", "2025-06-10", "OWN-101", "Belgium", 55,
      ["Last modified more than 1 year ago", "Owner identified", "Contains roles that have since changed",
       "Partially superseded by DOC-131"],
      ["- Project sponsor (Norvik): Jan De Smet, Chief Operating Officer.",
       "- Technical contact for ERP interfaces (Norvik): Pieter Claes, IT Manager.",
       "Escalation path: a blocking issue not solved within 5 working days is escalated to the sponsors."]),
    D("DOC-133", "email_sponsor_change", "Email - Change of sponsor at Norvik", "email",
      "2026-04-28", "2026-04-28", "OWN-103", "Belgium", 75,
      ["Last modified less than 6 months ago", "Owner identified", "Informal source (email)",
       "Applicable to Belgium", "Consistent with DOC-131"],
      ["Dear partners, Jan De Smet will leave Norvik Engineering NV on 30 April 2026.",
       "Hilde Vermeulen, CFO, takes over as project sponsor for Project Helios from 4 May 2026."]),
    D("DOC-134", "client_contact_list", "Client contact list export", "spreadsheet",
      "2025-10-01", "2025-10-01", None, "Belgium", 41,
      ["Last modified more than 11 months ago", "No owner identified",
       "Contains contacts who have left the company"],
      ["- Sponsor: Jan De Smet, COO, +32 9 555 01 10.",
       "- Technical contact: Pieter Claes, IT Manager, +32 9 555 01 34.",
       "- Escalation contact: Jan De Smet."]),
    D("DOC-135", "teams_pieter_leave", "Teams discussion - Pieter Claes availability", "teams_discussion",
      "2026-07-08", "2026-07-08", "OWN-101", "Belgium", 70,
      ["Last modified less than 3 months ago", "Owner identified", "Informal source (Teams discussion)",
       "Applicable to Belgium", "Announces a temporary change not yet in DOC-131"],
      ["Nathalie: Heads-up, Pieter Claes is on parental leave until 30 November 2026.",
       "Nathalie: Sofie Wouters, IT Architect at Norvik, is the interim technical contact for the ERP interfaces.",
       "Dimitri: Noted, I will invite Sofie to the interface workshops."]),
]

C5 = [  # contract terms
    D("DOC-141", "msa_terms", "Master Services Agreement Norvik Engineering NV - Terms and conditions", "document",
      "2025-04-10", "2025-04-10", "OWN-105", "Belgium", 78,
      ["Signed contract", "Owner identified", "Applicable to Belgium",
       "Payment and penalty clauses amended by Amendment 1 (DOC-142)"],
      ["Article 8 - Payment: invoices are payable within 45 days of the invoice date.",
       "Article 11 - Late delivery: a penalty of 1% of the milestone value applies per full week of delay, "
       "capped at 5% of the milestone value.",
       "Article 14 - Governing law: the agreement is governed by Belgian law; the courts of Brussels have "
       "exclusive jurisdiction."]),
    D("DOC-142", "msa_amendment_1", "Amendment 1 to the Master Services Agreement", "document",
      "2026-01-20", "2026-01-20", "OWN-105", "Belgium", 88,
      ["Last modified less than 9 months ago", "Signed contract", "Owner identified",
       "Applicable to Belgium", "Most recent contractual document"],
      ["Amendment 1, signed on 20 January 2026 and effective from 1 February 2026, replaces Articles 8 and 11 "
       "of the agreement.",
       "New Article 8 - Payment: invoices are payable within 30 days of the invoice date.",
       "New Article 11 - Late delivery: a penalty of 0.5% of the milestone value applies per full week of delay, "
       "capped at 10% of the milestone value.",
       "All other provisions of the agreement remain unchanged."]),
    D("DOC-143", "email_contract_summary", "Email - Summary of contract terms for the delivery team", "email",
      "2026-02-05", "2026-02-05", "OWN-105", "Belgium", 72,
      ["Last modified less than 8 months ago", "Owner identified", "Informal source (email)",
       "Applicable to Belgium", "Consistent with DOC-142"],
      ["Hi all, as a reminder, since Amendment 1 invoices to Norvik are payable within 30 days.",
       "The late-delivery penalty is 0.5% of the milestone value per full week of delay, with a cap of 10%.",
       "Please do not use the terms of the original agreement anymore."]),
    D("DOC-144", "proposal_commercial_v1", "Commercial proposal - Helios (v1)", "presentation",
      "2025-02-18", "2025-02-18", "OWN-103", "Belgium", 40,
      ["Last modified more than 1 year ago", "Owner identified", "Superseded by the signed contract",
       "Commercial terms no longer valid"],
      ["Proposed payment terms: 60 days end of month.",
       "Proposed late delivery penalty: 2% per week."]),
    D("DOC-145", "msa_norvik_france", "Master Services Agreement - Norvik France SAS", "document",
      "2025-09-15", "2025-09-15", "OWN-105", "France", 82,
      ["Signed contract", "Owner identified", "Applicable to France, not Belgium",
       "Different legal entity (subsidiary)"],
      ["Invoices are payable within 60 days of the invoice date.",
       "Late delivery penalty: 1.5% per week, capped at 15%."]),
    D("DOC-146", "teams_payment_terms", "Teams discussion - Norvik payment terms", "teams_discussion",
      "2026-03-10", "2026-03-10", "OWN-103", "Belgium", 55,
      ["Last modified less than 8 months ago", "Owner identified", "Informal source (Teams discussion)",
       "Speculative content, contradicts DOC-142"],
      ["Élodie: I think we agreed 30 days payment but the penalty is still 1% per week, right?",
       "Bart: Not sure, I have to ask legal."]),
]

C6 = [  # certifications (medium confidence)
    D("DOC-151", "supplier_questionnaire", "Supplier qualification questionnaire - Norvik Engineering NV", "document",
      "2026-03-03", "2026-03-03", "OWN-108", "Belgium", 66,
      ["Last modified less than 7 months ago", "Owner identified", "Applicable to Belgium",
       "Self-declared by the client, not independently verified"],
      ["- ISO 9001 (quality management): certified, valid until 14 June 2027.",
       "- ISO 14001 (environmental management): certified, valid until 10 December 2026.",
       "- ISO 27001 (information security): not certified."]),
    D("DOC-152", "website_quality_page", "Norvik website - Quality page (archived extract)", "document",
      "2024-09-16", "2024-09-16", None, "Belgium", 54,
      ["Last modified more than 2 years ago", "No owner identified", "Marketing content",
       "Contradicts DOC-151 on ISO 27001"],
      ["Norvik Engineering NV is ISO 9001, ISO 14001 and ISO 27001 certified.",
       "Our ISO 14001 certificate is valid until 10 December 2026."]),
    D("DOC-153", "email_iso14001_audit", "Email - Norvik Quality Manager: ISO 14001 recertification", "email",
      "2026-08-19", "2026-08-19", "OWN-108", "Belgium", 70,
      ["Last modified less than 2 months ago", "Owner identified", "Informal source (email)",
       "Applicable to Belgium", "Consistent with DOC-151"],
      ["Dear Yannick, our ISO 14001 recertification audit is scheduled for 18 November 2026.",
       "The current ISO 14001 certificate remains valid until 10 December 2026, the new certificate is "
       "expected in December.",
       "ISO 9001 is unchanged and valid until 14 June 2027."]),
]

C7 = [  # insufficient
    D("DOC-161", "brochure_2021", "Corporate brochure - Norvik Engineering (2021)", "presentation",
      "2022-01-20", "2022-01-20", None, "Belgium", 39,
      ["Last modified more than 4 years ago", "No owner identified", "Marketing content",
       "Figures refer to 2021, not 2025"],
      ["Norvik achieved a turnover of about EUR 92 million in 2021.",
       "The group employs around 300 people in Belgium."]),
    D("DOC-162", "press_lille_site", "Press article - Norvik opens a site in Lille", "document",
      "2024-03-12", "2024-03-12", None, "France", 34,
      ["Last modified more than 2 years ago", "No owner identified", "Applicable to France, not Belgium",
       "Does not mention any Japanese subsidiary"],
      ["Norvik France SAS opened a new site in Lille and employs 45 people."]),
    D("DOC-163", "teams_norvik_size", "Teams discussion - Norvik size", "teams_discussion",
      "2026-03-04", "2026-03-04", "OWN-103", "Belgium", 33,
      ["Last modified less than 8 months ago", "Owner identified", "Informal source (Teams discussion)",
       "Figures given from memory, no source cited"],
      ["Élodie: I think Norvik is around EUR 100M revenue now, but I am not sure.",
       "Élodie: No idea about other countries."]),
    D("DOC-164", "newsletter_automation", "Newsletter - Industry trends in automation (2024)", "document",
      "2024-06-01", "2024-06-01", None, "Belgium", 47,
      ["Last modified more than 2 years ago", "No owner identified",
       "Mentions Norvik only in passing, no financial data"],
      ["Norvik Engineering NV was among the exhibitors at the 2024 automation fair in Brussels."]),
]

CASES = [
    dict(id="company_identity", name="Redundant sources + typo in VAT number + legacy address + homonymous entity",
         question="What are the legal name, VAT number and current registered address of our Belgian client "
                  "Norvik Engineering NV (Project Helios)?",
         docs=C1,
         expected=dict(
             confidence_level="high",
             documents_that_must_be_used=["DOC-101", "DOC-102"],
             optional_documents=["DOC-103", "DOC-105"],
             documents_that_must_not_be_used=["DOC-104", "DOC-106"],
             expected_contradictions=[
                 dict(between=["DOC-101", "DOC-104"], subject="registered address (Ghent vs Antwerp)",
                      expected_resolution="DOC-101 retained: score 91 vs 39, DOC-104 is a legacy export with no owner"),
                 dict(between=["DOC-101", "DOC-103"], subject="VAT number (BE 0456.789.123 vs typo BE 0456.789.132)",
                      expected_resolution="DOC-101 retained: the email only quotes the wrong number to report an error")],
             key_points_of_the_answer=["legal name: Norvik Engineering NV",
                                       "VAT number: BE 0456.789.123",
                                       "registered address: Kortrijksesteenweg 1120, 9051 Ghent (since 1 March 2025)"],
             must_contain=["Norvik Engineering NV", "0456.789.123", "Kortrijksesteenweg 1120"],
             must_not_contain=["0456.789.132", "Noorderlaan", "Lille", "FR 12"],
             to_check="The VAT typo, the old Antwerp address and the French subsidiary (DOC-106) never appear as valid facts.")),
    dict(id="project_status", name="Project status: outdated reports, baseline plan, unverified client email",
         question="What is the current status of Project Helios (ERP migration for Norvik Engineering NV): which "
                  "milestones are completed, what is the forecast go-live date and what are the main open risks?",
         docs=C2,
         expected=dict(
             confidence_level="high",
             documents_that_must_be_used=["DOC-111", "DOC-112"],
             optional_documents=["DOC-116"],
             documents_that_must_not_be_used=["DOC-114"],
             expected_contradictions=[
                 dict(between=["DOC-111", "DOC-113"], subject="forecast go-live (23/11/2026 vs 14/09/2026) and duplicates rate",
                      expected_resolution="DOC-111/DOC-112 retained (scores 90/84 vs 52, week 31 report superseded)"),
                 dict(between=["DOC-111", "DOC-115"], subject="go-live date (23 Nov vs 19 Oct 2026)",
                      expected_resolution="DOC-111 retained: the email is an unverified forwarded message (55)")],
             key_points_of_the_answer=["M1, M2, M3 completed; M4 (UAT) in progress (70% scripts executed, end 16 Oct 2026)",
                                       "forecast go-live: 23 November 2026 (after CR-07)",
                                       "risks: supplier data quality (12% duplicates), key-user availability, MES interface"],
             must_contain=["23 November 2026|23/11/2026", "M3", "12%"],
             must_not_contain=["19 October 2026", "14/09/2026", "14 September 2026", "20% duplicates"],
             to_check="Old go-live dates (14 Sept, 19 Oct) are never presented as current.")),
    dict(id="project_budget", name="Budget: signed change request, rounded email figures and an arithmetic error",
         question="What is the current approved budget of Project Helios, how much has been invoiced so far and "
                  "how much remains to be invoiced?",
         docs=C3,
         expected=dict(
             confidence_level="high",
             documents_that_must_be_used=["DOC-121", "DOC-123"],
             optional_documents=["DOC-122"],
             documents_that_must_not_be_used=["DOC-125"],
             expected_contradictions=[
                 dict(between=["DOC-121", "DOC-124"], subject="budget (480,000 vs 450,000) and invoiced amount (273,000 vs ~270,000)",
                      expected_resolution="DOC-121 retained: controller report (89) vs informal email with rounded figures (57)"),
                 dict(between=["DOC-121", "DOC-126"], subject="invoiced (273,000 vs 263,000) and remaining (207,000 vs 217,000)",
                      expected_resolution="DOC-121 retained; DOC-126 contains an addition error (63,000+84,000+126,000 = 273,000)")],
             key_points_of_the_answer=["approved budget: EUR 480,000 (420,000 + CR-07 60,000)",
                                       "invoiced to date: EUR 273,000 (M1 63,000 + M2 84,000 + M3 126,000)",
                                       "remaining to invoice: EUR 207,000"],
             must_contain=["480,000", "273,000", "207,000"],
             must_not_contain=["450,000", "263,000", "217,000", "270,000"],
             to_check="The wrong total (263,000) and the rounded/draft figures are never used.")),
    dict(id="governance_contacts", name="Governance: sponsor change, outdated kick-off deck, newer but less trusted info",
         question="Who is the current project sponsor at Norvik Engineering NV for Project Helios, who is the "
                  "technical contact for the ERP interfaces and what is the escalation path for a blocking issue?",
         docs=C4,
         expected=dict(
             confidence_level="medium",
             documents_that_must_be_used=["DOC-131", "DOC-135"],
             optional_documents=["DOC-133"],
             documents_that_must_not_be_used=["DOC-134"],
             expected_contradictions=[
                 dict(between=["DOC-131", "DOC-132"], subject="sponsor (Hilde Vermeulen vs Jan De Smet) and escalation delay (2 vs 5 working days)",
                      expected_resolution="DOC-131 retained (86 vs 55), kick-off deck outdated"),
                 dict(between=["DOC-131", "DOC-135"], subject="technical contact (Pieter Claes vs interim Sofie Wouters)",
                      expected_resolution="UNRESOLVED on purpose: DOC-135 is more recent but less trusted, both must be shown and flagged")],
             key_points_of_the_answer=["sponsor: Hilde Vermeulen (CFO), replaced Jan De Smet in May 2026",
                                       "technical contact: Pieter Claes, but interim Sofie Wouters until 30 Nov 2026 (to be confirmed)",
                                       "escalation: project managers, then sponsors after 2 working days"],
             must_contain=["Hilde Vermeulen", "Sofie Wouters", "2 working days"],
             must_not_contain=["Chief Operating Officer", "5 working days"],
             to_check="The outdated sponsor and 5-day escalation are not used; the interim contact is shown with a warning instead of being silently dropped.")),
    dict(id="contract_terms", name="Contract: amendment overrides original terms, speculation in chat, other entity's contract",
         question="What are the payment terms and the late-delivery penalty in the contract between Brightline and "
                  "our Belgian client Norvik Engineering NV?",
         docs=C5,
         expected=dict(
             confidence_level="high",
             documents_that_must_be_used=["DOC-142"],
             optional_documents=["DOC-143"],
             documents_that_must_not_be_used=["DOC-144", "DOC-145", "DOC-146"],
             expected_contradictions=[
                 dict(between=["DOC-141", "DOC-142"], subject="payment delay (45 vs 30 days) and penalty (1%/5% vs 0.5%/10%)",
                      expected_resolution="DOC-142 retained: it explicitly replaces Articles 8 and 11 and is more recent"),
                 ],
             key_points_of_the_answer=["payment within 30 days of invoice date", "penalty 0.5% of milestone value per full week of delay, capped at 10%",
                                       "applies since Amendment 1 (effective 1 February 2026)"],
             must_contain=["30 days", "0.5%", "10%"],
             must_not_contain=["45 days", "1% of the milestone", "1% per week", "60 days", "2% per week", "1.5%"],
             to_check="The superseded terms of the original MSA, the French contract and the speculative Teams question (DOC-146, a question is not an assertion) are never given as valid.")),
    dict(id="certifications", name="Certifications: self-declared data and outdated marketing claim (medium confidence)",
         question="Which ISO certifications does Norvik Engineering NV currently hold and when does each of them expire?",
         docs=C6,
         expected=dict(
             confidence_level="medium",
             documents_that_must_be_used=["DOC-151", "DOC-153"],
             optional_documents=[],
             documents_that_must_not_be_used=[],
             expected_contradictions=[
                 dict(between=["DOC-151", "DOC-152"], subject="ISO 27001 (not certified vs certified)",
                      expected_resolution="DOC-151 retained: more recent and higher score; the website page is an old marketing claim")],
             key_points_of_the_answer=["ISO 9001 valid until 14 June 2027", "ISO 14001 valid until 10 December 2026 (recertification audit 18 Nov 2026)",
                                       "ISO 27001: not certified"],
             must_contain=["14 June 2027", "10 December 2026", "not certified"],
             must_not_contain=["ISO 9001, ISO 14001 and ISO 27001 certified"],
             to_check="Confidence stays MEDIUM (best score 70, self-declared data) and ISO 27001 is not claimed.")),
    dict(id="insufficient_financials", name="Insufficient: weak, outdated or irrelevant documents, the system must refuse",
         question="What was the annual revenue of Norvik Engineering NV in 2025 and how many employees work in its "
                  "Japanese subsidiary?",
         docs=C7,
         expected=dict(
             confidence_level="insufficient",
             documents_that_must_be_used=[],
             optional_documents=[],
             documents_that_must_not_be_used=["DOC-161", "DOC-162", "DOC-163", "DOC-164"],
             expected_contradictions=[],
             key_points_of_the_answer=["the system gives NO figure", "it explains that the best score (47) is below the threshold of 50 and that "
                                       "no document covers 2025 revenue or a Japanese subsidiary",
                                       "it recommends an expert (suggested: OWN-109, credit risk analyst)"],
             must_contain=[], must_not_contain=["92 million", "100M", "45 people"],
             suggested_expert_id="OWN-109",
             to_check="The guardrail blocks generation BEFORE any PDF is read or any AI is called; the 2021 figures and the vague Teams guess are not proposed.")),
]


# --------------------------------------------------------------------------- PDF
def write_pdf(doc, path):
    st = getSampleStyleSheet()
    pdf = SimpleDocTemplate(str(path), pagesize=A4, topMargin=50, bottomMargin=50,
                            leftMargin=55, rightMargin=55, title=doc["title"])
    owner = OWNER_NAME.get(doc["owner"], "unknown")
    story = [Paragraph(f"<b>{doc['title']}</b>", st["Heading3"]),
             Paragraph(f"Type: {doc['type'].replace('_', ' ').capitalize()} | Created: {doc['created']} | "
                       f"Last modified: {doc['modified']} | Owner: {owner}", st["Italic"]),
             Spacer(1, 10)]
    for line in doc["body"]:
        story += [Paragraph(line.replace("&", "&amp;"), st["BodyText"]), Spacer(1, 3)]
    pdf.build(story)


def main():
    (OUT / "pdf").mkdir(parents=True, exist_ok=True)
    owned = {o[0]: [] for o in OWNERS}
    for case in CASES:
        for d in case["docs"]:
            if d["owner"]:
                owned[d["owner"]].append(d["id"])
    owners = {"owners": [dict(owner_id=o[0], name=o[1], job_title=o[2], department=o[3], country="Belgium",
                              years_of_experience=o[4], seniority_level=o[5], expertise_domains=o[6],
                              languages=o[7], email=f"{o[1].split()[0].lower().replace('é', 'e')}."
                              f"{o[1].split()[-1].lower()}@example.com", documents_owned=sorted(owned[o[0]]))
                         for o in OWNERS]}
    cases = []
    for c in CASES:
        docs = []
        for d in c["docs"]:
            fname = f"{d['id']}_{d['slug']}.pdf"
            write_pdf(d, OUT / "pdf" / fname)
            docs.append(dict(id=d["id"], title=d["title"], type=d["type"], file=f"documents/{fname}",
                             created_date=d["created"], last_modified_date=d["modified"], owner_id=d["owner"],
                             country=d["country"], trust_score=d["score"], trust_reasons=d["reasons"]))
        cases.append(dict(id=c["id"], name=c["name"], input=dict(question=c["question"], documents=docs),
                          expected=c["expected"]))
    (OUT / "owners.json").write_text(json.dumps(owners, indent=2, ensure_ascii=False), "utf-8")
    (OUT / "test_cases.json").write_text(json.dumps({"cases": cases}, indent=2, ensure_ascii=False), "utf-8")
    print(f"{len(cases)} cases, {sum(len(c['docs']) for c in CASES)} PDFs written to {OUT}")


if __name__ == "__main__":
    main()