# Go2 Nav2 설치 매뉴얼

## 1. 패키지 설치

```bash
sudo apt update
sudo apt install -y \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  python3-colcon-common-extensions
```

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
