# Imitation Learning

## One-sentence definition

Imitation learning trains a policy to reproduce behavior from demonstrations.

```text
human demonstration
      ↓
observations + actions
      ↓
training dataset
      ↓
policy learns observation -> action
```

## LaundryBench relevance

The SO-101 leader arm can provide demonstrations while the follower records the corresponding robot state/actions and camera observations.

## Important limitation

A policy can copy demonstrated behavior without being generally intelligent. It may fail when the physical situation differs from the demonstrations.
