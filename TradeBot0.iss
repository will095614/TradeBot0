; TradeBot0 installer (Inno Setup 6)
; Installs the standalone TradeBot0_Arena.exe to {autopf}\TradeBot0.
;
; Node.js / OmniRoute are deliberately NOT bundled: the global omniroute
; install is ~2.6 GB / 164,349 files and no standalone OmniRoute binary
; exists (npm or Docker only), so bundling it is infeasible. On first run
; the app offers a one-click install of Node.js + OmniRoute into its own
; per-user runtime folder (%LOCALAPPDATA%\TradeBot0\runtime), and until
; then it runs in Pure Math mode. The installer shows a note when Node.js
; is missing (see [Code] below).
;
; Version: the single source of truth is src/version.py (APP_VERSION);
; keep MyAppVersion in sync with it at release time. Bump both per release.
#define MyAppName "TradeBot0"
#define MyAppVersion "V2.5.2"
#define MyAppPublisher "TradeBot0"
#define MyAppExeName "TradeBot0_Arena.exe"

[Setup]
AppId={{A21CE6E9-710C-4C80-B1A0-B1A4DF694A6E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
; Numeric form of MyAppVersion (no V prefix) for the version resource.
VersionInfoVersion=2.5.2
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
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

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
    OldDataPage.Add('Delete old TradeBot0 settings and trading history (keeps OmniRoute runtime and ~/.omniroute)');
    OldDataPage.Values[0] := False;
  end;
end;

function NodeJsMissing(): Boolean;
var
  Path, Dir, LocalNode: String;
  I: Integer;
begin
  Result := True;
  LocalNode := ExpandConstant('{localappdata}\TradeBot0\runtime\node\node.exe');
  if FileExists(LocalNode) then
  begin
    Result := False;
    Exit;
  end;
  Path := GetEnv('PATH');
  while Path <> '' do
  begin
    I := Pos(';', Path);
    if I = 0 then
    begin
      Dir := Path;
      Path := '';
    end
    else
    begin
      Dir := Copy(Path, 1, I - 1);
      Path := Copy(Path, I + 1, Length(Path));
    end;
    Dir := Trim(Dir);
    if (Length(Dir) >= 2) and (Dir[1] = '"') and (Dir[Length(Dir)] = '"') then
      Dir := Copy(Dir, 2, Length(Dir) - 2);
    Dir := RemoveBackslashUnlessRoot(Dir);
    if (Dir <> '') and FileExists(AddBackslash(Dir) + 'node.exe') then
    begin
      Result := False;
      Exit;
    end;
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
  if CurStep = ssPostInstall then
  begin
    if NodeJsMissing() then
      SuppressibleMsgBox('Node.js was not found on this computer.' + #13#10 +
        'TradeBot0 works without it (Pure Math mode), but the AI gateway needs Node.js 22 or later.' + #13#10 +
        'On first launch, use "Install Node.js & OmniRoute" in the setup wizard, or install Node.js from https://nodejs.org/ and run: npm install -g omniroute',
        mbInformation, MB_OK, IDOK);
  end;
end;
