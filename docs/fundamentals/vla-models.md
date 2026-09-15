# Vision-Language-Action Models

## One-sentence definition

A VLA model conditions on visual observations, language, and robot state to produce robot actions.

```text
camera + instruction + robot state
              ↓
             VLA
              ↓
        robot actions
```

## Why this feels closer to LLMs

Instead of training a completely separate model for every behavior, a pretrained VLA can learn broad manipulation priors and then be adapted to a new robot or task.

## LaundryBench relevance

V1 does not depend on a VLA. The architecture keeps the policy boundary replaceable so we can compare a simpler baseline such as ACT with a pretrained VLA later.
