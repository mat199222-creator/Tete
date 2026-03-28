name: Build Windows EXE

on:
  workflow_dispatch:
  push:
    branches: [ "main" ]

jobs:
  build-windows:
    runs-on: windows-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Build EXE with PyInstaller
        run: |
          pyinstaller --noconfirm --clean --onefile --windowed --name OXImageRenderTool app.py

      - name: Upload EXE artifact
        uses: actions/upload-artifact@v4
        with:
          name: OXImageRenderTool-Windows
          path: dist/OXImageRenderTool.exe
