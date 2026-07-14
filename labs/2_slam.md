# 2. SLAM으로 지도 만들기

SLAM은 로봇 위치를 추정하면서 주변 지도를 동시에 만드는 과정이다. 현재 구성은 `slam_toolbox`가 `/scan`과 `odom → base_link` TF를 사용한다.

## SLAM에 들어가는 데이터

| 입력 | 역할 | 현재 사용 여부 |
|---|---|---|
| `/go2/odom` | 짧은 시간 이동량 추정 | 사용 |
| `/scan` | 벽·장애물까지의 2D 거리 | 사용 |
| `/hesai/lidar_points` | LaserScan 생성용 원본 3D 데이터 | 사용 |
| `/go2/imu` | 자세·각속도 상태 | 직접 사용하지 않음 |
| `/cmd_vel` | 매핑 중 로봇 이동 | 필요 시 사용 |

## LaserScan이 만들어지는 과정

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
| `range_min` | `0.2 m` | 유효 거리 범위 |
| `range_max` | `20.0 m` | 유효 거리 범위 |

## SLAM이 지도를 만드는 원리

| 순서 | 과정 | 오차 |
|-----|----|----|
|  1  | odom으로 로봇의 이동을 예측한다. | 오차 누적 |
|  2  | 현재 LaserScan을 이전 스캔과 맞춰 위치 오차를 보정한다 | 오차 보정 |
|  3  | 보정된 위치에 관측값을 누적해 지도를 확장한다 | 그래도 오차는 남음 |
|  4  | 이전 장소를 재방문하면 loop closing으로 누적 오차 개선 | 해당 과정을 반복하여 오차 개선 |

### Odom

Odom은 로봇이 어디에서 얼마나 움직였는지를 계속 알려주는 값이다. 이 시스템에서는
`go2_state_bridge`가 Go2 상태를 받아 `/go2/odom`으로 발행하고, 같은 위치 정보를
`odom → base_link` TF로도 보낸다.

SLAM Toolbox는 odom을 보고 로봇이 이전 스캔 위치에서 어느 쪽으로 움직였을지 먼저
예상한다. 그다음 `/scan`을 맞춰 보면서 실제 위치를 다시 보정한다. 그래서 odom은
짧은 시간에는 움직임을 잘 따라가지만, 오래 움직일수록 실제 위치와 조금씩 달라질 수
있다. 이 누적 오차는 scan matching과 loop closing으로 줄인다.

#### `/go2/odom` 메시지 예시

| 항목 | 기준 좌표계 | 의미 | 주로 볼 값 |
|---|---|---|---|
| `pose` | `odom` | 시작 위치 기준 로봇이 현재 어디에 있고 어느 방향을 보는지 | `position.x`, `position.y`, `orientation` |
| `twist` | `base_link` | 로봇이 지금 얼마나 빠르게 움직이고 회전하는지 | `linear.x`, `linear.y`, `angular.z` |

`pose`는 위치·자세이고, `twist`는 속도다. 그래서 로봇이 멈춰 있어도 `pose`에는
마지막 위치가 남아 있지만, `twist`의 속도 값은 거의 `0`이 된다.

```yaml
header:
  frame_id: odom
child_frame_id: base_link
pose:
  pose:
    position:
      x: 0.00  # odom 기준 앞·뒤 위치(m)
      y: 0.00  # odom 기준 좌·우 위치(m)
      z: 0.05
twist:
  twist:
    linear:
      x: 0.00  # 앞·뒤 속도(m/s)
      y: 0.00  # 좌·우 속도(m/s)
    angular:
      z: 0.00  # 회전 속도(rad/s)
```

로봇이 앞으로 움직이는 중에는 다음처럼 보일 수 있다.

```yaml
header:
  frame_id: odom
child_frame_id: base_link
pose:
  pose:
    position:
      x: 1.25  # 출발점에서 1.25 m 전진한 상황.
      y: 0.03
      z: 0.05
twist:
  twist:
    linear:
      x: 0.15  # 0.15 m/s로 전진 중
      y: 0.00
    angular:
      z: 0.00
```

제자리에서 왼쪽으로 회전하면 `linear.x`는 거의 `0`이고, 대신 `angular.z`가 양수로
바뀐다. 오른쪽 회전에서는 `angular.z`가 음수가 된다.

#### Odom 확인 방법

```bash
ros2 topic echo /go2/odom --once # 내용 확인
ros2 topic hz /go2/odom # 발행 주기 확인
ros2 run tf2_ros tf2_echo odom base_link  # TF 확인
```

### Loop closing

