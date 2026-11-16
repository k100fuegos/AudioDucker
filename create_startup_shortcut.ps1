$WScriptShell = New-Object -ComObject WScript.Shell
$StartupFolder = $WScriptShell.SpecialFolders.Item("Startup")
$ShortcutPath = Join-Path $StartupFolder "AudioDucker.lnk"
$WorkingDir = $PSScriptRoot
$TargetExe = Join-Path $WorkingDir "AudioDucker.exe"

if (-not (Test-Path $TargetExe)) {
    $DistExe = Join-Path $WorkingDir "dist\AudioDucker.exe"
    if (Test-Path $DistExe) {
        $TargetExe = $DistExe
    }
}

$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetExe
$Shortcut.WorkingDirectory = $WorkingDir
$Shortcut.Description = "AudioDucker - Control de volumen inteligente en segundo plano"
$Shortcut.Save()

Write-Host "[+] Acceso directo de inicio creado exitosamente en: $ShortcutPath -> $TargetExe"
