$ErrorActionPreference = 'Stop'

$taskName = 'HermesCodexBridge-Desktop'
$python = Get-Command python.exe -CommandType Application | Select-Object -First 1 -ExpandProperty Source
$pythonWindowless = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonWindowless -PathType Leaf)) {
    throw "Could not find pythonw.exe beside $python"
}

$entry = Join-Path $PSScriptRoot 'bridge.py'
$arguments = '-X utf8 -B "{0}" worker --desktop-task' -f $entry
$existing = Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue
if ($existing -and ($existing.Actions.Count -ne 1 -or $existing.Actions[0].Arguments -ne $arguments)) {
    throw "The desktop launcher name is already registered for another entry: $taskName"
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$action = New-ScheduledTaskAction -Execute $pythonWindowless -Argument $arguments -WorkingDirectory $PSScriptRoot
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)

$task = @{
    TaskName = $taskName
    TaskPath = '\'
    Action = $action
    Principal = $principal
    Settings = $settings
    Description = 'Starts the file bridge on demand in the signed-in Windows desktop session.'
}
Register-ScheduledTask @task -Force | Out-Null
Write-Output "Registered $taskName for $identity (on demand)."
