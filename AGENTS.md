## Imported Claude Cowork project instructions

## Môi trường Python

- **Luôn dùng conda env `survey-digitizer`** cho mọi lệnh Python trong dự án này (chạy script, cài package, test).
- Interpreter: `E:\anaconda3\envs\survey-digitizer\python.exe` (Python 3.12).
- KHÔNG dùng `python`/`py` trên PATH — đó là stub Microsoft Store, không chạy được.
- Ví dụ chạy script: `& "E:\anaconda3\envs\survey-digitizer\python.exe" scripts/validate_schema.py schema/questionnaire_v1.json`
- Cài package: `& "E:\anaconda3\envs\survey-digitizer\python.exe" -m pip install <pkg>`
