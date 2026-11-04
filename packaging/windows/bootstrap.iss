; Small, cross-buildable bootstrap installer: Python is installed per-user by
; winget if absent, dependencies by pip, and speech weights by voxd.bootstrap.
#define AppVersion "0.1.0"
[Setup]
AppId={{6588D24A-CE0C-4C48-9A22-4464C966714B}
AppName=voxd
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\voxd
DefaultGroupName=voxd
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist\windows
OutputBaseFilename=voxd-bootstrap-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=voxd
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "compact"; Description: "Compact speech weights (~640 MB); spelling needs no LLM"; Flags: unchecked
Name: "englishdict"; Description: "English spelling dictionary (default: German)"; Flags: unchecked
Name: "autostart"; Description: "Start at login and keep recognition ready"; Flags: unchecked

[Files]
Source: "..\..\dist\voxd-0.1.0-py3-none-any.whl"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "..\..\install.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "..\..\uninstall.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\uninstall.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: "RemovePythonApplication"

[UninstallDelete]
Type: files; Name: "{app}\voxd-install.marker"
Type: files; Name: "{app}\uninstall.ps1"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  Args: String;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then begin
    Args := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\installer\install.ps1') + '" -InstallDir "' + ExpandConstant('{app}') + '"';
    if WizardIsTaskSelected('compact') then Args := Args + ' -Compact';
    if WizardIsTaskSelected('englishdict') then Args := Args + ' -English';
    if WizardIsTaskSelected('autostart') then Args := Args + ' -Autostart';
    WizardForm.StatusLabel.Caption := 'Installing Python dependencies and speech recognition weights. This can take several minutes.';
    if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Args,
                '', SW_SHOW, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
      RaiseException('Dependency/model setup failed. Run the installer again to resume. See PowerShell output for the failure.');
  end;
end;
