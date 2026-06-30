@echo off
title StudioKit Companion
cd /d E:\studiokit
"C:\Users\dylan\.local\bin\uv.exe" run --python 3.12 --with anthropic --with mido --with python-rtmidi python companion.py
pause
