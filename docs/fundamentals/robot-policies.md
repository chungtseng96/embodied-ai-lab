# Robot Policies

## One-sentence definition

A robot policy maps observations to actions.

```text
observation -> policy -> action
```

For LaundryBench an observation may include camera images and joint state. The action may be a set or sequence of target joint values.

## Important distinction

"Policy" does not imply a narrow model. ACT is a policy, but a generalist VLA can also act as a policy.

## Platform-engineering relevance

The surrounding system still needs dataset lineage, training/adaptation, deployment, evaluation, logging, and rollback regardless of which policy implementation is used.
