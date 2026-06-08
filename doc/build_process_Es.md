# Node Health Analyzer - Proceso de Compilación

## Objetivo

Este documento describe el proceso de compilación validado para Node Health Analyzer.

Los comandos aquí documentados fueron probados y confirmados como funcionales con:

* PySide6
* Plotly
* SQLAlchemy
* Sistema multilenguaje
* Exportación a Excel
* Exportación a PDF
* Visualización de gráficas
* Instalador Inno Setup

---

# 1. Limpiar compilaciones anteriores

Antes de generar una nueva versión eliminar siempre las carpetas de compilación previas.

```powershell
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
```

---

# 2. Generar el ejecutable

Utilizar siempre el comando validado.

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

---

# 3. Importante

NO utilizar:

```powershell
pyinstaller --onefile
```

Durante las pruebas presentó inconvenientes con:

* Plotly
* PySide6 WebEngine
* Tiempo de arranque
* Estabilidad general

La configuración validada utiliza:

```text
onedir
```

---

# 4. Validar el ejecutable

Ejecutar:

```powershell
.\dist\NodeHealthAnalyzer\NodeHealthAnalyzer.exe
```

Verificar:

* Apertura correcta del programa
* Apertura de detalles del nodo
* Comparación de nodos
* Visualización de gráficas
* Exportación a Excel
* Exportación a PDF
* Cambio de idioma
* Sistema Trial

---

# 5. Generar instalador

Compilar utilizando Inno Setup.

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Resultado esperado:

```text
installer_output\
NodeHealthAnalyzer_Setup_vX.X.X.exe
```

---

# 6. Validar instalador

Probar preferentemente en otra computadora.

Verificar:

* Instalación correcta
* Apertura del programa
* Creación automática de base de datos
* Sistema Trial
* Exportaciones
* Gráficas
* Idiomas

---

# 7. Flujo de Git

Trabajar siempre sobre:

```powershell
git checkout develop
```

Guardar cambios:

```powershell
git add .
git commit -m "Descripción de cambios"
```

Enviar cambios:

```powershell
git push origin develop
```

---

# 8. Flujo de liberación (Release)

1. Desarrollar en:

```text
develop
```

2. Validar funcionalidad.

3. Generar instalador.

4. Realizar merge hacia:

```text
main
```

5. Crear etiqueta (tag):

```powershell
git tag vX.X.X
git push origin vX.X.X
```

6. Publicar instalador.

---

# 9. Estructura de ramas

```text
main
│
├── Versiones estables publicadas

develop
│
├── Desarrollo activo

maintenance-v1.0
│
├── Respaldo histórico de la serie 1.0
```

---

# 10. Configuración validada

Versiones probadas:

```text
Node Health Analyzer v1.0.2
Node Health Analyzer v1.0.3
```

Funciones verificadas:

* Health Score
* Battery Health
* Vida Restante
* Confianza de Predicción
* Nivel de Degradación
* Temperatura Interna
* Comparación de Nodos
* Visualización Plotly
* Exportación Excel
* Exportación PDF
* Traducción Español / Inglés / Chino
* Sistema Trial
* Instalador Inno Setup

---

# Lecciones aprendidas

1. Si una compilación funciona correctamente, no cambiar el método de compilación sin necesidad.

2. Siempre probar el ejecutable antes de generar el instalador.

3. Mantener las versiones estables en `main`.

4. Realizar nuevas funciones en `develop`.

5. Crear tags para cada versión liberada.

6. Mantener documentación actualizada para evitar pérdida de conocimiento del proyecto.

---

Última actualización:

Junio 2026
Node Health Analyzer v1.0.3
