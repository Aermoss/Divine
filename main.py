import time

start = time.time()

import os, sys, tempfile, subprocess
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

    sdk_path = "C:\\Program Files (x86)\\Windows Kits\\10\\Lib\\"
    print(os.listdir(sdk_path))
    sdk_path += max(os.listdir(sdk_path), key = version.parse)

    vs_path = "C:\\Program Files\\Microsoft Visual Studio\\"
    vs_path += max(os.listdir(vs_path), key = int)
    vs_path += "\\Community\\VC\\Tools\\MSVC\\"
    vs_path += max(os.listdir(vs_path), key = version.parse)

    libDirs, libs, debug = [os.path.join(path, "lib"), f"{vs_path}\\lib\\x64", f"{sdk_path}\\um\\x64", f"{sdk_path}\\ucrt\\x64"], \
        ["LLVM-C", "raylibdll", "legacy_stdio_definitions", "msvcrt", "ucrt", "vcruntime"], True # msvcrt yerine ucrt + vcruntime olmalı
    libDirs, libs = [f"/LIBPATH:{os.path.abspath(dir).replace("/", "\\")}" for dir in libDirs], [f"{lib}.lib" for lib in libs]
    workDir, fileName = os.getcwd(), os.path.splitext(argv[1])[0]

    with open(f"{fileName}.llvm", "w", encoding = "utf-8") as file:
        file.write(str(module))

    os.chdir(tempfile.gettempdir())

    with open(f"{fileName}.llvm", "w", encoding = "utf-8") as file:
        file.write(str(module))

    result = subprocess.run(["opt", f"{fileName}.llvm", "-o", f"{fileName}.bc", "-O0"] + (["-O0"] if debug else []))
    if os.path.exists(f"{fileName}.llvm"): os.remove(f"{fileName}.llvm")
    if result.returncode != 0: return -1

    result = subprocess.run(["llc", "-filetype=obj", f"{fileName}.bc", "-o", f"{fileName}.obj"] + (["-O0"] if debug else []))
    if os.path.exists(f"{fileName}.bc"): os.remove(f"{fileName}.bc")
    if result.returncode != 0: return -1

    print(f"Program compiled in {time.time() - start} seconds.")
    result = subprocess.run([f"{vs_path}\\bin\\Hostx64\\x64\\link.exe", "/NOLOGO"] + (["/DEBUG"] if debug else []) + [f"{fileName}.obj", f"/OUT:{os.path.join(workDir, f'{fileName}.exe')}"] + libDirs + libs)
    if os.path.exists(f"{fileName}.obj"): os.remove(f"{fileName}.obj")
    if result.returncode != 0: return -1

    os.chdir(workDir)
    result = subprocess.run([os.path.join(workDir, f"{fileName}.exe").replace("\\", "/")] + argv[2:])
    print(f"Program finished with exit code: {result.returncode}.")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))