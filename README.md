# Duck Chess AI 🦆

A comprehensive Duck Chess engine and user interface developed as a Computer Science final project.

## Overview
Duck Chess is a strategic variant where a "duck" piece acts as a dynamic obstacle. This project features a full game engine, a graphical user interface, and an AI agent trained via Reinforcement Learning.

## Core Features
*	**Engine (Pure Python):** High-performance game logic for move generation and duck placement.
*	**Variant Logic:** Full implementation of Duck Chess rules (Capture the King, Blocking Mechanics).
*	**Graphical UI:** Interactive board rendering with real-time move validation and state updates.

## AI & Reinforcement Learning
The AI is developed using **Stable Baselines3** to master the unique positioning strategies of Duck Chess.

### Training Progress
1.	**Environment Design:** Developed a custom environment compatible with RL frameworks.
2.	**State Representation:** Formulated multi-layered feature maps to represent board occupancy and duck position.
3.	**Action Masking:** Integrated strict action masks to ensure valid move selection during training.
4.	**Reward Shaping:** Designed and refined reward functions to optimize piece coordination and defensive duck placement.
5.	**Baseline Training:** Completed initial training iterations to establish a performance foundation.

## Tech Stack
*	**Language:** Python
*	**AI Framework:** Stable Baselines3
*	**Libraries:** [Add specific libraries like NumPy, Pygame, etc., if applicable]
