# 3. Nav2로 자율주행하기

현재 Navigation은 전역 플래너 NavFn과 로컬 컨트롤러 DWB를 사용한다. 저장된 지도에서 AMCL로 위치를 찾고, LiDAR 기반 costmap으로 장애물을 피하며 `/cmd_vel`을 생성한다.

## 전체 흐름

```text
map.yaml → map_server → global costmap → NavFn 전역 경로
                                              │
/scan + TF + /go2/odom → local costmap → DWB 속도 선택
                                              │
                                              ▼
                                     /cmd_vel → Go2
```

| 구성요소 | 역할 |
|---|---|
| AMCL | 지도와 `/scan`을 비교해 `map → odom` 보정 |
| Global costmap | 지도 전체의 통행 가능 영역과 안전 여유 관리 |
| NavFn | 시작점에서 목표점까지 전역 경로 생성 |
| Local costmap | 로봇 주변의 최신 장애물 반영 |
| DWB | 후보 속도를 평가해 `/cmd_vel` 발행 |

## 실행

```bash
source /opt/ros/humble/setup.bash
source ~/ktl_ws/install/setup.bash

ros2 launch ktl go2_navigation.launch.py \
  map:=/home/ktl/ktl_ws/src/ktl/maps/map_practice.yaml \
  rviz:=true
```

지도 YAML의 `image:`가 실제 PGM 파일을 가리켜야 한다. 현재 launch는 `map`, `rviz`를 인자로 받고 내부 Go2 bringup은 기본 인터페이스 `eno1`을 사용한다.

## RViz 사용 순서

### 1. 초기 위치 지정

1. Fixed Frame을 `map`으로 설정한다.
2. `2D Pose Estimate`를 선택한다.
3. 지도에서 실제 위치를 클릭하고 실제 방향으로 드래그한다.
4. AMCL 포즈가 수렴하는지 확인한다.

> 📸 사진 삽입 위치: 2D Pose Estimate로 위치와 방향을 지정하는 RViz 화면

```bash
ros2 topic echo /initialpose --once
ros2 topic echo /amcl_pose --once
```

### 2. 목표 전송

1. `Nav2 Goal`을 선택한다.
2. 목표 위치를 클릭하고 목표 방향으로 드래그한다.
3. `/plan`과 `/cmd_vel`이 생성되는지 확인한다.

> 📸 사진 삽입 위치: Nav2 Goal과 전역 경로가 표시된 RViz 화면

도착은 위치와 방향을 모두 만족해야 한다.

| 파라미터 | 현재 값 | 의미 |
|---|---:|---|
| `xy_goal_tolerance` | `0.20 m` | 목표 위치 허용 오차 |
| `yaw_goal_tolerance` | `0.20 rad` | 목표 방향 허용 오차 |
| `stateful` | `true` | 위치 판정 후 방향 판정을 유지 |

목표에서 계속 회전하면 goal tolerance, DWB `RotateToGoal`, `/go2/odom`, `/cmd_vel` timeout을 함께 확인한다.

## 경로 계획과 costmap

### 전역 경로

전역 플래너는 `map` 프레임의 global costmap에서 목적지까지 큰 경로를 만든다. 현재 플러그인은 `nav2_navfn_planner/NavfnPlanner`이며 A*를 사용한다.

### 로컬 회피

로컬 costmap은 `odom` 프레임의 5 m × 5 m rolling window다. `/scan`으로 최신 장애물을 반영하고 DWB가 짧은 시간의 속도 후보를 평가한다.

### 안전 여유

설정 파일: [go2_nav2_params.yaml](../config/nav2/go2_nav2_params.yaml)

| 파라미터 | 현재 값 | 조정 효과 |
|---|---:|---|
| `robot_radius` | `0.28 m` | 로봇 외형으로 간주하는 반경 |
| local `inflation_radius` | `0.45 m` | 로컬 장애물 주변 여유 거리 |
| global `inflation_radius` | `0.50 m` | 전역 경로의 장애물 여유 거리 |
| `cost_scaling_factor` | `4.0` | 장애물에 가까워질 때 비용 증가율 |

벽에 너무 붙으면 inflation을 키운다. 좁은 길을 지나지 못하면 robot radius와 inflation을 실제 로봇 크기·안전 여유에 맞춰 검토한다. LiDAR 높이 필터가 잘못된 문제는 costmap 값으로 해결되지 않는다.

## DWB 제어기

DWB는 여러 속도 후보를 미리 시뮬레이션하고 장애물, 경로, 목표에 대한 점수로 최종 속도를 선택한다.

| 파라미터 | 현재 값 | 의미 |
|---|---:|---|
| `controller_frequency` | `15 Hz` | 속도 명령 계산 주기 |
| `max_vel_x` | `0.35 m/s` | 전진 최대 속도 |
| `max_vel_y` | `0.15 m/s` | 횡이동 최대 속도 |
| `max_vel_theta` | `0.8 rad/s` | 회전 최대 속도 |
| `sim_time` | `1.2 s` | 후보 속도 예측 시간 |

`max_vel_y`가 크면 횡이동 후보가 늘어난다. 게다리 걸음이 심하면 이 값을 낮추고, `PathAlign`, `GoalAlign`, `RotateToGoal` critic과 함께 확인한다.

## `/cmd_vel` 이해하기

타입은 `geometry_msgs/msg/Twist`다.

```text
linear.x   전진(+), 후진(-) [m/s]
linear.y   좌(+), 우(-) 횡이동 [m/s]
angular.z  좌회전(+), 우회전(-) [rad/s]
```

수동 명령은 안전한 장소에서 낮은 속도로만 시험한다.

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.10, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

정지 명령:

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

## Waypoint와 turtlesim

여러 지점은 Nav2의 `NavigateThroughPoses` 액션으로 전달한다. 모든 waypoint는 `map` 프레임을 사용하고 마지막 지점의 방향을 지정한다.

```bash
ros2 action list | grep navigate
ros2 action info /navigate_through_poses
```

Turtlesim은 Go2 시뮬레이터가 아니라 `Twist` 메시지와 토픽 구조를 연습하는 도구다.

```bash
ros2 run turtlesim turtlesim_node
ros2 run turtlesim turtle_teleop_key
ros2 topic echo /turtle1/cmd_vel
```

## 확인과 문제 진단

```bash
ros2 topic hz /scan
ros2 topic echo /amcl_pose --once
ros2 topic echo /plan --once
ros2 topic echo /cmd_vel
ros2 run tf2_tools view_frames
```

| 증상 | 우선 확인 |
|---|---|
| AMCL 위치가 틀어짐 | 2D Pose Estimate, `/scan` frame, `map → odom → base_link` |
| 경로 생성 실패 | 시작·목표가 장애물인지, global costmap, map YAML |
| 장애물을 피하지 않음 | `/scan`, local costmap obstacle layer |
| 도착 후 계속 회전 | goal tolerance, `RotateToGoal`, odom |

Navigation launch, Nav2 설정, LaserScan 설정은 각각 [go2_navigation.launch.py](../launch/go2_navigation.launch.py), [go2_nav2_params.yaml](../config/nav2/go2_nav2_params.yaml), [go2_pointcloud_to_laserscan.yaml](../config/laser_scan/go2_pointcloud_to_laserscan.yaml)에서 관리한다.
