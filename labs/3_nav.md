# 3. Nav2로 자율주행하기

## 3.1 Navigation의 전체 흐름

```text
map.yaml → map_server → global_costmap → NavFn 전역 플래너
                                              │
/scan + TF + /go2/odom → local_costmap → DWB 로컬 컨트롤러
                                              │
                                              ▼
                                      /cmd_vel → Go2
```

현재 구성은 MPPI가 아니라 **DWB(Dynamic Window Approach)**다.

- 전역 플래너: `nav2_navfn_planner/NavfnPlanner`
- 로컬 컨트롤러: `dwb_core::DWBLocalPlanner`
- 전역 costmap: 저장된 지도와 장애물을 이용해 전체 경로를 평가
- 로컬 costmap: 로봇 주변의 최신 장애물을 이용해 즉시 움직일 속도를 평가
- 속도 출력: `/cmd_vel`

## 3.2 지도 불러오기

Navigation launch의 `map` 인자로 YAML 파일을 넘긴다.

```bash
source /opt/ros/humble/setup.bash
source ~/ktl_ws/install/setup.bash

ros2 launch ktl go2_navigation.launch.py \
  map:=/home/ktl/ktl_ws/src/ktl/maps/map_practice.yaml \
  rviz:=true
```

현재 `go2_navigation.launch.py`는 `map`과 `rviz`를 외부 인자로 받으며, 네트워크 인터페이스는 내부 bringup의 기본값 `eno1`을 사용한다.

지도 YAML에는 보통 다음 정보가 들어 있다.

```yaml
image: map_practice.pgm
resolution: 0.05
origin: [-10.0, -10.0, 0.0]
occupied_thresh: 0.65
free_thresh: 0.196
negate: 0
```

YAML과 PGM을 다른 폴더로 옮겼다면 `image:` 경로가 실제 파일을 가리키는지 확인한다.

## 3.3 초기 위치 지정: 2D Pose Estimate

지도 서버가 시작되었다고 로봇의 현재 위치를 자동으로 아는 것은 아니다. AMCL에 지도상의 초기 위치를 알려줘야 한다.

1. RViz의 Fixed Frame이 `map`인지 확인한다.
2. `2D Pose Estimate` 도구를 선택한다.
3. 지도에서 로봇이 실제로 있는 위치를 클릭한다.
4. 로봇의 현재 방향으로 드래그한다.
5. `/initialpose`가 발행되고 AMCL이 위치를 수렴시킨다.

> 📸 실습 사진 삽입: RViz에서 `2D Pose Estimate`를 선택하고 화살표를 그리는 화면

확인 명령:

```bash
ros2 topic echo /initialpose --once
ros2 topic echo /amcl_pose --once
```

AMCL 위치가 계속 틀어지면 초기 화살표 방향, `/scan`의 프레임, `map → odom → base_link` TF를 확인한다.

## 3.4 목표 지정과 도착

초기 위치가 맞은 뒤 RViz의 `Nav2 Goal` 도구를 선택한다.

1. 목적지를 클릭한다.
2. 목적지에서 로봇이 바라볼 방향으로 드래그한다.
3. Nav2가 전역 경로를 만들고, DWB가 로컬 속도를 계산한다.
4. DWB가 `/cmd_vel`을 발행하고 Go2가 이동한다.

> 📸 실습 사진 삽입: RViz에서 `Nav2 Goal`을 지정하고 경로가 표시된 화면

도착은 단순히 위치가 가까운지만 보는 것이 아니다. 현재 설정의 기본 목표 판정값은 다음과 같다.

| 설정 | 현재 값 | 의미 |
|---|---:|---|
| `xy_goal_tolerance` | `0.20` m | 목표 위치에서 허용되는 거리 |
| `yaw_goal_tolerance` | `0.20` rad | 목표 방향에서 허용되는 각도 |
| `stateful` | `true` | 위치·방향 판정을 상태적으로 처리 |

따라서 목표 방향이 진행 방향과 반대여도 Nav2는 위치에 도착한 뒤 회전할 수 있다. 목표에서 계속 돌거나 지나치면 `goal_checker`, DWB의 `RotateToGoal`, `/cmd_vel` timeout, odom TF를 함께 확인한다.

## 3.5 전역 경로와 로컬 경로

### 전역 플래너

전역 플래너는 지도 전체에서 시작점부터 목표점까지 갈 큰 길을 찾는다. 현재는 NavFn이며 `/plan`으로 경로를 확인할 수 있다.

```yaml
planner_server:
  ros__parameters:
    planner_plugins: [GridBased]
    GridBased:
      plugin: nav2_navfn_planner/NavfnPlanner
      tolerance: 0.5
      use_astar: true
      allow_unknown: true
```

`allow_unknown`을 false로 바꾸면 미탐색 영역을 통과하지 않도록 한다. `tolerance`를 키우면 목표 주변에서 경로를 찾을 수 있는 허용 범위가 넓어진다.

### 전역 costmap

전역 costmap은 `map` 프레임을 기준으로 저장된 지도와 센서 장애물을 합친다. 현재 주요 layer는 `static_layer`, `obstacle_layer`, `inflation_layer`다.

### 로컬 costmap

로컬 costmap은 `odom` 프레임의 rolling window다. 현재 크기는 5m × 5m이며 `/scan`을 최신 장애물 정보로 사용한다.

```yaml
local_costmap:
  local_costmap:
    ros__parameters:
      global_frame: odom
      rolling_window: true
      width: 5
      height: 5
      resolution: 0.05
```

로봇 주변 장애물이 잘 안 보이면 `/scan`과 local costmap의 observation source를 먼저 확인한다.

## 3.6 패딩과 장애물 영향 범위

