# End-Effector Pose

## One-sentence definition

The **pose** of the end effector describes both **where the gripper is** and **which way it is pointing**.

```text
pose = position + orientation
     = [x, y, z] + [roll, pitch, yaw]   # one common representation
```

## LaundryBench mental model

It is not enough for the gripper to reach the sock's location. The gripper may also need the right orientation to grasp it.

```text
same XYZ, wrong orientation  -> poor grasp
same XYZ, right orientation  -> usable grasp
```

## Why it matters

This explains why Cartesian space is usually more than just x/y/z and why manipulation gets harder than simply "move the hand to the object."
