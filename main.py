import time

start = time.time()

import os, sys, tempfile, subprocess, llvmlite

llvmlite.opaque_pointers_enabled = True

import llvmlite.binding as llvm

from lexer import Lexer
from parser import Parser
from compiler import Compiler

from packaging import version

def main(argv):
    path = os.path.split(__file__)[0]
    lexer, parser, compiler = Lexer(), Parser(), Compiler()
    parser.parse(lexer.Lex(open(argv[1], "r", encoding = "utf-8").read()))
    compiler.includePaths.append(os.path.join(path, "include"))
    module = compiler.Compile(parser.ast["body"])
    module.name = os.path.splitext(os.path.basename(argv[1]))[0]
    module.triple = llvm.get_default_triple()

    sdkPath = "C:\\Program Files (x86)\\Windows Kits\\10\\Lib\\"
    sdkPath += max([i for i in os.listdir(sdkPath) if i not in ["wdf"]], key = version.parse)

    vsPath = "C:\\Program Files\\Microsoft Visual Studio\\"
    vsPath += max(os.listdir(vsPath), key = int)
    vsPath += f"\\{os.listdir(vsPath)[0]}\\VC\\Tools\\MSVC\\"
    vsPath += max(os.listdir(vsPath), key = version.parse)

    libDirs, libs = [os.path.join(path, "lib"), f"{vsPath}\\lib\\x64", f"{sdkPath}\\um\\x64", f"{sdkPath}\\ucrt\\x64"], \
        ["LLVM-C", "raylibdll", "legacy_stdio_definitions", "msvcrt", "ucrt", "vcruntime"]

    libDirs, libs = [f"/LIBPATH:{os.path.abspath(dir).replace("/", "\\")}" for dir in libDirs], [f"{lib}.lib" for lib in libs]
    workDir, fileName, debug = os.getcwd(), os.path.splitext(argv[1])[0], True

    with open(f"{fileName}.llvm", "w", encoding = "utf-8") as file:
        file.write(str(module))

    os.chdir(tempfile.gettempdir())

    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine(codemodel = "large", opt = (0 if debug else 2))

    _module = llvm.parse_assembly(str(module))
    _module.verify()

    with open(f"{fileName}.obj", "wb") as file:
        file.write(target_machine.emit_object(_module))

    print(f"Program compiled in {time.time() - start} seconds.")
    result = subprocess.run([f"{vsPath}\\bin\\Hostx64\\x64\\link.exe", "/NOLOGO"] + (["/DEBUG"] if debug else []) + [f"{fileName}.obj", f"/OUT:{os.path.join(workDir, f'{fileName}.exe')}"] + libDirs + libs)
    if os.path.exists(f"{fileName}.obj"): os.remove(f"{fileName}.obj")
    if result.returncode != 0: return -1

    os.chdir(workDir)
    result = subprocess.run([os.path.join(workDir, f"{fileName}.exe").replace("\\", "/")] + argv[2:])
    print(f"Program finished with exit code: {result.returncode}.")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))