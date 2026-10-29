# Requires elevation. Share WLAN internet to Ethernet (OpenWrt LAN).
$ErrorActionPreference = "Stop"
Write-Host "Enabling IP forwarding + NAT for 192.168.1.0/24 via WLAN..."

# IP forwarding
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" -Name "IPEnableRouter" -Value 1 -Type DWord
Get-NetIPInterface | Where-Object { $_.AddressFamily -eq "IPv4" } | ForEach-Object {
  try { Set-NetIPInterface -InterfaceIndex $_.InterfaceIndex -Forwarding Enabled -ErrorAction SilentlyContinue } catch {}
}

# Firewall allow forwarding-ish inbound from OpenWrt LAN
$rules = @(
  @{ Name = "NDS-Lab-Forward-In"; Dir = "Inbound" },
  @{ Name = "NDS-Lab-Forward-Out"; Dir = "Outbound" }
)
foreach ($r in $rules) {
  if (-not (Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $r.Name -Direction $r.Dir -Action Allow -Protocol Any -Profile Any | Out-Null
  } else {
    Set-NetFirewallRule -DisplayName $r.Name -Enabled True -Action Allow | Out-Null
  }
}
if (-not (Get-NetFirewallRule -DisplayName "NDS-8080" -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName "NDS-8080" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow | Out-Null
}

# Prefer Hyper-V NetNat if available
try {
  Get-NetNat -Name "OpenWrtLab" -ErrorAction SilentlyContinue | Remove-NetNat -Confirm:$false -ErrorAction SilentlyContinue
  New-NetNat -Name "OpenWrtLab" -InternalIPInterfaceAddressPrefix "192.168.1.0/24" -ErrorAction Stop | Out-Null
  Write-Host "NetNat OpenWrtLab created"
} catch {
  Write-Host "NetNat failed: $($_.Exception.Message)"
  Write-Host "Trying ICS COM fallback..."
  # ICS: share WLAN to Ethernet 2
  $wlan = Get-NetAdapter | Where-Object { $_.Name -eq "WLAN" -and $_.Status -eq "Up" } | Select-Object -First 1
  $eth = Get-NetAdapter | Where-Object { $_.Status -eq "Up" -and $_.Name -like "*太*" } | Select-Object -First 1
  if (-not $wlan -or -not $eth) { throw "need WLAN + Ethernet" }
  $public = $wlan.InterfaceDescription
  $private = $eth.InterfaceDescription
  Write-Host "ICS public=$public private=$private"
  $m = New-Object -ComObject HNetCfg.HNetShare
  $pubConn = $null
  $priConn = $null
  foreach ($c in $m.EnumEveryConnection()) {
    $props = $m.NetConnectionProps($c)
    if ($props.Name -eq $wlan.Name -or $props.DeviceName -eq $public) { $pubConn = $c }
    if ($props.Name -eq $eth.Name -or $props.DeviceName -eq $private) { $priConn = $c }
  }
  if (-not $pubConn -or -not $priConn) { throw "ICS connections not found" }
  $cfg = $m.INetSharingConfigurationForINetConnection($pubConn)
  if ($cfg.SharingEnabled) { $cfg.DisableSharing() }
  $cfg.EnableSharing(0) # 0=public
  $cfg2 = $m.INetSharingConfigurationForINetConnection($priConn)
  if ($cfg2.SharingEnabled) { $cfg2.DisableSharing() }
  $cfg2.EnableSharing(1) # 1=private
  Write-Host "ICS enabled"
}

# Quick self-check
ipconfig | Out-String | Select-String -Pattern "192.168.1.|WLAN|以太网" | ForEach-Object { $_.Line }
Write-Host "DONE_PC_UPLINK"
