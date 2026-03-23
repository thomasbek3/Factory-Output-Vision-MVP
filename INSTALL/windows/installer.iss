#ifndef SourcePath
  #define SourcePath "."
#endif

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
AppId={{8D8E68D5-1557-4C15-9E85-654E0ED0E8C3}
AppName=Factory Counter
AppVersion={#AppVersion}
AppPublisher=Factory Counter
DefaultDirName={localappdata}\FactoryCounter
DefaultGroupName=Factory Counter
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=FactoryCounterSetup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=no
UninstallDisplayIcon={app}\INSTALL\windows\start-app.bat

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "launchapp"; Description: "Start Factory Counter after setup"; Flags: unchecked

[Files]
Source: "{#SourcePath}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Factory Counter\Start Factory Counter"; Filename: "{app}\INSTALL\windows\start-app.bat"; WorkingDir: "{app}"
Name: "{autoprograms}\Factory Counter\Stop Factory Counter"; Filename: "{app}\INSTALL\windows\stop-app.bat"; WorkingDir: "{app}"
Name: "{autoprograms}\Factory Counter\Windows Install Readme"; Filename: "{app}\INSTALL\windows\README.md"; WorkingDir: "{app}"
Name: "{autodesktop}\Factory Counter"; Filename: "{app}\INSTALL\windows\start-app.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\INSTALL\windows\start-app.bat"; Description: "Start Factory Counter now"; Flags: postinstall skipifsilent unchecked; Tasks: launchapp

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\INSTALL\windows\stop-app.ps1"""; Flags: runhidden skipifdoesntexist; RunOnceId: "StopFactoryCounter"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  BootstrapCommand: String;
begin
  if CurStep = ssPostInstall then
  begin
    BootstrapCommand := '/C "' + ExpandConstant('{app}\INSTALL\windows\bootstrap-install.bat') + '"';
    if not Exec(ExpandConstant('{cmd}'), BootstrapCommand, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      SuppressibleMsgBox(
        'Failed to start the Factory Counter bootstrap script. Check data\logs\installer-bootstrap.log in the install folder.',
        mbCriticalError,
        MB_OK,
        IDOK
      );
      Abort;
    end;

    if ResultCode <> 0 then
    begin
      SuppressibleMsgBox(
        'Factory Counter dependency installation failed. Check data\logs\installer-bootstrap.log in the install folder.',
        mbCriticalError,
        MB_OK,
        IDOK
      );
      Abort;
    end;
  end;
end;
