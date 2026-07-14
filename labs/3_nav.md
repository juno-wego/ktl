# 3. Nav2로 자율주행하기

현재 Navigation은 전역 플래너 NavFn과 로컬 컨트롤러 DWB를 사용한다. 저장된 지도에서 AMCL로 위치를 찾고, LiDAR 기반 costmap으로 장애물을 피하며 `/cmd_vel`을 생성한다.

## Navigation에 들어가는 데이터

| 입력·출력 | 역할 |
|---|---|
| `map.yaml`, `map.pgm` | 로봇이 주행할 정적 지도 |
| `/scan` | 현재 벽과 장애물의 거리 |
| `/go2/odom` | 짧은 시간 동안의 로봇 이동량 |
| `map → odom → base_link` TF | 지도·주행 추정·로봇 몸체 좌표계 연결 |
| `/cmd_vel` | Nav2가 Go2에 보내는 속도 명령 |

`/scan`과 저장된 지도를 비교해 현재 위치를 찾고, 그 위치에서 목표까지의 경로와
속도를 계산한다.

## Nav2가 주행하는 원리

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
| Global costmap | 지도 전체의 통행 가능 영역과 장애물 주변 여유 거리 관리 |
| NavFn | 시작점에서 목표점까지 전역 경로 생성 |
| Local costmap | 로봇 주변의 최신 장애물 반영 |
| DWB | 후보 속도를 평가해 `/cmd_vel` 발행 |

### AMCL로 현재 위치 찾기

AMCL은 `/scan`을 저장된 지도와 비교해 `map → odom` TF를 추정한다. odom은 짧은 시간 이동을 부드럽게 연결하고, AMCL은 장기 누적 오차를 지도 기준으로 보정한다. 따라서 RViz에서 로봇 모델이 지도 위에 맞아 보여도 `/scan`의 벽이 지도 벽과 맞지 않으면 위치는 다시 틀어진다.

현재 AMCL은 Go2의 횡이동을 허용하는 `OmniMotionModel`을 사용한다. 입자는 최소 500개에서 최대 2000개이며, 로봇이 `0.10 m` 이동하거나 `0.10 rad` 회전하면 scan 기반 갱신을 수행한다. 사람·다리처럼 지도에 없는 물체의 영향을 줄이기 위해 beam skipping도 활성화되어 있다.

AMCL이 불안정할 때는 `alpha1~alpha5`를 먼저 바꾸지 않는다. 초기 위치·방향, LaserScan 높이 필터, map/scan frame, 지도 품질을 먼저 확인한다. 이들이 맞는데도 주행 중 위치가 지속적으로 밀릴 때만 alpha 값을 조금씩 조정한다.

### 경로를 만들고 장애물을 피하는 방법

#### 전체 경로 만들기

전역 플래너는 `map` 프레임의 global costmap에서 목적지까지 큰 경로를 만든다. 현재 플러그인은 `nav2_navfn_planner/NavfnPlanner`이며 A*를 사용한다.

#### 주변 장애물 피하기

로컬 costmap은 `odom` 프레임의 5 m × 5 m rolling window다. `/scan`으로 최신 장애물을 반영하고 DWB가 짧은 시간의 속도 후보를 평가한다.

| 구성 | 현재 값 | 의미 |
|---|---:|---|
| local costmap 갱신 | `8 Hz` | 가까운 장애물 변화 반영 주기 |
| global costmap 갱신 | `1 Hz` | 지도·전역 장애물 갱신 주기 |
| 전역 플래너 기대 주기 | `5 Hz` | planner server의 계획 처리 기준 |
| BT 재계획 주기 | `1 Hz` | NavigateToPose 기본 트리의 경로 재요청 주기 |
| local 장애물 최대 거리 | `4.5 m` | DWB 회피에 표시할 최대 거리 |
| global 장애물 최대 거리 | `5.0 m` | 전역 costmap에 표시할 최대 거리 |

Obstacle layer는 `marking: true`로 실제 장애물을 추가하고, `clearing: true`로 LiDAR가 빈 공간을 다시 관측하면 오래된 장애물 표시를 지운다. 장애물이 사라졌는데 costmap에 남으면 `/scan`의 빈 빔, raytrace 범위, TF를 확인한다.

#### 장애물과의 안전거리

설정 파일: [go2_nav2_params.yaml](../config/nav2/go2_nav2_params.yaml)

