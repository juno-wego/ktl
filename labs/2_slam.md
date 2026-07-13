# 2. SLAM으로 지도 만들기

## 2.1 SLAM 실행 전에 필요한 데이터

현재 매핑 경로는 다음과 같다.

```text
Hesai PointCloud2
  /hesai/lidar_points
        │
        ▼
pointcloud_to_laserscan_node
        │  TF로 hesai_lidar → base_link 변환
        ▼
/hesai/scan_raw ── restamp_laserscan.py ──→ /scan
                                             │
/go2/odom ── go2_state_bridge ──→ TF odom→base_link
                                             │
                                             ▼
                                      slam_toolbox
                                             │
                                             ▼
                                      /map, map→odom
```

필요한 입력은 다음과 같다.

| 입력 | 역할 | 현재 사용 위치 |
|---|---|---|
| `/go2/odom` | 짧은 시간 동안의 이동량, 초기 위치 추정 | `odom → base_link` TF로 변환되어 사용 |
| `/scan` | 벽·장애물까지의 2D 거리 | SLAM Toolbox의 `scan_topic` |
| `/hesai/lidar_points` | 원본 3D LiDAR 데이터 | LaserScan 생성 입력 |
| `/go2/imu` | 자세·각속도 센서 데이터 | 상태 확인용. 현재 SLAM Toolbox의 직접 입력은 아님 |
| `/cmd_vel` | 로봇을 움직이는 명령 | 매핑 주행 시 선택적으로 사용 |

중요한 점은 현재 SLAM Toolbox가 3D PointCloud나 IMU를 직접 받는 것이 아니라, **`/scan`과 TF/odom을 중심으로 동작한다는 것**이다. IMU는 `go2_state_bridge`가 `/go2/imu`로 발행하지만 현재 SLAM 설정에는 IMU 입력 플러그인이 연결되어 있지 않다.

## 2.2 LaserScan은 어떻게 만들어지는가

설정 파일은 `ktl/config/laser_scan/go2_pointcloud_to_laserscan.yaml`이다.

1. Hesai가 `/hesai/lidar_points`로 3D 포인트를 보낸다.
2. 각 포인트를 `hesai_lidar`에서 `base_link` 기준으로 TF 변환한다.
3. `min_height: -0.15`, `max_height: 0.45` 사이의 점만 남긴다.
4. XY 평면에서 각도를 계산해 약 0.5도 간격의 LaserScan으로 투영한다.
5. 가까운 점을 거리값으로 선택하고 `/scan`으로 전달한다.

현재 핵심값:

| 파라미터 | 현재 값 | 바꾸면 어떻게 변하는가 |
|---|---:|---|
| `target_frame` | `base_link` | 모든 점을 어느 좌표계로 변환할지 결정 |
| `min_height` | `-0.15` m | 이보다 낮은 점을 제거 |
| `max_height` | `0.45` m | 이보다 높은 점을 제거 |
| `angle_increment` | `0.0087` rad | 작을수록 각도 해상도 증가, 처리량 증가 |
| `range_min` | `0.2` m | 너무 가까운 점 제거 |
| `range_max` | `20.0` m | 먼 점 제거 |

지면이 안 보이거나 로봇 다리가 장애물로 잡히면 높이 필터를 먼저 확인한다. 라이다의 물리적 높이와 센서 방향은 URDF의 고정 관절에서 확인한다.

## 2.3 매핑 실행

먼저 네트워크와 로봇 상태를 확인한다.

```bash
ip link show eno1
ping -c 3 192.168.123.20
ping -c 3 192.168.123.161
source /opt/ros/humble/setup.bash
source ~/ktl_ws/install/setup.bash
```

매핑 실행:

```bash
ros2 launch ktl go2_mapping.launch.py \
  network_interface:=eno1 \
  rviz:=true
```

기본 설정에서는 `use_sim_time:=false`, `enable_control:=false`이다. `/cmd_vel`로 직접 주행할 때만 다음처럼 제어 브리지를 켠다.

```bash
ros2 launch ktl go2_mapping.launch.py \
  network_interface:=eno1 \
  enable_control:=true
```

### 매핑 launch에 들어 있는 것

`go2_mapping.launch.py`는 다음을 한 번에 실행한다.

- Go2 bringup: 상태, TF, Hesai 드라이버
- `pointcloud_to_laserscan_node`: PointCloud2 → `/hesai/scan_raw`
- `restamp_laserscan.py`: scan timestamp를 보정해 `/scan` 발행
- `slam_toolbox/online_async_launch.py`: 실시간 지도 생성
- RViz 2: 센서와 지도 확인

필요하면 입력과 SLAM 설정을 인자로 바꿀 수 있다.

```bash
ros2 launch ktl go2_mapping.launch.py \
  cloud_topic:=/hesai/lidar_points \
  slam_params_file:=/home/ktl/ktl_ws/src/ktl/config/slam/go2_slam_toolbox.yaml
```

## 2.4 SLAM의 원리

SLAM은 “내 위치를 추정하면서 동시에 지도를 만드는” 문제다.

1. `/go2/odom`으로 로봇이 얼마나 이동했는지 예측한다.
2. 같은 시점의 `/scan`에서 벽과 장애물의 상대 위치를 얻는다.
3. 이전 스캔과 현재 스캔을 맞춰 odom 오차를 보정한다.
4. 보정된 로봇 위치에 센서 점을 누적해 지도를 확장한다.

