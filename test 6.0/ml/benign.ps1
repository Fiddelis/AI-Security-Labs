# BenignLogSim.ps1
param(
  [int]$Iterations = 50,
  [int]$MinSleepSec = 5,
  [int]$MaxSleepSec = 20,
  [string]$Root = "$env:ProgramData\BenignSim",
  [switch]$VerboseLog
)

New-Item -ItemType Directory -Path $Root -ErrorAction SilentlyContinue | Out-Null
$TempDir = Join-Path $Root "work"
New-Item -ItemType Directory -Path $TempDir -ErrorAction SilentlyContinue | Out-Null

# Cria alguns arquivos dummy
1..10 | ForEach-Object {
  $f = Join-Path $TempDir ("doc_{0:00}.txt" -f $_)
  "Benign simulator line $_ - $(Get-Date -Format o)" | Out-File -FilePath $f -Encoding utf8
}

function Invoke-WithMeta {
  param([scriptblock]$Action, [string]$Name)
  $id = [guid]::NewGuid().ToString()
  try {
    & $Action.InvokeReturnAsIs($id)
  } catch {
    if ($VerboseLog) { Write-Warning "[$Name][$id] $_" }
  }
}

$Actions = @()

# 1) Abrir/fechar Notepad com arquivo
$Actions += {
  param($id)
  $file = Get-ChildItem $TempDir -File | Get-Random
  Start-Process -FilePath "notepad.exe" -ArgumentList "`"$($file.FullName)`" --SIM_BENIGN id=$id" -WindowStyle Minimized
  Start-Sleep -Seconds (Get-Random -Minimum 1 -Maximum 4)
  Get-Process notepad -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

# 2) Listar diretório com cmd
$Actions += {
  param($id)
  Start-Process -FilePath "cmd.exe" -ArgumentList "/c dir `"$TempDir`" & timeout /t 1 --SIM_BENIGN id=$id" -NoNewWindow
}

# 3) Hash de arquivo com certutil (somente leitura)
$Actions += {
  param($id)
  $file = Get-ChildItem $TempDir -File | Get-Random
  Start-Process -FilePath "certutil.exe" -ArgumentList "-hashfile `"$($file.FullName)`" SHA256 --SIM_BENIGN id=$id" -NoNewWindow
}

# 4) Copiar arquivos com robocopy
$Actions += {
  param($id)
  $dst = Join-Path $TempDir ("copy_" + (Get-Random))
  New-Item -ItemType Directory -Path $dst -ErrorAction SilentlyContinue | Out-Null
  Start-Process -FilePath "robocopy.exe" -ArgumentList "`"$TempDir`" `"$dst`" *.txt /XO /R:0 /W:0 --SIM_BENIGN id=$id" -NoNewWindow
}

# 5) Compactar com tar (Windows 10+)
$Actions += {
  param($id)
  $zip = Join-Path $TempDir ("arch_" + (Get-Random) + ".zip")
  Start-Process -FilePath "tar.exe" -ArgumentList "-a -c -f `"$zip`" -C `"$TempDir`" . --SIM_BENIGN id=$id" -NoNewWindow
}

# 6) Criar/rodar/apagar tarefa agendada (gera Task Scheduler)
$Actions += {
  param($id)
  $task = "BenignSim_$((Get-Random))"
  $ps = "powershell.exe -NoLogo -NoProfile -Command `"Get-Date > `"$TempDir\ts_$((Get-Random)).txt`"`" --SIM_BENIGN id=$id"
  schtasks /Create /SC ONCE /ST 23:59 /TN $task /TR $ps /RL LIMITED /F | Out-Null
  schtasks /Run /TN $task | Out-Null
  Start-Sleep -Seconds 1
  schtasks /Delete /TN $task /F | Out-Null
}

# 7) Gerar evento informativo no log de Aplicativo
$Actions += {
  param($id)
  eventcreate /T INFORMATION /ID 1000 /L APPLICATION /SO "BenignSim" /D "Benign simulation id=$id" | Out-Null
}

# 8) Abrir ajuda de msiexec (gera processo, não instala)
$Actions += {
  param($id)
  Start-Process -FilePath "msiexec.exe" -ArgumentList "/?" -WindowStyle Hidden
}

# 9) Consultas simples do sistema
$Actions += {
  param($id)
  Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -Command `"Get-ChildItem Env:\ | Out-Null`" --SIM_BENIGN id=$id" -WindowStyle Hidden
}

for ($i=1; $i -le $Iterations; $i++) {
  $action = Get-Random -InputObject $Actions
  Invoke-WithMeta -Action $action -Name "Action"
  Start-Sleep -Seconds (Get-Random -Minimum $MinSleepSec -Maximum $MaxSleepSec)
}
Write-Host "Concluído. Eventos benignos gerados."
