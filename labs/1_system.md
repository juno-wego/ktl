# 1. 시스템 개요와 통신 구조

이 문서는 Go2, Hesai XT16, Jetson Orin으로 구성된 ROS 2 시스템의 구조와 기본 점검 방법을 설명한다. 실습 전에는 [명령어 모음](cmd_manuals.md)의 네트워크 확인부터 수행한다.

## 시스템 구성

```text
Go2 모션 컨트롤러 ── Unitree DDS ─┐
Go2 확장 컴퓨터                   ├─ eno1 유선망 ─ Jetson Orin (ROS 2)
Hesai XT16 ─────────── UDP ───────┘                    │
                                                       ├─ SLAM Toolbox
                                                       ├─ Nav2
                                                       └─ RViz 2
```

| 구성요소 | 역할 |
|---|---|
| Go2 | 보행 제어와 로봇 상태 제공 |
| Jetson Orin | ROS 2 노드, 센서 처리, SLAM, Navigation 실행 |
| Hesai XT16 | 3D 포인트클라우드 전송 |
| RViz 2 | TF, 센서, 지도, 경로 시각화 |

## 네트워크

모든 장치는 Jetson의 `eno1` 유선 인터페이스를 사용한다.

| 장치 | IP | 용도 |
|---|---|---|
| Jetson ROS 호스트 | `192.168.123.222/24` | ROS 2와 LiDAR 수신 |
| Go2 모션 컨트롤러 | `192.168.123.161` | Unitree 보행 제어 |
| Go2 확장 컴퓨터 | `192.168.123.18` | Go2 보조 컴퓨터 |
| Hesai XT16 | `192.168.123.20` | LiDAR |

Hesai는 UDP `2368`으로 포인트를 보내고 PTC는 `9347` 포트를 사용한다. 로봇이나 LiDAR가 꺼져 있으면 ROS 2 에러를 먼저 해석하지 말고 전원, 케이블, IP를 확인한다.

```bash
ip link show eno1
ping -c 3 192.168.123.20   # Hesai
ping -c 3 192.168.123.161 # Go2
```

## ROS 2, DDS, CycloneDDS

ROS 2 노드는 토픽·서비스·액션으로 데이터를 주고받는다. 실제 발견과 전송은 DDS가 담당하며, 이 시스템은 `rmw_cyclonedds_cpp`를 사용한다.

| 계층 | 역할 |
|---|---|
| ROS 2 | 노드, 토픽, 서비스, 액션 인터페이스 |
| RMW | ROS 2와 DDS 구현을 연결 |
| CycloneDDS | 노드 발견과 실제 네트워크 전송 |

Bringup의 `network_interface:=eno1`은 CycloneDDS가 유선망만 사용하도록 제한한다. Wi-Fi·VPN·Docker 인터페이스를 잘못 선택하는 문제를 예방한다.

```bash
ros2 launch go2_base go2_bringup.launch.py \
  network_interface:=eno1 rviz:=false
```

## Unitree와 ROS 2의 연결

`go2_state_bridge`는 Unitree DDS 상태를 표준 ROS 2 메시지로 변환한다. `go2_cmd_vel_bridge`는 ROS 2 속도 명령을 Unitree 제어 요청으로 변환한다.

```text
Unitree DDS 상태                         ROS 2 상태
/lf/sportmodestate, /lowstate ──→ go2_state_bridge ──→ /go2/odom, /go2/imu
                                                        /joint_states, /go2/battery_state

ROS 2 제어                              Unitree 제어
/cmd_vel ──→ go2_cmd_vel_bridge ──→ /api/sport/request 또는 /lowcmd
```

`/cmd_vel`은 표준 `geometry_msgs/msg/Twist` 토픽이다. 제어 브리지는 기본적으로 명령이 약 0.5초 동안 끊기면 정지 명령을 보낸다.

## 좌표계와 URDF

```text
map → odom → base_link → hesai_lidar
```