| 파라미터 | 현재 값 | 조정 효과 |
|---|---:|---|
| `robot_radius` | `0.28 m` | 로봇 외형으로 간주하는 반경 |
| local `inflation_radius` | `0.45 m` | 로컬 장애물 주변 여유 거리 |
| global `inflation_radius` | `0.50 m` | 전역 경로의 장애물 여유 거리 |
| `cost_scaling_factor` | `4.0` | 장애물에 가까워질 때 비용 증가율 |

벽에 너무 붙으면 inflation을 키운다. 좁은 길을 지나지 못하면 robot radius와 inflation을 실제 로봇 크기와 필요한 통과 여유에 맞춰 검토한다. LiDAR 높이 필터가 잘못된 문제는 costmap 값으로 해결되지 않는다.

### DWB가 속도를 정하는 방법

DWB는 여러 속도 후보를 미리 시뮬레이션하고 장애물, 경로, 목표에 대한 점수로 최종 속도를 선택한다.

| 파라미터 | 현재 값 | 의미 |
|---|---:|---|
| `controller_frequency` | `15 Hz` | 속도 명령 계산 주기 |
| `max_vel_x` | `0.35 m/s` | 전진 최대 속도 |
| `max_vel_y` | `0.15 m/s` | 횡이동 최대 속도 |
| `max_vel_theta` | `0.8 rad/s` | 회전 최대 속도 |
| `sim_time` | `1.2 s` | 후보 속도 예측 시간 |

`max_vel_y`가 크면 횡이동 후보가 늘어난다. 게다리 걸음이 심하면 이 값을 낮추고, `PathAlign`, `GoalAlign`, `RotateToGoal` critic과 함께 확인한다.

| critic | 판단 기준 |
|---|---|
| `BaseObstacle` | 충돌하거나 장애물에 너무 가까운 후보 제거 |
| `PathAlign`, `PathDist` | 전역 경로 방향과 거리 유지 |
| `GoalAlign`, `GoalDist` | 목표 위치·방향 접근 |
| `RotateToGoal` | 목표 근처에서 목표 yaw 맞춤 |
| `Oscillation` | 좌우·앞뒤 반복 움직임 억제 |

`progress_checker`는 10초 안에 0.3m 이상 진행하지 못하면 진행 실패로 판단한다. 이 값은 좁은 곳에서 정지한 로봇을 실패로 판단하는 기준이지, 목표 도착 판정값은 아니다.

### 길을 못 찾을 때의 복구 동작

현재 BT XML을 별도로 지정하지 않았으므로 Nav2 Humble의 기본 `navigate_to_pose_w_replanning_and_recovery.xml`을 사용한다. 목표 주행 중 전역 경로는 초당 1회 재계획한다.

계획이나 제어가 실패하면 Nav2는 우선 해당 costmap을 비우고 다시 시도한다. 계속 실패하면 전체 복구 단계에서 다음을 순환 실행한다.

1. local·global costmap 전체 비우기
2. 약 90도 제자리 회전
3. 5초 대기
4. 0.30m를 0.05m/s로 후진

최대 6회 복구를 시도할 수 있다. 실제 Go2 주변에서 후진이 안전하지 않다면 이 기본 동작을 이해한 뒤 `behavior_server`와 BT를 별도로 조정해야 한다.

## 자율주행 시작하기

```bash
source /opt/ros/humble/setup.bash
source ~/ktl_ws/install/setup.bash

ros2 launch ktl go2_navigation.launch.py \
  map:=/home/ktl/ktl_ws/src/ktl/maps/map_practice.yaml \
  rviz:=true
```

