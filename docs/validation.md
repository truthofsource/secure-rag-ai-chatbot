# Validation and operating boundaries

## Recorded local checks

- Python 3.12: **44 offline tests passed** for this project.
- Fictional CLI demonstrations and relevant duplicate, denial and recovery cases passed.
- Architecture SVG/PNG, README links and desktop/mobile documentation views were checked.
- Terraform retains its previous provider-schema validation; no plan/apply or live provisioning was performed.
- A manual GitHub Actions workflow is included; no Actions run is required to execute the local tests.

Run from the project root:

```powershell
python -m unittest discover -s tests -v
```

Read [the recorded output](test-output.txt) for the individual cases. Provider
responses and scanner callbacks are simulated in tests. These checks do not
prove live service quality, genuine malware scanning, authenticated hosted
access, physical printing, measured cloud costs or full disaster recovery.
Optional provider calls remain Off unless explicitly selected and configured.
