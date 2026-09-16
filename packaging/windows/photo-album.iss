#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Photo Album"
#define AppPublisher "Photo Album Contributors"
#define AppExeName "photo-album.exe"

[Setup]
AppId={{D90F136D-7B99-49F5-91BB-5A72CC01CC93}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Photo Album
DefaultGroupName=Photo Album
DisableProgramGroupPage=yes
OutputDir=..\..\dist-installer
OutputBaseFilename=PhotoAlbum-{#AppVersion}-Windows-x64-Setup
SetupIconFile=..\pyinstaller\photoalbum.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
Source: "..\pyinstaller\dist\photo-album\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Photo Album"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Photo Album"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,Photo Album}"; Flags: nowait postinstall skipifsilent
