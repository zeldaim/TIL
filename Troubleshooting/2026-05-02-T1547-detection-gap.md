# T1547 Sysmon EventID 13 — Wazuh 룰 탐지 실패 기록

**날짜**: 2026-05-02  
**프로젝트**: home-soc-lab Week 6  
**상태**: ❌ 미해결 (FIM 방식으로 대체 탐지 중)

---

## 목표

Sysmon EventID 13 (Registry value set) → Wazuh rule 100010 → 알럿 생성

---

## 성공한 것

- Sysmon이 Run Key 추가를 EventID 13으로 로컬 탐지 ✅
- Wazuh archives.json에 EventID 13 로그 수신 ✅
- logtest Phase 2 디코딩 성공 ✅
- FIM(syscheck)으로 Run Key 변경 탐지 ✅

---

## 시도 1 — if_sid 61600

```xml
<rule id="100010" level="12">
  <if_sid>61600</if_sid>
  <field name="win.system.eventID">^13$</field>
  <field name="win.eventdata.targetObject">CurrentVersion\\Run</field>
</rule>
```

**결과**: ❌  
**원인**: 61600은 Sysmon 베이스 룰 (level 0). EventID 13 전용 룰은 61615

---

## 시도 2 — if_sid 61615 + targetObject 패턴

```xml
<rule id="100010" level="12">
  <if_sid>61615</if_sid>
  <field name="win.system.eventID">^13$</field>
  <field name="win.eventdata.targetObject">CurrentVersion\\Run</field>
</rule>
```

**결과**: ❌  
**원인**: 실제 경로가 `HKU\SID\SOFTWARE\...\Run` 형태라 패턴 불일치

---

## 시도 3 — targetObject 패턴 변경

```xml
<field name="win.eventdata.targetObject">CurrentVersion.Run</field>
```

**결과**: ❌  
**원인**: 정규식 오류

---

## 시도 4 — ruleName 필드로 변경

```xml
<rule id="100010" level="12">
  <if_sid>61615</if_sid>
  <field name="win.system.eventID">^13$</field>
  <field name="win.eventdata.ruleName">T1547_Run_Key_Create</field>
</rule>
```

**결과**: ❌  
**원인**: logtest Phase 3 미도달 — if_sid 체이닝 문제 추정

---

## logtest 분석

```
Phase 1: ✅ pre-decoding 완료
Phase 2: ✅ 디코딩 완료
Phase 3: ❌ 룰 매칭 없음
```

파싱된 필드 확인:
```
data.win.eventdata.ruleName: 'T1547_Run_Key_Create'
data.win.eventdata.targetObject: 'HKU\S-1-5-21-...\Run\TestPersistence'
data.win.system.eventID: '13'
```

---

## 현재 대안

ossec.conf에 HKCU Run key 추가:
```xml
<windows_registry arch="both">HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run</windows_registry>
```
→ FIM rule 750으로 탐지 중 (T1112 매핑)

---

## 다음 시도 예정

1. `if_sid` 없이 직접 매칭 방식
2. Wazuh 공식 문서 windows_eventchannel 룰 재확인
3. 커뮤니티에서 유사 사례 탐색
