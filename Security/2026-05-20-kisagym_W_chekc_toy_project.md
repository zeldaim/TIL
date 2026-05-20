# kisagym 실습 환경 기반 보안 점검 프로젝트

**날짜**: 2026-05-20  
**환경**: kisagym.net (Win10 + WinSrv2016)  
**목표**: PowerShell 기반 Windows 보안 점검 자동화

---

## 1. W-Check HTML 리포트 생성기

### 목표
W-번호 점검 스크립트를 작성하고 HTML 리포트를 자동 생성하는 PowerShell 스크립트 완성

### 구현 내용

**Check-Item 함수 구조**
```powershell
function Check-Item {
    param (
        [string]$Code,
        [string]$Name,
        [bool]$IsGood,
        [string]$Detail
    )
    return [PSCustomObject]@{
        Code   = $Code
        Name   = $Name
        Result = if ($IsGood) { "양호" } else { "취약" }
        Detail = $Detail
        Color  = if ($IsGood) { "#2ecc71" } else { "#e74c3c" }
    }
}
```

**점검 항목 구현 완료**
| 항목 | 명령어 | 양호 기준 |
|------|--------|-----------|
| W-02 패스워드 복잡성 | `secedit /export` | 최소길이 8 이상, 복잡성 활성화 |
| W-20 Guest 계정 | `Get-LocalUser` | Enabled = False |
| W-23 원격 레지스트리 | `Get-Service RemoteRegistry` | StartType = Disabled |
| W-39 RDP NLA | `Get-ItemProperty HKLM:\...RDP-Tcp` | UserAuthenticationRequired = 1 |
| W-45 Defender | `Get-MpComputerStatus` | RealTimeProtectionEnabled = True |
| W-64 감사 로그 | `auditpol /get` | Success and Failure |

### 트러블슈팅

**문제 1: Here-String `@"..."@` 내부 CSS 중괄호 충돌**
- 증상: `Missing closing '}'` 에러
- 원인: PowerShell이 `{}` 를 스크립트 블록으로 인식
- 해결: CSS를 문자열 연결 방식으로 분리
```powershell
$css  = "body { background:#1a1a2e; }"
$css += " h1 { color:#00d4ff; }"
```

**문제 2: `<$good / $total>` HTML 태그에서 `<` 연산자 충돌**
- 증상: `The '<' operator is reserved for future use`
- 원인: Here-String 안에서 `<$변수` 패턴을 연산자로 인식
- 해결: `<span>` 태그 제거, 괄호로 대체

**문제 3: `$PSScriptRoot` null**
- 증상: `Test-Path : Cannot bind argument to parameter 'Path' because it is null`
- 원인: PowerShell 콘솔에서 직접 실행 시 `$PSScriptRoot` 가 null
- 해결: 고정 경로로 대체
```powershell
$resultDir = "C:\Lab\result"
```

**문제 4: HTML 출력은 되지만 내용 없음**
- 원인: `ForEach-Object` 내부 `{}` 중괄호 충돌로 `$rows` 가 비어있음
- 해결: `foreach` 루프로 교체
```powershell
$rows = ""
foreach ($item in $results) {
    $rows += "<tr><td>" + $item.Code + "</td>..."
}
```

### 현재 상태
- HTML 파일 생성 및 브라우저 오픈 성공
- 내용 표시는 미완성 (인코딩/파싱 이슈 추가 디버깅 필요)

---

## 2. 브루트포스 탐지 (4625 이벤트 파싱)

### 목표
WinSrv2016 보안 이벤트 로그에서 로그인 실패(4625)를 파싱해 IP별 집계

### 성공한 명령어

```powershell
# IP별 로그인 실패 횟수 집계
Get-EventLog -LogName Security -InstanceId 4625 -Newest 100 |
ForEach-Object {
    $rs = $_.ReplacementStrings
    [PSCustomObject]@{ IP=$rs[19]; Account=$rs[5] }
} | Group-Object IP | Sort-Object Count -Descending | Select-Object Count, Name
```

**결과 예시**
```
Count  Name
-----  ----
10     192.168.2.20
```

### 핵심 발견: ReplacementStrings 인덱스

4625 이벤트의 `ReplacementStrings` 배열 구조:
| 인덱스 | 값 |
|--------|-----|
| [5] | Account Name (로그인 시도 계정) |
| [19] | Source Network Address (공격자 IP) |

### 트러블슈팅

**문제 1: 정규식으로 Message 파싱 실패**
- 원인: 이벤트 로그 메시지가 CRLF(`\r\n`)로 줄바꿈되어 `-split "\n"` 매칭 안됨
- 시도한 방법: `-match "Source Network Address:\s+(\S+)"` → unknown
- 해결: `Message` 파싱 대신 `ReplacementStrings` 배열 직접 접근

**문제 2: Logon Type 5 로그는 IP가 없음**
- 증상: Source Network Address가 `-` (대시)
- 원인: Logon Type 5는 서비스 로그온 (로컬 발생)
- 해결: Win10에서 WinSrv2016으로 RDP 틀린 비밀번호 시도로 Logon Type 3 생성

**문제 3: CredSSP 에러로 RDP 접속 불가**
- 증상: `An authentication error has occurred. The function is not supported`
- 원인: NLA(W-39) 활성화 + CredSSP 버전 불일치
- 해결:
  1. WinSrv2016에서 NLA 비활성화
  ```powershell
  Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" -Name "UserAuthenticationRequired" -Value 0
  ```
  2. Win10에서 CredSSP 레지스트리 수정
  ```powershell
  Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\CredSSP\Parameters" -Name "AllowEncryptionOracle" -Value 2
  ```

**문제 4: 로그가 계속 사라짐**
- 원인: kisagym 공용 환경에서 다른 수강생 사용 시 로그 덮어씌워짐
- 해결: RDP 시도 직후 바로 원라이너로 실행

---

## 3. 계정 보안 점검

### 계정 목록 조회
```powershell
Get-LocalUser | Select-Object Name, Enabled, PasswordLastSet, PasswordNeverExpires
```

**WinSrv2016 계정 현황**
| 계정 | 활성화 | 마지막 비밀번호 변경 |
|------|--------|---------------------|
| DefaultAccount | False | - |
| Emily | True | 2026-02-15 |
| Guest | False | 2026-02-15 |
| John | True | 2026-02-15 |
| test | True | 2026-02-15 |
| testadmin | True | 2026-02-11 |

**보안 이슈**
- `test`, `testadmin` 계정 활성화 상태 → 불필요한 계정 존재
- Guest 계정 비활성화 → 양호

---

## 배운 것

1. **PowerShell Here-String** (`@"..."@`) 안에서 `{}`, `<$변수>` 등 특수문자는 충돌 발생
2. **이벤트 로그 파싱**은 `Message` 문자열보다 `ReplacementStrings` 배열이 안정적
3. **Logon Type** 구분 중요: Type 2(로컬), Type 3(네트워크), Type 5(서비스)
4. **kisagym 공용 환경** 특성상 로그가 빠르게 초기화됨

---

## 다음 단계

- [ ] W-Check HTML 리포트 인코딩 문제 최종 해결
- [ ] bruteforce_check.ps1 스크립트 파일로 저장
- [ ] 패스워드 정책 위반 계정 탐지 완성
- [ ] 비활성 계정 자동 탐지 추가
