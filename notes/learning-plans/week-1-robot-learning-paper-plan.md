# Week 1 Robot Learning Paper Plan

Goal: build a strong enough mental model of modern robot learning to understand what is happening when working with the SO-101, without trying to master the entire literature before touching hardware.

The priority is **depth over volume**. For each paper, the target is to be able to answer:

1. What problem are they fixing?
2. What goes into the model?
3. What comes out?
4. How is it trained?
5. What is the novel trick?

---

## Reading order

### ✅ 1. ACT / ALOHA — completed

**Paper:** *Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware*

- Paper: https://arxiv.org/abs/2304.13705
- Notes: `notes/papers/act-aloha-learning-notes.md`

Why it matters:
- Foundation for imitation learning
- Action chunking
- Temporal ensembling
- CVAE-based handling of noisy / variable human demonstrations
- End-to-end mapping from vision + robot state to future joint targets

Key mental model:

```text
camera + joint state
       ↓
    policy
       ↓
K × joint targets
       ↓
temporal ensemble
       ↓
physical motion
```

---

### 2. Diffusion Policy — deep read

**Paper:** *Diffusion Policy: Visuomotor Policy Learning via Action Diffusion*

- PDF: https://arxiv.org/pdf/2303.04137

Why it matters:
- Introduces another major way to generate continuous robot actions
- Uses diffusion to model action trajectories
- Introduces the intuition behind multimodal action distributions
- Useful contrast against ACT
- Important concept: receding-horizon control

Target takeaway:

```text
observation
   ↓
diffusion policy
   ↓
future action sequence
   ↓
execute part of sequence
   ↓
observe again
```

Focus on understanding **why generating a trajectory can be better than predicting a single next action**.

---

### 3. RT-2 — deep-ish read

**Paper:** *RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control*

- PDF: https://arxiv.org/pdf/2307.15818

Why it matters:
- Core conceptual jump from task-specific policies to **Vision-Language-Action (VLA)** models
- Connects pretrained vision-language knowledge to robot control
- Helps bridge existing LLM / AI knowledge into robotics

Target mental model:

```text
vision + language instruction
           ↓
          VLA
           ↓
      robot actions
```

Key question:
> What knowledge can come from large-scale vision-language pretraining, and what still needs robot demonstration data?

---

### 4. SmolVLA — deep-ish read

**Paper:** *SmolVLA: A Vision-Language-Action Model for Affordable and Efficient Robotics*

- PDF: https://arxiv.org/pdf/2506.01844

Why it matters:
- Very practical follow-up to the VLA idea
- Relevant to affordable hardware and the ecosystem around SO-101 / LeRobot-style workflows
- Useful for understanding action chunking in a more modern VLA context
- Introduces practical inference / serving ideas such as asynchronous execution

Target takeaway:

```text
small VLA
  + affordable robot data
  + efficient inference
        ↓
practical embodied AI system
```

Focus especially on:
- Data standardization
- Observation / action representation
- Asynchronous inference
- Action queues / policy serving

---

### 5. DAgger — skim only

**Paper:** *A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning*

- Paper: https://proceedings.mlr.press/v15/ross11a.html

Why it matters:
- Explains a core imitation-learning failure mode
- A model trained only on expert demonstrations can drift into states that were never present in the training data
- Once it reaches those unfamiliar states, errors can compound

Target takeaway:

```text
expert demonstrations
        ↓
      policy
        ↓
small error
        ↓
unseen state
        ↓
bigger error
        ↓
compounding failure
```

DAgger's core idea:
> Let the learned policy visit states, then ask the expert what should have been done there and add those examples back into training.

A 20–30 minute skim is enough for now.

---

# Save for next week

These are important, but not required before starting hands-on SO-101 work.

## π₀

**Paper:** *π₀: A Vision-Language-Action Flow Model for General Robot Control*

- PDF: https://arxiv.org/pdf/2410.24164

Why later:
- Modern VLA architecture
- Highly relevant to manipulation
- Includes laundry-related tasks, making it especially relevant to the eventual laundry benchmark
- Easier to understand after RT-2 and SmolVLA

---

## Open X-Embodiment / RT-X

**Paper:** *Open X-Embodiment: Robotic Learning Datasets and RT-X Models*

- PDF: https://arxiv.org/pdf/2310.08864

Why later:
- Important for understanding robot data at scale
- Cross-robot datasets
- Shared data formats
- Generalization across embodiments
- Strong connection to AI / ML platform engineering

This is especially relevant to the long-term career direction, but less necessary before first SO-101 experiments.

---

## OpenVLA

**Paper:** *OpenVLA: An Open-Source Vision-Language-Action Model*

- PDF: https://arxiv.org/pdf/2406.09246

Why later:
- Open-source VLA implementation
- Useful for fine-tuning, deployment, and practical model adaptation
- Will make more sense after understanding RT-2 and SmolVLA

---

# Week 1 target

The goal by the end of the week is **not** to finish every paper.

```text
ACT ✅
 │
 ▼
Diffusion Policy
 │
 ├──────────────► DAgger (skim)
 │
 ▼
RT-2
 │
 ▼
SmolVLA
 │
 ▼
SO-101 hands-on work
```

If ACT + Diffusion Policy + RT-2 + SmolVLA are understood at a meaningful level, that is a very productive first robotics-learning week.

After that, stop reading temporarily and start working with the hardware. The physical robot should make many of these abstractions much easier to internalize.

---

# Reading rule

Do **not** optimize for paper count.

Avoid:

```text
2 papers/day
→ recognize lots of terminology
→ retain very little architecture
```

Prefer:

```text
1 paper
→ understand the problem
→ understand inputs / outputs
→ understand training
→ understand the key architectural idea
→ connect it to the SO-101
```

The standard to aim for is the same level of understanding reached with ACT: enough to explain the system in plain English and reason about why each major component exists.
