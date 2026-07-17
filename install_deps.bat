@echo off
echo ============================================
echo  MedVoice Dependency Installer
echo ============================================

set PIP="%~dp0.venv\Scripts\pip.exe"
echo Using pip: %PIP%

echo.
echo [1/4] Installing Ollama Python client...
%PIP% install ollama
echo Ollama done. Exit: %ERRORLEVEL%

echo.
echo [2/4] Installing SpeechRecognition...
%PIP% install SpeechRecognition
echo SpeechRecognition done. Exit: %ERRORLEVEL%

echo.
echo [3/4] Installing pyttsx3 (offline TTS)...
%PIP% install pyttsx3
echo pyttsx3 done. Exit: %ERRORLEVEL%

echo.
echo [4/4] Installing edge-tts (online TTS fallback)...
%PIP% install edge-tts
echo edge-tts done. Exit: %ERRORLEVEL%

echo.
echo ============================================
echo Verifying installations...
echo ============================================
%PIP% show ollama
%PIP% show SpeechRecognition
%PIP% show pyttsx3
%PIP% show edge-tts

echo.
echo ============================================
echo  ALL DONE! Now pulling Qwen3 model in Ollama
echo  Run: ollama pull qwen3:8b
echo ============================================
pause
