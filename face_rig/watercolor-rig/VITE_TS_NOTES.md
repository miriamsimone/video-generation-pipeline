# TypeScript Import Notes

## Issue: Module Export Errors

If you see errors like:
```
The requested module '/src/transitionGraph.ts' does not provide an export named 'ExpressionId'
```

## Cause

This project uses TypeScript 5.9+ with these compiler options:
- `"verbatimModuleSyntax": true` - Requires explicit type-only imports
- `"allowImportingTsExtensions": true` - Allows `.ts` extensions in imports
- `"moduleResolution": "bundler"` - Modern bundler resolution

## Solution

When importing from `.ts` files, **include the `.ts` extension**:

```typescript
// ✅ Correct
import { ExpressionId } from "./transitionGraph.ts";

// ❌ Incorrect (may cause module resolution errors)
import { ExpressionId } from "./transitionGraph";
```

## Fixed Files

All imports in the following files have been updated:
- `src/FaceTrackedPlayer.tsx`
- `src/App.tsx`
- `src/components/TimelineViewer.tsx`

## If Issues Persist

1. **Clear Vite cache**:
   ```bash
   rm -rf node_modules/.vite
   ```

2. **Restart dev server**:
   ```bash
   npm run dev
   ```

3. **Hard refresh browser**:
   - Chrome/Edge: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
   - Firefox: Ctrl+F5 (Windows) or Cmd+Shift+R (Mac)

## TypeScript Config Reference

From `tsconfig.app.json`:
```json
{
  "compilerOptions": {
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force"
  }
}
```

This is a modern TypeScript configuration for Vite projects that enforces stricter module handling.

