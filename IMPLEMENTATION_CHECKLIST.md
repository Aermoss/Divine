# Implementation Checklist: Fixing _main.ll

This checklist guides you through fixing the struct packing issue in the Divine compiler that generates `_main.ll`.

## 📋 Pre-Implementation

### Understanding the Problem
- [ ] Read [QUICK_SUMMARY.md](QUICK_SUMMARY.md) for overview
- [ ] Review [VISUAL_COMPARISON.md](VISUAL_COMPARISON.md) for examples
- [ ] Study [LLVM_IR_ANALYSIS_REPORT.md](LLVM_IR_ANALYSIS_REPORT.md) Section "Recommendations"

### Backup Current State
```bash
# Backup the compiler code
cp compiler.py compiler.py.backup
cp _compiler.div _compiler.div.backup

# Save current output for comparison
cp _main.ll _main.ll.before_fix
```

## 🔧 Implementation Steps

### Step 1: Locate Struct Emission Code

Find where the compiler emits LLVM IR struct type definitions:

```bash
# Search for struct type emission in Python compiler
grep -n "= type {" compiler.py _compiler.div

# Look for type definition generation
grep -n "def.*type" compiler.py | grep -i struct
```

**Expected location:** Function that emits type definitions in LLVM IR

- [ ] Found struct emission code
- [ ] Identified the function/method name: ______________________
- [ ] Noted current implementation

### Step 2: Implement Packed Struct Syntax

**Current code (example):**
```python
def emit_struct_type(self, name, fields):
    field_list = ', '.join(field.llvm_type for field in fields)
    return f"%{name} = type {{ {field_list} }}"
```

**Change to:**
```python
def emit_struct_type(self, name, fields):
    field_list = ', '.join(field.llvm_type for field in fields)
    return f"%{name} = type <{{ {field_list} }}>"
    #                      ^                  ^
    #                      Add these brackets
```

- [ ] Added `<` before opening brace
- [ ] Added `>` after closing brace
- [ ] Tested on simple struct

### Step 3: Add Padding Calculation

**Add padding function:**
```python
def calculate_padding(self, current_offset, next_type):
    """Calculate padding bytes needed for alignment"""
    alignment = self.get_alignment(next_type)
    
    if current_offset % alignment == 0:
        return 0  # Already aligned
    
    padding = alignment - (current_offset % alignment)
    return padding

def get_alignment(self, llvm_type):
    """Get required alignment for a type"""
    alignments = {
        'i1': 1,
        'i8': 1,
        'i16': 2,
        'i32': 4,
        'i64': 8,
        'ptr': 8,
        'float': 4,
        'double': 8,
    }
    
    # Handle basic types
    for type_pattern, align in alignments.items():
        if type_pattern in llvm_type:
            return align
    
    # Handle struct types - use largest member alignment
    # (This is simplified; real implementation should parse struct)
    return 8  # Default to 8-byte alignment

def get_size(self, llvm_type):
    """Get size of a type in bytes"""
    sizes = {
        'i1': 1,
        'i8': 1,
        'i16': 2,
        'i32': 4,
        'i64': 8,
        'ptr': 8,
        'float': 4,
        'double': 8,
    }
    
    for type_pattern, size in sizes.items():
        if type_pattern in llvm_type:
            return size
    
    # Handle struct types recursively
    # (Simplified implementation)
    return 8  # Default
```

- [ ] Added `calculate_padding()` function
- [ ] Added `get_alignment()` function
- [ ] Added `get_size()` function
- [ ] Tested padding calculation

### Step 4: Emit Structs with Padding

**Updated struct emission:**
```python
def emit_struct_type_with_padding(self, name, fields):
    """Emit struct with explicit padding for alignment"""
    field_types = []
    current_offset = 0
    
    for field in fields:
        # Calculate padding needed before this field
        padding = self.calculate_padding(current_offset, field.llvm_type)
        
        if padding > 0:
            # Add padding array
            field_types.append(f"[{padding} x i8]")
            current_offset += padding
        
        # Add the field
        field_types.append(field.llvm_type)
        current_offset += self.get_size(field.llvm_type)
    
    # Emit with packed syntax
    field_list = ', '.join(field_types)
    return f"%{name} = type <{{ {field_list} }}>"
```

- [ ] Implemented padding insertion logic
- [ ] Updated struct emission to use padding
- [ ] Verified padding arrays are correct

### Step 5: Update Data Layout

**Option A: Use empty datalayout (recommended)**
```python
def emit_target_config(self):
    return 'target datalayout = ""\n' + \
           'target triple = "x86_64-pc-windows-msvc"'
```

**Option B: Keep explicit but ensure consistency**
```python
# If keeping explicit, ensure it matches your padding calculations
DATALAYOUT = "e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
```

- [ ] Updated datalayout emission
- [ ] Tested with empty datalayout OR
- [ ] Verified explicit datalayout matches padding

### Step 6: Update GEP Field Indices

**Before (without padding):**
```python
# Accessing field at index 2
gep = f"getelementptr %Token, ptr %base, i32 0, i32 2"
```

