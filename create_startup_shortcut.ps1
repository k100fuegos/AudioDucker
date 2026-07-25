$WScriptShell = New-Object -ComObject WScript.Shell
$StartupFolder = $WScriptShell.SpecialFolders.Item("Startup")
$ShortcutPath = Join-Path $StartupFolder "AudioDucker.lnk"
$TargetExe = "C:\Users\kelvi\Downloads\AudioDucker\AudioDucker.exe"
$WorkingDir = "C:\Users\kelvi\Downloads\AudioDucker"

$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetExe
$Shortcut.WorkingDirectory = $WorkingDir
$Shortcut.Description = "AudioDucker - Control de volumen de Spotify en segundo plano"
$Shortcut.Save()

Write-Host "[+] Acceso directo de inicio creado exitosamente en: $ShortcutPath"
