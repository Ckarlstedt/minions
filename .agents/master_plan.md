# MASTER PLAN --- GRU & Minions

> This document is a design brief, **not** a specification.
>
> The purpose is to describe the problem space, desired outcomes,
> constraints and guiding principles while intentionally leaving room
> for architectural exploration. If a better solution exists than the
> ideas presented here, prefer the better solution and document the
> reasoning.

# Mission

Design and build a system that allows frontier reasoning models (Claude,
GPT, Gemini, etc.) to spend **dramatically fewer tokens** on information
gathering while preserving---or improving---the quality and
trustworthiness of the information they receive.

The implementation should optimize for engineering quality,
extensibility and correctness over implementation speed.

# Background

Today's strongest coding models are excellent at reasoning but expensive
because they repeatedly consume repository context, logs, terminal
output and metadata before they can solve a problem.

Smaller local models are generally not competitive for software
engineering itself, but they are capable of performing constrained
investigation tasks.

The opportunity is therefore **not** replacing frontier models.

The opportunity is separating **investigation** from **reasoning**.

# High-Level Vision

GRU is the primary reasoning agent.

Minions are investigation agents.

GRU should delegate investigation work.

Minions should gather information, filter irrelevant context, leverage
deterministic tooling whenever possible, and return compact
evidence-backed reports.

GRU remains responsible for reasoning, coding and editing.

# Guiding Principles

-   Reasoning is expensive; investigation is comparatively cheap.
-   Prefer deterministic tooling over probabilistic reasoning whenever
    possible.
-   Never optimize for "using an LLM"; optimize for solving the problem.
-   Architecture should emerge from the problem rather than assumptions.
-   Trustworthiness is more important than compression.
-   Every important design decision should be documented.

# Core Responsibilities

## GRU

-   Planning
-   Architecture
-   Reasoning
-   Debugging
-   Editing files
-   Final decisions
-   Validation of findings when needed

## Minions

-   Repository investigation
-   Search
-   Git analysis
-   Dependency analysis
-   Log inspection
-   Tool orchestration
-   Evidence collection
-   Context compression

Minions are **not** autonomous coding agents.

# Open Architectural Problem

Do not assume MCP is the correct solution.

Evaluate the appropriate abstraction.

Possible integrations include (non-exhaustive):

-   MCP
-   HTTP
-   gRPC
-   stdio
-   background daemon
-   plugin architecture
-   another design entirely

Likewise, determine the correct execution abstraction:

-   commands
-   tasks
-   workflows
-   pipelines
-   execution graphs
-   planners
-   another abstraction

Avoid over-fragmenting investigations if doing so loses semantic
context.

# Trust

The returned information should maximize confidence.

Investigate techniques such as:

-   structured outputs
-   references
-   source locations
-   confidence estimates
-   deterministic extraction
-   validation pipelines

Hallucinations should be minimized through engineering rather than
prompting alone.

# Permissions

Investigation components must operate read-only.

No file modifications.

No commits.

No branch manipulation.

No repository mutations.

Only GRU edits the project.

# Extensibility

Providers and models must be interchangeable.

Initial implementation target:

-   Provider: MLX Server
-   Model: gpt-oss-20b-MXFP4-Q8

Do not tightly couple the architecture to this choice.

# Initial Project State

Assume the repository is empty.

Bootstrap everything required.

Available local tooling:

-   pyenv
-   Python 3.14.6
-   pnpm
-   nvm
-   Homebrew
-   pi
-   wezTerm with tmux (partially configured)

Assume these are correctly installed.

# Documentation Strategy

Documentation is a first-class deliverable.

Create early:

-   README.md
-   AGENTS.md
-   ARCHITECTURE.md
-   DEVELOPMENT.md

Introduce additional documentation whenever it improves maintainability.

# Working Memory

Maintain a `.agents/` directory throughout development.

Continuously document:

-   plans
-   decisions
-   architecture discussions
-   trade-offs
-   findings
-   assumptions
-   future ideas
-   open questions
-   progress

Treat `.agents/` as persistent engineering memory.

# Tooling

Evaluate deterministic tools before relying on LLM reasoning.

Examples include:

-   Graphifyy
-   AST parsers
-   Language Server Protocols
-   symbol indexing
-   dependency graphs
-   repository metadata extraction
-   semantic indexing

These are examples only.

# Engineering Requirements

Prioritize:

-   SOLID
-   Clean Architecture
-   modularity
-   provider abstraction
-   model abstraction
-   dependency inversion
-   comprehensive tests
-   maintainable interfaces
-   structured logging

# Success Criteria

The project should demonstrate measurable reductions in:

-   prompt tokens
-   completion tokens
-   unnecessary repository context

while maintaining or improving:

-   correctness
-   debugging quality
-   engineering quality
-   developer experience
-   trustworthiness

# Instructions to the Implementing Agent

Think before implementing.

Challenge every assumption in this document.

If you discover a cleaner abstraction, adopt it and document why.

When making architectural decisions:

1.  Describe the problem.
2.  Explain alternatives considered.
3.  Explain why one approach was selected.
4.  Document drawbacks.
5.  Keep the design easy to evolve.

The goal is not to faithfully implement this document.

The goal is to build the best possible system for the problem being
solved.
