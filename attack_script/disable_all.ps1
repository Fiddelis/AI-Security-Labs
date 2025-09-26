<# 
    AVISO: USE APENAS EM VM DE LAB.
    Este script desativa várias proteções de segurança.
    Rode o PowerShell **como Administrador**.
#>

#--- 0) Checagem de Admin
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "Abra o PowerShell como Administrador e rode novamente."
    exit 1
}

# Facilita saída de erros
$ErrorActionPreference = "Stop"

function Set-RegistryValue {
    param(
        [string]$Path, [string]$Name, [string]$Type, [Object]$Value
    )
    New-Item -Path $Path -Force | Out-Null
    New-ItemProperty -Path $Path -Name $Name -PropertyType $Type -Value $Value -Force | Out-Null
}

Write-Host "`n=== Desativando Windows Firewall (Domain, Private, Public) ==="
Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled False

Write-Host "`n=== Desativando Microsoft Defender (tempo real e correlatos) ==="
try {
    Set-MpPreference -DisableRealtimeMonitoring $true
    Set-MpPreference -MAPSReporting 0
    Set-MpPreference -SubmitSamplesConsent 2           # Never send
    Set-MpPreference -DisableIOAVProtection $true      # Desabilita verificação de downloads
    Set-MpPreference -DisableScriptScanning $true
    # (Opcional) Desativa proteção de rede e nuvem
    Set-MpPreference -SpynetReporting 0 -CloudBlockLevel 0 -EnableNetworkProtection Disabled
} catch {
    Write-Warning "Falha ao configurar o Defender (pode haver política forçando). Erro: $($_.Exception.Message)"
}

Write-Host "`n=== Desativando proteção do LSASS (RunAsPPL) ==="
Set-RegistryValue -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "RunAsPPL" -Type DWord -Value 0
Set-RegistryValue -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "RunAsPPLBoot" -Type DWord -Value 0

Write-Host "`n=== Desativando UAC (User Account Control) ==="
Set-RegistryValue -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "EnableLUA" -Type DWord -Value 0
Set-RegistryValue -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "ConsentPromptBehaviorAdmin" -Type DWord -Value 0

Write-Host "`nTudo configurado. É necessário reiniciar para aplicar 100% das mudanças."
Start-Sleep -Seconds 2
Restart-Computer -Force
