---
name: node-native-typescript
description: >
  Run TypeScript projects on Node.js 22+ without any build tools or dependencies
  (no tsx, ts-node, deno, or tsc). Uses Node's native --experimental-strip-types.
  Use when setting up or fixing a TS project to run on bare Node, or migrating from tsx/ts-node.
tags: [typescript, node, esm, zero-dependency, native]
triggers:
  - TypeScript project has no package.json or tsconfig
  - Need to run .ts files without installing build tools
  - Cannot find module or does not provide an export named errors with .ts imports
  - Migrating from tsx/ts-node to native Node TypeScript
  - Making TypeScript projects work on Node 22+/24+
---

# Node Native TypeScript (No Build Tools)

Run TypeScript directly on Node.js 22+ using `--experimental-strip-types`. Zero dependencies needed.

## Prerequisites

- Node.js >= 22.0.0 (check: `node --version`)
- Verify support: `node --experimental-strip-types -e "const x: string = 'hi'; console.log(x)"`

## Setup Steps

### 1. Create package.json with ESM

```json
{
  "name": "project-name",
  "version": "0.1.0",
  "type": "module",
  "engines": { "node": ">=22.0.0" },
  "exports": { ".": "./index.ts" },
  "scripts": {
    "test": "node --experimental-strip-types scripts/run-tests.ts"
  }
}
```

### 2. Fix Imports — The Critical Part

Node's type stripping removes all type annotations but does NOT resolve TypeScript-specific module features. These rules are mandatory:

#### Rule A: Separate type imports from value imports

BAD — will crash because IProviderClient is an interface (stripped to nothing):
```typescript
import { LeadOrchestrator, IProviderClient } from './lead-types.ts';
```

GOOD — split type-only and value imports:
```typescript
import type { IProviderClient } from './lead-types.ts';
import { LeadOrchestrator } from './lead-orchestrator.ts';
```

#### Rule B: Use export type for type-only barrel exports

BAD — export * from a types-only module fails:
```typescript
export * from './types.ts';  // Fails if types.ts only has interfaces/types
```

GOOD — explicit type re-exports:
```typescript
export type { MyInterface, MyType, AnotherType } from './types.ts';
export { MyClass } from './implementation.ts';
```

#### Rule C: import type for all pure type/interface imports

```typescript
import type { OperatorRun, TruthSummary } from '../entrypoint/lead-types.ts';
```

### 3. Handle CJS Scripts in ESM Projects

When package.json has "type": "module", ALL .js files are treated as ESM. Scripts using require() will break.

Fix: Rename .js to .cjs for CommonJS scripts:
```bash
mv bin/my-script.js bin/my-script.cjs
```

Update all references (shell scripts, package.json scripts, shebangs).

### 4. Shell Scripts Need the Flag

Always pass --experimental-strip-types when running .ts files:
```bash
node --experimental-strip-types scripts/my-script.ts
```

For shell wrappers:
```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"
node --experimental-strip-types scripts/my-script.ts "$@"
```

## What Works (Surprising)

- `class Foo implements IBar {}` — Node 24 strips implements correctly
- `as const` assertions
- Generic type parameters
- Enum declarations (transformed to objects)
- `import assert from 'node:assert/strict'` (node builtins)

## What Does NOT Work

- `export * from './types-only-module.ts'` for type-only modules
- Mixed value + type imports from type-only modules
- TypeScript namespaces (not stripped)
- const enum (requires compilation, not just stripping)
- Decorators with emitDecoratorMetadata (metadata needs compilation)

## Diagnostic Commands

```bash
# Check if Node supports type stripping
node --experimental-strip-types -e "const x: number = 1; console.log(x)"

# Test barrel exports
node --experimental-strip-types -e "import { MyExport } from './index.ts'; console.log(typeof MyExport);"

# Find problematic imports (non-type imports of interfaces)
grep -rn "^import {" --include="*.ts" | grep -v "import type"
```

## Pitfalls

1. The error message is misleading: "does not provide an export named X" usually means X is a type/interface imported as a value, NOT that the export is missing
2. export * silently fails: It won't error on types-only modules — it just exports nothing, then downstream imports break
3. Don't forget .ts extensions: Node requires explicit .ts extensions in import paths (unlike bundlers)
4. No tsconfig needed: Node ignores tsconfig.json entirely when using strip-types
5. In Hermes, the patch tool may auto-run a TypeScript syntax/lint check that complains "This is not the tsc command you are looking for" when the project has no local typescript package. For native Node strip-types projects, treat that as a tooling false alarm and verify with the real runtime command instead (for example: `node --experimental-strip-types scripts/run-tests.ts`).