**After (with padding):**
```python
# If padding array is at index 1, increment subsequent indices
# Field that was at index 2 is now at index 3
gep = f"getelementptr inbounds nuw %Token, ptr %base, i32 0, i32 3"
```

**Implementation:**
```python
def get_field_index(self, struct_name, field_name):
    """Get field index accounting for padding"""
    struct_def = self.types[struct_name]
    index = 0
    
    for i, field in enumerate(struct_def.fields):
        # Check if padding was inserted before this field
        if i > 0:
            prev_offset = self.get_field_offset(struct_name, i-1)
            curr_alignment = self.get_alignment(field.llvm_type)
            if prev_offset % curr_alignment != 0:
                index += 1  # Skip padding array
        
        if field.name == field_name:
            return index
        
        index += 1
    
    raise ValueError(f"Field {field_name} not found in {struct_name}")
```

- [ ] Updated GEP index calculation
- [ ] Tested field access with padding
- [ ] Verified all struct member accesses

## ✅ Testing

### Test 1: Visual Inspection

```bash
# Recompile a test file
python3 compiler.py test.div

# Compare struct definitions
echo "=== OLD VERSION ==="
grep "%Token = type" _main.ll.before_fix | head -1

echo "=== NEW VERSION ==="
grep "%Token = type" _main.ll | head -1

# Expected: New version should have <{...}> and padding arrays
```

- [ ] Struct definitions use `<{...}>` syntax
- [ ] Padding arrays `[N x i8]` are present
- [ ] Field types are correct

### Test 2: LLVM Validation

```bash
# Validate the IR
llvm-as _main.ll -o _main.bc

# Should compile without errors
if [ $? -eq 0 ]; then
    echo "✓ IR is valid"
else
    echo "✗ IR has errors"
fi

# Disassemble to verify
llvm-dis _main.bc -o _main_roundtrip.ll
diff _main.ll _main_roundtrip.ll
```

- [ ] `llvm-as` succeeds without errors
- [ ] Roundtrip disassembly matches

### Test 3: Struct Layout Comparison

```bash
# Compare with working version
echo "=== main.llvm (working) ==="
grep "%\"Token\" = type" main.llvm

echo "=== _main.ll (fixed) ==="
grep "%Token = type" _main.ll

# Should be structurally similar (same padding pattern)
```

- [ ] Token struct layouts match
- [ ] String struct layouts match
- [ ] Compiler struct layouts match
- [ ] All critical structs have correct padding

### Test 4: Compilation Test

```bash
# Compile to object file
clang -c _main.ll -o _main.o

# Should succeed without warnings
if [ $? -eq 0 ]; then
    echo "✓ Compilation successful"
else
    echo "✗ Compilation failed"
fi
```

- [ ] Compiles to object file
- [ ] No warnings about struct layout

### Test 5: Runtime Test

```bash
# If you have a test program:
clang _main.ll -o test_program -lLLVM-C -lraylibdll

# Run with test input
./test_program test_input.div > output.txt

# Should not crash
if [ $? -eq 0 ]; then
    echo "✓ Program executed successfully"
else
    echo "✗ Program crashed (exit code $?)"
fi
```

- [ ] Program runs without crashing
- [ ] Output is correct
- [ ] No segmentation faults
- [ ] Matches output from main.llvm version

## 📊 Final Verification

### Checklist Summary

**Code Changes:**
- [ ] Packed struct syntax implemented
- [ ] Padding calculation added
- [ ] Field index calculation updated
- [ ] Data layout configured
- [ ] All tests pass

**Documentation:**
- [ ] Code comments added
- [ ] Changes documented
- [ ] Test cases added

**Quality Checks:**
- [ ] No compiler warnings
- [ ] LLVM IR validates
- [ ] Struct layouts match main.llvm
- [ ] Runtime behavior correct

## 🐛 Troubleshooting

### Issue: "Invalid LLVM IR syntax"

**Check:**
- Ensure `<>` brackets are balanced
- Verify padding arrays use correct syntax: `[N x i8]`
- Check field separators (commas)

### Issue: "Struct size mismatch"

**Check:**
- Padding calculation logic
- Field size calculations
- Alignment requirements

### Issue: "Segmentation fault at runtime"

**Check:**
- GEP field indices are correct
- Padding arrays are in right positions
- Field offsets match expected layout

### Issue: "Different output than main.llvm"

**Check:**
- All structs use packed syntax
- Data layout matches
- Field access indices updated

## 📝 Notes

**Important:**
- Test incrementally after each change
- Keep backups of working code
- Compare with main.llvm frequently
- Verify both compile-time and runtime behavior

**Performance:**
- Packed structs may affect performance slightly
- But correctness is more important
- Profile if needed after fix is working

## ✨ Success Criteria

The fix is complete when:

1. ✅ All struct definitions use `<{...}>` syntax
2. ✅ Explicit padding arrays present where needed
3. ✅ LLVM IR validates with `llvm-as`
4. ✅ Struct layouts match main.llvm
5. ✅ Programs compile without errors
6. ✅ Programs run without crashes
7. ✅ Output matches main.llvm version

---

**After completing this checklist, your Divine compiler should generate correct LLVM IR with proper struct packing!**