Nav2에서 말하는 로봇 주변 여유 공간은 주로 `robot_radius` 또는 footprint와 `inflation_layer`로 만든다.

현재 주요값:

| 파라미터 | 현재 값 | 바꾸면 어떻게 변하는가 |
|---|---:|---|
| `robot_radius` | `0.28` m | 로봇 자체로 간주하는 반경 |
| local `inflation_radius` | `0.45` m | 주변 장애물의 비용이 퍼지는 거리 |
| global `inflation_radius` | `0.50` m | 전역 경로가 장애물을 피하는 여유 거리 |
| `cost_scaling_factor` | `4.0` | 장애물 가까이 갈 때 비용이 증가하는 정도 |

수정 파일은 `ktl/config/nav2/go2_nav2_params.yaml`이다.

- 벽에 너무 붙으면 `inflation_radius`를 늘린다.
- 좁은 통로를 못 지나가면 `robot_radius`나 inflation을 무작정 줄이기 전에 실제 Go2 외형과 안전 여유를 확인한다.
- LiDAR 높이 필터가 잘못되면 costmap 값을 조정해도 해결되지 않는다.

## 3.7 DWB 컨트롤러

현재 DWB가 후보 속도들을 시뮬레이션하고, 장애물·경로·목표와의 점수를 비교해 최종 `/cmd_vel`을 선택한다.

주요 설정은 다음과 같다.

```yaml
controller_server:
  ros__parameters:
    controller_frequency: 15.0
    FollowPath:
      plugin: dwb_core::DWBLocalPlanner
      max_vel_x: 0.35
      max_vel_y: 0.15
      max_vel_theta: 0.8
      vx_samples: 12
      vy_samples: 5
      vtheta_samples: 16
      sim_time: 1.2
```

`max_vel_y`가 0보다 크면 Go2가 횡이동 후보도 만들 수 있다. 게다리 걸음이 심하면 이 값을 낮추고 `max_vel_x`, `max_vel_theta`, `PathAlign`, `GoalAlign`의 균형을 확인한다. 단, 실제 보행 방식은 Go2의 제어 브리지와 보행 모드에도 영향을 받는다.

주요 critic:

- `BaseObstacle`: 장애물 충돌 회피
- `PathAlign`, `PathDist`: 전역 경로를 따라가기
- `GoalAlign`, `GoalDist`: 목표에 접근하기
- `RotateToGoal`: 목표 방향 맞추기
- `Oscillation`: 좌우 반복 진동 방지

## 3.8 `cmd_vel` 구조

토픽 타입은 `geometry_msgs/msg/Twist`다.

```text
Twist
├─ linear.x  앞(+)/뒤(-) 속도 [m/s]
├─ linear.y  좌(+)/우(-) 횡속도 [m/s]
├─ linear.z  일반 지상 주행에서는 0
├─ angular.x 롤 속도, 일반적으로 0
├─ angular.y 피치 속도, 일반적으로 0
└─ angular.z 반시계방향(좌) 회전 속도 [rad/s]
```

현재 브리지는 `/cmd_vel`을 받아 Unitree 명령으로 변환한다. 명령이 약 0.5초 동안 들어오지 않으면 timeout 정지 명령을 보낸다.

수동 시험은 작은 값으로 시작한다.

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.10, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

정지:

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

## 3.9 Waypoint

한 지점씩 RViz에서 `Nav2 Goal`을 보내는 것이 가장 쉬운 실습 방법이다. 여러 지점을 한 번에 보내려면 Nav2의 `NavigateThroughPoses` 액션을 사용한다.

```bash
ros2 action list | grep navigate
ros2 action info /navigate_through_poses
```

Waypoint를 사용할 때 각 지점의 `frame_id`는 `map`이어야 하고, 마지막 지점의 orientation도 명확히 지정한다. 좁은 공간에서는 지점 간 간격과 각 지점의 방향을 크게 잡아 급격한 회전을 줄인다.

## 3.10 turtlesim으로 개념 연습하기

Turtlesim은 Go2를 시뮬레이션하는 프로그램이 아니라 `Twist`와 ROS 2 토픽 구조를 연습하는 도구다.

```bash
ros2 run turtlesim turtlesim_node
ros2 run turtlesim turtle_teleop_key
```

별도 터미널에서 다음을 관찰한다.

```bash
ros2 topic echo /turtle1/cmd_vel
ros2 topic info /turtle1/cmd_vel
```

Turtlesim의 `/turtle1/cmd_vel`과 Go2의 `/cmd_vel`은 메시지 타입은 같지만, 실제 로봇으로 연결되지는 않는다.

## 3.11 Navigation launch 구성

`ktl/launch/go2_navigation.launch.py`는 다음을 실행한다.

- Go2 bringup: 상태·TF·Hesai 드라이버
- `pointcloud_to_laserscan_node`: Hesai PointCloud2 → `/scan`
- Nav2 bringup: map server, AMCL, planner, controller, costmap, behavior server
- RViz 2: 선택 실행

주요 설정 파일:

| 목적 | 파일 |
|---|---|
| Navigation 실행 인자 | `ktl/launch/go2_navigation.launch.py` |
| Nav2/AMCL/DWB/costmap | `ktl/config/nav2/go2_nav2_params.yaml` |
| PointCloud → LaserScan | `ktl/config/laser_scan/go2_pointcloud_to_laserscan.yaml` |
| Go2 상태·제어 브리지 | `go2_driver/go2_base/config/go2_driver_params.yaml` |

실행 중 구성 확인:

```bash
ros2 node list
ros2 topic hz /scan
ros2 topic echo /cmd_vel
ros2 topic echo /plan --once
ros2 topic echo /amcl_pose --once
```
