#define AppVersion "0.1.0"
#ifndef PayloadDir
#define PayloadDir "..\..\dist\windows\voxd"
#endif
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
OutputBaseFilename=voxd-setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\voxd.exe
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "compact"; Description: "Use compact speech recognition (~640 MB); spelling needs no LLM"; Flags: unchecked
Name: "englishdict"; Description: "Use English spelling dictionary (default: German)"; Flags: unchecked
Name: "autostart"; Description: "Start voxd at login and keep recognition ready"; Flags: unchecked
Name: "desktopicon"; Description: "Create desktop shortcut"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\voxd"; Filename: "{app}\voxd.exe"
Name: "{group}\voxd Settings"; Filename: "{app}\voxd.exe"; Parameters: "--setup"
Name: "{group}\Uninstall voxd"; Filename: "{uninstallexe}"
Name: "{autodesktop}\voxd"; Filename: "{app}\voxd.exe"; Tasks: desktopicon
Name: "{userstartup}\voxd"; Filename: "{app}\voxd.exe"; Tasks: autostart

[Run]
Filename: "{app}\voxd.exe"; Description: "Start voxd"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\voxd.exe"; Parameters: "--ctl quit"; Flags: runhidden waituntilterminated; RunOnceId: "StopDaemon"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  Args: String;
  ResultCode: Integer;
  Retry: Integer;
begin
  if CurStep = ssPostInstall then begin
    Args := '--install-models --apply';
    if WizardIsTaskSelected('compact') then Args := Args + ' --profile compact'
    else Args := Args + ' --profile auto';
    if WizardIsTaskSelected('englishdict') then Args := Args + ' --language en';
    WizardForm.StatusLabel.Caption := 'Detecting hardware and downloading speech recognition weights...';
    repeat
      if Exec(ExpandConstant('{app}\voxd.exe'), Args, '', SW_HIDE,
              ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then Break;
      if WizardSilent then RaiseException('Model installation failed. Run voxd --install-models --apply to retry.');
      Retry := MsgBox('Model installation failed. Check network and disk space. Retry now? ' +
                      'No keeps the application installed; first launch will reopen setup.', mbError, MB_YESNO);
    until Retry <> IDYES;
  end;
end;
