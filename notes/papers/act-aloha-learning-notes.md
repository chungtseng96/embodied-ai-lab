# ACT / ALOHA Learning Notes

**Paper:** [Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware](https://arxiv.org/abs/2304.13705)  
**Algorithm:** ACT — Action Chunking with Transformers

## One-sentence takeaway

ACT learns an end-to-end mapping from **camera images + current robot joint state** to a **chunk of future joint targets**. Its main idea is that predicting a sequence of actions together is much easier and more reliable for long-horizon imitation learning than predicting one tiny action at a time.

---

## 1. Teleoperation = data collection

Teleoperation is not the AI model. It is the mechanism used to collect demonstrations from a human operator.

```text
Human moves leader arms
        ↓
Follower robot copies movement
        ↓
Record cameras + joint states + actions
        ↓
Imitation-learning dataset
```

The demonstrations become supervised training examples for the policy.

---

## 2. Policy = trained model that chooses robot actions

A robotics **policy** is a model/function that maps observations to actions.

```text
observation → policy → action
```

For ACT:

```text
camera images + current joint state
              ↓
          ACT policy
              ↓
     next K joint targets
```

Calling it a *model* describes what it is. Calling it a *policy* describes the role it plays in controlling the robot.

---

## 3. Action chunking is the core idea

A standard one-step imitation policy predicts:

```text
state_t → action_t
state_t+1 → action_t+1
state_t+2 → action_t+2
...
```

Small errors can compound over a long task.

ACT instead predicts a chunk:

```text
state_t → [action_t, action_t+1, ..., action_t+K]
```

This shortens the effective decision horizon and lets the model learn temporally coherent movement patterns.

### Main result to remember

The ablations show that **action chunking is the largest contributor to ACT's performance gains**. Temporal ensembling helps too, but action chunking is the main design choice.

---

## 4. Temporal ensembling = blend overlapping predictions

ACT can predict a new action chunk as new observations arrive. Different chunks therefore make overlapping predictions for the same future timestep.

Example for action at timestep 3:

```text
prediction made at t=1 ─┐
prediction made at t=2 ─┼─→ blend → execute action at t=3
prediction made at t=3 ─┘
```

The important point is that we are **not averaging action 1, action 2, and action 3 together**. We are blending multiple predictions of the **same future action**.

This makes execution smoother and reduces abrupt jumps between chunks.

---

## 5. Markovian vs. history-dependent behavior

A Markovian policy assumes the current state contains everything needed to decide what happens next.

```text
current state → next action
```

Human demonstrations can contain short-term temporal variation such as pauses, hesitation, re-grasps, or other sequencing effects that are not fully captured by one snapshot.

ACT still predicts from the current observation, but action chunking captures short temporal structure. Temporal ensembling also introduces dependence on predictions made at previous timesteps.

---

## 6. CVAE = model demonstration variability

ACT uses a **Conditional Variational Autoencoder (CVAE)** during training.

The idea is that there can be more than one valid way for a human to perform the same successful task.

```text
same task
├── slightly faster trajectory
├── slightly slower trajectory
├── small pause
├── different grasp angle
└── small path variation
```

The CVAE gives the model a way to represent that variation rather than pretending there is exactly one correct trajectory.

### Encoder vs. decoder

```text
TRAINING

human demonstrated action sequence
              ↓
           encoder
              ↓
         latent code Z
              ↓
images + current joints + Z
              ↓
           decoder
              ↓
      predicted action chunk
```

The **encoder only exists during training**. It summarizes demo-specific variation into the latent variable `Z`.

The **decoder is the part retained as the policy at deployment**.

At inference time:

```text
encoder: removed
Z: fixed to 0

images + current joints + Z=0
              ↓
           decoder
              ↓
        next K actions
```

---

## 7. What is the style variable Z?

`Z` is a learned latent representation of how a particular demonstration was carried out.

A useful intuition is "style," such as:

- slightly faster vs. slower
- smooth vs. hesitant
- small trajectory differences
- pause/re-grasp patterns

It is **not** a human-readable label like `fast` or `slow`; it is a learned numerical vector.

---

## 8. What does beta (β) do?

`β` is a CVAE hyperparameter controlling how strongly the latent variable `Z` is regularized.

```text
smaller β
→ Z can carry more demo-specific information

larger β
→ stronger pressure for Z to remain simple / close to the prior
```

`β` does **not** directly mean "more precise" or "less precise," and it does not decide whether a demonstration is valid.

It is a normal ML hyperparameter that should be tuned empirically based on generalization and rollout performance.

---

## 9. ACT learns perception-to-action without explicit kinematics

This was one of the most important conceptual takeaways.

A classical robotics stack may look like:

```text
camera
  ↓
estimate object XYZ
  ↓
choose desired end-effector pose
  ↓
solve inverse kinematics
  ↓
joint targets
```

ACT skips the explicit inverse-kinematics solve inside the learned policy:

```text
camera images + current joints
              ↓
          neural network
              ↓
       future joint targets
```

The robot still physically obeys kinematics. ACT simply learns the mapping **implicitly from demonstration data** rather than explicitly calculating it with geometry equations during inference.

---

## 10. Vision features vs. kinematics

ACT first processes images with a **ResNet-18 backbone**.

The ResNet converts RGB images into learned visual feature maps. Because Transformers need to know where a feature appeared in the image, ACT adds **2D sinusoidal positional embeddings**.

Important distinction:

```text
2D image positional embedding
= where did this feature appear in the image?

robot kinematics
= how do joint positions map to the robot's physical pose in 3D?
```

The positional embeddings preserve image-space structure. They are not an explicit kinematics solver.

---

## 11. Transformer architecture mental model

```text
Images ──→ ResNet ───────┐
                         │
Current joint state ─────┼──→ Transformer
                         │
Z ───────────────────────┘
                              ↓
                           K × 512
                              ↓
                             MLP
                              ↓
                           K × 14
```

The Transformer's internal representation uses 512-dimensional features.

The final MLP projects those features down to robot action space.

### What is the 14-D vector?

ALOHA has two arms. Each contributes 7 controllable values (arm joints + gripper), so one complete action is 14-dimensional.

```text
7 values for left arm
+
7 values for right arm
=
14-D action
```

Therefore:

```text
K × 14
```

means **K future timesteps**, each containing a complete target joint configuration for both arms.

These are **joint-space targets**, not Cartesian XYZ end-effector coordinates.

---

## 12. BERT-like encoder does not mean language

The paper describes the CVAE encoder as **BERT-like**.

That means ACT borrows a Transformer encoder architecture similar to BERT. It does not mean the robot is processing language or words.

The encoder receives sequences of robot state/action numbers and compresses demo-specific variation into `Z`.

---

## 13. Cross-attention

The decoder needs to generate future actions while conditioning on the encoded current situation.

Cross-attention can be thought of as:

> While predicting a future action, look back at the representation of the current scene/state and determine which parts matter.

So at a high level:

```text
current situation representation
           ↓
     cross-attention
           ↓
future action representation
```

---

## 14. Linear layers and MLPs

The linear layers mainly act as learned dimensional adapters.

```text
robot-sized vectors
       ↕
512-D Transformer space
```

An MLP is simply multiple linear layers with nonlinear activations between them.

In ACT, the final MLP converts each 512-D Transformer output into the 14 joint-target values the robot needs.

This is learned representation conversion, **not a kinematics calculation**.

---

## 15. L1 reconstruction loss

ACT uses **L1 loss** for action reconstruction.

```text
L1 = |predicted joint target - demonstrated joint target|
```

This is a standard ML loss function. It measures how far the predicted joint targets are from the human demonstration during training.

It is a **training objective**, not the final measure of whether the robot succeeds in the real world.

---

## 16. End-to-end mental model

```text
Human operator
      │
      │ teleoperation
      ▼
Demonstrations
(images + joints + actions)
      │
      ▼
CVAE + Transformer training
      │
      ▼
ACT policy
      │
      ├── camera images
      ├── current joint state
      └── Z = 0 at deployment
      │
      ▼
Next K joint targets
      │
      ▼
Temporal ensemble
      │
      ▼
Robot movement
```

## What to retain from the paper

1. **Teleoperation is the data-generation mechanism.**
2. **The trained neural network becomes the policy.**
3. **Action chunking is the main innovation and performance driver.**
4. **Temporal ensembling blends overlapping predictions for smoother execution.**
5. **The CVAE handles variability/noise in human demonstrations.**
6. **The encoder is training-only; the decoder becomes the deployed policy.**
7. **Z represents demo-specific latent variation; β regularizes how much information Z carries.**
8. **ACT predicts future joint targets directly rather than explicitly solving inverse kinematics.**
9. **ResNet handles visual feature extraction; positional embeddings preserve where visual features appeared in the image.**
10. **The Transformer learns the mapping from perception + current robot state to future actions.**

## Relevance to this lab

For the SO-101 laundry-sorting benchmark, the analogous workflow will be:

```text
teleoperate SO-101
      ↓
record laundry-sorting demonstrations
      ↓
train imitation policy
      ↓
observation → predicted action chunk
      ↓
run autonomous rollouts
      ↓
log failures + evaluate success rate
      ↓
improve data / policy / system
```

That makes ACT a useful baseline for understanding the full **data → training → policy → rollout → evaluation** loop that this repository is intended to explore.
