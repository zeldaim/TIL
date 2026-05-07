# Troubleshooting — Windows Defender 비활성화 (실습 환경)

> ⚠️ **실습 VM 전용**. 실제 운영 환경에서 절대 수행 금지.

---

## 증상별 원인 분류

| 증상 | 원인 |
|------|------|
| `payload.exe` 실행 직후 삭제됨 | 실시간 보호 (RealtimeMonitoring) |
| Meterpreter `session closed. Reason: Died` | 행동 모니터링 (BehaviorMonitoring) |
| `Set-MpPreference` 권한 오류 | Tamper Protection 또는 일반 권한 PowerShell |
| 레지스트리 써도 재부팅 시 False로 복귀 | 로컬 GPO가 설정 덮어쓰기 |

---

## Step 1 — 관리자 PowerShell 열기

```
시작 버튼 우클릭
→ Windows PowerShell(관리자)
→ UAC 팝업 → 예
```

프롬프트 확인:
```
PS C:\Windows\system32>   ← 관리자 (system32)
PS C:\Users\yhc>          ← 일반 권한 (불가)
```

---

## Step 2 — Tamper Protection 끄기 (필수 선행)

Tamper Protection이 켜져 있으면 관리자 권한, GPO, 레지스트리 모두 무시된다.

```
Windows 보안 앱 열기 (작업표시줄 방패 아이콘)
→ 바이러스 및 위협 방지
→ 설정 관리 클릭
→ 스크롤 내려서 "변조 보호" 항목
→ 토글 끄기 (꺼짐으로 변경)
```

---

## Step 3 — gpedit.msc로 GPO 비활성화

PowerShell 명령이 GPO에 의해 덮어씌워지는 경우 직접 GPO를 수정해야 한다.

```
시작 → gpedit.msc 실행
→ 컴퓨터 구성
  → 관리 템플릿
    → Windows 구성 요소
      → Microsoft Defender 바이러스 백신
        → 실시간 보호
```

| 항목 | 변경값 |
|------|--------|
| 실시간 보호 기능 끄기 | **사용** |
| Turn on behavior monitoring | **사용 안 함** |
| Scan all downloaded files and attachments | **사용 안 함** |

설정 후 즉시 적용:
```powershell
gpupdate /force
```

---

## Step 4 — 레지스트리 직접 설정

gpedit.msc 변경이 반영 안 될 때 레지스트리로 강제 설정.

```powershell
$path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection"

New-Item -Path $path -Force
New-ItemProperty -Path $path -Name "DisableRealtimeMonitoring"  -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $path -Name "DisableBehaviorMonitoring"  -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $path -Name "DisableIOAVProtection"      -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $path -Name "DisableScriptScanning"      -Value 1 -PropertyType DWORD -Force
```

적용 확인:
```powershell
Get-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection"
```

기대 결과:
```
DisableRealtimeMonitoring : 1
DisableBehaviorMonitoring : 1
DisableIOAVProtection     : 1
DisableScriptScanning     : 1
```

재부팅:
```powershell
Restart-Computer -Force
```

---

## Step 5 — 재부팅 후에도 False인 경우

레지스트리는 1인데 `Get-MpPreference`가 False를 반환하면 WinDefend 서비스가 레지스트리를 무시하는 것.  
이 경우 `Set-MpPreference`로 직접 적용:

```powershell
Set-MpPreference -DisableBehaviorMonitoring $true
Set-MpPreference -DisableIOAVProtection $true
```

그래도 안 되면 `권한이 부족하여` 오류 → Step 1로 돌아가서 관리자 PowerShell 확인.

---

## Step 6 — 최종 확인

```powershell
Get-MpPreference | Select DisableRealtimeMonitoring, DisableBehaviorMonitoring, DisableIOAVProtection
```

기대 결과:
```
DisableRealtimeMonitoring  DisableBehaviorMonitoring  DisableIOAVProtection
-------------------------  -------------------------  ---------------------
                     True                      True                   True
```

---

## 트러블슈팅 — Metasploit

### 문제 1: `session closed. Reason: Died`

**원인**: Defender BehaviorMonitoring이 메모리 내 Meterpreter를 탐지해 프로세스 강제 종료.  
**해결**: Step 3–4 수행 후 payload 재실행.

---

### 문제 2: `Handler failed to bind to 0.0.0.0:4444`

**원인**: 이전 리스너 프로세스가 포트를 점유 중.

```bash
sudo lsof -i :4444
sudo kill -9 <PID>
```

또는 포트 변경:
```
set LPORT 5555
```
payload도 새로 생성 필요 (LPORT 일치).

---

### 문제 3: `[-] Database not connected`

**원인**: PostgreSQL 미실행.

```bash
sudo service postgresql start
sudo msfdb init
```

---

### 문제 4: Wazuh 재시작 시 `Invalid root element "rule"`

**원인**: local_rules.xml에 `<group>` 태그 없음.

올바른 형식:
```xml
<group name="local,soc-lab">

  <rule id="100020" level="14">
    ...
  </rule>

</group>
```

---

### 문제 5: `migrate` 후 권한이 SYSTEM → 일반 사용자로 낮아짐

**원인**: 정상 동작. explorer.exe가 일반 사용자 권한으로 실행되기 때문.  
SYSTEM 권한 유지가 필요하면 `svchost.exe` (Session 0, SYSTEM 권한) 로 migrate:

```
meterpreter > ps | grep svchost
meterpreter > migrate <svchost PID>
```

---

## GPO 적용 현황 확인

어떤 정책이 적용되고 있는지 확인:

```powershell
gpresult /h C:\Temp\gpo_report.html /f
Start-Process "C:\Temp\gpo_report.html"
```

브라우저에서 열려 **로컬 그룹 정책[LocalGPO]** 항목 확인.
