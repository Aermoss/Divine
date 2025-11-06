# Visual LLVM IR Comparison

## Side-by-Side Comparison of Key Structures

### 1. Token Struct Definition

| Feature | main.llvm (Working) ✅ | _main.ll (Failing) ❌ |
|---------|----------------------|---------------------|
| **Syntax** | `%"Token" = type <{...}>` | `%Token = type {...}` |
| **Packing** | Packed (no auto-padding) | Unpacked (auto-padding) |
| **Fields** | `i32, [4 x i8], %"String", i64, i64` | `i32, %String, i64, i64` |
| **Padding** | Explicit `[4 x i8]` array | None (LLVM adds it) |
| **Size** | Exactly 40 bytes | Platform-dependent |

#### Memory Layout Visualization

**main.llvm (PREDICTABLE):**
```
┌─────┬─────┬──────────────────┬────────┬────────┐
│ i32 │ pad │     String       │ lineno │ column │
│  4B │ 4B  │  8B ptr + 8B len │   8B   │   8B   │
└─────┴─────┴──────────────────┴────────┴────────┘
  0     4     8                  24       32     40
```

**_main.ll (UNPREDICTABLE):**
```
┌─────┬─────?┬──────────────────┬────────┬────────┐
│ i32 │ ??? │     String       │ lineno │ column │
│  4B │ ??  │  8B ptr + 8B len │   8B   │   8B   │
└─────┴─────?┴──────────────────┴────────┴────────┘
  0     4??   8??                24??     32??    40??
              ↑
        LLVM decides based on datalayout!
        Could be 0, 4, or 8 bytes of padding!
```

### 2. String Struct Definition

| Feature | main.llvm ✅ | _main.ll ❌ |
|---------|------------|-----------|
| **Definition** | `%"String" = type <{ptr, i64}>` | `%String = type {ptr, i64}` |
| **Size** | 16 bytes (8+8) | 16 bytes (but LLVM could change) |
| **Issue** | None - simple struct | Low risk (naturally aligned) |

#### Memory Layout

**Both versions (similar structure):**
```
┌─────────┬─────────┐
│   ptr   │   i64   │
│   8B    │   8B    │
└─────────┴─────────┘
  0         8       16
```
⚠️ **Note**: Even though this struct is simple, the unpacked syntax in _main.ll means LLVM *could* add padding if the datalayout requires it!

### 3. Compiler Struct Definition

| Feature | main.llvm ✅ | _main.ll ❌ |
|---------|------------|-----------|
| **First fields** | `%"Mangler", i1, [7 x i8], ...` | `%Mangler, i1, ...` |
| **Padding** | Explicit `[7 x i8]` | None! |
| **Problem** | Correct alignment | **i1 → Mangler misalignment!** |

#### Memory Layout (First 3 Fields)

**main.llvm (CORRECT):**
```
┌──────────────────┬────┬────────────┬──────────...
│     Mangler      │ i1 │  [7 x i8]  │  Vector...
│      16B         │ 1B │     7B     │    24B
└──────────────────┴────┴────────────┴──────────...
  0                 16   17           24
                         ↑            ↑
                         Padding ensures next field at 8-byte boundary
```

**_main.ll (WRONG):**
```
┌──────────────────┬────┬────────?...
│     Mangler      │ i1 │  Vector?...
│      16B         │ 1B │   ???
└──────────────────┴────┴────────?...
  0                 16   17       ???
                         ↑        ↑
                         LLVM might pad differently!
                         Vector might be at wrong offset!
```

### 4. GetElementPtr Operations

#### main.llvm ✅
```llvm
%ptr = getelementptr %"Token", ptr %base, i32 0, i32 3
                               ^^^^^^^^^^^^^^^^^^^
                               Access field at index 3 (lineno)
                               Index accounts for padding array at index 1
```

#### _main.ll ❌
```llvm
%ptr = getelementptr inbounds nuw %Token, ptr %base, i32 0, i32 2
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                     Assumes pointer is always valid (dangerous!)
                     Index 2 expects no padding array
                     But LLVM might add padding anyway!
```

**Visual:**
```
Expected (with padding):      Actual (LLVM's choice):
Field 0: i32 _type            Field 0: i32 _type
Field 1: [4 x i8] padding     Field 1: (auto-padding)
Field 2: String value         Field 2: String value
Field 3: i64 lineno ← HERE    Field 3: i64 lineno
                              
Code accesses index 2         But lineno is at index 3!
Wrong field! 💥               (if padding exists)
```

