# Secure RAG AI Chatbot — Build Your Own


### Prerequisites

Use Python 3.11 or newer and your own fictional test files. Azure and external AI are optional; live examples require your own approved account, network path and reviewed processing costs.

Commands run from your new project root; use PowerShell for the shown environment-variable syntax. Follow the named source files as implementation references without needing to clone a portfolio repository.


### Step 1 — Create the project structure

Create a folder named `secure-rag-ai-chatbot` with `rag_project`,
`examples`, `tests` and `docs` subfolders. Use the accompanying files as
implementation references to build each component below, without needing
to clone an existing repository.

```powershell
mkdir secure-rag-ai-chatbot
cd secure-rag-ai-chatbot
python -m venv .venv
```

Commands below run from that folder after placing the accompanying files in
their indicated paths. On Windows use `.venv\Scripts\python`; on Linux/macOS
substitute `.venv/bin/python`.

### Step 2 — Define audiences before indexing documents

Define a tenant, source ID, title, classification, explicit staff audience and
separate AI/OCR permissions for each document. General means the listed staff
roles, not public internet access; this example allows Restricted sources only
for explicitly selected Admin, HR or Payroll roles.

```json
{
  "tenant": "fictional",
  "id": "attendance-instructions",
  "title": "Attendance instructions",
  "file": "general.txt",
  "classification": "General",
  "roles": ["Admin", "HR", "Payroll", "Supervisor", "Caregiver"],
  "ai_allowed": true,
  "ocr_allowed": false,
  "reviewed_sha256": "REPLACE_WITH_EXACT_FILE_SHA256"
}
```

Save this as a manifest next to the referenced file. Paths are resolved relative
to that manifest; the operator must review the exact source and its safety.

### Step 3 — Prepare original text or approved OCR output

Read UTF-8 TXT/Markdown locally and preserve the exact original hash, or import
page-numbered JSON from the separate Azure OCR project with OCR permission On.
Do not invent page numbers for a plain-text file, pass a fictional fixture as
real OCR evidence or automatically send unreadable files to a paid service.

```powershell
.venv\Scripts\python -m rag_project --db work/import-example/library.db index examples/manifest.json --reviewed-input
# For an actual approved scanned PDF with matching genuine OCR JSON:
.venv\Scripts\python -m rag_project --db work/ocr-example/library.db index examples/scan-manifest.json --ocr-result work/ocr-pages.json --reviewed-input
```

The included `examples/manifest.json` matches the fictional text file. Create
`examples/scan-manifest.json` separately with your own approved PDF and reviewed hash. The import examples use separate databases, so they do not leave
a duplicate source in the walkthrough demo database. Native PDF/DOCX parsers
are outside this implementation; add and test them separately when required.

### Step 4 — Publish a complete source revision

Split text into whole-word chunks of at most 1,200 characters with up to 30
words of overlap, and store normalized terms alongside source provenance.
Commit the new source and all chunks atomically so a failed extraction cannot
leave a partially published replacement.

```powershell
.venv\Scripts\python -m rag_project --db work/demo/library.db demo
```

This creates two fictional sources without any Azure call. The chunking and
128-codepoint term rules count Python Unicode characters. Revalidate these
limits when adding other parsers or changing the indexing strategy.

Rerunning `demo` deliberately restores its two fictional sources and advances
their revisions. Run it only in the dedicated demo database; repeat it before
restarting the walkthrough after the withdrawal step.

### Step 5 — Retrieve evidence before asking AI

Filter by tenant, active source and permitted role, rank local term metadata,
then validate the selected originals before loading at most five passage texts.
Recheck every selected source again immediately before returning search results. Return no
evidence for unrelated questions rather than confusing a search match with
proof that an answer is correct.

```powershell
.venv\Scripts\python -m rag_project --db work/demo/library.db search "attendance" --role Caregiver
.venv\Scripts\python -m rag_project --db work/demo/library.db search "restricted" --role Caregiver
.venv\Scripts\python -m rag_project --db work/demo/library.db search "restricted" --role Admin
```

The Caregiver restricted search returns `[]`, while Admin can see the permitted
fictional passage. `--role` simulates a trusted caller for the local exercise;
**it is not Entra sign-in and must never become a client-selected web role**.

### Step 6 — Prepare keyless Azure generation

Prepare an Azure OpenAI account and a chat-compatible model deployment with
JSON mode, then give the intended caller the account-scoped `Cognitive Services
OpenAI User` role. Verify the region, private DNS/path, model compatibility and
current price before setting an explicit conservative answer estimate.

```powershell
.venv\Scripts\python -m pip install -r requirements-azure.txt
az login
$env:AZURE_OPENAI_ENDPOINT = 'https://YOUR-RESOURCE.openai.azure.com'
$env:AZURE_OPENAI_DEPLOYMENT = 'YOUR-CHAT-DEPLOYMENT'
$env:ANSWER_ESTIMATE_MICRO = '10000' # Example $0.01 hold, not a current quote.
$env:ALLOW_AZURE_CALLS = 'yes'
```

### Step 7 — Generate and validate one grounded answer

Send only the question and permitted passages, with an instruction to treat
document text as untrusted evidence and cite supplied IDs. Reject malformed,
uncited or foreign-citation answers and recheck every supplied source before
disclosure, including passages the model did not cite.

```powershell
.venv\Scripts\python -m rag_project --db work/demo/library.db answer "What should I do about a missed clock event?" --role Caregiver --request-id YOUR-UUID
```

This operator-run example was not executed against Azure for the project.
Citation validation proves referenced IDs were supplied, not that every model
sentence is factually entailed; human review and relevance evaluation remain necessary.

### Step 8 — Prove revocation, denial and uncertainty

Withdraw a fictional source and confirm new searches omit it, then run tests
that change or withdraw evidence while a mocked model is responding. Keep the
old usage/audit records and hold uncertain paid work instead of creating a new
request ID to bypass it.

```powershell
.venv\Scripts\python -m rag_project --db work/demo/library.db withdraw general
.venv\Scripts\python -m rag_project --db work/demo/library.db search "attendance" --role Caregiver
.venv\Scripts\python -m unittest discover -s tests -v
```

After withdrawing `general`, the attendance search in this dedicated demo
database returns `[]`. The separate import-example database is unaffected.

### Step 9 — Plan the hosted identity boundary separately

Before exposing an API, validate Entra access-token signature, issuer, audience,
expiry, tenant and current staff/role state server-side and derive the principal
there. Replace local file paths/CLI authority with protected Blob/version reads,
real scan proofs, category/person rules and an authoritative policy store, then
test genuine lower-role denials and private paths in an isolated environment.
