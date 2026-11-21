# Optional Azure infrastructure preparation

No plan or apply was executed for this portfolio project. This illustrative
Terraform creates a dedicated resource group, keyless/private S0 AI account,
one private endpoint/DNS group and one account-scoped data role assignment.
It uses an **existing** endpoint subnet and existing `privatelink.openai.azure.com` zone; the zone
must already be linked to the caller's VNet or resolvable through approved DNS.
The endpoint location must match the subnet's region; choose the AI account
location accordingly for this simplified template, or split location inputs
deliberately in your own cross-region design. The RAG example also requires a separately selected chat-compatible model deployment; this Terraform intentionally does not pick a model/version/region or allocate model quota.

Supply a dedicated subscription/resource group/account name and the intended
caller's **object ID**, not an application/client ID. For local CLI tests the
caller is the signed-in developer; for hosted deployment it is the workload's
managed identity. Creating a role assignment needs appropriate access-management
authority, not merely service invocation permission.

```powershell
cd infra
terraform init
terraform fmt -check
terraform validate
terraform plan -var-file=your-private-values.tfvars -out=reviewed.tfplan
# Inspect the plan and all costs before deciding whether to apply it.
```

Do not commit tfvars, state, saved plans, tenant IDs or live resource endpoints.
No hosted Function, VNet, routing, private caller, DNS zone/link, scan service,
Blob store or database is commissioned by this template. A normal public
laptop cannot call the private account without a working authorized path.
Terraform formatting and provider-schema validation passed locally with AzureRM
4.81.0. No plan/apply or hosted compatibility test was performed; offline Python
tests do not validate a live private path or model deployment.

Use a separate state key per project/environment. Destroy only this dedicated
lab's owned resources after preserving required data; never run a generic
cleanup against a shared network or existing application environment. Private
endpoints and shared DNS/log resources can incur charges while no requests run.

Reference: [AzureRM cognitive account resource](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/cognitive_account).