| TF | 발행 주체 | 의미 |
|---|---|---|
| `map → odom` | SLAM Toolbox 또는 AMCL | 지도 기준 위치 보정 |
| `odom → base_link` | `go2_state_bridge` | Go2 주행 추정 |
| `base_link → hesai_lidar` | URDF / robot_state_publisher | LiDAR 장착 위치와 방향 |

LiDAR의 물리적 위치나 방향은 [go2_description.urdf](../../go2_driver/go2_description/urdf/go2_description.urdf)에서 관리한다. LaserScan에 포함할 높이 범위는 [go2_pointcloud_to_laserscan.yaml](../config/laser_scan/go2_pointcloud_to_laserscan.yaml)에서 관리한다.

## 핵심 노드와 토픽

| 노드 | 역할 |
|---|---|
| `go2_state_bridge` | Go2 상태, odom, IMU, 배터리 발행 |
| `go2_cmd_vel_bridge` | `/cmd_vel`을 Go2 명령으로 변환 |
| `hesai_ros_driver_node` | Hesai UDP를 PointCloud2로 변환 |
| `pointcloud_to_laserscan_node` | PointCloud2를 2D LaserScan으로 변환 |
| `slam_toolbox` | 지도 생성과 pose graph 관리 |
| Nav2 | 위치 추정, 경로 계획, 장애물 회피, 속도 제어 |

| 토픽 | 용도 |
|---|---|
| `/go2/odom` | 로봇 위치·속도 추정 |
| `/go2/imu` | Go2 IMU 상태 |
| `/go2/battery_state` | 배터리 상태 |
| `/hesai/lidar_points` | Hesai 3D 포인트클라우드 |
| `/scan` | SLAM·Nav2가 사용하는 2D LaserScan |
| `/cmd_vel` | 로봇 속도 명령 |
| `/map`, `/plan` | 지도와 전역 경로 |

```bash
ros2 topic info /go2/odom
ros2 topic echo /go2/battery_state --once
ros2 topic hz /hesai/lidar_points
ros2 node list
```

## 저장소와 설정 파일

```text
src/
├─ go2_driver/
│  ├─ go2_base/          Go2 상태·제어 브리지와 bringup
│  └─ go2_description/   URDF, TF, RViz 설정
├─ hesai_lidar/          Hesai XT16 드라이버 소스
├─ ktl/
│  ├─ config/            LiDAR, SLAM, Nav2 설정
│  ├─ launch/            매핑·내비게이션 launch
│  ├─ maps/              지도와 pose graph
│  └─ labs/              교육 자료
└─ unitree_ros2/         Unitree DDS 메시지·SDK
```

`hesai_lidar`는 소스 폴더명이다. 실제 ROS 패키지와 실행 파일 이름은 다음과 같다.

```text
패키지: hesai_ros_driver
실행 파일: hesai_ros_driver_node
```

실제 LiDAR 설정은 [config.yaml](../../hesai_lidar/config/config.yaml)에서 확인한다. 현재는 `source_type: 1`의 실시간 UDP 모드이며, PointCloud 토픽은 `/hesai/lidar_points`다.

## 설치·빌드·장비 정보

주요 ROS 의존성은 `ros-humble-desktop`, `ros-humble-rmw-cyclonedds-cpp`, `ros-humble-slam-toolbox`, `ros-humble-navigation2`, `ros-humble-nav2-bringup`, `ros-humble-pointcloud-to-laserscan`이다. Hesai GPU 빌드에는 CUDA 12.6과 Orin용 아키텍처 `87`이 필요하다.

```bash
cd ~/ktl_ws
colcon build --packages-select hesai_ros_driver --symlink-install \
  --cmake-clean-cache \
  --cmake-args -DFIND_CUDA=ON \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.6/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=87
colcon build --symlink-install --packages-skip hesai_ros_driver
source install/setup.bash
```

Jetson은 50W 전력 모드를 권장한다. 이미지마다 모드 번호가 다르므로 먼저 확인한 후 설정한다.

```bash
sudo nvpmodel -q
sudo nvpmodel -m <50W_모드번호>
```

로그인 비밀번호는 교육 문서에 기록하지 않고 별도 보안 채널로 관리한다.
