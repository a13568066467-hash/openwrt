$ErrorActionPreference = "Continue"
foreach ($p in @("HOOK","GQ_5G","GQ","NDS-WiFi")) {
  "===== $p =====" | Out-File "d:\Users\Documents\project\openwrt\build\logs\wifi-keys-all.txt" -Append -Encoding utf8
  netsh wlan show profile name="$p" key=clear 2>&1 | Out-File "d:\Users\Documents\project\openwrt\build\logs\wifi-keys-all.txt" -Append -Encoding utf8
}
