# Node Health Analyzer - Build Process

## Purpose

This document describes the validated build process for Node Health Analyzer.

The commands below were tested and confirmed to work with:

* PySide6
* Plotly
* SQLAlchemy
* Multi-language support
* Export features
* Graph visualization
* Installer generation

---

# Clean Previous Build

Always remove old build artifacts before compiling.

```powershell
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
```

---

# Build Executable

Use the validated PyInstaller command.

```powershell
pyinstaller --noconfirm --onedir --windowed `
--name NodeHealthAnalyzer `
--collect-data plotly `
--collect-submodules plotly `
--collect-submodules PySide6.QtCore `
--collect-submodules PySide6.QtGui `
--collect-submodules PySide6.QtWidgets `
--collect-submodules PySide6.QtNetwork `
--collect-submodules PySide6.QtWebEngineWidgets `
--collect-submodules PySide6.QtWebEngineCore `
--collect-submodules PySide6.QtWebChannel `
--collect-submodules PySide6.QtPrintSupport `
main.py
```

Important:

Do not use:

```powershell
pyinstaller --onefile
```

because it increases startup time and caused issues during testing.

The project uses:

```text
onedir
```

distribution mode.

---

# Validate Executable

Run the generated executable.

```powershell
.\dist\NodeHealthAnalyzer\NodeHealthAnalyzer.exe
```

Verify:

* Application starts correctly
* Node details window works
* Node comparison works
* Plotly graphs display correctly
* Export functions work
* Language switching works

---

# Generate Installer

Compile the Inno Setup installer.

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Expected output:

```text
installer_output\
NodeHealthAnalyzer_Setup_vX.X.X.exe
```

---

# Installer Validation

Install on a clean machine when possible.

Validate:

* Installation completes successfully
* Application starts correctly
* Database is created automatically
* Trial system works
* Export functions work
* Graphs display correctly

---

# Git Workflow

Development branch:

```powershell
git checkout develop
```

Commit changes:

```powershell
git add .
git commit -m "Description of changes"
```

Push:

```powershell
git push origin develop
```

Stable releases are merged later into:

```text
main
```

---

# Release Workflow

1. Develop in:

```text
develop
```

2. Validate functionality.

3. Generate installer.

4. Merge into:

```text
main
```

5. Create tag:

```powershell
git tag vX.X.X
git push origin vX.X.X
```

6. Publish installer.

---

# Known Good Configuration

Validated release:

```text
Node Health Analyzer v1.0.2
Node Health Analyzer v1.0.3
```

Features verified:

* Battery Health
* Remaining Life Prediction
* Prediction Confidence
* Degradation Level
* Internal Temperature
* Node Comparison
* Plotly Visualization
* Excel Export
* PDF Export
* Multi-language Support
* Trial License System

```

---

Last updated: June 2026
```
