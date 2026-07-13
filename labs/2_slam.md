# 2. SLAM으로 지도 만들기

SLAM은 로봇 위치를 추정하면서 주변 지도를 동시에 만드는 과정이다. 현재 구성은 `slam_toolbox`가 `/scan`과 `odom → base_link` TF를 사용한다.

## 데이터 흐름

```text
/hesai/lidar_points ─→ pointcloud_to_laserscan_node ─→ /hesai/scan_raw
                                                            │
                                                    restamp_laserscan.py
                                                            │
/go2/odom ─→ TF odom→base_link ──────────────────────────→ /scan
                                                            │
                                                            ▼
                                                      slam_toolbox
                                                            │
                                                            ▼
                                                    /map, map→odom
```

| 입력 | 역할 | 현재 사용 여부 |
|---|---|---|
| `/go2/odom` | 짧은 시간 이동량 추정 | 사용 |
| `/scan` | 벽·장애물까지의 2D 거리 | 사용 |
| `/hesai/lidar_points` | LaserScan 생성용 원본 3D 데이터 | 사용 |
| `/go2/imu` | 자세·각속도 상태 | 직접 사용하지 않음 |
| `/cmd_vel` | 매핑 중 로봇 이동 | 필요 시 사용 |

현재 SLAM Toolbox는 IMU와 PointCloud를 직접 입력받지 않는다. PointCloud는 LaserScan으로 변환되고, IMU는 상태 확인 용도다.

## 실행 전 확인

```bash
source /opt/ros/humble/setup.bash
source ~/ktl_ws/install/setup.bash
ip link show eno1
ping -c 3 192.168.123.20
ping -c 3 192.168.123.161
```

## 매핑 실행

```bash
ros2 launch ktl go2_mapping.launch.py \
  network_interface:=eno1 rviz:=true
```

기본값은 `enable_control:=false`다. `/cmd_vel`로 Go2를 제어해야 할 때만 다음처럼 켠다.

```bash
ros2 launch ktl go2_mapping.launch.py \
  network_interface:=eno1 enable_control:=true
```

매핑 launch는 Go2 bringup, Hesai 드라이버, PointCloud→LaserScan 변환, timestamp 보정, SLAM Toolbox, RViz를 실행한다.

```bash
ros2 topic hz /hesai/lidar_points
ros2 topic hz /scan
ros2 topic echo /scan --once
ros2 topic echo /go2/odom --once
```

## LaserScan 생성

설정 파일: [go2_pointcloud_to_laserscan.yaml](../config/laser_scan/go2_pointcloud_to_laserscan.yaml)

1. `/hesai/lidar_points`를 `hesai_lidar`에서 `base_link`로 TF 변환한다.
2. 지정한 높이 범위의 포인트만 남긴다.
3. XY 평면에 투영해 2D LaserScan을 만든다.
4. 매핑 launch에서는 `/hesai/scan_raw`를 보정해 `/scan`으로 발행한다.

| 파라미터 | 현재 값 | 조정 기준 |
|---|---:|---|
| `target_frame` | `base_link` | LaserScan 기준 좌표계 |
| `min_height` | `-0.15 m` | 이보다 낮은 포인트 제거 |
| `max_height` | `0.45 m` | 이보다 높은 포인트 제거 |
| `range_min` / `range_max` | `0.2 / 20.0 m` | 유효 거리 범위 |
| `angle_increment` | `0.0087 rad` | 작을수록 해상도·처리량 증가 |

다리나 지면이 장애물로 들어오면 높이 범위를 확인한다. 센서 자체의 위치·방향은 URDF에서 수정한다.

### 높이 기준과 timestamp

`min_height`, `max_height`는 지면 기준이 아니라 **`base_link` 기준 z값**이다. 현재 URDF에서 `hesai_lidar`는 `base` 기준 `z=0.15 m`, yaw `+90°`로 고정되어 있다. 따라서 로봇 몸체의 기울기나 실제 지면 높이를 직접 나타내는 값으로 높이 필터를 해석하면 안 된다.

매핑 launch에만 있는 `restamp_laserscan.py`는 `/hesai/scan_raw`의 `header.stamp`를 현재 ROS 시간으로 바꿔 `/scan`을 발행한다. 이는 scan과 현재 odom/TF의 시간 차이로 TF 조회가 실패하는 상황을 완화하기 위한 것이다. 다만 실제 센서 취득 시간을 보존하는 방식은 아니므로, timestamp 문제가 반복되면 upstream LiDAR 시간과 TF 발행 시간을 함께 점검해야 한다.

## SLAM이 지도를 만드는 방식

1. odom으로 로봇의 이동을 예측한다.
2. 현재 LaserScan을 이전 스캔과 맞춰 위치 오차를 보정한다.
3. 보정된 위치에 관측값을 누적해 지도를 확장한다.
4. 이전 장소를 재방문하면 loop closing으로 누적 오차를 줄인다.

Odom은 부드럽지만 시간이 지날수록 drift가 생긴다. LaserScan은 이를 보정하지만 반복되는 복도나 빈 공간에서는 모호할 수 있다. 따라서 안정적인 TF, timestamp, 적절한 주행 속도가 중요하다.