로봇이 한 바퀴 돌아 전에 지나간 곳으로 다시 오면, SLAM Toolbox는 지금의 `/scan`과
예전 `/scan`을 비교한다. 같은 장소라고 판단하면 그동안 쌓인 위치 오차를 한 번에
보정한다. 이 기능을 loop closing이라고 한다.

Loop closing이 잘 되면 출발 지점으로 돌아왔을 때 어긋나 있던 벽과 통로가 다시
맞춰진다. 반대로 같은 장소를 지나지 않으면 보정할 기회가 없으므로, 계속 한 방향으로
가는 경로에서는 loop closing이 일어나지 않는다.

현재 설정은 `do_loop_closing: true`라서 기능이 켜져 있다. 벽·기둥·문처럼 구별하기
쉬운 물체가 있는 곳을 천천히 지나고, 시작 지점으로 돌아오는 경로로 주행하면 확인하기
좋다. 긴 복도처럼 비슷한 장면이 계속 반복되거나 빈 공간에서는 같은 장소를 잘못
판단할 수 있다.

<img src="images/loop_closing.png" style="width:500px; height:auto;">

#### Loop closing 확인 방법

- 시작 지점으로 돌아온 뒤 RViz에서 벽이 두 겹으로 보이던 부분이 맞춰지는지 본다.
- `SlamToolboxPlugin`에서 스캔 위치들이 연결된 모습을 확인한다.
- 다시 왔는데도 변화가 없으면 한 바퀴 더 돈다.
- 지도가 갑자기 크게 휘면 반복되는 복도나 비슷한 벽 때문에 잘못 맞춘 것일 수 있다.

## 지도 만들기 시작

```bash
ros2 launch ktl go2_mapping.launch.py rviz:=true
```

<img src="images/slamtoolbox.png" style="width:500px; height:auto;">

매핑 launch는 Go2 bringup, Hesai 드라이버, PointCloud → LaserScan 변환, timestamp
보정, SLAM Toolbox, RViz를 함께 실행한다.

### 실행 뒤 확인

로봇을 움직이기 전에 `/scan`, odom, TF가 정상인지 확인한다.

```bash
ros2 topic hz /scan
ros2 topic echo /go2/odom --once
ros2 run tf2_ros tf2_echo odom base_link
```

`/scan`이 계속 들어오고 `odom → base_link` TF가 출력되면 매핑을 시작할 수 있다.

## 지도를 잘 만들기 위한 주행 방법

- 시작 전에 RViz에서 `/scan`이 벽과 장애물을 안정적으로 표현하는지 확인한다.
- 처음에는 벽·기둥 등 특징이 있는 구역을 지나며 천천히 한 바퀴 돈다.
- 급가속·급회전 중에는 한 프레임 안에서 로봇 자세가 많이 달라져 scan matching이 불안정할 수 있다.
- 같은 장소로 돌아와 loop closing이 가능한 경로를 만든다.
- 지도 품질이 나쁘다고 바로 solver 값을 바꾸지 말고, TF·높이 필터·scan 주기·odom을 먼저 확인한다.

## SlamToolboxPlugin

`go2_mapping.launch.py`로 RViz를 실행하면 `SlamToolboxPlugin` 패널이 함께 열린다.
터미널에서 서비스 명령을 입력하지 않고, 매핑을 멈추거나 지도 상태를 저장·불러올 때
쓰는 도구다.

| 화면 항목 | 하는 일 | 언제 쓰는지 |
|---|---|---|
| `Interactive Mode` | 지도 안의 스캔 위치와 연결을 직접 확인·수정하는 모드 | loop 연결이나 스캔 위치를 직접 살펴볼 때 |
| `Accept New Scans` | 새 `/scan`을 받아 지도에 계속 추가할지 정함 | 체크를 끄면 매핑을 잠시 멈출 수 있음 |
| `Clear Changes` | Interactive Mode에서 바꾼 내용을 취소 | 잘못 움직이거나 연결한 내용을 되돌릴 때 |
| `Save Changes` | Interactive Mode에서 바꾼 내용을 적용 | 수정한 위치·연결을 지도에 반영할 때 |
| `Save Map` | 현재 점유 지도를 저장 | Nav2에서 쓸 지도 이미지를 만들 때 |
| `Serialize Map` | 현재 매핑 작업 상태를 저장 | 나중에 같은 pose graph를 이어서 작업할 때 |
| `Deserialize Map` | 저장한 매핑 작업 상태를 불러옴 | 이전 pose graph를 다시 열 때 |
| `Clear Measurement Queue` | 아직 처리하지 않은 scan을 비움 | scan이 밀렸을 때만 사용 |

