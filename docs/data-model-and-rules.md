# Data Model and Occupancy Rules

## Purpose

Define consistent rules for:

- Single-cell units
- Multi-cell (cross-cell) buildings
- Fixed large buildings

This prevents logic fragmentation in detection and simulation code.

## Core Entities

## `CellState`

- `row`, `col`
- `class_id`
- `label`
- `confidence`
- `is_fixed_reserved` (bool)

## `BuildingState`

- `building_id`
- `class_id`
- `label`
- `cells` (list of row/col)
- `footprint_w`, `footprint_h`
- `is_fixed` (bool)

## Occupancy Categories

1. Single-cell dynamic unit (`1x1`)
2. Multi-cell dynamic unit (`NxM`, rectangular only)
3. Fixed large unit (pre-registered footprint)

## Rule Set

1. Multi-cell units must be contiguous.
2. Multi-cell geometry is rectangular in MVP.
3. Fixed units are loaded from config and can be excluded from dynamic merge.
4. Unknown cells are not merged.
5. Same-color touching groups can merge only if class allows merge.

## Fixed Unit Configuration Example

```json
{
  "id": "library_A",
  "class_id": 1,
  "label": "library",
  "is_fixed": true,
  "cells": [[2,3],[2,4],[2,5],[3,3],[3,4],[3,5]]
}
```

## Merge Strategy (Dynamic Units)

1. Build binary mask per class.
2. Run connected components (4-neighborhood).
3. Fit bounding box for each component.
4. Validate size against allowed footprints for class.
5. Emit valid buildings, reject invalid fragments.

## Validation Rules for Editing/Placement

- No overlap between fixed units and dynamic units.
- No overlap between two dynamic merged buildings.
- Out-of-grid placements are invalid.