### 좋은 지도를 위한 주행 원칙

- 시작 전에 RViz에서 `/scan`이 벽과 장애물을 안정적으로 표현하는지 확인한다.
- 처음에는 벽·기둥 등 특징이 있는 구역을 지나며 천천히 한 바퀴 돈다.
- 급가속·급회전 중에는 한 프레임 안에서 로봇 자세가 많이 달라져 scan matching이 불안정할 수 있다.
- 같은 장소로 돌아와 loop closing이 가능한 경로를 만든다.
- 지도 품질이 나쁘다고 바로 solver 값을 바꾸지 말고, TF·높이 필터·scan 주기·odom을 먼저 확인한다.

## 핵심 설정

설정 파일: [go2_slam_toolbox.yaml](../config/slam/go2_slam_toolbox.yaml)

| 파라미터 | 현재 값 | 의미 |
|---|---:|---|
| `odom_frame`, `map_frame`, `base_frame` | `odom`, `map`, `base_link` | SLAM 좌표계 |
| `scan_topic` | `/scan` | 입력 LaserScan |
| `resolution` | `0.05 m` | 지도 셀 크기 |
| `map_update_interval` | `2.0 s` | 지도 갱신 주기 |
| `minimum_travel_distance` | `0.15 m` | 이 거리 이상 이동 시 스캔 처리 |
| `minimum_travel_heading` | `0.15 rad` | 이 각도 이상 회전 시 스캔 처리 |
| `do_loop_closing` | `true` | 재방문 장소의 drift 보정 |

처음에는 TF와 `scan_topic`, 레이저 범위가 맞는지 먼저 확인하고, 세부 파라미터는 그 다음에 조정한다.

### 품질 문제별 조정 순서

| 현상 | 먼저 확인 | 이후 조정 후보 |
|---|---|---|
| 벽이 두 겹으로 보임 | TF, scan timestamp, odom drift | `minimum_travel_*`, scan matching 범위 |
| 지도가 너무 듬성듬성함 | `throttle_scans`, 이동 속도 | `minimum_travel_distance`, `minimum_travel_heading` 낮춤 |
| CPU 사용량이 높음 | scan 주기, map 해상도 | `throttle_scans`, `minimum_time_interval`, `resolution` |
| loop가 잘 안 닫힘 | 실제로 재방문했는지, scan 품질 | loop 응답 임계값·검색 범위 |
| 잘못된 loop로 지도 휨 | 반복 구조 환경인지, TF | loop 응답 임계값을 높여 후보를 엄격화 |

한 번에 한 종류의 값만 작게 바꾸고, 같은 경로를 다시 주행해 전후 지도를 비교한다.

## Pose graph와 지도 저장

Pose graph는 SLAM의 스캔 위치와 연결 제약을 저장한다. 매핑을 중단하기 전 중간 상태를 저장할 때 사용한다.

```bash
ros2 service call /slam_toolbox/serialize_map \
  slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/home/ktl/ktl_ws/src/ktl/maps/map_practice'}"
```

저장한 pose graph를 지정 위치에서 불러온다.

```bash
ros2 service call /slam_toolbox/deserialize_map \
  slam_toolbox/srv/DeserializePoseGraph \
  "{filename: '/home/ktl/ktl_ws/src/ktl/maps/map_practice', match_type: 2, initial_pose: {x: 0.0, y: 0.0, theta: 0.0}}"
```

Nav2에서 사용할 점유 지도는 별도로 저장한다.

```bash
ros2 run nav2_map_server map_saver_cli \
  -f /home/ktl/ktl_ws/src/ktl/maps/map_practice
```

생성 파일:

| 파일 | 내용 |
|---|---|
| `map_practice.pgm` | 흑백 점유 격자 이미지 |
| `map_practice.yaml` | 이미지 경로, 해상도, 원점, 임계값 |

Pose graph와 점유 지도는 목적이 다르다. pose graph는 SLAM을 이어서 최적화하기 위한 데이터이고, PGM/YAML은 Nav2가 정적 지도로 읽는 결과물이다. PGM/YAML만 저장하면 SLAM을 같은 graph 상태로 재개할 수 없다.

GIMP로 PGM을 수정할 때는 원본을 백업하고, 픽셀 크기와 YAML의 `resolution`을 유지한다. 안티앨리어싱이나 흐린 회색 영역은 점유 판정을 불안정하게 만들 수 있다.

수정 후에는 Navigation에서 맵을 열고, 벽을 지운 곳·새로 막은 곳이 local/global costmap에 의도대로 반영되는지 확인한다.

## 빠른 문제 진단

| 증상 | 우선 확인 |
|---|---|
| PointCloud 없음 | Hesai 전원·IP·UDP 2368·`eno1` |
| `/scan` 없음 | PointCloud 변환 노드, TF, 높이 필터 |
| 지도 갱신 안 됨 | `/scan`, `/go2/odom`, `odom → base_link` TF |
| 지도 휘어짐·중복 | TF, timestamp, 주행 속도, loop closing |

```bash
ros2 run tf2_tools view_frames
ros2 run tf2_ros tf2_echo odom base_link
ros2 service list | grep slam_toolbox
```
