@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m streamlit run app.py
  exit /b
)
if exist "..\..\..\work\.venv\Scripts\python.exe" (
  "..\..\..\work\.venv\Scripts\python.exe" -m streamlit run app.py
  exit /b
)
echo No se encontro el entorno de Python del proyecto.
echo Sigue los pasos de instalacion de README.md y vuelve a ejecutar este archivo.
pause
