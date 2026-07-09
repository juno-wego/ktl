# KTL ROS2 Workspace Notes

이 저장소는 KTL ROS2 워크스페이스의 로봇 세팅/운용 문서를 관리합니다.

## Manuals

- [Unitree Go2 세팅 매뉴얼](docs/go2_setup_manual.md)
- [Unitree Go2 CycloneDDS 셋업 매뉴얼](docs/cyclonedds_go2_setup.md)

## Directory Structure

```text
ktl/
├── config/
│   ├── cyclonedds/   # CycloneDDS XML 설정
│   ├── go2/          # Go2 bringup/SDK 관련 설정
│   └── nav2/         # Nav2 파라미터 설정
├── docs/
│   ├── assets/       # 매뉴얼 이미지, 캡처, 다이어그램
│   └── checklists/   # 현장 점검표
├── launch/           # 통합 launch 파일
├── maps/             # SLAM으로 생성한 map yaml/pgm
├── rviz/             # RViz 설정 파일
├── scripts/          # 설치/실행 보조 스크립트
└── logs/             # 현장 테스트 로그 및 기록
```

# DDS? (Data Distribution Service)

- data 통신을 주관하는 middleware layer

middleware layer 설명
- 미들웨어란 
  - 소프트웨어와 소프트웨어 사이에서 통신을 중재하는 소프트웨어 계층
  - 서로 다른 시스템 간의 데이터 교환을 용이하게 함
  - 예: DDS, ROS2, MQTT, ZeroMQ 등

[DDS 종류]
- FastDDS (eProsima)
- CycloneDDS (Eclipse)
- RTI Connext DDS (RTI)
- Zenoh DDS (ADLINK)
등이 있으며, ROS2에서 기본으로 사용하는 DDS는 FastDDS와 CycloneDDS입니다.





```
[Go2 내부 제어 서비스 / 센서 상태]
              │
        DDS / RTPS over UDP
              │
        Cyclone DDS
        ┌─────┴─────────────┐
        │                   │
[Unitree SDK2 C++/Python] [ROS 2 노드]
                            │
                    rclcpp / rclpy
                            │
                 rmw_cyclonedds_cpp
```