$ErrorActionPreference = "Continue"
# Allow forwarded traffic from OpenWrt LAN
New-NetFirewallRule -DisplayName "NDS-Lab-From-LAN" -Direction Inbound -RemoteAddress 192.168.1.0/24 -Action Allow -Enabled True -ErrorAction SilentlyContinue
Set-NetFirewallRule -DisplayName "NDS-Lab-From-LAN" -Action Allow -Enabled True -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "NDS-Lab-To-Any" -Direction Outbound -Action Allow -Enabled True -ErrorAction SilentlyContinue

# Ensure ICS/NAT path: disable RFC1918 blocking if any
# Test receive ping from router by enabling ICMPv4
New-NetFirewallRule -DisplayName "NDS-Lab-ICMPv4" -Direction Inbound -Protocol ICMPv4 -Action Allow -ErrorAction SilentlyContinue
Set-NetFirewallRule -DisplayName "NDS-Lab-ICMPv4" -Enabled True -Action Allow -ErrorAction SilentlyContinue

# Explicit route: replies already fine
Get-NetNat | Format-List | Out-File "d:\Users\Documents\project\openwrt\build\logs\pc-uplink2.log"
"---" | Out-File "d:\Users\Documents\project\openwrt\build\logs\pc-uplink2.log" -Append
# Try enabling Windows Routing Service if present
try { Set-Service RemoteAccess -StartupType Manual -ErrorAction SilentlyContinue; Start-Service RemoteAccess -ErrorAction SilentlyContinue } catch {}

# Packet test: listen - use Test-NetConnection from nowhere
# Add route metric: prefer WLAN for default
$wlan = Get-NetIPInterface -InterfaceAlias WLAN -AddressFamily IPv4
Set-NetIPInterface -InterfaceAlias WLAN -AddressFamily IPv4 -InterfaceMetric 10 -ErrorAction SilentlyContinue
Set-NetIPInterface -InterfaceAlias "以太网 2" -AddressFamily IPv4 -InterfaceMetric 50 -ErrorAction SilentlyContinue

# Alternative NAT via netsh portproxy won't work for general IP
# Use wintun-less: install simple nft via WSL?
# Try rrastart

"DONE_FW" | Out-File "d:\Users\Documents\project\openwrt\build\logs\pc-uplink2.log" -Append
Get-NetFirewallRule -DisplayName "NDS-Lab*" | Format-Table DisplayName, Enabled, Direction, Action | Out-File "d:\Users\Documents\project\openwrt\build\logs\pc-uplink2.log" -Append
