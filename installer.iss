#define MyAppName "Node Health Analyzer"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Control de Material"
#define MyAppExeName "NodeHealthAnalyzer.exe"

[Setup]
AppId={{9F6A9E7A-7C7C-4C1D-9E5E-100000000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Node Health Analyzer
DefaultGroupName=Node Health Analyzer
OutputDir=installer_output
OutputBaseFilename=NodeHealthAnalyzer_Setup_v1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Files]
Source: "dist\NodeHealthAnalyzer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Node Health Analyzer"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Node Health Analyzer"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar Node Health Analyzer"; Flags: nowait postinstall skipifsilent