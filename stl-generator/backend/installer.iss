; Inno Setup Script for STL Creator
; Compile with Inno Setup 6.x

#define AppName "STL Creator"
#define AppVersion "1.0.0"
#define AppPublisher "3D Printer Converter"
#define AppExeName "Start-STL-Creator.bat"

[Setup]
AppId={{3D-STL-CREATOR-APP}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=installer-output
OutputBaseFilename=STL-Creator-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=app\static\icon.ico
UninstallDisplayIcon={app}\Start-STL-Creator.bat

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main application files
Source: "dist\STL-Creator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Stop {#AppName}"; Filename: "{app}\Stop-STL-Creator.bat"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent shellexec

[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nThis application converts photos into 3D-printable STL files using photogrammetry.%n%nRequirements:%n- NVIDIA GPU (for fast processing)%n- 8GB RAM minimum%n- 2GB disk space

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Could add GPU check here
end;
