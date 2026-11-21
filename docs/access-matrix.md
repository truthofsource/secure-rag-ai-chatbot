# Access matrix

| Operation | General source | Restricted source | Additional condition |
| --- | --- | --- | --- |
| Search | Listed role and matching tenant | Listed Admin/HR/Payroll role and matching tenant | Active source, current revision/hash |
| Generate answer | Same read rights | Same read rights | AI permission on every supplied source |
| Import OCR result | Trusted local operator | Trusted local operator | OCR allowed, schema 1, numbered pages, exact original hash, expected method label |
| Index/withdraw | Trusted local operator | Trusted local operator | Local file/database access is administrative authority |

There is no internet/public audience, automatic Admin override or cross-tenant
fallback. Local operator role arguments are simulations, not verified tokens.
No account/person-linked permission or public API is provided. Source withdrawal
preserves originals and accounting but cannot recall previous disclosure.

The method label is not a signed provider proof. Hosted ingestion must verify
server-owned operation/output lineage; local operator JSON is trusted input here.
