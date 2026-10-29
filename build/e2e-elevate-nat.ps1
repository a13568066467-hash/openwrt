$ErrorActionPreference = "Continue"
netsh wlan show profile name="HOOK" key=clear | Out-File -FilePath "d:\Users\Documents\project\openwrt\build\logs\hook-profile.txt" -Encoding utf8
# Enable forwarding
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" -Name "IPEnableRouter" -Value 1 -Type DWord
Get-NetIPInterface -AddressFamily IPv4 | ForEach-Object { Set-NetIPInterface -InterfaceIndex $_.InterfaceIndex -Forwarding Enabled -ErrorAction SilentlyContinue }
# Try NetNat
try {
  if (Get-Command New-NetNat -ErrorAction SilentlyContinue) {
    Get-NetNat -Name OpenWrtLab -ErrorAction SilentlyContinue | Remove-NetNat -Confirm:$false -ErrorAction SilentlyContinue
    New-NetNat -Name OpenWrtLab -InternalIPInterfaceAddressPrefix 192.168.1.0/24
    "NAT_OK" | Out-File "d:\Users\Documents\project\openwrt\build\logs\pc-uplink.log" -Append
  } else { "NO_NETNAT" | Out-File "d:\Users\Documents\project\openwrt\build\logs\pc-uplink.log" }
} catch {
  $_ | Out-File "d:\Users\Documents\project\openwrt\build\logs\pc-uplink.log"
}
Get-NetNat | Out-File "d:\Users\Documents\project\openwrt\build\logs\pc-uplink.log" -Append
"FORWARD" | Out-File "d:\Users\Documents\project\openwrt\build\logs\pc-uplink.log" -Append
Get-NetIPInterface -AddressFamily IPv4 | Where-Object Forwarding -eq Enabled | Format-Table InterfaceAlias,IfIndex,Forwarding | Out-File "d:\Users\Documents\project\openwrt\build\logs\pc-uplink.log" -Append
