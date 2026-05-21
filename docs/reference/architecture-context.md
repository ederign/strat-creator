# Architecture Context

The strategy pipeline uses real platform architecture data to ground strategies in reality.

## How It Works

Architecture context is fetched from [opendatahub-io/architecture-context](https://github.com/opendatahub-io/architecture-context) into `.context/architecture-context/` via sparse checkout. It includes:

- **Component documentation**: Boundaries, APIs, dependencies for each RHOAI component
- **Dependency maps**: How components relate to each other
- **Overlays**: Cross-strategy patches that update facts between regeneration cycles

### Fetching

```bash
# From remote (default)
bash scripts/fetch-architecture-context.sh

# From a local checkout (for testing overlays)
bash scripts/fetch-architecture-context.sh /path/to/local/architecture-context
```

## Overlays

Overlays are the preferred way to fix architecture-related issues in strategies. They live in the `overlays/` directory of the architecture-context repo.

### What They Fix

- Version bumps (component X is now on version Y)
- Maturity changes (component X graduated from alpha to GA)
- Dependency shifts (component X now depends on Y instead of Z)
- New components or component removals

### Why Overlays Over Direct Edits

Architecture context is regenerated periodically. Direct edits to the base context would be overwritten. Overlays persist across regeneration cycles and are applied on top of the base context.

### Creating an Overlay

1. Clone `opendatahub-io/architecture-context` locally
2. Create your overlay file in `overlays/` following the [Overlays README](https://github.com/opendatahub-io/architecture-context/blob/main/overlays/README.md) format
3. Test locally:
   ```bash
   bash scripts/fetch-architecture-context.sh /path/to/local/architecture-context
   claude "/strategy-refine RHAISTRAT-NNNN --architecture-context /path/to/local/architecture-context"
   claude "/strategy-review RHAISTRAT-NNNN --architecture-context /path/to/local/architecture-context"
   ```
4. Verify the overlay fixes the issue in the strategy
5. Submit a PR to `opendatahub-io/architecture-context`

### Lifecycle

1. Staff engineer identifies an architecture fact that's wrong or missing
2. Creates an overlay in a local checkout
3. Tests it against the affected strategy
4. Submits PR to architecture-context
5. After merge, all future pipeline runs pick up the fix automatically
