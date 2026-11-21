# Commands

Run these from the project root after creating your files and virtual environment.
Use the README for each command’s prerequisites and expected result; configure optional live calls only when authorized.

```powershell
mkdir secure-rag-ai-chatbot
cd secure-rag-ai-chatbot
python -m venv .venv
```

```powershell
.venv\Scripts\python -m rag_project --db work/import-example/library.db index examples/manifest.json --reviewed-input
# For an actual approved scanned PDF with matching genuine OCR JSON:
.venv\Scripts\python -m rag_project --db work/ocr-example/library.db index examples/scan-manifest.json --ocr-result work/ocr-pages.json --reviewed-input
```

```powershell
.venv\Scripts\python -m rag_project --db work/demo/library.db demo
```

```powershell
.venv\Scripts\python -m rag_project --db work/demo/library.db search "attendance" --role Caregiver
.venv\Scripts\python -m rag_project --db work/demo/library.db search "restricted" --role Caregiver
.venv\Scripts\python -m rag_project --db work/demo/library.db search "restricted" --role Admin
```

```powershell
.venv\Scripts\python -m pip install -r requirements-azure.txt
az login
$env:AZURE_OPENAI_ENDPOINT = 'https://YOUR-RESOURCE.openai.azure.com'
$env:AZURE_OPENAI_DEPLOYMENT = 'YOUR-CHAT-DEPLOYMENT'
$env:ANSWER_ESTIMATE_MICRO = '10000' # Example $0.01 hold, not a current quote.
$env:ALLOW_AZURE_CALLS = 'yes'
```

```powershell
.venv\Scripts\python -m rag_project --db work/demo/library.db answer "What should I do about a missed clock event?" --role Caregiver --request-id YOUR-UUID
```

```powershell
.venv\Scripts\python -m rag_project --db work/demo/library.db withdraw general
.venv\Scripts\python -m rag_project --db work/demo/library.db search "attendance" --role Caregiver
.venv\Scripts\python -m unittest discover -s tests -v
```