Odom은 단기적으로 부드럽지만 시간이 지나면 drift가 생긴다. LaserScan은 벽의 모양을 기준으로 위치를 보정하지만, 반복되는 복도나 빈 공간에서는 모호할 수 있다. 두 정보를 함께 사용하기 때문에 주행 속도와 센서 TF가 모두 중요하다.

## 2.5 Loop closing

로봇이 같은 장소를 다시 지나가면 SLAM Toolbox가 “현재 장소와 과거 장소가 같다”는 제약을 찾는다. 이를 loop closing이라고 한다.

현재 설정은 `do_loop_closing: true`이며, 후보 검색 범위는 `loop_search_maximum_distance: 3.0`이다. Loop closing이 성공하면 누적된 odom drift가 전체 pose graph에 분배되어 지도가 맞춰진다.

지도가 갑자기 크게 휘거나 잘못 붙는다면 다음을 확인한다.

- 센서 TF의 위치·방향
- `/scan` timestamp와 주기
- 같은 모양이 반복되는 환경에서 잘못된 loop가 잡히지 않았는지
- `minimum_travel_distance`, `minimum_travel_heading`이 너무 작은지

## 2.6 중요한 SLAM 파라미터

설정 파일: `ktl/config/slam/go2_slam_toolbox.yaml`

| 파라미터 | 현재 값 | 의미 |
|---|---:|---|
| `odom_frame` | `odom` | 주행 추정 좌표계 |
| `map_frame` | `map` | 지도 좌표계 |
| `base_frame` | `base_link` | 로봇 기준 좌표계 |
| `scan_topic` | `/scan` | SLAM 입력 LaserScan |
| `resolution` | `0.05` m | 지도 한 칸의 크기 |
| `map_update_interval` | `2.0` s | 지도 갱신 주기 |
| `minimum_travel_distance` | `0.15` m | 이 거리 이상 움직였을 때 처리 |
| `minimum_travel_heading` | `0.15` rad | 이 각도 이상 회전했을 때 처리 |
| `minimum_laser_range` | `0.1` m | LaserScan 최소 유효 거리 |
| `maximum_laser_range` | `20.0` m | LaserScan 최대 유효 거리 |
| `do_loop_closing` | `true` | 과거 장소 재방문 보정 |

처음에는 `resolution`, `scan_topic`, TF 프레임, 레이저 범위만 확인하고 나머지는 기본값을 유지하는 것이 안전하다.

## 2.7 Pose graph 저장·불러오기

### Pose graph 저장

Pose graph는 SLAM의 노드와 제약을 저장한다. 중간 상태를 저장하려면 SLAM이 실행 중인 터미널에서 다음을 실행한다.

```bash
ros2 service call /slam_toolbox/serialize_map \
  slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/home/ktl/ktl_ws/src/ktl/maps/map_practice'}"
```

파일 확장자는 서비스가 처리하므로 경로에 같은 이름의 기존 파일이 있으면 덮어쓰기 여부를 확인한다.

### Pose graph 불러오기

불러오기는 SLAM Toolbox의 `deserialize_map` 서비스를 사용한다.

```bash
ros2 service call /slam_toolbox/deserialize_map \
  slam_toolbox/srv/DeserializePoseGraph \
  "{filename: '/home/ktl/ktl_ws/src/ktl/maps/map_practice', match_type: 2, initial_pose: {x: 0.0, y: 0.0, theta: 0.0}}"
```

`match_type: 2`는 지정한 초기 포즈에서 시작하는 방식이다. 실제 시작 위치가 다르면 RViz에서 위치를 맞추거나 서비스의 `initial_pose`를 바꾼다. 서비스 필드는 설치된 ROS 버전에 따라 확인할 수 있다.

```bash
ros2 interface show slam_toolbox/srv/DeserializePoseGraph
```

## 2.8 지도 파일 저장과 수정

SLAM이 만든 점유 격자 지도는 다음 명령으로 저장한다.

```bash
ros2 run nav2_map_server map_saver_cli \
  -f /home/ktl/ktl_ws/src/ktl/maps/map_practice
```

일반적으로 다음 두 파일이 만들어진다.

- `map_practice.pgm`: 흑백 점유 격자 이미지
- `map_practice.yaml`: 이미지 경로, 해상도, 원점, 점유 임계값

YAML의 `resolution`과 `origin`은 지도와 좌표계의 관계를 결정한다. 이미지 크기나 해상도를 임의로 바꾸면 실제 공간의 좌표가 달라질 수 있다.

GIMP로 PGM을 수정할 때:

1. 원본을 복사해 백업한다.
2. 벽을 검정, 주행 가능 영역을 흰색으로 유지한다.
3. 부드러운 브러시나 안티앨리어싱을 피한다.
4. 같은 픽셀 크기와 `map.yaml`의 `resolution`을 유지한다.
5. Nav2에서 다시 불러와 로봇 위치와 벽 위치를 확인한다.

## 2.9 문제 확인 명령

```bash
ros2 topic hz /hesai/lidar_points
ros2 topic hz /scan
ros2 topic echo /scan --once
ros2 run tf2_tools view_frames
ros2 topic echo /go2/odom --once
ros2 service list | grep slam_toolbox
```

`/hesai/lidar_points`는 나오는데 `/scan`이 없으면 LaserScan 변환 설정, TF, 높이 필터를 확인한다. `/scan`은 나오는데 지도가 움직이지 않으면 `odom → base_link` TF와 timestamp를 확인한다.
