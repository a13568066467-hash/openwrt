$ErrorActionPreference = "Continue"
netsh wlan show profile name="HOOK" key=clear | Out-File "d:\Users\Documents\project\openwrt\build\logs\hook-key.txt" -Encoding utf8
netsh wlan show profile name="NDS-WiFi" key=clear | Out-File "d:\Users\Documents\project\openwrt\build\logs\nds-key.txt" -Encoding utf8
"OK" | Out-File "d:\Users\Documents\project\openwrt\build\logs\hook-key-done.txt"
