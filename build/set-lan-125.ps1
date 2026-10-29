$ErrorActionPreference = "Stop"
$adapter = Get-NetAdapter | Where-Object { $_.ifIndex -eq 25 }
Write-Host "Using $($adapter.Name)"
Get-NetIPAddress -InterfaceIndex 25 -AddressFamily IPv4 -ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
Get-NetRoute -InterfaceIndex 25 -ErrorAction SilentlyContinue | Where-Object { $_.DestinationPrefix -ne '255.255.255.255/32' } | Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
Set-NetIPInterface -InterfaceIndex 25 -AddressFamily IPv4 -Dhcp Disabled
New-NetIPAddress -InterfaceIndex 25 -IPAddress 192.168.1.125 -PrefixLength 24 -DefaultGateway 192.168.1.1 | Out-Null
Set-DnsClientServerAddress -InterfaceIndex 25 -ServerAddresses 192.168.1.1
if (-not (Get-NetFirewallRule -DisplayName 'NDS-8080' -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName 'NDS-8080' -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow | Out-Null
}
Get-NetIPAddress -InterfaceIndex 25 -AddressFamily IPv4 | Format-Table IPAddress, PrefixLength
"DONE"
