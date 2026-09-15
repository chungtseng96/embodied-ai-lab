# Joint Space vs Cartesian Space

## One-sentence definitions

**Joint space** describes the robot by the position of each joint.

**Cartesian space** describes where the end effector is in the physical world using position and orientation.

## Mental model

```text
joint space                  cartesian space
[base, shoulder, ...]  -->   [x, y, z, roll, pitch, yaw]
```

## Why this matters for SO-101

The robot motors are ultimately commanded through joint values, while higher-level tasks are often easier to reason about as gripper positions in space.

## Related concepts

- Forward kinematics: joint values -> end-effector pose
- Inverse kinematics: desired end-effector pose -> joint values
