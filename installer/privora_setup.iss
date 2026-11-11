; Privora — Private Document Intelligence
; Inno Setup Installer Script
; Target: Windows 10 / Windows 11 (64-bit)

#define MyAppName "Privora"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Privora Intelligence"
#define MyAppURL "https://github.com/privora/privora"
#define MyAppExeName "Privora.exe"
#define MyAppEngineDir "privora-engine"

[Setup]
; Basic Application Info
AppId={{9F7B2F6E-2E4E-4E65-9B21-B4FE8A155160}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Privora
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=
OutputDir=..\dist-installer
OutputBaseFilename=Privora-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Custom UI and Branding
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} Document Intelligence
SetupIconFile=..\public\favicon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Privora Launcher Executable
Source: "..\dist\Privora.exe"; DestDir: "{app}"; Flags: ignoreversion
; Privora Backend Engine and Static Next.js distribution
Source: "..\dist\privora-engine\*"; DestDir: "{app}\privora-engine"; Flags: ignoreversion recursesubdirs createallsubdirs
; Optional documentation
Source: "..\README_DESKTOP.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon; Comment: "Launch Privora — Private Document Intelligence"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "Privora Private Document Intelligence"

[Run]
; Option to launch Privora upon completion
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up temp files, but NEVER delete or purge user databases/documents in %LOCALAPPDATA%\Privora\data
Type: files; Name: "{app}\*.log"

[Code]
// Inno Setup Pascal Script for safety checks and user guidance

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Explicitly notify user that their local documents and SQLite database are preserved
    MsgBox('Privora was successfully uninstalled.' + #13#10 + #13#10 +
           'Your documents and database in %LOCALAPPDATA%\Privora\data have been preserved for your privacy and data retention.',
           mbInformation, MB_OK);
  end;
end;
