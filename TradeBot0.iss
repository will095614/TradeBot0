; TradeBot0 installer (Inno Setup 6)
; Installs the standalone TradeBot0_Arena.exe to {autopf}\TradeBot0.
;
; Direct Google Gemini API integration via Python/aiohttp (no Node.js or
; local AI gateway runtime required). Users enter a single Gemini
; API key in the in-app Setup Wizard.
;
; Version: the single source of truth is src/version.py (APP_VERSION);
; keep MyAppVersion in sync with it at release time. Bump both per release.
#define MyAppName "TradeBot0"
#define MyAppVersion "V3.2.0"
#define MyAppPublisher "TradeBot0"
#define MyAppExeName "TradeBot0_Arena.exe"

[Setup]
AppId={{A21CE6E9-710C-4C80-B1A0-B1A4DF694A6E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
; Numeric form of MyAppVersion (no V prefix) for the version resource.
VersionInfoVersion=3.2.0
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=installer-output
OutputBaseFilename=TradeBot0Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=src\gui\assets\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; AppUserModelID: "TradeBot0.QuantArena"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; AppUserModelID: "TradeBot0.QuantArena"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  OldDataPage: TInputOptionWizardPage;
  OldDataFound: Boolean;

function OldDataExists(): Boolean;
begin
  Result := DirExists(ExpandConstant('{userappdata}\TradeBot0'));
end;

procedure InitializeWizard();
begin
  OldDataFound := OldDataExists();
  if OldDataFound then
  begin
    OldDataPage := CreateInputOptionPage(wpSelectTasks,
      'Old data found',
      'TradeBot0 data from a previous install was found on this computer.',
      'Your old data is kept by default. Check the box only if you want to remove it and start fresh.',
      False, False);
    OldDataPage.Add('Delete old TradeBot0 settings and trading history (from LocalAppData)');
    OldDataPage.Values[0] := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    if OldDataFound and (OldDataPage <> nil) and OldDataPage.Values[0] then
    begin
      if not DelTree(ExpandConstant('{userappdata}\TradeBot0'), True, True, True) then
      begin
        SuppressibleMsgBox(
          'Some old TradeBot0 files in %APPDATA%\TradeBot0 could not be deleted (they may be locked by a running process). ' +
          'Close TradeBot0 and remove the folder manually if you want a completely fresh start.',
          mbError, MB_OK, IDOK);
      end;
    end;
  end;
end;
