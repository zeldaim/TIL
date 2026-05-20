# Windows Security Hardening — KISA W-Check Reference

> Windows Server 2016 기준 | KISA 보안 점검 항목 자동화 실습

---

## Overview

KISA 윈도우 서버 보안 점검 항목을 PowerShell로 자동화한 실습 환경입니다.  
취약 환경 조성 → 자동 점검 → 수동 하드닝 → 재점검의 흐름으로 구성됩니다.

## Environment

- OS: Windows Server 2016
- Tool: PowerShell 5.1
- Structure:

```
C:\Lab\
├── W_settings.ps1       # 취약 환경 조성
├── run_all.ps1          # 전체 점검 실행
├── W01_check.ps1
├── W02_check.ps1
│   ...
├── W64_check.ps1
└── result\
    ├── Wxx_Good.txt
    ├── Wxx_Bad.txt
    └── Wxx_Review.txt
```

---

## Check Items

### Account

| ID | Name | Criteria | Method |
|---|---|---|---|
| W-01 | Administrator Account Rename | Name ≠ "Administrator" | SID S-1-5-21-*-500 |
| W-02 | Guest Account Disabled | Enabled = False | `Get-LocalUser` |
| W-03 | Unnecessary Account Removal | Manual review | List all accounts |
| W-04 | Account Lockout Threshold | 1 ≤ value ≤ 5 | `secedit` → LockoutBadCount |
| W-05 | Store Password Reversible Encryption | ClearTextPassword = 0 | `secedit` |
| W-06 | Administrators Group Members | Only built-in Administrator | Filter non SID-500 |

### Services / Network

| ID | Name | Criteria | Method |
|---|---|---|---|
| W-18 | Unnecessary Services (Simple TCP/IP) | Not installed or Stopped | `Get-Service simptcp` |
| W-64 | Windows Firewall Settings | All profiles enabled | `Get-NetFirewallProfile` |

### Antivirus

| ID | Name | Criteria | Method |
|---|---|---|---|
| W-39 | Antivirus Signature Update | Updated within 7 days | `Get-MpComputerStatus` |
| W-45 | Antivirus Installation | Windows Defender installed | `Get-MpComputerStatus` |

### Audit / Logging

| ID | Name | Criteria | Method |
|---|---|---|---|
| W-40 | Audit Policy Settings | 6 subcategories match KISA | `auditpol /get /category:* /r` |
| W-41 | NTP Time Synchronization | time.windows.com or internal NTP | Registry W32Time |
| W-42 | Security Event Log Settings | Size ≥ 10240KB + AutoBackup | `Get-WinEvent -ListLog Security` |
| W-43 | Event Log File Access Control | No Everyone permission | `Get-Acl` on winevt\Logs |
| W-50 | Crash On Audit Full | CrashOnAuditFail = 0 (Disabled) | Registry HKLM\...\Lsa |

---

## W-40 Audit Policy Details (KISA Standard)

```powershell
$policies = @(
    @{ Subcategory = "User Account Management";  Expected = "Failure"           },
    @{ Subcategory = "Credential Validation";    Expected = "Success and Failure"},
    @{ Subcategory = "Sensitive Privilege Use";  Expected = "Success and Failure"},
    @{ Subcategory = "Directory Service Access"; Expected = "Failure"           },
    @{ Subcategory = "Logon";                    Expected = "Success and Failure"},
    @{ Subcategory = "Audit Policy Change";      Expected = "Success and Failure"}
)
```

---

## Key PowerShell Commands for Manual Hardening

```powershell
# W-01: Administrator 계정명 변경
Rename-LocalUser -Name "Administrator" -NewName "NewAdminName"

# W-02: Guest 계정 비활성화
Disable-LocalUser -Name "Guest"

# W-04: 계정 잠금 임계값 설정
net accounts /lockoutthreshold:5

# W-05: 평문 암호 저장 비활성화
secedit /export /cfg $env:TEMP\sec.cfg /quiet
# secpol.msc > 계정 정책 > 암호 정책 > 해독 가능한 암호화 사용 = 사용 안 함

# W-06: Administrators 그룹에서 불필요한 계정 제거
Remove-LocalGroupMember -Group "Administrators" -Member "Jack"

# W-40: 감사 정책 설정
auditpol /set /subcategory:"Logon" /success:enable /failure:enable
auditpol /set /subcategory:"Account Management" /success:enable /failure:enable

# W-42: 보안 로그 크기 및 모드 설정
# eventvwr.msc > Windows 로그 > 보안 > 속성
# 최대 로그 크기: 10240KB 이상, 보관 방법: 필요할 때 보관

# W-50: CrashOnAuditFail 비활성화
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "CrashOnAuditFail" -Value 0
```

---

## GUI Paths Quick Reference

| 항목 | 도구 | 경로 |
|---|---|---|
| 계정 관리 (W-01,02,03,06) | `lusrmgr.msc` | 사용자 / 그룹 |
| 암호/잠금 정책 (W-04,05) | `secpol.msc` | 계정 정책 > 암호 정책 / 계정 잠금 정책 |
| 감사 정책 (W-40) | `secpol.msc` | 로컬 정책 > 감사 정책 |
| 이벤트 로그 설정 (W-42) | `eventvwr.msc` | Windows 로그 > 보안 > 속성 |
| 방화벽 (W-64) | `wf.msc` | 각 프로필 속성 |
| 레지스트리 (W-50) | `regedit` | HKLM\SYSTEM\CurrentControlSet\Control\Lsa |

---

## Result File Format

각 점검 스크립트는 `result/` 디렉토리에 결과 파일을 생성합니다:

```
ITEM_NAME : W-01 (Administrator Account Rename)
ACCOUNT   : Administrator
RESULT    : Bad
```

- `Wxx_Good.txt` → 양호
- `Wxx_Bad.txt` → 취약 (하드닝 필요)
- `Wxx_Review.txt` → 수동 검토 필요 (W-03, W-41 등)

---

## Notes

- `run_all.ps1`은 `*_check.ps1` 패턴으로 자동 탐색 실행 — 새 항목 추가 시 파일만 추가하면 됨
- `W_settings.ps1`은 실습용 취약 환경 조성 스크립트 — 운영 환경에서 절대 실행 금지
- Review 항목(W-03, W-41)은 자동 판정 불가, 반드시 수동 확인 필요
- W-39/W-45는 백신의 **존재(설치)**와 **상태(업데이트)**를 분리해서 점검
