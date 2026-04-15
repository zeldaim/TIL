# Troubleshooting — 디스크 100% 풀 & Docker 초기화

## 증상

```
/dev/mapper/rl-root   48G   48G   136K  100%  /
```

- `dnf install` 불가 (Errno 28: 장치에 남은 공간이 없음)
- Docker 컨테이너 시작 불가 (failed to mount)
- `docker system prune` 0B 반환

---

## 원인 분석

```
/var/lib/docker      29G  ← Wazuh queue 누적
/var/lib/containerd  12G  ← 컨테이너 레이어
/var/lib/mysql      124M
```

**근본 원인:** Wazuh가 처리 못한 이벤트를 queue 볼륨에 누적 저장.  
Kali에서 지속적인 Nmap 스캔 → iptables 로그 폭증 → Wazuh queue 30GB 누적

---

## 왜 일반 rm으로 안 지워졌나?

Docker가 **containerd + overlay 파일시스템** 방식을 사용하기 때문.

```
예전 Docker (단순)
/var/lib/docker/volumes/wazuh-queue/_data/ → 파일 직접 존재

현재 Docker + containerd (복잡)
Docker 메타데이터 → /var/lib/docker/
실제 데이터      → /var/lib/containerd/io.containerd.snapshotter.v1.overlayfs/snapshots/
                   (수백 개 레이어에 분산 저장)
```

`docker volume ls`에는 보이지만 `ls /var/lib/docker/volumes/wazuh-queue/_data/`가 없는 이유:  
볼륨 포인터만 있고 실제 데이터는 containerd 스냅샷 레이어 안에 분산되어 있기 때문.

---

## 시도한 방법들 (실패)

| 시도 | 결과 | 실패 원인 |
|---|---|---|
| `docker system prune -f` | 0B | 모든 이미지가 실행 중 컨테이너에 연결 |
| `docker volume rm` | 실패 | 컨테이너가 볼륨 사용 중 |
| alpine 컨테이너로 큐 직접 삭제 | 실패 | 디스크 꽉 차서 이미지 pull 불가 |
| `docker exec`로 내부 접근 | 실패 | 컨테이너가 디스크 부족으로 중지됨 |
| `rm /var/lib/docker/volumes/*` | 0B 확보 | 포인터만 삭제, 실제 데이터는 containerd에 |
| Docker root를 /home으로 이동 | 실패 | cp 자체가 디스크 부족으로 불가 |

---

## 해결 방법 — Docker + containerd 완전 초기화

```bash
# 1. 서비스 완전 중지
sudo systemctl stop docker docker.socket containerd

# 2. 데이터 완전 삭제
sudo rm -rf /var/lib/docker
sudo rm -rf /var/lib/containerd

# 3. 디렉토리 재생성
sudo mkdir /var/lib/docker
sudo mkdir /var/lib/containerd

# 4. 서비스 재시작
sudo systemctl start containerd
sudo systemctl start docker

# 5. 용량 확인
df -h /
```

**결과:**
```
/dev/mapper/rl-root   48G   7.6G   41G   16%   /
```

---

## Wazuh 재설치 후 복구 순서

```bash
# 1. 인증서 생성
cd ~/wazuh-docker/single-node
docker compose -f generate-indexer-certs.yml run --rm generator

# 2. Wazuh 시작
docker compose up -d

# 3. local_rules.xml 재적용
cat > /tmp/local_rules.xml << 'EOF'
<group name="nmap,recon,">
  <rule id="100004" level="10">
    <if_sid>4100</if_sid>
    <match>PORTSCAN</match>
    <description>Nmap port scan detected via iptables</description>
    <mitre>
      <id>T1046</id>
    </mitre>
  </rule>
</group>
EOF
docker cp /tmp/local_rules.xml single-node-wazuh.manager-1:/var/ossec/etc/rules/local_rules.xml
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-control restart

# 4. iptables PORTSCAN 룰 재적용
sudo iptables -I INPUT -p tcp --tcp-flags SYN,ACK,FIN,RST RST \
  -m limit --limit 1/s \
  -j LOG --log-prefix "PORTSCAN: "

# 5. iptables 영구 적용
sudo dnf install iptables-services -y
sudo iptables-save | sudo tee /etc/sysconfig/iptables
sudo systemctl enable --now iptables
```

---

## 재발 방지

Kali에서 자동 스캔이 돌지 않도록 주의. iptables rate limit(`--limit 1/s`)이 설정되어 있지만 장시간 스캔 시 queue가 누적될 수 있음.

Wazuh queue 모니터링:
```bash
docker exec single-node-wazuh.manager-1 du -sh /var/ossec/queue/
```
