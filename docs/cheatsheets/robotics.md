# Robotics Cheatsheet

- **DOF** — one independent way the robot can move
- **Joint state** — current joint positions/velocities/etc.
- **End effector** — tool at the end of the robot arm, such as a gripper
- **Joint space** — robot described by joint values
- **Cartesian space** — end-effector pose described in physical coordinates
- **Forward kinematics** — joints -> gripper pose
- **Inverse kinematics** — desired gripper pose -> joints
- **Coordinate transform** — convert a point/pose from one frame to another
- **Policy** — maps observations to actions
- **Episode** — one complete attempt at a task
- **Trajectory** — sequence of states/actions over time
- **Observation** — information available to the policy, such as images and robot state
- **Action** — command produced by the policy for the robot
