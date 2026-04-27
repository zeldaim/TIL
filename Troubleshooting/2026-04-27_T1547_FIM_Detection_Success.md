# T1547.001 FIM 탐지 구현 완료

> \*\*날짜\*\*: 2026-04-27
> \*\*결과\*\*: ✅ 성공
> \*\*방식\*\*: Wazuh FIM (File Integrity Monitoring) — 레지스트리 모니터링

\---

## 핵심 발견

Wazuh 공식 T1547 탐지 방식은 **Sysmon EventID 13이 아닌 FIM**임.

공식 블로그: https://wazuh.com/blog/detecting-windows-persistence-techniques-with-wazuh/

FIM이 `HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run` 키를 모니터링하고
변경 시 자동으로 alert 발생.

\---

## 발동된 Alert

```json
{
  "rule": {
    "id": "752",
    "level": 5,
    "description": "Registry Value Entry Added to the System",
    "mitre": { "id": \["T1112"] }
  },
  "syscheck": {
    "path": "HKEY\_LOCAL\_MACHINE\\\\Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run",
    "value\_name": "FIMTest2",
    "event": "added"
  },
  "agent": { "name": "DESKTOP-5408CBA" }
}
```

관련 rule ID:

* `750` — Registry Value Integrity Checksum Changed (수정)
* `751` — Registry Value Entry Deleted (삭제)
* `752` — Registry Value Entry Added (추가) ← T1547 탐지

\---

## 설정 확인

### Windows agent ossec.conf (기본 설정, 수정 불필요)

```xml
<syscheck>
  <frequency>300</frequency>  <!-- 테스트용, 운영 시 43200 -->
  <windows\_registry arch="both">HKEY\_LOCAL\_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\Run</windows\_registry>
  <windows\_registry arch="both">HKEY\_LOCAL\_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce</windows\_registry>
</syscheck>
```

**주의**: `windows\_registry`는 realtime 미지원. frequency 주기로 스캔.  
운영 환경에서는 `<frequency>43200</frequency>` (12시간) 권장.

\---

## 공격 시뮬레이션

```powershell
# Run 키 추가 (T1547.001 시뮬레이션)
New-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run" `
  -Name "MalwareTest" -Value "calc.exe" -PropertyType String -Force

# 정리
Remove-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run" `
  -Name "MalwareTest" -Force
```

frequency 주기 후 alert 자동 발생.

\---

## FIM vs Sysmon EventID 13 비교

|항목|FIM|Sysmon EventID 13|
|-|-|-|
|탐지 방식|주기적 스캔|실시간 이벤트|
|설정 난이도|낮음 (기본 설정)|높음|
|실시간성|❌ (주기적)|✅|
|공식 지원|✅ Wazuh 기본|⚠️ rule 설정 필요|
|현재 상태|✅ 완료|❌ 미해결 (GitHub 문의 중)|

\---

## 미해결

Sysmon EventID 13 rule 미발동 문제는 GitHub에 문의 중.

* Issue URL: https://github.com/wazuh/wazuh/issues/35707
* 해결되면 FIM + Sysmon 이중 탐지로 고도화 예정

