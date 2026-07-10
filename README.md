# KTL ROS 2 패키지

이 패키지는 Go2 + Hesai 통합 Mapping, SLAM Toolbox, Nav2 launch와 설정을
제공한다.

설치 패키지, DDS/네트워크 구조, CUDA 빌드, 지도 저장 및 자율주행을 포함한 전체
운영 문서는 상위 워크스페이스의 [README](../README.md)에 통합돼 있다.

빠른 실행:

```bash
source /opt/ros/humble/setup.bash
source ~/ktl_ws/install/setup.bash

# SLAM Mapping
ros2 launch ktl go2_mapping.launch.py network_interface:=eno1

# 저장 지도 기반 Nav2
ros2 launch ktl go2_navigation.launch.py
```

패키지 구성:

```text
ktl/
├── config/   # CycloneDDS, Go2, SLAM, Nav2 파라미터
├── launch/   # Mapping 및 Navigation 통합 launch
├── maps/     # Occupancy Grid와 pose graph
├── rviz/     # Mapping/Navigation 화면 설정
└── scripts/  # 네트워크 및 데이터 보조 도구
```
