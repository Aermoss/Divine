# Quick Summary: Why _main.ll Fails

## The Problem in 3 Sentences

1. **main.llvm** (working) uses **packed structs** `<{...}>` with explicit padding bytes
2. **_main.ll** (failing) uses **unpacked structs** `{...}` and LLVM adds automatic padding
3. The automatic padding puts struct members at **different offsets** than expected, causing crashes

## Visual Comparison

### Working (main.llvm):
```llvm
%"Token" = type <{i32, [4 x i8], %"String", i64, i64}>
                  ^^^^^^^^^^^
                  Explicit 4-byte padding to align the String field
```

### Failing (_main.ll):
```llvm
%Token = type { i32, %String, i64, i64 }
                ^^^
                Missing padding! LLVM adds it automatically,
                but might use different rules = WRONG OFFSETS!
```

## The Impact

```
Expected memory layout:
[i32][pad][String ptr][String size][lineno][column]
 0    4   8          16            24      32

Actual layout in _main.ll (depends on platform):
[i32][pad?][String ptr][String size][lineno][column]  
 0    ???  ???        ???           ???     ???
                     ↑
              LLVM decides padding based on datalayout!
```

When code tries to read `lineno` at offset 24, it might actually be at offset 28 or elsewhere → **CRASH** 💥

## The Fix

In the Divine compiler that generates _main.ll:

```python
# Change from:
struct_def = f"%{name} = type {{ {fields} }}"

# To:
struct_def = f"%{name} = type <{{ {fields_with_padding} }}>"
#                          ^                            ^
#                          Add these brackets for packed structs
```

And calculate explicit padding:

```python
def add_padding(fields):
    result = []
    offset = 0
    for field in fields:
        # Add padding to align this field
        alignment = get_alignment(field.type)
        if offset % alignment != 0:
            padding = alignment - (offset % alignment)
            result.append(f"[{padding} x i8]")
            offset += padding
        result.append(field.type_str)
        offset += get_size(field.type)
    return result
```

## How to Verify the Fix

```bash
# After fixing the compiler, compare struct definitions:

# Working version:
$ grep "%\"Token\"" main.llvm
%"Token" = type <{i32, [4 x i8], %"String", i64, i64}>

# Fixed version should match:
$ grep "%Token" _main.ll  
%Token = type <{i32, [4 x i8], %String, i64, i64}>
                ^^^^^^^^^^^
                Padding must be here!
```

## Bottom Line

- ❌ **Problem**: Unpacked structs + automatic padding = wrong offsets
- ✅ **Solution**: Packed structs + explicit padding = correct offsets
- 📊 **Impact**: ALL 27+ struct types need packed syntax
- ⏱️  **Effort**: ~1-2 hours to fix compiler IR emission logic

See `LLVM_IR_ANALYSIS_REPORT.md` for the complete technical analysis.
