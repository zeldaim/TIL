# windows-security-cmd-cheatsheet

> CMD / PowerShell 기반 Windows 보안 상태 점검 명령어 모음  
> KISA 보안 교육 실습 · W-check 스크립트 작성 참고용

---

## Overview

Windows 시스템의 보안 상태를 CMD 또는 PowerShell로 확인하는 명령어 레퍼런스.  
보안기사 실기, CTF, 사고 대응(IR), W-check 자동화 스크립트 작성 시 참고.

```
환경: Windows 10/11, Windows Server 2016+
권한: 관리자 권한 실행 권장
표기: [CMD] / [PS] / [both]
```

---

## Table of Contents

- [Account](#account)
- [Password Policy](#password-policy)
- [Firewall](#firewall)
- [Network & Ports](#network--ports)
- [Process & Service](#process--service)
- [Windows Defender](#windows-defender)
- [Event Log](#event-log)
- [Quick Reference](#quick-reference)

---

## Account

### Current session

```cmd
whoami                   # [both] current user
whoami /priv             # [both] privilege list
whoami /groups           # [both] group membership + SID
```

### Local user list

```cmd
net user                           # [CMD] list all local users
net user <username>                # [CMD] user detail (expiry, last logon, groups)
wmic useraccount list full         # [CMD] full detail including SID, disabled status
```

```powershell
Get-LocalUser                                         # list + enabled status
Get-LocalUser | Select Name, Enabled, LastLogon       # key fields only
```

### Group membership

```cmd
net localgroup                            # [CMD] list all local groups
net localgroup administrators             # [CMD] Administrators members
net localgroup "Remote Desktop Users"     # [CMD] RDP-allowed accounts
```

```powershell
Get-LocalGroup                                    # list all local groups
Get-LocalGroupMember Administrators               # Administrators members
Get-LocalGroupMember "Remote Desktop Users"       # RDP-allowed accounts
```

> **Security check**
> - Standard user in `Administrators` group → **VULNERABLE**
> - Unnecessary accounts in `Remote Desktop Users` → Lateral Movement risk
> - `Guest` account enabled → **VULNERABLE**

---

## Password Policy

```cmd
net accounts    # [CMD] password length, expiry, lockout policy at a glance
```

```cmd
# [CMD] export full security policy to file (used in W-check script parsing)
secedit /export /cfg C:\security_policy.txt
```

Key fields to parse from exported file:

| Field | Key | KISA Recommended |
|---|---|---|
| Minimum password length | `MinimumPasswordLength` | ≥ 8 |
| Password complexity | `PasswordComplexity` | `1` (enabled) |
| Lockout threshold | `LockoutBadCount` | ≤ 5 |
| Lockout duration | `LockoutDuration` | ≥ 30 min |
| Max password age | `MaximumPasswordAge` | ≤ 90 days |

> **W-02 usage**: Parse `secedit /export` output in PowerShell to auto-judge pass/fail per field.

---

## Firewall

### Profile status

```cmd
netsh advfirewall show allprofiles      # [CMD] Domain / Private / Public — all at once
netsh advfirewall show currentprofile   # [CMD] active profile only
```

```powershell
Get-NetFirewallProfile                              # all 3 profiles
Get-NetFirewallProfile | Select Name, Enabled       # enabled status only
```

### Rules

```cmd
netsh advfirewall firewall show rule name=all           # [CMD] all rules
netsh advfirewall firewall show rule name=all dir=in    # [CMD] inbound only
```

```powershell
Get-NetFirewallRule | Where-Object Enabled -eq True
Get-NetFirewallRule | Where-Object {
    $_.Direction -eq "Inbound" -and $_.Enabled -eq "True"
}
```

> **Security check**
> - All 3 profiles must be `ON` → pass
> - Unnecessary inbound allow rules → attack surface
> - Whitelist approach recommended (deny all, allow minimum)

---

## Network & Ports

```cmd
ipconfig              # [both] IP address
ipconfig /all         # [both] IP, MAC, DNS, DHCP full detail

netstat -ano                          # [both] ports + state + PID
netstat -ano | findstr LISTENING      # [CMD] listening ports only
netstat -ano | findstr ESTABLISHED    # [CMD] active connections (check external IPs)
netstat -ano | findstr <port>         # [CMD] specific port status
```

> **Forensics tip**: `netstat -ano` → get PID of suspicious external connection → match with `tasklist` to identify process → judge C2 communication

---

## Process & Service

### Process

```cmd
tasklist                             # [CMD] running process list
tasklist /v                          # [CMD] process + running account
tasklist /svc                        # [CMD] process + associated service name
tasklist /fi "pid eq <PID>"          # [CMD] specific PID lookup
```

```powershell
Get-Process | Select Name, Id, Path
Get-Process | Where-Object { $_.Path -like "*temp*" }     # suspicious path filter
Get-Process | Where-Object { $_.Path -like "*AppData*" }
```

### Service

```cmd
sc query type= all          # [CMD] all services + status
sc query <servicename>      # [CMD] specific service
```

```powershell
Get-Service
Get-Service | Where-Object Status -eq Running
Get-WmiObject Win32_Service | Select Name, StartName, PathName   # service account + path
```

> **Security check**
> - Duplicate process name running twice → suspicious
> - Execution path outside `System32` / `Program Files` (e.g. `Temp`, `AppData`, `Downloads`) → **high suspicion**
> - Service running as `SYSTEM` unnecessarily → violates least privilege

---

## Windows Defender

```powershell
# full status
Get-MpComputerStatus

# key fields
Get-MpComputerStatus | Select `
    RealTimeProtectionEnabled, `
    AntivirusEnabled, `
    AntivirusSignatureLastUpdated, `
    QuickScanAge

# exclusion paths — attackers may place malware here
Get-MpPreference | Select ExclusionPath, ExclusionExtension

# recent threat detection history
Get-MpThreatDetection
```

| Field | Key | Pass Condition |
|---|---|---|
| Real-time protection | `RealTimeProtectionEnabled` | `True` |
| Antivirus enabled | `AntivirusEnabled` | `True` |
| Signature up to date | `AntivirusSignatureLastUpdated` | Recent date |
| Exclusion paths | `ExclusionPath` | Empty or business-justified only |

---

## Event Log

```cmd
eventvwr    # [both] open Event Viewer GUI
```

```powershell
# security log — recent 50
Get-EventLog -LogName Security -Newest 50

# login failure — brute force detection
Get-EventLog -LogName Security -InstanceId 4625 -Newest 20

# login success — unauthorized access check
Get-EventLog -LogName Security -InstanceId 4624 -Newest 20

# account creation
Get-EventLog -LogName Security -InstanceId 4720 -Newest 10

# time range filter
Get-EventLog -LogName Security -After "2025-05-01" -Before "2025-05-31"
```

### Key Event IDs

| Event ID | Description | Detection Point |
|---|---|---|
| `4624` | Logon success | Off-hours access, unknown account |
| `4625` | Logon failure | Repeated failures → brute force |
| `4720` | Account created | Unauthorized account creation |
| `4732` | Member added to group | Account added to Administrators |
| `4648` | Explicit credential logon | Pass-the-Hash / credential theft |
| `7045` | New service installed | Malicious service installation |
| `4698` | Scheduled task created | Persistence mechanism |

---

## Quick Reference

| Scenario | Command |
|---|---|
| Who am I? | `whoami /priv` |
| Who's in Administrators? | `net localgroup administrators` |
| Password policy? | `net accounts` |
| Firewall on? | `netsh advfirewall show allprofiles` |
| Any external connections? | `netstat -ano \| findstr ESTABLISHED` |
| Suspicious process paths? | `Get-Process \| Select Name,Id,Path` |
| Defender real-time on? | `Get-MpComputerStatus \| Select RealTimeProtectionEnabled` |
| Any exclusion paths set? | `Get-MpPreference \| Select ExclusionPath` |
| Recent login failures? | `Get-EventLog -LogName Security -InstanceId 4625 -Newest 20` |

---

## Related Projects

- [home-soc-lab](https://github.com/zeldaim/home-soc-lab) — Proxmox 기반 홈 SOC 환경 구축
- [wazuh-slack-alertbot](https://github.com/zeldaim/wazuh-slack-alertbot) — SSH 브루트포스 엔트로피 탐지
- [lab-attack-runner](https://github.com/zeldaim/lab-attack-runner) — 공격 자동화 + Flask SOC 대시보드

---

## References

- [KISA 주요정보통신기반시설 기술적 취약점 분석·평가 가이드](https://www.kisa.or.kr)
- [MITRE ATT&CK](https://attack.mitre.org)
- [LOLBAS Project](https://lolbas-project.github.io)
