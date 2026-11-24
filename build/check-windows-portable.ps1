param([Parameter(Mandatory)][string]$Package)

$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class WindowProbe {
    [StructLayout(LayoutKind.Sequential)]
    private struct IconIdentifier {
        public uint Size;
        public IntPtr Window;
        public uint Id;
        public Guid Guid;
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct Rect {
        public int Left, Top, Right, Bottom;
    }
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr FindWindow(string className, string title);
    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("shell32.dll")]
    private static extern int Shell_NotifyIconGetRect(ref IconIdentifier id, out Rect bounds);

    public static bool HasVisibleWindow(string title) {
        return IsWindowVisible(FindWindow(null, title));
    }
    public static bool HasTrayIcon(uint process) {
        IntPtr window = FindWindow("GuanHaiShiGuangTray", null);
        if (window == IntPtr.Zero)
            return false;
        uint owner;
        GetWindowThreadProcessId(window, out owner);
        return owner == process && TrayIconRegistered(window);
    }
    private static bool TrayIconRegistered(IntPtr window) {
        var id = new IconIdentifier { Size = (uint)Marshal.SizeOf<IconIdentifier>(), Window = window, Id = 1 };
        Rect bounds;
        return Shell_NotifyIconGetRect(ref id, out bounds) >= 0;
    }
}
'@

$destination = Join-Path $env:RUNNER_TEMP '免安装 便携包'
Expand-Archive -LiteralPath $Package -DestinationPath $destination
$entries = @(Get-ChildItem -Force -LiteralPath $destination)
$runtime = Join-Path $destination 'runtime'
if ($entries.Count -ne 2 -or !(Test-Path -LiteralPath $runtime -PathType Container)) {
    throw 'The archive must contain the executable and runtime directory only.'
}
$target = (Resolve-Path -LiteralPath (Join-Path $destination 'GuanHaiShiGuang.exe')).Path
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$link = Join-Path $desktop '观海·拾光.lnk'
$exe = Start-Process -FilePath $target -WorkingDirectory $env:RUNNER_TEMP -PassThru
try {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($exe.HasExited) { throw "Packaged application exited with code $($exe.ExitCode)" }
        if ([WindowProbe]::HasVisibleWindow('观海·拾光 v0.0.6') -and
            (Test-Path -LiteralPath $link -PathType Leaf) -and
            [WindowProbe]::HasTrayIcon($exe.Id)) {
            Stop-Process -Id $exe.Id
            $exe.WaitForExit()
            $exe = Start-Process -FilePath $link -PassThru
            for ($startup = 0; $startup -lt 20; $startup++) {
                if ($exe.HasExited) { throw 'The program exited after launching from the shortcut.' }
                if ([WindowProbe]::HasVisibleWindow('观海·拾光 v0.0.6') -and $exe.Path) {
                    python -c "import os, sys; sys.exit(not os.path.samefile(sys.argv[1], sys.argv[2]))" $exe.Path $target
                    if ($LASTEXITCODE -ne 0) { throw "Shortcut launched '$($exe.Path)', expected '$target'." }
                    Write-Host 'Main window, notification-area icon and relaunch from the desktop shortcut verified.'
                    return
                }
                Start-Sleep -Seconds 1
            }
            throw 'The desktop shortcut did not open the application.'
        }
        Start-Sleep -Seconds 1
    }
    Write-Host "Main window: $([WindowProbe]::HasVisibleWindow('观海·拾光 v0.0.6'))"
    Write-Host "Desktop shortcut: $(Test-Path -LiteralPath $link)"
    Write-Host "Notification-area icon: $([WindowProbe]::HasTrayIcon($exe.Id))"
    Get-ChildItem -Force -LiteralPath $desktop | Select-Object Name, Length
    throw 'Portable desktop integration did not become ready.'
} finally {
    if (!$exe.HasExited) { taskkill /PID $exe.Id /T /F | Out-Null }
}
