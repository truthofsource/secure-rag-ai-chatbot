# Platform Architecture

The illustrated diagram follows the implemented platform design. The runnable
Python examples exercise core rules locally; hosted infrastructure, authentication
and scanner integrations are separate from executing those examples.

| Platform component | Responsibility |
| --- | --- |
| React / Azure Static Web Apps | Documents management, reader and floating assistant |
| Microsoft Entra ID | Staff sign-in; API token validation and refreshed account/role checks |
| Azure Functions API | Authorized requests, extraction/retrieval coordination and protected original-file reads |
| Private Blob Storage | Original/quarantined files with exact version, ETag, size and hash |
| Defender for Storage / Event Grid / scan queues and processor | Existing trusted scan-result route; clean upload is separate from search inclusion |
| Azure SQL | Source policies, leased index jobs, published text passages, usage and RAG audit |
| API-host indexing timer | Five-minute UTC schedule or Admin maintenance action; no dedicated RAG container |
| Native parsing | Existing PDF/DOCX/plain-text extraction before considering OCR |
| Azure Document Intelligence Read | Optional OCR; requires server and source permission; transfers whole approved file for selected-page processing |
| Azure OpenAI deployment | Optional answer generation using a question and at most five permitted passages |
| Managed identities / Hub private endpoints and DNS | Service authentication and private reachability; managed AI accounts themselves are not inside the VNet |

The current retrieval design is keyword-based Azure SQL, with no vector database,
embedding service or Azure AI Search tier. Index jobs use SQL leases; Storage
queues in the diagram belong to the separate Defender scan pipeline.

General is an explicitly selected internal staff audience. Restricted access
also intersects category rights and supported record-link checks; a person link
does not imply self-only or assigned-client access. W-4/I-9 sources are excluded.
Every passage inherits its whole document's policy, and Admin has no audience bypass.

AI answers and OCR have separate enablement and source consent. OCR receives
the whole approved file, while answer generation receives only the question and
bounded permitted passages. The API rechecks sources before publication and
answer disclosure; protected source opening never grants a permanent Blob URL.

Usage is reserved before paid processing. Unknown submissions retain their hold;
the platform saves OCR receipts but does not automatically resume them after a
worker restart. An operator must reconcile uncertain work before any new submission.

Recognized text is stored as derived search content in SQL. The original file
remains unchanged; OCR does not create a new searchable-PDF download.

The diagram describes implementation paths, not a live health or availability
check. Runtime flags, source settings, service state and private paths determine
which operations can execute. Purpose icons follow the portfolio's existing style.
