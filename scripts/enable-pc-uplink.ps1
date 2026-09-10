# Enable Windows PC uplink for the Newifi/OpenWrt lab.
# Run this from an elevated PowerShell window.
$ErrorActionPreference = "Stop"

$InternalPrefix = if ($env:NDS_PC_NAT_PREFIX) { $env:NDS_PC_NAT_PREFIX } else { "192.168.1.0/24" }
$NatName = if ($env:NDS_PC_NAT_NAME) { $env:NDS_PC_NAT_NAME } else { "OpenWrtLab" }

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
  throw "Run this script in an elevated PowerShell window."
}

Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" -Name "IPEnableRouter" -Value 1 -Type DWord

Get-NetIPInterface -AddressFamily IPv4 | ForEach-Object {
  Set-NetIPInterface -InterfaceIndex $_.InterfaceIndex -Forwarding Enabled -ErrorAction SilentlyContinue
}

Get-NetNat -Name $NatName -ErrorAction SilentlyContinue | Remove-NetNat -Confirm:$false -ErrorAction SilentlyContinue
New-NetNat -Name $NatName -InternalIPInterfaceAddressPrefix $InternalPrefix | Out-Null

foreach ($rule in @("NDS-Lab-Forward-In", "NDS-Lab-Forward-Out")) {
  $direction = if ($rule -like "*Out") { "Outbound" } else { "Inbound" }
  if (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue) {
    Set-NetFirewallRule -DisplayName $rule -Enabled True -Action Allow | Out-Null
  } else {
    New-NetFirewallRule -DisplayName $rule -Direction $direction -Action Allow -Protocol Any -Profile Any | Out-Null
  }
}

Write-Host "PC uplink enabled."
Write-Host "NAT name: $NatName"
Write-Host "Internal prefix: $InternalPrefix"
Get-NetNat -Name $NatName | Format-List Name,InternalIPInterfaceAddressPrefix,Active
Get-NetIPInterface -AddressFamily IPv4 | Sort-Object InterfaceIndex | Format-Table InterfaceIndex,InterfaceAlias,Forwarding,ConnectionState -AutoSize
