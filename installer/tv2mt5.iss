; installer/tv2mt5.iss — per-user installer for TV2MT5 Desktop.
; Build via build.ps1, or: ISCC.exe /DAppVersion=2.0.0-beta.1 installer\tv2mt5.iss
#define AppName "TV2MT5 Desktop"
#define AppExe "TV2MT5.exe"
#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{A7E9C4F2-3B61-4D8E-9F2A-6C1B2D5E7F90}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Abhi D
AppPublisherURL=https://github.com/abhidp/tradingview-to-metatrader5
DefaultDirName={localappdata}\Programs\TV2MT5
DefaultGroupName=TV2MT5
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=TV2MT5-Setup-{#AppVersion}
SetupIconFile=..\app\ui\img\tv2mt5.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\TV2MT5\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\TV2MT5"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\TV2MT5"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; \
  Check: WV2Needed; Flags: waituntilterminated; StatusMsg: "Installing WebView2 Runtime..."
Filename: "{app}\{#AppExe}"; Description: "Launch TV2MT5"; Flags: nowait postinstall skipifsilent

[Code]
const
  WV2_CLIENT = '{F3017226-FA46-457B-9129-E1B887D33167}';

var
  DownloadPage: TDownloadWizardPage;
  gWV2Needed: Boolean;

function WV2RegHas(RootKey: Integer; SubKey: String): Boolean;
var
  pv: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', pv) and (pv <> '') and (pv <> '0.0.0.0');
end;

function WebView2Installed(): Boolean;
begin
  Result :=
    WV2RegHas(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WV2_CLIENT) or
    WV2RegHas(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2_CLIENT) or
    WV2RegHas(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2_CLIENT);
end;

function WV2Needed(): Boolean;
begin
  Result := gWV2Needed;
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard();
begin
  gWV2Needed := not WebView2Installed();
  DownloadPage := CreateDownloadPage(
    'Downloading WebView2 Runtime',
    'TV2MT5 needs the Microsoft WebView2 runtime. Downloading the installer...',
    @OnDownloadProgress);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and gWV2Needed then
  begin
    DownloadPage.Clear;
    DownloadPage.Add(
      'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
      'MicrosoftEdgeWebview2Setup.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
      except
        SuppressibleMsgBox(
          'Could not download the WebView2 runtime. The app may not display ' +
          'correctly until it is installed.' + #13#10 + GetExceptionMessage,
          mbError, MB_OK, IDOK);
        gWV2Needed := False;
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;
