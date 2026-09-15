# Coordinate Frames

A coordinate frame answers: **where is this point relative to what?**

For LaundryBench, the camera, robot base, and gripper can each describe the same sock differently.

```text
camera frame
    ↓ transform
robot base frame
    ↓ plan target
end-effector frame
```

The practical goal is to convert what the camera sees into coordinates the robot can act on.
