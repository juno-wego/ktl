# Go2 Nav2 설치 매뉴얼

주행 중 abort가 발생하던 문제를 잡기 위해 Nav2 설정을 교체했다.
아래 순서대로 진행하면 된다.

## 1. 패키지 설치

```bash
source /opt/ros/humble/setup.bash

sudo apt update
sudo apt install -y \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  python3-colcon-common-extensions
```

따로 clone 하거나 빌드할 플러그인은 없다.

## 2. 설정 받기

```bash
cd ~/ktl_ws/src/ktl
git pull
```

## 3. 빌드

```bash
cd ~/ktl_ws

colcon build --symlink-install
source install/setup.bash
```

## 4. 실행

```bash
ros2 launch ktl go2_navigation.launch.py
```

RViz가 뜨면 **2D Pose Estimate**로 로봇의 현재 위치를 먼저 찍어준다.
그 다음 **2D Goal Pose**로 목표를 지정한다.

문제가 생기면 터미널 로그와 함께 알려주세요.