일반적인 매핑에서는 `Accept New Scans`를 켜 둔다. 주행을 끝낸 뒤에는 로봇을 멈추고
지도를 저장한다. `Save Map`과 `Serialize Map`은 서로 다른 기능이다. `Save Map`은
Nav2에서 쓰는 점유 지도이고, `Serialize Map`은 SLAM Toolbox가 매핑을 이어서 하기
위해 필요한 작업 기록이다.

`Add Submap`, `Generate Map` 같은 `Merge Map Tool` 항목은 여러 지도를 합칠 때 쓰는
고급 기능이다. 현재처럼 한 대의 Go2로 지도를 만드는 실습에서는 사용하지 않는다.

## 주요 설정값

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

### 지도 품질이 좋지 않을 때

| 현상 | 먼저 확인 | 이후 조정 후보 |
|---|---|---|
| 벽이 두 겹으로 보임 | TF, scan timestamp, odom drift | `minimum_travel_*`, scan matching 범위 |
| 지도가 너무 듬성듬성함 | `throttle_scans`, 이동 속도 | `minimum_travel_distance`, `minimum_travel_heading` 낮춤 |
| CPU 사용량이 높음 | scan 주기, map 해상도 | `throttle_scans`, `minimum_time_interval`, `resolution` |
| loop가 잘 안 닫힘 | 실제로 재방문했는지, scan 품질 | loop 응답 임계값·검색 범위 |
| 잘못된 loop로 지도 휨 | 반복 구조 환경인지, TF | loop 응답 임계값을 높여 후보를 엄격화 |

한 번에 한 종류의 값만 작게 바꾸고, 같은 경로를 다시 주행해 전후 지도를 비교한다.

## Pose graph와 지도 파일 저장

Pose graph는 SLAM의 스캔 위치와 연결 제약을 저장한다. 매핑을 중단하기 전 중간 상태를 저장할 때 사용한다.

```bash
ros2 service call /slam_toolbox/serialize_map \
  slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/home/ktl/ktl_ws/src/ktl/maps/map_practice'}"
```

저장한 pose graph를 지정 위치에서 불러온다. 꼭 맵핑 시작 위치에서 다시 시작해야 한다.

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

## GIMP로 지도 수정하기

지도에서 없애고 싶은 노이즈를 지우거나, 실제로 막힌 곳을 장애물로 표시해야 할 때는
PGM 파일을 수정한다. 이 작업은 Nav2용 점유 지도만 바꾸며, SLAM Toolbox의 pose graph는
바뀌지 않는다.

### 1. 원본 백업

원본 파일을 직접 덮어쓰지 말고, 수정본을 별도 이름으로 만든다.

```bash
cd ~/ktl_ws/src/ktl/maps
cp map_practice.pgm map_practice_edited.pgm
cp map_practice.yaml map_practice_edited.yaml
```

### 2. GIMP에서 PGM 수정

`map_practice_edited.pgm`을 GIMP로 열고 Pencil처럼 경계가 흐려지지 않는 도구를 쓴다.

| 색 | Nav2가 해석하는 의미 | 사용할 때 |
|---|---|---|
| 검정 (`0`) | 장애물 | 벽·출입 금지 구역을 추가할 때 |
| 흰색 (`255`) | 이동 가능한 공간 | 잘못 들어간 장애물을 지울 때 |
| 회색 (`205`) | 알 수 없는 공간 | 관측하지 않은 영역으로 남길 때 |

이미지 크기를 바꾸거나 자르거나 회전하면 지도 좌표가 달라진다. 픽셀 크기를 그대로
유지하고, 안티앨리어싱·블러·흐린 브러시는 사용하지 않는다. 중간 회색이 생기면 Nav2가
장애물인지 빈 공간인지 애매하게 판단할 수 있다.

수정이 끝나면 같은 이름의 `map_practice_edited.pgm`으로 내보낸다. 형식은 8비트
grayscale PGM으로 유지하고, 색상 이미지나 알파 채널을 넣지 않는다.

### 3. YAML 파일 이름 확인

`map_practice_edited.yaml`의 `image:`가 수정한 PGM 파일을 가리키게 바꾼다.

```yaml
image: map_practice_edited.pgm
```

이미지 크기를 바꾸지 않았다면 `resolution`과 `origin`은 원래 값 그대로 둔다.

### 4. Navigation에서 확인

수정한 지도를 열어 벽을 지운 곳과 새로 막은 곳이 의도대로 보이는지 확인한다.

```bash
ros2 launch ktl go2_navigation.launch.py \
  map:=/home/ktl/ktl_ws/src/ktl/maps/map_practice_edited.yaml \
  rviz:=true
```

RViz에서 2D Pose Estimate로 초기 위치를 잡은 뒤, 수정한 구역이 지도와 costmap에
같이 반영되는지 확인한다.
