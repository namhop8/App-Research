@echo off
rem Mở văn phòng ResearchLab (không kèm cửa sổ đen, tắt bằng nút ⏻ trên app).
rem Lần đầu chạy sẽ tự tạo shortcut "Văn phòng ResearchLab" trên Desktop.
chcp 65001 >nul
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw tools\office.py serve --open & exit /b)
where pyw >nul 2>nul && (start "" pyw -3 tools\office.py serve --open & exit /b)
echo.
echo  Máy này chưa có Python 3.
echo  Cài bằng lệnh:  winget install -e --id Python.Python.3.12
echo  hoặc tải ở https://www.python.org/downloads/ (nhớ tick "Add python.exe to PATH"),
echo  cài xong thì bấm lại file này.
echo.
pause
