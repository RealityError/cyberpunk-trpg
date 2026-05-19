# Development

Run commands from the project root.

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Open the API docs:

```text
http://127.0.0.1:8000/docs
```

Example check roll:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/rolls/check `
  -ContentType "application/json" `
  -Body '{"label":"handgun","stat":8,"skill":6,"modifier":0,"dv":15}'
```