지도 YAML의 `image:`가 실제 PGM 파일을 가리켜야 한다. 지도를 수정해야 한다면
[GIMP로 지도 수정하기](2_slam.md#gimp로-지도-수정하기)를 먼저 따른다. Navigation
launch는 Go2 bringup, Hesai 드라이버, LaserScan 변환, Nav2, RViz를 함께 실행한다.

### 실행 뒤 확인

처음에는 아직 AMCL 초기 위치를 주지 않았으므로, 지도·scan·odom TF가 정상인지 먼저
확인한다.

```bash
ros2 topic echo /map --once
ros2 topic hz /scan
ros2 run tf2_ros tf2_echo odom base_link
```

`/map`이 보이고 `/scan`이 계속 들어오며 `odom → base_link` TF가 출력되면 다음 단계로
진행한다.

## RViz에서 목표 보내기

### 1. 초기 위치 지정

1. Fixed Frame을 `map`으로 설정한다.
2. `2D Pose Estimate`를 선택한다.
3. 지도에서 실제 위치를 클릭하고 실제 방향으로 드래그한다.
4. AMCL 포즈가 지도 위에서 안정되는지 확인한다.

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

## `/cmd_vel`로 속도 명령하기

`/cmd_vel`의 타입은 `geometry_msgs/msg/Twist`다. 이는 “어디로 이동할지”가 아니라 **지금부터 어느 방향으로 얼마나 빠르게 움직일지**를 보내는 속도 명령이다. Nav2의 DWB나 수동 명령 노드가 계속 발행하고, `go2_cmd_vel_bridge`가 이를 Unitree 이동 명령으로 변환한다.

현재 Go2 브리지가 사용하는 필드는 세 개다.

| 필드 | 단위 | 양수 방향 | Go2에서의 의미 |
|---|---|---|---|
| `linear.x` | m/s | 앞 | 전진 속도. 음수면 후진 |
| `linear.y` | m/s | 왼쪽 | 횡이동 속도. 음수면 오른쪽 이동 |
| `angular.z` | rad/s | 반시계 방향 | 좌회전 속도. 음수면 우회전 |

`linear.z`, `angular.x`, `angular.y`는 이 지상 주행 브리지에서 사용하지 않으므로 0으로 둔다. 현재 Nav2의 최대 출력은 전진 `0.35 m/s`, 횡이동 `0.15 m/s`, 회전 `0.8 rad/s`다.

| 의도 | 핵심 값 | 예시 |
|---|---|---|
| 직진 | `linear.x` | `x: 0.10` |
| 전진하며 좌회전 | `linear.x` + `angular.z` | `x: 0.10`, `z: 0.30` |
| 제자리 좌회전 | `angular.z` | `z: 0.30` |
| 좌측 횡이동 | `linear.y` | `y: 0.05` |

횡이동은 Go2가 옆으로 걷게 하므로, 전진하며 곡선 주행을 원할 때는 보통 `linear.x`와 `angular.z`를 함께 사용하고 `linear.y`는 0에 가깝게 둔다. 수동 명령은 안전한 장소에서 낮은 속도로만 시험한다.

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.10, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

전진하며 좌회전:

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.10, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.30}}"
```

정지 명령:

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

진행 중인 Nav2 목표를 모두 취소하려면 action의 cancel 서비스를 호출한다. 목표 취소 후에도 로봇이 움직인다면 즉시 0 속도 명령을 한 번 더 보낸다.

```bash
ros2 service call /navigate_to_pose/_action/cancel_goal \
  action_msgs/srv/CancelGoal \
  "{goal_info: {goal_id: {uuid: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}, stamp: {sec: 0, nanosec: 0}}}"
```

`/cmd_vel`의 0 속도 발행은 소프트웨어 정지 수단이다. 사람이나 장비와 충돌할 위험이 있는 상황에서는 이것만을 비상정지 장치로 간주하지 말고, 현장 안전 절차에 따라 로봇을 안전 상태로 전환한다.

명령은 한 번만 보내는 것이 아니라 주기적으로 보내야 한다. 브리지는 마지막 `/cmd_vel`이 0.5초 동안 갱신되지 않으면 `StopMove`를 보낸다. 이는 통신 단절 시 로봇이 계속 움직이지 않도록 하는 보호 동작이다.

## Waypoint 활용

여러 지점은 Nav2의 `NavigateThroughPoses` 액션으로 전달한다. 모든 waypoint는 `map` 프레임을 사용하고 마지막 지점의 방향을 지정한다.

```bash
ros2 action list | grep navigate
ros2 action info /navigate_through_poses
```

현재 waypoint follower는 도착 후 200ms 대기하고, 한 waypoint에 실패해도 다음 waypoint를 계속 시도하도록 `stop_on_failure: false`로 설정되어 있다. 현장 점검처럼 모든 지점 성공이 중요하면 이 정책을 바꾸기 전에 실패 시 로봇의 안전한 정지 방법을 먼저 정한다.

## 실행 중 확인할 것

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

YAML 값을 바꾼 뒤에는 Navigation launch를 다시 시작한다. 평소에는 `map`과 `rviz`
인자만 지정하면 되고, Nav2의 동작 값은 `go2_nav2_params.yaml`에서 관리한다.