### 5. Target Configuration

```
┌─────────────────────────────────────────────────────────┐
│                   main.llvm (Working)                   │
├─────────────────────────────────────────────────────────┤
│ target triple = "x86_64-pc-windows-msvc"               │
│ target datalayout = ""           ← EMPTY (use defaults)│
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   _main.ll (Failing)                    │
├─────────────────────────────────────────────────────────┤
│ target triple = "x86_64-pc-windows-msvc"               │
│ target datalayout = "e-m:w-p270:32:32-p271:32:32-..."  │
│                      ↑                                  │
│                      EXPLICIT (enforces Windows ABI)    │
└─────────────────────────────────────────────────────────┘
```

**Datalayout breakdown:**
```
e        = Little-endian byte order
m:w      = Windows name mangling
p270:32  = Address space 270 pointers: 32-bit, 32-bit aligned
i64:64   = 64-bit integers: 64-bit aligned
S128     = Stack alignment: 128 bits (16 bytes)
```

### 6. Function Signatures

```llvm
# String constructor
main.llvm: define void @"$dN6String6StringEP6String"(ptr %".1")
_main.ll:  define void @"$dN6String6StringEPN6String6StringE"(ptr %0)
                                              ^^
                                              Different mangling scheme
```

**Impact:** Linking issues if mixing object files from both compilers

### 7. Statistics Summary

```
┌────────────────────────────────┬─────────────┬───────────┐
│ Feature                        │ main.llvm   │ _main.ll  │
├────────────────────────────────┼─────────────┼───────────┤
│ Packed struct types            │    ALL      │   NONE    │
│ Types with explicit padding    │     27      │     0     │
│ GEP with 'inbounds'            │      0      │  10,000+  │
│ GEP with 'nuw'                 │      0      │  10,000+  │
│ Target datalayout              │   Empty     │ Explicit  │
│ Type name quoting              │   Quoted    │ Unquoted  │
│ Lines of code                  │  57,286     │  57,777   │
└────────────────────────────────┴─────────────┴───────────┘
```

## The Core Problem Illustrated

```
┌─────────────────────────────────────────────────────────┐
│           What the Divine Compiler Expects              │
├─────────────────────────────────────────────────────────┤
│  Token struct has specific byte-level layout            │
│  lineno is always at offset 24 from base pointer        │
│  Code generates: base_ptr + 24 to access lineno         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                What main.llvm Provides                   │
├─────────────────────────────────────────────────────────┤
│  <{i32, [4 x i8], String, i64, i64}>                   │
│  ↑                                                       │
│  Packed syntax GUARANTEES no automatic padding          │
│  lineno IS at offset 24 ✓                              │
└─────────────────────────────────────────────────────────┘
                          ✓ WORKS

                          ↓
┌─────────────────────────────────────────────────────────┐
│                What _main.ll Provides                    │
├─────────────────────────────────────────────────────────┤
│  {i32, String, i64, i64}                               │
│  ↑                                                       │
│  Unpacked syntax - LLVM ADDS padding per datalayout     │
│  lineno MIGHT BE at offset 24, 28, or 32 ??           │
│  Depends on how LLVM pads the struct                    │
└─────────────────────────────────────────────────────────┘
                          ✗ CRASHES
```

## The Fix in One Image

```
Before (Broken):                    After (Fixed):
┌─────────────────┐                ┌─────────────────┐
│ Compiler emits: │                │ Compiler emits: │
│ {...}           │                │ <{...}>         │
│                 │    ┌──────┐    │                 │
│ No padding      │───→│ FIX! │───→│ With padding    │
│                 │    └──────┘    │                 │
│ LLVM decides    │                │ Explicit layout │
└─────────────────┘                └─────────────────┘
        │                                  │
        ↓                                  ↓
   💥 CRASH                             ✅ WORKS
```

## Key Takeaway

```
╔════════════════════════════════════════════════════════╗
║  The difference between <{...}> and {...}             ║
║  is the difference between:                           ║
║                                                        ║
║  ✅ Code that works reliably                          ║
║  ❌ Code that crashes unpredictably                   ║
║                                                        ║
║  FIX: Make _main.ll use packed structs like main.llvm ║
╚════════════════════════════════════════════════════════╝
```
