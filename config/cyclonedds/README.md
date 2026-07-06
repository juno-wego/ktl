# config/cyclonedds

Unitree Go2와 ROS2 PC 사이의 CycloneDDS 통신 설정을 관리한다.

- `go2_eth.template.xml`: Go2 유선 연결용 CycloneDDS 템플릿
- `go2_local.xml`: 로봇 없이 local loopback으로 ROS2 통신을 확인할 때 쓰는 설정

실제 실행 시 `scripts/setup_go2_cyclonedds.bash`가 템플릿의 `@NETWORK_INTERFACE@`를 실제 NIC 이름으로 치환해 `.runtime/cyclonedds/` 아래 XML을 생성한다.

