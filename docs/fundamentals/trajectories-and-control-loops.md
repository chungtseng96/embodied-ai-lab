# Trajectories and Control Loops

## Trajectory

A trajectory is a sequence of robot states or targets over time.

```text
pose_0 -> pose_1 -> pose_2 -> ...
```

A robot usually does not teleport from one pose to another; it follows a path through intermediate states.

## Control loop

A control loop repeatedly:

```text
observe -> choose action -> execute -> observe again
```

The important robotics difference from one-shot prediction is that each action changes the world and therefore changes the next observation.

## LaundryBench relevance

A grasp error early in the episode can change every later observation. This is why closed-loop physical evaluation matters more than evaluating isolated predictions.
