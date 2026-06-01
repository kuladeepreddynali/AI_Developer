@echo off

echo Starting Enterprise AI API...

uvicorn main:app --host 0.0.0.0 --port 8000 
@REM python Services/schema_extractor.py

pause