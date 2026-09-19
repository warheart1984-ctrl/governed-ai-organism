# Governed AI Organism Constitutional Engineering

An experimental constitutional engineering framework for a governed AI organism.

This repository contains the constitutional source documents, the Constitutional Dependency Graph seed, the Constitutional Evolution Protocol tooling, and a small standard-library implementation of the Constitutional Observability Protocol.

## What is here

- `CEP-1` through `CEP-4`: constitutional evolution, boundary classification, observability, and dependency-graph specifications.
- `CS-11` and `CS-12`: ethics/alignment and audit/accountability specifications.
- `cep3/`: the observability substrate, append-only event ledger, replay harness, and EGL-1 equivalence harness.
- `drill/`: adversarial amendment drill materials and execution records.
- `ratify.py`: deterministic corpus manifest, verification, and sealing tool.
- `ratification_manifest.json` and `ratification_record.json`: the current corpus root and signed sealing record.

## Current status

The ratified corpus root is:

`42e1bbacb29f65828fed456f03bbd9171bca035d49bd01d2d19c494f872158db`

The implementation is research-grade and intentionally incomplete. The current drill demonstrates working Stage 1, Stage 3, and Stage 4 mechanisms, while also recording honest rejection conditions including insufficient demand evidence, missing historical quorum behavior, and lack of independently authored EGL-1 implementations.

This repository is not a claim that an autonomous AI organism exists, nor that the framework is production-safe. It is an auditable experimental substrate and specification set.

## Verification

From the repository root:

```powershell
python ratify.py verify
python cep3/constitution_observability.py verify
```

The HMAC signing key is intentionally not part of this repository. Keep local signing material outside the checkout.

## Independent EGL-1 implementations

The EGL-1 harness evaluates implementations against the observable specification and equivalence vectors. Independent implementations are welcome. Do not copy either drill implementation when testing provenance independence; implement the observable rule independently and register it through the harness.

## Contributing

The most useful contribution is an independently authored EGL-1 implementation.
Implement the observable specification without copying the existing house or
drill implementations, then register it with:

```powershell
python cep3/egl1_harness.py register --module path/to/implementation.py --author "Your Name" --origin external
python cep3/egl1_harness.py run --candidate AMEND-2026-002
```

Include the implementation strategy, author identity, provenance, and exact
verification command. Do not submit keys, credentials, local paths, or caches.
Changes to constitutional semantics require rationale and test vectors.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
