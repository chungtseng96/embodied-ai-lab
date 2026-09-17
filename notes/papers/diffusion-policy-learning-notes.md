# Diffusion Policy Learning Notes

**Paper:** [Diffusion Policy: Visuomotor Policy Learning via Action Diffusion](https://arxiv.org/abs/2303.04137)  
**Session date:** 2026-09-16

## One-sentence takeaway

Diffusion Policy learns a **conditional distribution over future robot action sequences**. Given the current observation, it starts from a noisy candidate action trajectory and iteratively denoises it into a coherent action chunk, executes part of that chunk, observes again, and replans.

---

## 1. Policy = observation → action sequence

At the highest level:

```text
camera images + current robot state
                ↓
        Diffusion Policy
                ↓
       future action sequence
```

Like ACT, the output is not just one isolated action. The policy predicts a sequence of future actions so that movement is temporally coherent rather than myopic.

---

## 2. DDPM is the diffusion framework, not a standalone neural-network architecture

A useful mental model:

```text
DDPM / diffusion process
├── defines how noise is added during training
├── defines the iterative denoising process at inference
└── uses a learned neural network to predict how to denoise
```

The neural network is one component **inside** the diffusion-policy system.

In Diffusion Policy, that network can be implemented with different architectures, including a temporal CNN or a Transformer.

---

## 3. Training: learn to remove noise from demonstrated action sequences

A demonstration gives us a clean action trajectory.

```text
clean demonstrated action sequence A
              ↓
     add Gaussian noise
              ↓
       noisy sequence A_k
              ↓
noise predictor(A_k, observation, diffusion step k)
              ↓
      predicted noise
              ↓
compare with actual noise that was added
```

The model is trained to predict the noise added to the demonstrated action sequence.

The observation conditions the denoising process, so the question is not simply:

> "What does a valid action trajectory look like?"

It is:

> "Given what the robot currently sees and its current state, what action trajectory is appropriate?"

---

## 4. Inference: start from random actions and iteratively denoise

At deployment there is no ground-truth demonstrated trajectory available.

Instead:

```text
random Gaussian action sequence
              ↓
      denoising step K
              ↓
      denoising step K-1
              ↓
             ...
              ↓
      denoising step 1
              ↓
coherent candidate action sequence
```

At every denoising step, the model uses the current observation as conditioning information.

The number of denoising iterations is generally configured ahead of time rather than running until an arbitrary confidence threshold is reached. More steps can improve refinement but cost more inference time.

---

## 5. Why diffusion helps with multimodal behavior

Robotic tasks often have multiple valid solutions.

Example:

```text
object blocks direct path

valid trajectory A → go around left
valid trajectory B → go around right
```

A simple regression policy can average those solutions and produce something like:

```text
left + right average → go straight into obstacle
```

Diffusion instead models a distribution over valid trajectories. Because sampling begins from noise, a rollout can settle into one coherent mode rather than averaging incompatible modes together.

This is one of the core reasons diffusion is attractive for robot behavior.

---

## 6. Action-sequence prediction = temporal consistency

Instead of:

```text
observation_t → action_t
observation_t+1 → action_t+1
observation_t+2 → action_t+2
```

Diffusion Policy predicts:

```text
observation_t → [action_t, action_t+1, ..., action_t+H]
```

This allows the model to reason about a short trajectory jointly.

Benefits:

- smoother and more coherent motion
- less myopic planning
- less chance of rapidly switching between incompatible behavior modes
- better handling of short-horizon temporal structure

This is conceptually similar to why action chunking is important in ACT.

---

## 7. Closed-loop action-sequence execution

The robot does **not** blindly execute an entire long predicted trajectory and ignore new information.

A better mental model is receding-horizon control:

```text
observe
  ↓
predict action sequence
  ↓
execute first few actions
  ↓
observe again
  ↓
predict a new sequence
  ↓
repeat
```

This balances:

```text
sequence prediction → temporal consistency / planning
re-observation       → responsiveness / correction
```

This is a major practical idea to carry forward.

---

## 8. Section 3.1: CNN vs. Transformer noise-prediction networks

The paper evaluates two architectures for the denoising/noise-prediction network.

### Temporal CNN

Good default for many manipulation tasks.

Advantages:

- stable training
- efficient
- strong performance on many tasks

Potential limitation:

- convolutional inductive bias can smooth rapidly changing action trajectories

### Transformer

Useful when the policy needs to model sharper or more complex temporal relationships across the predicted sequence.

Advantages:

- flexible long-range dependencies
- can preserve abrupt temporal changes better

Tradeoff:

- typically more difficult to train and tune

### Takeaway

The important lesson is **not** "Transformers are always better." The diffusion framework is independent of the specific noise-prediction architecture. CNN and Transformer are interchangeable architectural choices inside the larger policy.

---

## 9. Section 3.2: visual encoder

Camera images need to be converted into compact visual features before they condition the policy.

Conceptually:

```text
camera image(s)
      ↓
visual encoder / ResNet
      ↓
visual features
      ↓
combine with robot state
      ↓
condition diffusion network
```

The paper uses a ResNet-based visual encoder with robotics-specific modifications such as spatial feature extraction and normalization choices.

For multiple cameras, the views are encoded into features and combined into the observation representation. Implementations may use separate encoders or shared weights depending on configuration; the important abstraction is that multiple camera views become a single policy observation.

This is directly analogous to ACT's use of visual encoders before its Transformer policy.

---

## 10. ACT vs. Diffusion Policy

The high-level system is surprisingly similar:

```text
             ACT                         Diffusion Policy
             ---                         ----------------
images + joint state                images + joint state
        ↓                                   ↓
   visual encoder                       visual encoder
        ↓                                   ↓
 Transformer policy                 diffusion network
        ↓                                   ↓
action chunk                        action sequence
```

The major difference is **how the action distribution is modeled**.

### ACT

```text
observation → Transformer/CVAE → action chunk
```

### Diffusion Policy

```text
observation + noisy trajectory
            ↓
iterative conditional denoising
            ↓
action sequence
```

Both reinforce the same broader lesson: modern manipulation policies frequently predict chunks/sequences rather than isolated actions.

---

## 11. What matters for our SO-101 project

We should not rebuild LeRobot's policy implementations from scratch just to prove that we can.

LeRobot can handle much of the robot-specific and policy-specific machinery:

```text
SO-101 + cameras
       ↓
LeRobot robot / dataset abstractions
       ↓
ACT / Diffusion / future policy backend
       ↓
robot actions
```

Our engineering value should sit primarily around that policy layer.

```text
                      ┌──────── ACT adapter
camera + joints ─────→│
                      ├──────── Diffusion adapter
                      │
                      └──────── future VLA adapter
                               ↓
                        standard action output
                               ↓
                   evaluator / logger / rollout system
```

---

## 12. Policy abstraction to build

Do **not** try to create a giant abstraction that predicts every future robotics framework.

Create one clean boundary:

```python
class Policy:
    def predict(self, observation) -> ActionSequence:
        ...
```

Where a standardized observation contains things like:

```text
Observation
├── camera frames
├── joint positions
├── timestamps
└── optional task metadata
```

And the output contains:

```text
ActionSequence
├── joint targets / robot commands
├── horizon
└── optional policy metadata
```

Then adapters isolate framework-specific behavior:

```text
ACTPolicyAdapter
DiffusionPolicyAdapter
FutureVLAPolicyAdapter
```

The evaluator should not need to care which policy produced the actions.

---

## 13. Platform layer we should build

The portfolio project becomes more compelling if the policy is treated as one interchangeable component in a larger robotics experimentation system.

```text
                Robotics Experiment Platform

Data collection ─┐
Dataset versions ├──→ Training ───→ Policy artifact
Metadata         ┘                     ↓
                                  Rollout runner
                                       ↓
                         ┌─────────────┼─────────────┐
                         ↓             ↓             ↓
                    success rate   failure logs   video/telemetry
                         └─────────────┼─────────────┘
                                       ↓
                               compare experiments
```

High-value platform features:

- dataset/version tracking
- policy/config tracking
- rollout logging
- video + robot-state synchronization
- success/failure labels
- failure taxonomy
- reproducible evaluation runs
- policy comparison across the same benchmark
- model-agnostic metrics

Start with ACT. Add Diffusion Policy as the second backend. If the same evaluation system works for both, that proves the abstraction is real rather than theoretical.

---

## 14. Simulation vs. real-world demonstrations

Robotics data collection is genuinely expensive, but real robot data has not disappeared.

Modern robotics teams mix several sources:

```text
real teleoperation demonstrations
simulation / synthetic data
pretrained robotics datasets
policy rollouts
human corrections / interventions
```

For our project, the sensible sequence is:

```text
1. Get pipeline working in simulation
2. Use a simple rigid-object pick-and-place task
3. Validate logging + evaluation + policy adapters
4. Move to the physical SO-101
5. Collect a small clean real-world dataset
6. Train/evaluate ACT
7. Add Diffusion Policy
8. Progress toward laundry sorting
```

Laundry is a difficult first simulation benchmark because cloth dynamics are substantially harder than rigid-body manipulation.

Use rigid objects first to validate the platform.

---

## 15. Simulation tools to investigate

### LeIsaac + Isaac Lab

Especially relevant to this project because LeIsaac integrates SO-101 simulation with LeRobot workflows.

It supports simulated SO-101 environments, teleoperation, data conversion, and LeRobot-compatible training workflows.

Useful starting point:

- https://github.com/LightwheelAI/leisaac
- https://huggingface.co/docs/lerobot/envhub_leisaac

### MuJoCo

A mature, lightweight physics simulator that is useful when we want a simpler local environment or more control over our own task implementation.

The important principle is:

> Use Claude/Codex to generate environment code **inside an established simulator** rather than asking an LLM to invent a physics simulator from scratch.

---

## 16. Are ACT and Diffusion Policy too primitive?

No. They are better thought of as foundational manipulation-policy architectures.

The frontier is moving toward larger vision-language-action models, flow matching, diffusion transformers, and more generalist robot policies. But many of the ideas we are learning survive:

```text
action chunking
multimodal action distributions
visual conditioning
closed-loop replanning
sequence prediction
data quality
policy evaluation
```

The portfolio goal is not to prove that a company uses the exact vanilla ACT or Diffusion Policy repository in production.

The goal is to demonstrate that we understand the architecture of a modern robotics learning system and can build the software platform required to train, evaluate, compare, and deploy multiple policies.

---

## Final mental model

```text
                    TRAINING

human/sim demonstrations
         ↓
images + joint states + action sequences
         ↓
      LeRobot dataset
         ↓
  ACT / Diffusion Policy
         ↓
      policy artifact


                    DEPLOYMENT

cameras + SO-101 joint state
           ↓
      Policy Adapter
           ↓
     action sequence
           ↓
 execute short chunk
           ↓
        observe
           ↓
         repeat


                     PLATFORM

        same dataset / benchmark
                   ↓
        ┌──────────┴──────────┐
        ↓                     ↓
      ACT                 Diffusion
        ↓                     ↓
        └──────────┬──────────┘
                   ↓
         same rollout evaluator
                   ↓
      logs + video + metrics
                   ↓
          compare / iterate
```

## What I should be able to explain after this paper

1. What a robotics policy is.
2. Why Diffusion Policy predicts action sequences instead of single actions.
3. Why multimodal action distributions matter.
4. What DDPM contributes versus what the neural network contributes.
5. What happens during diffusion training.
6. What happens during inference.
7. Why the policy runs in a closed loop rather than executing one long trajectory blindly.
8. The role of CNN/Transformer denoising architectures.
9. The role of the visual encoder.
10. How ACT and Diffusion Policy fit behind the same platform abstraction.
11. Why our portfolio value should focus on data, evaluation, logging, reproducibility, and policy interchangeability.
12. Why simulation is useful but does not eliminate the need for real robot data.

At this point, this is enough conceptual depth to move on from the paper and begin implementing the end-to-end robotics software loop.