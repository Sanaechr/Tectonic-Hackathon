# Tectonic Hackathon - SD Worx Challenge: "Unlock the Knowledge Within"

## Team

- Chakroune Reda
- Chakroune Sanae

## Context: how we chose this problem

The SD Worx challenge starts from a simple observation: in large organisations, knowledge exists but is fragmented across documents, emails, chats and people. It is often duplicated, outdated, or has no clear owner. Finding information is only the first step. The harder question is: **can I trust it?** This is fundamentally a trust problem.

We split the problem into three stages:

1. **Find**: retrieve the documents relevant to an employee's question.
2. **Evaluate**: assess each document and assign it a Trust Score.
3. **Answer**: use the retrieved, scored documents to give the employee a reliable answer.

We decided to focus on **stage 3**. Stages 1 and 2 are well-known retrieval and scoring problems, and we assumed them to be solved so that we could spend our limited time on a less explored question: *once the documents and their trust scores exist, how do we generate a reliable answer for the employee without a black box behind it?*

## Use case

An employee starts working on a project for an existing client company, previously handled by a colleague. They need accurate information about the state of the project and the company's data. When they search the database (for example by company name), they find several documents. Each document has its content and metadata (owner, creation date, last modification date, title, type, etc.) along with a Trust Score for the whole document. The employee wants a consolidated answer that gathers all the relevant information, and can ask questions or use keywords to get it.

- **Input:** the employee's question and all the documents found in the database, with their metadata and Trust Scores.
- **Output:** an aggregation of texts extracted from the documents that answers the employee's request. The employee can ask for details about the source of each element of the output.

## Assumptions

The following steps are considered **already done** and are not part of this project:

1. The employee's question has been analysed.
2. The relevant documents have already been found in the database.
3. The documents have been evaluated and a Trust Score has been computed for each of them (pre-processing, including metadata extraction).

We made these assumptions because they are simpler to implement and because we wanted to concentrate on what happens afterwards: producing an answer the employee can understand and verify.

## Design principle: no black box

The employee should not just receive "here is the answer". They should understand why this answer was produced and how far it can be trusted. The system is therefore designed to show:

- the documents used and their Trust Scores,
- the passages that actually contributed to the answer,
- where each piece of information comes from,
- a clear signal when the available documents are not reliable enough to answer.

## Current status

- The answer is built by **rule-based aggregation** of text extracted from the documents, prioritising documents with higher Trust Scores, with source traceability.
- **No LLM is integrated in this version.** We attempted to integrate Google Gemini, but our API project had a quota of zero requests, so we could not complete it in time.
- Trust Scores and document retrieval are taken as given (see Assumptions).

## How to run

Requirements: Python 3.10+ and Git.

```powershell
# 1. Clone the repository
git clone <REPOSITORY_URL>
cd Tectonic-Hackathon

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux

# 3. Install the dependencies
pip install -r requirements.txt

# 4. Launch the app
streamlit run app.py
```

If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope Process Bypass` and try again.

**Environment variables:** this version does not need any API key. If you add an LLM later, copy `.env.example` to `.env` and fill in your key. Never commit `.env`.

## Possible improvements

**1. Add an LLM for answer generation (main next step)**
- Give the model only the question and the retrieved documents with their Trust Scores, and forbid it from using outside knowledge.
- Require a structured output: answer, confidence level, sources used with their role, exact excerpts, contradictions and uncertainties.
- Verify in code that every cited excerpt exists word for word in the source document, to prove that nothing was invented.
- Add a code-level guardrail: if the best Trust Score is below a threshold, do not call the model and tell the employee that the documents are not reliable enough.

**2. Formalise the parameters that are currently not clearly defined**
- Minimum Trust Score below which a document is ignored or flagged.
- How the Trust Score weights a document in the aggregation (filtering, ranking, or weighting).
- How relevance to the question is measured (keyword matching today, semantic search with embeddings later).
- Thresholds for confidence levels (high / medium / low / insufficient).
- Maximum number of documents and maximum excerpt length used in an answer.
- How contradictions are resolved (for example keep the highest-scored source and flag the disagreement).

**3. Detect and explain contradictions** between documents instead of only prioritising by score, and show them side by side to the employee.

**4. Use the owner's profile** (years of experience, domain of expertise) as an additional trust signal, and **suggest the right expert to contact** when confidence is too low.

**5. Close the loop:** when an employee or expert confirms an answer, save it as a validated knowledge card that becomes a more trusted source for the next colleague, moving from fragmented to shared knowledge.

**6. Replace the assumptions with real components:** a retrieval step (semantic search over the company's documents) and a Trust Score computation (freshness, owner identified, country applicability, consistency with other sources).

**7. Support more document types** (emails, chat exports, presentations) and broaden the test cases.